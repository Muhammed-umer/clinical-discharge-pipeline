"""
SummaryRepository — all FinalDischargeSummary database operations.

Responsibilities:
  - Fetch the summary for a stay
  - Upsert the structured summary JSON after pipeline execution
  - Record audit fields (grounding_score, pipeline_version, reviewed_by, etc.)
"""

import logging
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.models import FinalDischargeSummary

logger = logging.getLogger(__name__)


class SummaryRepository:
    """
    Encapsulates all SQLAlchemy operations for the final_discharge_summaries table.
    Stateless — safe to use as a singleton.
    """

    async def get_by_stay(
        self, db: AsyncSession, stay_id: str
    ) -> Optional[FinalDischargeSummary]:
        """Returns the FinalDischargeSummary for a stay, or None."""
        result = await db.execute(
            select(FinalDischargeSummary).where(
                FinalDischargeSummary.stay_id == stay_id
            )
        )
        return result.scalars().first()

    async def upsert(
        self,
        db: AsyncSession,
        stay_id: str,
        structured_data: Dict[str, Any],
        grounding_score: float = 0.0,
        pipeline_version: str = "1.2.0",
        judge_version: str = "gemini-2.5-flash",
        is_reconciled: int = 0,
    ) -> FinalDischargeSummary:
        """
        Updates the existing summary for a stay if one exists, or creates a
        new one. Returns the persisted FinalDischargeSummary ORM object.
        Caller is responsible for committing the session.
        """
        existing = await self.get_by_stay(db, stay_id)
        if existing:
            existing.structured_data = structured_data
            existing.is_reconciled = is_reconciled
            existing.grounding_score = grounding_score
            existing.pipeline_version = pipeline_version
            existing.judge_version = judge_version
            logger.info("Updated FinalDischargeSummary for stay: %s", stay_id)
            return existing

        summary = FinalDischargeSummary(
            stay_id=stay_id,
            structured_data=structured_data,
            is_reconciled=is_reconciled,
            grounding_score=grounding_score,
            pipeline_version=pipeline_version,
            judge_version=judge_version,
        )
        db.add(summary)
        logger.info("Created FinalDischargeSummary for stay: %s", stay_id)
        return summary
