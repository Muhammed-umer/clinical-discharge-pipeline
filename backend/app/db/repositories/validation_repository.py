"""
ValidationRepository — all ValidationReport database operations.

Responsibilities:
  - Delete and recreate validation reports (one per stay per pipeline run)
  - Encapsulate all ValidationReport persistence logic
"""

import logging
from typing import List

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import ValidationReport
from app.models.schemas import ConflictSchema

logger = logging.getLogger(__name__)


class ValidationRepository:
    """
    Encapsulates all SQLAlchemy operations for the validation_reports table.
    Stateless — safe to use as a singleton.
    """

    async def delete_by_stay(self, db: AsyncSession, stay_id: str) -> None:
        """Removes all validation reports for a stay before creating a new one."""
        await db.execute(
            delete(ValidationReport).where(ValidationReport.stay_id == stay_id)
        )

    async def create(
        self,
        db: AsyncSession,
        stay_id: str,
        grounded: bool,
        confidence: float,
        unsupported_claims: List[str],
        conflicts: List[ConflictSchema],
        notes: List[str],
    ) -> ValidationReport:
        """
        Persists a new ValidationReport for the given stay.
        Conflicts are serialized with mode='json' to avoid datetime serialization
        issues in the PostgreSQL JSON column.
        Caller is responsible for committing the session.
        """
        report = ValidationReport(
            stay_id=stay_id,
            grounded=grounded,
            confidence=confidence,
            unsupported_claims=unsupported_claims,
            conflicts=[c.model_dump(mode="json") for c in conflicts],
            notes=notes,
        )
        db.add(report)
        logger.info(
            "Created ValidationReport for stay %s: grounded=%s confidence=%.2f",
            stay_id,
            grounded,
            confidence,
        )
        return report
