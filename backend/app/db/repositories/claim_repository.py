"""
ClaimRepository — all ClinicalClaim database operations.

Responsibilities:
  - Delete existing claims for a stay before re-running the pipeline
  - Bulk-create new atomic claims
  - Update claim statuses based on grounding validation results
"""

import logging
from datetime import datetime
from typing import List

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.models import ClinicalClaim
from app.models.schemas import ClaimSchema

logger = logging.getLogger(__name__)


class ClaimRepository:
    """
    Encapsulates all SQLAlchemy operations for the clinical_claims table.
    Stateless — safe to use as a singleton.
    """

    async def delete_by_stay(self, db: AsyncSession, stay_id: str) -> None:
        """
        Removes all claims for a stay prior to re-generating them.
        Called at the start of both pipeline execution and conflict resolution.
        """
        await db.execute(
            delete(ClinicalClaim).where(ClinicalClaim.stay_id == stay_id)
        )
        logger.info("Deleted existing claims for stay: %s", stay_id)

    async def bulk_create(
        self,
        db: AsyncSession,
        stay_id: str,
        claims: List[ClaimSchema],
        timestamp: datetime,
    ) -> None:
        """
        Persists a list of ClaimSchema objects as ClinicalClaim ORM rows.
        Uses mode='json' serialization to ensure datetime fields in evidence
        are converted to ISO strings before being stored in the JSON column.
        """
        for claim in claims:
            db_claim = ClinicalClaim(
                id=claim.claim_id,
                stay_id=stay_id,
                category=claim.category,
                value=claim.value,
                confidence_score=claim.confidence.score,
                confidence_level=claim.confidence.level,
                evidence=[ev.model_dump(mode="json") for ev in claim.evidence],
                author_role=claim.author,
                recorded_at=claim.timestamp,
                status="UNVERIFIED",
            )
            db.add(db_claim)

        await db.flush()
        logger.info(
            "Bulk-created %d claims for stay: %s", len(claims), stay_id
        )

    async def update_statuses_from_validation(
        self,
        db: AsyncSession,
        stay_id: str,
        unsupported_claim_strings: List[str],
    ) -> None:
        """
        Marks each claim as SUPPORTED or NOT_SUPPORTED based on the grounding
        validation results. Updates confidence score to 0.0 for unsupported claims.
        """
        result = await db.execute(
            select(ClinicalClaim).where(ClinicalClaim.stay_id == stay_id)
        )
        db_claims = result.scalars().all()

        updated = 0
        for db_claim in db_claims:
            is_unsupported = any(
                db_claim.value in uc for uc in unsupported_claim_strings
            )
            if is_unsupported:
                db_claim.status = "NOT_SUPPORTED"
                db_claim.confidence_score = 0.0
                db_claim.confidence_level = "LOW"
                updated += 1
            else:
                db_claim.status = "SUPPORTED"

        logger.info(
            "Updated claim statuses for stay %s: %d NOT_SUPPORTED, %d SUPPORTED",
            stay_id,
            updated,
            len(db_claims) - updated,
        )
