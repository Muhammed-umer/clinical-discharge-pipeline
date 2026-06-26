"""
Centralized configuration module for the Clinical Discharge Pipeline.

All model names, thresholds, retry parameters, and version strings are
defined here. No service should hardcode these values directly.
"""

import os
from dotenv import load_dotenv

load_dotenv(override=True)

# ─── Gemini Model Identifiers ─────────────────────────────────────────────────
GEMINI_EXTRACTION_MODEL: str = "gemini-2.5-flash"
GEMINI_JUDGE_MODEL: str = "gemini-2.5-flash"
GEMINI_EMBEDDING_MODEL: str = "models/gemini-embedding-001"
EMBEDDING_DIMENSIONS: int = 768

# ─── Vector Search ────────────────────────────────────────────────────────────
VECTOR_RETRIEVAL_TOP_K: int = 3

# ─── Grounding Thresholds ─────────────────────────────────────────────────────
GROUNDING_PASS_THRESHOLD: float = 0.75   # Minimum score to mark a claim SUPPORTED
GROUNDING_WARN_THRESHOLD: float = 0.75   # Below this, emit a ClinicalWarning
GROUNDING_STAY_THRESHOLD: float = 0.75   # Below this, stay → NEEDS_RECONCILIATION

# ─── Retry / Backoff ──────────────────────────────────────────────────────────
MAX_RETRIES: int = 3
INITIAL_BACKOFF_SECONDS: float = 2.0     # Base backoff; doubles each attempt

# ─── Pipeline Versioning ──────────────────────────────────────────────────────
PIPELINE_VERSION: str = "1.2.0"
JUDGE_VERSION: str = "gemini-2.5-flash"
EXTRACTION_PROMPT_VERSION: str = "v1"
JUDGE_PROMPT_VERSION: str = "v1"

# ─── Evidence / Citation ──────────────────────────────────────────────────────
MIN_EVIDENCE_TEXT_LENGTH: int = 10  # Chars; shorter evidence is treated as missing

# ─── API Key ──────────────────────────────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    raise RuntimeError(
        "CRITICAL: GEMINI_API_KEY is not set. "
        "Add it to your .env file before starting the server."
    )
