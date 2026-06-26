"""
Structured pipeline logging using PipelineContext.

Every log line emitted through PipelineContext automatically includes:
  - pipeline_version
  - stay_id
  - request_id (UUID hex)
  - stage (e.g. EXTRACTION, VALIDATION, GROUNDING)
  - elapsed_ms since context creation

Usage:
    ctx = PipelineContext(stay_id="CASE-PNEUMONIA-983")
    ctx.info("EXTRACTION", "Batch prompt submitted to Gemini")
    ctx.error("GROUNDING", "Vector retrieval failed")
    ctx.elapsed_seconds()  # Total wall-clock time
"""

import logging
import time
import uuid
from dataclasses import dataclass, field

from app.core.config import PIPELINE_VERSION

logger = logging.getLogger(__name__)


@dataclass
class PipelineContext:
    """
    Request-scoped metadata carrier for structured pipeline logging.
    Instantiate once per pipeline execution; pass through to sub-calls.
    """

    stay_id: str
    pipeline_version: str = PIPELINE_VERSION
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    _start_time: float = field(default_factory=time.time, init=False, repr=False)

    # ── Logging helpers ──────────────────────────────────────────────────────

    def info(self, stage: str, message: str) -> None:
        logger.info(
            "[v%s] stay=%s req=%s stage=%-12s elapsed=%7.1fms | %s",
            self.pipeline_version,
            self.stay_id,
            self.request_id,
            stage,
            self._elapsed_ms(),
            message,
        )

    def warning(self, stage: str, message: str) -> None:
        logger.warning(
            "[v%s] stay=%s req=%s stage=%-12s elapsed=%7.1fms | %s",
            self.pipeline_version,
            self.stay_id,
            self.request_id,
            stage,
            self._elapsed_ms(),
            message,
        )

    def error(self, stage: str, message: str) -> None:
        logger.error(
            "[v%s] stay=%s req=%s stage=%-12s elapsed=%7.1fms | %s",
            self.pipeline_version,
            self.stay_id,
            self.request_id,
            stage,
            self._elapsed_ms(),
            message,
        )

    # ── Timing helpers ───────────────────────────────────────────────────────

    def elapsed_seconds(self) -> float:
        """Total wall-clock time since context was created."""
        return time.time() - self._start_time

    def _elapsed_ms(self) -> float:
        return round((time.time() - self._start_time) * 1000, 1)
