"""
Pipeline orchestration routes — /api/pipeline/*

Handles:
  - POST /api/pipeline/process/{stay_id}   → Execute the full discharge pipeline
  - POST /api/pipeline/approve/{stay_id}   → Physician approval / HITL sign-off
  - POST /api/pipeline/resolve/{stay_id}   → Conflict resolution
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_pipeline_service
from app.db.database import get_db
from app.services.pipeline_service import PipelineService

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Request models ───────────────────────────────────────────────────────────

class MedicationResolveItem(BaseModel):
    name: str
    dosage: str
    frequency: str
    duration: str


class ResolutionRequest(BaseModel):
    medications: List[MedicationResolveItem]


# ─── Route handlers ───────────────────────────────────────────────────────────

@router.post("/pipeline/process/{stay_id}")
async def execute_discharge_pipeline(
    stay_id: str,
    db: AsyncSession = Depends(get_db),
    svc: PipelineService = Depends(get_pipeline_service),
):
    """
    Orchestrates the multi-stage AI clinical discharge pipeline:

      1. Fetch and deduplicate raw notes
      2. Batch Gemini extraction (1 LLM call)
      3. Chronological arbitration and conflict detection
      4. Atomic claim compilation + persistence
      5. Batch grounding validation with Gemini Judge (1 LLM call)
      6. Clinical safety rule engine evaluation
      7. Persist all results to PostgreSQL

    Total LLM calls: 2 (regardless of note count or claim count).

    Returns 503 with a structured failure payload on AI service unavailability,
    preserving all uploaded documents and enabling retry.
    """
    result = await svc.execute_pipeline(stay_id, db)

    # Safe-failure sentinel — PipelineService saved state; return 503 with payload
    if result.get("_safe_failure"):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=result["payload"],
        )

    return result


@router.post("/pipeline/approve/{stay_id}")
async def approve_discharge_summary(
    stay_id: str,
    db: AsyncSession = Depends(get_db),
    svc: PipelineService = Depends(get_pipeline_service),
):
    """
    Applies Human-in-the-Loop physician approval.
    Marks summary as reconciled, signs the audit columns (reviewed_by, reviewed_at),
    and transitions the stay to COMPLETED.
    """
    return await svc.approve_summary(stay_id, db)


@router.post("/pipeline/resolve/{stay_id}")
async def resolve_conflicts(
    stay_id: str,
    payload: ResolutionRequest,
    db: AsyncSession = Depends(get_db),
    svc: PipelineService = Depends(get_pipeline_service),
):
    """
    Allows a physician to resolve medication conflicts.
    Accepts the resolved medication list, updates the discharge summary,
    re-runs grounding and rule evaluation, and transitions stay to READY_FOR_REVIEW.
    """
    resolved = [
        {
            "name": med.name,
            "dosage": med.dosage,
            "frequency": med.frequency,
            "duration": med.duration,
        }
        for med in payload.medications
    ]
    return await svc.resolve_conflicts(stay_id, resolved, db)
