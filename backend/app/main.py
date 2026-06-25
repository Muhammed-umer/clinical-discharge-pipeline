import os
import logging
import datetime
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import text, delete
from typing import List, Dict, Any
from pydantic import BaseModel

from app.db.database import get_db, engine, Base
from app.models.models import PatientStay, RawDocumentNode, ClinicalClaim, ValidationReport, FinalDischargeSummary
from app.models.schemas import FinalDischargeSummary as FinalDischargeSummarySchema
from app.services.extraction_service import ClinicalExtractionService, ClinicalPipelineException, ClinicalValidationError, ClinicalExtractionError
from app.services.arbitration_service import ClinicalArbitrationEngine
from app.services.validation_service import ClinicalValidationLayer
from app.services.claim_service import ClaimService
from app.services.clinical_rules_service import ClinicalRulesEngine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="NABH Hospital Discharge Summary Pipeline Engine",
    version="1.2.0",
    description="An enterprise-grade, hybrid clinical data extraction, arbitration, and validation pipeline."
)

# Enable CORS for Next.js frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize our pipeline services
extraction_service = ClinicalExtractionService()
arbitration_engine = ClinicalArbitrationEngine()
validation_layer = ClinicalValidationLayer()
claim_service = ClaimService()
clinical_rules_engine = ClinicalRulesEngine()  # Priority 5: clinical safety rule engine

# Request schemas for incoming API payloads
class DocumentUploadRequest(BaseModel):
    stay_id: str
    patient_name: str
    author_role: str  # ATTENDING, CONSULTANT, RESIDENT, WARD_NURSE
    recorded_at: datetime.datetime
    content: str


class MedicationResolveItem(BaseModel):
    name: str
    dosage: str
    frequency: str
    duration: str


class ResolutionRequest(BaseModel):
    medications: List[MedicationResolveItem]
@app.get("/")
async def root():
    return {
        "application": "Clinical Discharge Summary Pipeline",
        "status": "Healthy",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health")
async def health():
    return {
        "status": "UP"
    }

@app.on_event("startup")
async def startup_event():
    """Ensures database tables and pgvector extensions are prepared upon server initialization."""
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        await conn.run_sync(Base.metadata.create_all)
        # Migrate schema dynamically in case tables existed from older builds
        await conn.execute(text("ALTER TABLE final_discharge_summaries ADD COLUMN IF NOT EXISTS reviewed_by VARCHAR;"))
        await conn.execute(text("ALTER TABLE final_discharge_summaries ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP WITHOUT TIME ZONE;"))
        await conn.execute(text("ALTER TABLE final_discharge_summaries ADD COLUMN IF NOT EXISTS grounding_score FLOAT;"))
        await conn.execute(text("ALTER TABLE final_discharge_summaries ADD COLUMN IF NOT EXISTS pipeline_version VARCHAR;"))
        await conn.execute(text("ALTER TABLE final_discharge_summaries ADD COLUMN IF NOT EXISTS judge_version VARCHAR;"))


@app.get("/api/stays", response_model=List[Dict[str, Any]])
async def list_patient_stays(db: AsyncSession = Depends(get_db)):
    """Lists all active and completed patient stays."""
    try:
        query = await db.execute(select(PatientStay))
        stays = query.scalars().all()
        return [
            {
                "id": stay.id,
                "patient_name": stay.patient_name,
                "status": stay.status
            }
            for stay in stays
        ]
    except Exception as e:
        logger.error(f"Failed to list stays: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve patient stays database records.")


@app.get("/api/stays/{stay_id}")
async def get_stay_details(stay_id: str, db: AsyncSession = Depends(get_db)):
    """Fetches details of a specific stay, including raw notes, claims, and final summary."""
    try:
        stay_query = await db.execute(select(PatientStay).where(PatientStay.id == stay_id))
        stay = stay_query.scalars().first()
        if not stay:
            raise HTTPException(status_code=404, detail="Patient stay not found.")

        notes_query = await db.execute(
            select(RawDocumentNode)
            .where(RawDocumentNode.stay_id == stay_id)
            .order_by(RawDocumentNode.recorded_at.asc())
        )
        notes = notes_query.scalars().all()

        claims_query = await db.execute(select(ClinicalClaim).where(ClinicalClaim.stay_id == stay_id))
        claims = claims_query.scalars().all()

        summary_query = await db.execute(select(FinalDischargeSummary).where(FinalDischargeSummary.stay_id == stay_id))
        summary = summary_query.scalars().first()

        return {
            "stay_id": stay.id,
            "patient_name": stay.patient_name,
            "status": stay.status,
            "notes": [
                {
                    "id": note.id,
                    "author_role": note.author_role,
                    "recorded_at": note.recorded_at.isoformat(),
                    "content": note.content
                }
                for note in notes
            ],
            "claims": [
                {
                    "id": claim.id,
                    "category": claim.category,
                    "value": claim.value,
                    "confidence_score": claim.confidence_score,
                    "confidence_level": claim.confidence_level,
                    "evidence": claim.evidence,
                    "author_role": claim.author_role,
                    "recorded_at": claim.recorded_at.isoformat(),
                    "status": claim.status
                }
                for claim in claims
            ],
            "final_summary": summary.structured_data if summary else None,
            "is_reconciled": bool(summary.is_reconciled) if summary else False,
            "reviewed_by": summary.reviewed_by if summary else None,
            "reviewed_at": summary.reviewed_at.isoformat() if summary and summary.reviewed_at else None,
            "grounding_score": summary.grounding_score if summary else 0.0
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch stay details: {str(e)}")
        raise HTTPException(status_code=500, detail="Database error occurred while fetching stay parameters.")


@app.post("/api/documents/upload", status_code=status.HTTP_201_CREATED)
async def upload_clinical_document(payload: DocumentUploadRequest, db: AsyncSession = Depends(get_db)):
    """
    Ingests an unstructured clinical note, vectorizes its content using
    text-embedding-004, and stores it in PostgreSQL.
    """
    try:
        logger.info(f"Ingesting document for stay: {payload.stay_id}")
        stay_query = await db.execute(select(PatientStay).where(PatientStay.id == payload.stay_id))
        stay = stay_query.scalars().first()
        
        if not stay:
            stay = PatientStay(id=payload.stay_id, patient_name=payload.patient_name, status="PROCESSING")
            db.add(stay)
            await db.flush()

        # Check if identical note already exists for this stay to prevent duplication
        dup_query = await db.execute(
            select(RawDocumentNode).where(
                RawDocumentNode.stay_id == payload.stay_id,
                RawDocumentNode.author_role == payload.author_role.upper(),
                RawDocumentNode.recorded_at == payload.recorded_at,
                RawDocumentNode.content == payload.content
            )
        )
        existing_node = dup_query.scalars().first()
        if existing_node:
            logger.info(f"Document already exists, skipping duplicate ingestion.")
            return {"status": "success", "message": f"Document already ingested for Stay ID {payload.stay_id}"}

        # Compute semantic vector embedding
        embedding_vector = validation_layer.get_embedding(payload.content)

        new_node = RawDocumentNode(
            stay_id=payload.stay_id,
            author_role=payload.author_role.upper(),
            recorded_at=payload.recorded_at,
            content=payload.content,
            embedding=embedding_vector
        )
        db.add(new_node)
        
        # Reset stay status to PROCESSING on new doc upload
        stay.status = "PROCESSING"
        
        await db.commit()
        logger.info(f"Successfully ingested note from {payload.author_role} for stay {payload.stay_id}")
        return {"status": "success", "message": f"Document successfully ingested for Stay ID {payload.stay_id}"}
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Ingestion Pipeline Failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Database write error occurred during document upload.")


@app.post("/api/pipeline/process/{stay_id}")
async def execute_discharge_pipeline(stay_id: str, db: AsyncSession = Depends(get_db)):
    """
    Orchestrates the multi-stage AI pipeline:
    1. Fetch notes.
    2. Parallel clinical extraction with Gemini.
    3. Chronological arbitration and conflict detection.
    4. Claim compilation.
    5. Factual grounding validation (pgvector + Gemini Judge).
    6. Save state to database.
    """
    try:
        logger.info(f"Executing clinical discharge pipeline for stay: {stay_id}")
        
        # 1. Fetch raw notes
        notes_query = await db.execute(select(RawDocumentNode).where(RawDocumentNode.stay_id == stay_id))
        raw_notes = notes_query.scalars().all()

        if not raw_notes:
            raise HTTPException(status_code=404, detail=f"No clinical notes found matching stay reference: {stay_id}")

        # Deduplicate raw notes in memory to prevent duplicate extraction/arbitration runs
        seen_notes = set()
        unique_raw_notes = []
        for note in raw_notes:
            note_key = (note.author_role, note.recorded_at, note.content.strip())
            if note_key not in seen_notes:
                seen_notes.add(note_key)
                unique_raw_notes.append(note)

        extractions_pipeline_input = []

        # 2. Extract structured fields from each note using Gemini 2.5 Pro
        for note in unique_raw_notes:
            try:
                structured_extraction = await extraction_service.extract_structured_data(
                    raw_note_content=note.content,
                    author_role=note.author_role
                )
                extractions_pipeline_input.append((structured_extraction, note.recorded_at, note.author_role))
            except ClinicalValidationError as cve:
                logger.error(f"Structured Pydantic validation failed for note {note.id}: {str(cve)}")
                continue
            except ClinicalExtractionError as cee:
                logger.error(f"LLM API extraction failed for note {note.id}: {str(cee)}")
                continue
            except Exception as ex:
                logger.error(f"Bypassing note extraction due to unhandled error: {str(ex)}")
                continue

        if not extractions_pipeline_input:
            logger.error(
                f"All note extractions failed for stay {stay_id}. "
                "Gemini API may be unavailable or all notes failed schema validation."
            )
            raise HTTPException(
                status_code=500,
                detail={
                    "status": "PIPELINE_FAILED",
                    "requires_human_review": True,
                    "reason": (
                        "Clinical extraction unavailable: all notes failed structured extraction. "
                        "Gemini API may be down or rate-limited. "
                        "No clinical data was fabricated. Manual review required."
                    ),
                },
            )

        # 3. Deterministically arbitrate and merge extractions chronologically
        merged_summary: FinalDischargeSummarySchema = arbitration_engine.merge_extractions(extractions_pipeline_input)

        # 4. Compile atomic claims and persist them in DB
        await db.execute(delete(ClinicalClaim).where(ClinicalClaim.stay_id == stay_id))
        
        claims = claim_service.generate_claims(
            extraction=merged_summary.summary,
            author="SYSTEM_MERGE",
            timestamp=datetime.datetime.utcnow()
        )
        
        for claim in claims:
            db_claim = ClinicalClaim(
                id=claim.claim_id,
                stay_id=stay_id,
                category=claim.category,
                value=claim.value,
                confidence_score=claim.confidence.score,
                confidence_level=claim.confidence.level,
                evidence=[ev.model_dump() for ev in claim.evidence],
                author_role=claim.author,
                recorded_at=claim.timestamp,
                status="UNVERIFIED"
            )
            db.add(db_claim)
        
        await db.flush()

        # 5. Execute Factual Grounding validation
        finalized_summary: FinalDischargeSummarySchema = await validation_layer.verify_summary_grounding(
            stay_id=stay_id,
            merged_summary=merged_summary,
            db=db
        )

        # 5b. Run Clinical Rule Engine (Priority 5)
        # Evaluates safety rules against the finalized summary and appends
        # ClinicalWarningSchema entries for any violations (e.g., Metformin + creatinine).
        finalized_summary = clinical_rules_engine.evaluate_rules(finalized_summary)
        logger.info(
            f"Clinical rules evaluated. "
            f"Total warnings: {len(finalized_summary.validation.warnings)}"
        )

        # Update clinical claim status in database using the judge's result
        db_claims_query = await db.execute(select(ClinicalClaim).where(ClinicalClaim.stay_id == stay_id))
        db_claims = db_claims_query.scalars().all()
        
        for db_claim in db_claims:
            is_unsupported = any(db_claim.value in uc for uc in finalized_summary.validation.unsupported_claims)
            if is_unsupported:
                db_claim.status = "NOT_SUPPORTED"
                db_claim.confidence_score = 0.0
                db_claim.confidence_level = "LOW"
            else:
                db_claim.status = "SUPPORTED"

        # 6. Evaluate overall pipeline safety flags to update stay status
        has_conflicts = len(finalized_summary.validation.conflicts) > 0
        has_unsupported = len(finalized_summary.validation.unsupported_claims) > 0
        has_missing = len(finalized_summary.summary.missing_information) > 0
        grounding_score_val = finalized_summary.validation.grounding_metrics.grounding_score

        if has_conflicts or has_unsupported or has_missing or grounding_score_val < 0.75:
            pipeline_status = "NEEDS_RECONCILIATION"
        else:
            pipeline_status = "READY_FOR_REVIEW"

        # Update stay status
        stay_query = await db.execute(select(PatientStay).where(PatientStay.id == stay_id))
        current_stay = stay_query.scalars().first()
        current_stay.status = pipeline_status

        # 7. Save Validation Report
        await db.execute(delete(ValidationReport).where(ValidationReport.stay_id == stay_id))
        db_report = ValidationReport(
            stay_id=stay_id,
            grounded=finalized_summary.validation.grounded,
            confidence=finalized_summary.validation.confidence,
            unsupported_claims=finalized_summary.validation.unsupported_claims,
            conflicts=[c.model_dump() for c in finalized_summary.validation.conflicts],
            notes=finalized_summary.validation.notes
        )
        db.add(db_report)

        # 8. Save Final Summary and populate audit fields
        summary_query = await db.execute(select(FinalDischargeSummary).where(FinalDischargeSummary.stay_id == stay_id))
        existing_summary = summary_query.scalars().first()

        summary_dict = finalized_summary.model_dump(mode='json')

        if existing_summary:
            existing_summary.structured_data = summary_dict
            existing_summary.is_reconciled = 0
            existing_summary.grounding_score = grounding_score_val
            existing_summary.pipeline_version = "1.2.0"
            existing_summary.judge_version = "gemini-2.5-pro"
        else:
            new_summary = FinalDischargeSummary(
                stay_id=stay_id,
                structured_data=summary_dict,
                is_reconciled=0,
                grounding_score=grounding_score_val,
                pipeline_version="1.2.0",
                judge_version="gemini-2.5-pro"
            )
            db.add(new_summary)

        await db.commit()
        logger.info(f"Pipeline executed successfully. Status: {pipeline_status}. Grounding: {grounding_score_val}")
        return {
            "stay_id": stay_id,
            "pipeline_status": pipeline_status,
            "data": summary_dict
        }

    except ClinicalPipelineException as cpe:
        await db.rollback()
        logger.error(f"Internal pipeline safety validation failure: {str(cpe)}")
        raise HTTPException(status_code=500, detail=f"Safety Layer Error: {str(cpe)}")
    except Exception as e:
        await db.rollback()
        logger.error(f"Pipeline process execution failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Critical Database or Pipeline execution failure.")


@app.post("/api/pipeline/approve/{stay_id}")
async def approve_discharge_summary(stay_id: str, db: AsyncSession = Depends(get_db)):
    """
    Applies Human-in-the-Loop physician approval.
    Marks summary as reconciled, signs the audit columns, and transitions stay to COMPLETED.
    """
    try:
        stay_query = await db.execute(select(PatientStay).where(PatientStay.id == stay_id))
        stay = stay_query.scalars().first()
        if not stay:
            raise HTTPException(status_code=404, detail="Stay not found.")

        summary_query = await db.execute(select(FinalDischargeSummary).where(FinalDischargeSummary.stay_id == stay_id))
        summary = summary_query.scalars().first()
        if not summary:
            raise HTTPException(status_code=404, detail="Summary not found. Process note first.")

        stay.status = "COMPLETED"
        summary.is_reconciled = 1
        summary.reviewed_by = "Dr. Sarah Jenkins (Attending Physician)"
        summary.reviewed_at = datetime.datetime.utcnow()
        
        struct_data = dict(summary.structured_data)
        if "validation" in struct_data:
            struct_data["validation"]["grounded"] = True
            struct_data["validation"]["notes"].append(
                f"Approved by attending physician Dr. Sarah Jenkins at {summary.reviewed_at.isoformat()}"
            )
        summary.structured_data = struct_data

        await db.commit()
        logger.info(f"Stay {stay_id} has been manually approved and signed by Dr. Sarah Jenkins.")
        return {"status": "success", "message": "Discharge summary approved, signed, and finalized."}
    except Exception as e:
        await db.rollback()
        logger.error(f"Approval endpoint failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Database write error occurred during manual approval.")


@app.post("/api/pipeline/resolve/{stay_id}")
async def resolve_conflicts(stay_id: str, payload: ResolutionRequest, db: AsyncSession = Depends(get_db)):
    """
    Allows a physician to resolve conflicts.
    Submits resolved medications, updates structured summary, sets audit columns,
    and transitions stay to COMPLETED.
    """
    try:
        stay_query = await db.execute(select(PatientStay).where(PatientStay.id == stay_id))
        stay = stay_query.scalars().first()
        if not stay:
            raise HTTPException(status_code=404, detail="Stay not found.")

        summary_query = await db.execute(select(FinalDischargeSummary).where(FinalDischargeSummary.stay_id == stay_id))
        summary = summary_query.scalars().first()
        if not summary:
            raise HTTPException(status_code=404, detail="Summary not found.")

        struct_data = dict(summary.structured_data)
        
        resolved_meds = []
        for index, item in enumerate(payload.medications):
            resolved_meds.append({
                "name": item.name,
                "dosage": item.dosage,
                "frequency": item.frequency,
                "duration": item.duration,
                "confidence": {"score": 1.0, "level": "HIGH"},
                "evidence": [{
                    "source_document": "Attending Physician Resolution Log",
                    "extracted_text": f"Resolved conflict manually by physician Dr. Sarah Jenkins.",
                    "author_role": "ATTENDING",
                    "recorded_at": datetime.datetime.utcnow().isoformat()
                }],
                "claim_id": f"CLM_MED_RESOLVED_{index}"
            })

        # Overwrite medications and clear active validation report flags
        struct_data["summary"]["prescribed_medications"] = resolved_meds
        struct_data["validation"]["conflicts"] = []
        struct_data["validation"]["grounded"] = True
        
        # Reset warnings and metrics
        struct_data["validation"]["warnings"] = []
        if "grounding_metrics" in struct_data["validation"]:
            struct_data["validation"]["grounding_metrics"]["grounding_score"] = 1.0
            struct_data["validation"]["grounding_metrics"]["evidence_coverage"] = 1.0

        approval_time = datetime.datetime.utcnow()
        struct_data["validation"]["notes"].append(
            f"Conflicts manually resolved by Attending Physician Dr. Sarah Jenkins at {approval_time.isoformat()}"
        )

        summary.structured_data = struct_data
        summary.is_reconciled = 1
        summary.reviewed_by = "Dr. Sarah Jenkins (Attending Physician)"
        summary.reviewed_at = approval_time
        summary.grounding_score = 1.0
        stay.status = "COMPLETED"

        # Update clinical claims in database
        await db.execute(delete(ClinicalClaim).where(ClinicalClaim.stay_id == stay_id))
        for index, item in enumerate(payload.medications):
            db_claim = ClinicalClaim(
                id=f"CLM_MED_RESOLVED_{index}",
                stay_id=stay_id,
                category="MEDICATION",
                value=f"Prescribed medication: {item.name} at dosage: {item.dosage}, frequency: {item.frequency}, for duration: {item.duration}",
                confidence_score=1.0,
                confidence_level="HIGH",
                evidence=[{
                    "source_document": "Attending Physician Resolution Log",
                    "extracted_text": f"Resolved conflict manually by physician Dr. Sarah Jenkins.",
                    "author_role": "ATTENDING",
                    "recorded_at": approval_time.isoformat()
                }],
                author_role="ATTENDING",
                recorded_at=approval_time,
                status="SUPPORTED"
            )
            db.add(db_claim)

        await db.commit()
        logger.info(f"Stay {stay_id} conflicts resolved, signed, and saved by Attending.")
        return {"status": "success", "message": "Discharge summary reconciled, conflicts resolved, and finalized."}
    except Exception as e:
        await db.rollback()
        logger.error(f"Resolution endpoint failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Database write error occurred during conflict resolution.")