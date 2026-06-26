"""
Versioned prompts for the Clinical Discharge Pipeline.

All prompts are defined inline here to avoid Python module/package
name-shadowing with the legacy prompts.py file.

Version constants are module-level attributes so callers can
include them in audit logs.
"""

from app.core.prompts.extraction_v1 import (
    EXTRACTION_PROMPT,
    BATCH_EXTRACTION_PROMPT,
    EXTRACTION_PROMPT_VERSION,
    BATCH_EXTRACTION_PROMPT_VERSION,
)
from app.core.prompts.judge_v1 import (
    JUDGE_PROMPT,
    BATCH_JUDGE_PROMPT,
    JUDGE_PROMPT_VERSION,
    BATCH_JUDGE_PROMPT_VERSION,
)
from app.core.prompts.summary_v1 import (
    VALIDATION_PROMPT,
    CONFLICT_RESOLUTION_PROMPT,
    RULE_ENGINE_PROMPT,
    SUMMARY_PROMPT,
)

__all__ = [
    "EXTRACTION_PROMPT",
    "BATCH_EXTRACTION_PROMPT",
    "EXTRACTION_PROMPT_VERSION",
    "BATCH_EXTRACTION_PROMPT_VERSION",
    "JUDGE_PROMPT",
    "BATCH_JUDGE_PROMPT",
    "JUDGE_PROMPT_VERSION",
    "BATCH_JUDGE_PROMPT_VERSION",
    "VALIDATION_PROMPT",
    "CONFLICT_RESOLUTION_PROMPT",
    "RULE_ENGINE_PROMPT",
    "SUMMARY_PROMPT",
]
