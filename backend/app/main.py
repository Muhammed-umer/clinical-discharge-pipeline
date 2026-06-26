"""
NABH Hospital Discharge Summary Pipeline Engine — Application Entry Point.

This module contains only:
  - FastAPI app instantiation and metadata
  - CORS middleware
  - Global exception handlers (unchanged behavior)
  - Startup event (DB init + Gemini API configuration)
  - Router registration
  - Health check endpoints

All business logic, orchestration, and DB access has been moved to:
  - app/services/pipeline_service.py  (orchestration)
  - app/api/routes/stays.py           (stay endpoints)
  - app/api/routes/documents.py       (upload endpoint)
  - app/api/routes/pipeline.py        (pipeline endpoints)
  - app/db/repositories/             (all DB access)
  - app/core/dependencies.py          (DI wiring)
"""

import datetime
import logging
import uuid

import google.generativeai as genai
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes import documents, pipeline, stays
from app.core.config import GEMINI_API_KEY, PIPELINE_VERSION
from app.core.exceptions import ClinicalPipelineException
from app.db.database import Base, engine

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Application ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="NABH Hospital Discharge Summary Pipeline Engine",
    version=PIPELINE_VERSION,
    description=(
        "An enterprise-grade, hybrid clinical data extraction, arbitration, "
        "and validation pipeline."
    ),
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Exception handlers ───────────────────────────────────────────────────────

@app.exception_handler(ClinicalPipelineException)
async def clinical_pipeline_exception_handler(request, exc: ClinicalPipelineException):
    request_id = uuid.uuid4().hex[:8]
    timestamp = datetime.datetime.utcnow().isoformat()
    logger.error(
        "Pipeline error [Req ID: %s] status_code=%s status_str=%s: %s",
        request_id, exc.status_code, exc.status_str, exc.message,
        exc_info=True,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": exc.status_str,
            "message": exc.message,
            "safe_state": exc.safe_state,
            "requires_manual_review": exc.requires_manual_review,
            "retry_available": exc.retry_available,
            "documents_preserved": exc.documents_preserved,
            "summary_generated": exc.summary_generated,
            "request_id": request_id,
            "timestamp": timestamp,
        },
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request, exc: SQLAlchemyError):
    request_id = uuid.uuid4().hex[:8]
    timestamp = datetime.datetime.utcnow().isoformat()
    logger.error(
        "Database transaction failure [Req ID: %s]: %s",
        request_id, str(exc), exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "DATABASE_UNAVAILABLE",
            "message": "Clinical records cannot currently be accessed.",
            "safe_state": True,
            "requires_manual_review": True,
            "retry_available": True,
            "documents_preserved": True,
            "summary_generated": False,
            "request_id": request_id,
            "timestamp": timestamp,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    from fastapi import HTTPException

    request_id = uuid.uuid4().hex[:8]
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "status": "HTTP_ERROR",
                "message": exc.detail,
                "safe_state": True,
                "requires_manual_review": True,
                "retry_available": False,
                "documents_preserved": True,
                "summary_generated": False,
                "request_id": request_id,
                "timestamp": datetime.datetime.utcnow().isoformat(),
            },
        )

    logger.error(
        "Unhandled system error [Req ID: %s]: %s", request_id, str(exc), exc_info=True
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred during processing.",
            "safe_state": True,
            "requires_manual_review": True,
            "retry_available": False,
            "documents_preserved": True,
            "summary_generated": False,
            "request_id": request_id,
            "timestamp": datetime.datetime.utcnow().isoformat(),
        },
    )


# ─── Startup ──────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """
    Ensures database tables and pgvector extensions are prepared.
    Configures the Gemini SDK exactly once at startup.
    """
    # Configure Gemini globally (called once here; services no longer do it)
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info("Gemini API configured successfully.")

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        await conn.run_sync(Base.metadata.create_all)
        # Migrate schema columns that may not exist in older deployments
        await conn.execute(
            text("ALTER TABLE final_discharge_summaries ADD COLUMN IF NOT EXISTS reviewed_by VARCHAR;")
        )
        await conn.execute(
            text("ALTER TABLE final_discharge_summaries ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP WITHOUT TIME ZONE;")
        )
        await conn.execute(
            text("ALTER TABLE final_discharge_summaries ADD COLUMN IF NOT EXISTS grounding_score FLOAT;")
        )
        await conn.execute(
            text("ALTER TABLE final_discharge_summaries ADD COLUMN IF NOT EXISTS pipeline_version VARCHAR;")
        )
        await conn.execute(
            text("ALTER TABLE final_discharge_summaries ADD COLUMN IF NOT EXISTS judge_version VARCHAR;")
        )
    logger.info("Database initialized successfully.")


# ─── Health checks ────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "application": "Clinical Discharge Summary Pipeline",
        "status": "Healthy",
        "version": PIPELINE_VERSION,
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "UP"}


# ─── Route registration ───────────────────────────────────────────────────────
app.include_router(stays.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(pipeline.router, prefix="/api")