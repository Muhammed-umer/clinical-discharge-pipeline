"""
Patient Stays routes — /api/stays/*

Handles:
  - GET /api/stays       → List all patient stays (dashboard)
  - GET /api/stays/{id}  → Fetch full stay detail (notes, claims, summary)
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.dependencies import get_pipeline_service
from app.core.exceptions import DatabaseUnavailable
from app.db.database import get_db
from app.db.repositories.claim_repository import ClaimRepository
from app.db.repositories.note_repository import NoteRepository
from app.db.repositories.patient_repository import PatientRepository
from app.db.repositories.summary_repository import SummaryRepository
from app.models.models import (
    ClinicalClaim,
    FinalDischargeSummary,
    PatientStay,
    RawDocumentNode,
)
from app.services.pipeline_service import PipelineService

logger = logging.getLogger(__name__)
router = APIRouter()

# Per-request repository instances are fine since repositories are stateless
_patient_repo = PatientRepository()
_note_repo = NoteRepository()
_summary_repo = SummaryRepository()


@router.get("/stays", response_model=List[Dict[str, Any]])
async def list_patient_stays(db: AsyncSession = Depends(get_db)) -> List[Dict[str, Any]]:
    """
    Returns all patient stays for the dashboard.
    Each item contains id, patient_name, and status.
    """
    try:
        stays = await _patient_repo.list_all(db)
        return [
            {"id": stay.id, "patient_name": stay.patient_name, "status": stay.status}
            for stay in stays
        ]
    except Exception as exc:
        logger.error("Failed to list stays: %s", str(exc))
        raise DatabaseUnavailable("Failed to retrieve patient stays database records.")


@router.get("/stays/{stay_id}")
async def get_stay_details(
    stay_id: str, db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Returns the complete detail of a patient stay including raw notes,
    atomic claims, and the final discharge summary.
    """
    try:
        stay = await _patient_repo.get_by_id(db, stay_id)
        if not stay:
            raise HTTPException(status_code=404, detail="Patient stay not found.")

        notes = await _note_repo.get_by_stay(db, stay_id)

        claims_result = await db.execute(
            select(ClinicalClaim).where(ClinicalClaim.stay_id == stay_id)
        )
        claims = claims_result.scalars().all()

        summary = await _summary_repo.get_by_stay(db, stay_id)

        return {
            "stay_id": stay.id,
            "patient_name": stay.patient_name,
            "status": stay.status,
            "notes": [
                {
                    "id": note.id,
                    "author_role": note.author_role,
                    "recorded_at": note.recorded_at.isoformat(),
                    "content": note.content,
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
                    "status": claim.status,
                }
                for claim in claims
            ],
            "final_summary": summary.structured_data if summary else None,
            "is_reconciled": bool(summary.is_reconciled) if summary else False,
            "reviewed_by": summary.reviewed_by if summary else None,
            "reviewed_at": (
                summary.reviewed_at.isoformat()
                if summary and summary.reviewed_at
                else None
            ),
            "grounding_score": summary.grounding_score if summary else 0.0,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to fetch stay details: %s", str(exc))
        raise DatabaseUnavailable(
            "Database error occurred while fetching stay parameters."
        )
