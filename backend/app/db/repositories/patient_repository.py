"""
PatientRepository — all PatientStay database operations.

Responsibilities:
  - Lookup stays by ID
  - Upsert stays on first document upload
  - Update stay status throughout the pipeline
  - List all stays for the dashboard endpoint
"""

import logging
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.models import PatientStay

logger = logging.getLogger(__name__)


class PatientRepository:
    """
    Encapsulates all SQLAlchemy operations for the patient_stays table.
    Accepts an AsyncSession per method call; the repository itself is stateless
    and safe to use as a singleton.
    """

    async def get_by_id(self, db: AsyncSession, stay_id: str) -> Optional[PatientStay]:
        """Returns the PatientStay for the given stay_id, or None if not found."""
        result = await db.execute(
            select(PatientStay).where(PatientStay.id == stay_id)
        )
        return result.scalars().first()

    async def list_all(self, db: AsyncSession) -> List[PatientStay]:
        """Returns all patient stays ordered by default (unspecified) order."""
        result = await db.execute(select(PatientStay))
        return result.scalars().all()

    async def get_or_create(
        self, db: AsyncSession, stay_id: str, patient_name: str
    ) -> PatientStay:
        """
        Returns the existing stay if found, otherwise creates a new one
        with status PROCESSING and flushes it to the session.
        """
        stay = await self.get_by_id(db, stay_id)
        if not stay:
            stay = PatientStay(
                id=stay_id,
                patient_name=patient_name,
                status="PROCESSING",
            )
            db.add(stay)
            await db.flush()
            logger.info("Created new PatientStay: %s (%s)", stay_id, patient_name)
        return stay

    async def update_status(
        self, db: AsyncSession, stay_id: str, status: str
    ) -> None:
        """
        Updates the processing status of a stay.
        Caller is responsible for committing the session.
        """
        stay = await self.get_by_id(db, stay_id)
        if stay:
            stay.status = status
            logger.info("PatientStay %s status → %s", stay_id, status)
