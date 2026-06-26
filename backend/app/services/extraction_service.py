"""
ClinicalExtractionService — Gemini-powered clinical note extraction.

Refactoring changes vs original:
  - Removed module-level genai.configure() side effect (now in startup_event)
  - Removed module-level GEMINI_API_KEY validation (now in config.py)
  - Removed duplicate logging.basicConfig() call
  - All constants (model name, retries, backoff) sourced from config.py
  - ClinicalConfidenceService, ClinicalSchemaValidator, ClinicalClaimIdService
    injected via constructor instead of instantiated internally
  - Dead code removed; no behavioral changes
"""

import asyncio
import json
import logging
import random
import re
import time
from typing import List, Optional, Tuple

import google.generativeai as genai
import pydantic
from google.api_core import exceptions as google_exceptions

from app.core.config import (
    GEMINI_EXTRACTION_MODEL,
    INITIAL_BACKOFF_SECONDS,
    MAX_RETRIES,
)
from app.core.exceptions import (
    AIServiceUnavailable,
    ClinicalExtractionError,
    ClinicalPipelineException,
    DatabaseUnavailable,
    DocumentValidationError,
    UnsupportedFileType,
)
from app.core.prompts import EXTRACTION_PROMPT, BATCH_EXTRACTION_PROMPT
from app.models.schemas import NABHDischargeSummaryExtraction
from app.services.claim_id_service import ClinicalClaimIdService
from app.services.confidence_service import ClinicalConfidenceService
from app.services.schema_validator import ClinicalSchemaValidator, ClinicalValidationError

logger = logging.getLogger(__name__)

# Compat aliases preserved for any legacy import sites
AIServiceUnavailableError = AIServiceUnavailable
QuotaExceededError = AIServiceUnavailable
ClinicalExtractionUnavailable = AIServiceUnavailable


class ClinicalExtractionService:
    """
    A production-ready service that extracts structured clinical facts from raw
    clinical notes using Gemini with exponential backoff retries.

    Delegates concern layers to injected helper services:
      - ClinicalConfidenceService  → authority annotation
      - ClinicalSchemaValidator    → schema validation and evidence reconciliation
      - ClinicalClaimIdService     → deterministic claim ID generation
    """

    def __init__(
        self,
        schema_validator: Optional[ClinicalSchemaValidator] = None,
        claim_id_service: Optional[ClinicalClaimIdService] = None,
        confidence_service: Optional[ClinicalConfidenceService] = None,
    ) -> None:
        self.model_name = GEMINI_EXTRACTION_MODEL
        self.max_retries = MAX_RETRIES
        self.initial_backoff = INITIAL_BACKOFF_SECONDS

        # Accept injected dependencies or create defaults (backwards compat)
        self.schema_validator = schema_validator or ClinicalSchemaValidator()
        self.claim_id_service = claim_id_service or ClinicalClaimIdService()
        self.confidence_service = confidence_service or ClinicalConfidenceService()

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    async def extract_structured_data(
        self, raw_note_content: str, author_role: str
    ) -> NABHDischargeSummaryExtraction:
        """
        Extracts structured clinical data from a single raw note.
        Used for single-note debugging and testing. Production pipeline uses
        extract_structured_data_batch for efficiency.
        """
        logger.info("[Extraction] Starting single-note extraction (role=%s)", author_role)

        if not raw_note_content or not raw_note_content.strip():
            logger.warning("[Extraction] Empty raw note content — returning empty schema.")
            return NABHDischargeSummaryExtraction(
                patient_details={}, admission_details={}, follow_up_instructions={}
            )

        cleaned_content = self._preprocess_note(raw_note_content)
        prompt = self._build_prompt(cleaned_content, author_role)

        response_text = await self._call_gemini_with_retry(prompt)

        try:
            extraction = self.schema_validator.parse_response(response_text)
            extraction = self.schema_validator.verify_and_reconcile_evidence(extraction)
            extraction = self.claim_id_service.generate_claim_ids(extraction)
            extraction = self.confidence_service.assign_authority(extraction, author_role)
        except (json.JSONDecodeError, pydantic.ValidationError, ClinicalValidationError) as err:
            logger.error("[Extraction] Schema validation failed: %s", err)
            raise ClinicalExtractionUnavailable(
                f"Structured data extraction failed schema validation: {err}"
            ) from err
        except Exception as err:
            logger.error("[Extraction] Post-processing failed: %s", err)
            raise ClinicalExtractionUnavailable(
                f"Structured data extraction failed: {err}"
            ) from err

        logger.info("[Extraction] Single-note extraction completed successfully")
        return extraction

    async def extract_structured_data_batch(
        self, unique_raw_notes: list
    ) -> list:
        """
        Ingests all raw notes for a stay in a single Gemini API call.

        Steps:
          1. Format each note with role/timestamp boundary headers
          2. Submit combined prompt to Gemini (1 LLM call)
          3. Parse the structured response per-role
          4. Validate, reconcile evidence, generate claim IDs, annotate authority
          5. Return list of (extraction, recorded_at, author_role) tuples

        Returns:
            List of (NABHDischargeSummaryExtraction, datetime, str) tuples.
        """
        logger.info("[Extraction] Starting batch extraction for %d notes", len(unique_raw_notes))

        if not unique_raw_notes:
            logger.warning("[Extraction] No unique raw notes provided — returning empty list.")
            return []

        # Build combined prompt
        headers = []
        for note in unique_raw_notes:
            cleaned = self._preprocess_note(note.content)
            role_header = f"{self._format_role_for_header(note.author_role)} Note"
            if note.recorded_at:
                role_header += f" (recorded at {note.recorded_at.isoformat()})"
            headers.append(f"{role_header}\n==============\n{cleaned}")

        combined_notes = "\n\n".join(headers)
        prompt = BATCH_EXTRACTION_PROMPT.format(combined_notes=combined_notes)

        logger.info("[Extraction] Batch prompt constructed — submitting to Gemini")
        response_text = await self._call_gemini_with_retry(prompt)
        logger.info("[Extraction] Batch response received — parsing schemas")

        try:
            parsed_extractions = self.schema_validator.parse_batch_response(response_text)

            extractions_pipeline_input = []
            for note in unique_raw_notes:
                ext = parsed_extractions.get(note.author_role.upper())
                if not ext:
                    logger.warning(
                        "[Extraction] Role %s not found in batch response — using empty extraction.",
                        note.author_role,
                    )
                    ext = NABHDischargeSummaryExtraction(
                        patient_details={}, admission_details={}, follow_up_instructions={}
                    )

                # Post-extraction pipeline
                ext = self.schema_validator.verify_and_reconcile_evidence(ext)
                ext = self.claim_id_service.generate_claim_ids(ext)
                ext = self.confidence_service.assign_authority(ext, note.author_role)

                extractions_pipeline_input.append((ext, note.recorded_at, note.author_role))

            logger.info(
                "[Extraction] Batch extraction completed: %d roles processed",
                len(extractions_pipeline_input),
            )
            return extractions_pipeline_input

        except (json.JSONDecodeError, pydantic.ValidationError, ClinicalValidationError) as err:
            logger.error("[Extraction] Batch schema validation failed: %s", err)
            raise ClinicalExtractionUnavailable(
                f"Structured data extraction failed schema validation: {err}"
            ) from err
        except Exception as other_err:
            logger.error("[Extraction] Batch post-processing failed: %s", other_err)
            raise ClinicalExtractionUnavailable(
                f"Structured data extraction failed validation: {other_err}"
            ) from other_err

    # ─────────────────────────────────────────────────────────────────────────
    # Gemini I/O
    # ─────────────────────────────────────────────────────────────────────────

    async def _call_gemini_with_retry(self, prompt: str) -> str:
        """
        Submits a prompt to Gemini with exponential backoff retries.
        Raises AIServiceUnavailable on non-transient errors or exhausted retries.
        Returns the raw response text on success.
        """
        retry_count = 0
        start_time = time.time()

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info("[Extraction] Gemini call attempt %d/%d", attempt, self.max_retries)
                model = genai.GenerativeModel(
                    model_name=self.model_name,
                    generation_config={
                        "response_mime_type": "application/json",
                        "temperature": 0.0,
                        "top_p": 0.1,
                    },
                )
                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(
                    None, lambda: model.generate_content(prompt)
                )

                if not response or not response.text:
                    raise ValueError("Gemini API returned an empty or invalid response.")

                duration = time.time() - start_time
                logger.info(
                    "Extraction metrics: duration=%f, provider=gemini, retries=%d, status=success",
                    duration,
                    retry_count,
                )
                return response.text

            except Exception as exc:
                err_msg = str(exc).lower()
                is_transient = self._is_transient_error(exc, err_msg)

                if not is_transient or attempt == self.max_retries:
                    exc_class, exc_msg = self._classify_error(exc, err_msg)
                    logger.error("[Extraction] Gemini unavailable — %s", exc_msg)
                    raise exc_class(exc_msg) from exc

                retry_count += 1
                backoff = self._compute_backoff(attempt)
                logger.info(
                    "[Extraction] Transient error (%s). Retrying in %.2fs...",
                    type(exc).__name__,
                    backoff,
                )
                await asyncio.sleep(backoff)

        # Should never reach here, but satisfies type checker
        raise AIServiceUnavailable("Gemini API extraction failed after all retries.")

    # ─────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _preprocess_note(self, text: str) -> str:
        """
        Normalizes whitespace, carriage returns, tabs, and removes repeated
        formatting symbols without altering clinical terminology.
        """
        text = re.sub(r"[\r\t\v\f\n]", " ", text)
        text = re.sub(r"[#*\-`_\|]{2,}", " ", text)
        text = re.sub(r" +", " ", text)
        return text.strip()

    @staticmethod
    def _format_role_for_header(role: str) -> str:
        """Converts WARD_NURSE → Ward Nurse for use in prompt boundary headers."""
        return " ".join(p.capitalize() for p in role.split("_"))

    def _build_prompt(self, raw_note_content: str, author_role: str) -> str:
        """
        Formats the single-note extraction prompt with schema guidelines appended.
        Used only by extract_structured_data (single-note path).
        """
        schema_guidelines = """
Your JSON response MUST match the following JSON structure exactly:
{
  "patient_details": {
    "name": "string (patient name or 'NOT_DOCUMENTED')",
    "age_sex": "string (age/gender or 'NOT_DOCUMENTED')",
    "patient_id": "string (patient id or 'NOT_DOCUMENTED')",
    "date_of_admission": "string (ISO 8601 datetime format YYYY-MM-DDTHH:MM:SS or null)",
    "date_of_discharge": "string (ISO 8601 datetime format YYYY-MM-DDTHH:MM:SS or null)"
  },
  "admission_details": {
    "reason_for_admission": "string or 'NOT_DOCUMENTED'",
    "mode_of_admission": "string or 'NOT_DOCUMENTED'"
  },
  "diagnoses": [
    {
      "diagnosis": "string",
      "confidence": {"score": number, "level": "HIGH|MEDIUM|LOW"},
      "evidence": [{"source_document": "string", "extracted_text": "string", "author_role": "string", "recorded_at": "string or null"}],
      "claim_id": null
    }
  ],
  "symptoms": [],
  "clinical_summary": "string or 'NOT_DOCUMENTED'",
  "treatment_provided": "string or 'NOT_DOCUMENTED'",
  "investigations": [],
  "discharge_condition": "string or 'NOT_DOCUMENTED'",
  "prescribed_medications": [],
  "follow_up_instructions": {
    "recommended_follow_up": "string or 'NOT_DOCUMENTED'",
    "next_follow_up_date": "string or 'NOT_DOCUMENTED'",
    "lifestyle_dietary_instructions": "string or 'NOT_DOCUMENTED'",
    "confidence": {"score": number, "level": "HIGH|MEDIUM|LOW"},
    "evidence": [],
    "claim_id": null
  },
  "discharging_physician_name": "string or 'NOT_DOCUMENTED'",
  "missing_information": []
}
"""
        return (
            EXTRACTION_PROMPT.format(
                author_role=author_role.upper(),
                raw_note_content=raw_note_content,
            )
            + "\n\n"
            + schema_guidelines
        )

    @staticmethod
    def _is_transient_error(exc: Exception, err_msg: str) -> bool:
        """Returns True if the error is likely transient and worth retrying."""
        return (
            isinstance(exc, google_exceptions.ResourceExhausted)
            or isinstance(exc, google_exceptions.ServiceUnavailable)
            or isinstance(exc, (TimeoutError, asyncio.TimeoutError, ConnectionError, OSError))
            or any(k in err_msg for k in ("429", "quota", "rate limit", "503", "unavailable", "timeout", "connection", "network"))
        )

    def _compute_backoff(self, attempt: int) -> float:
        """Computes exponential backoff with ±0.5s random jitter."""
        raw = (self.initial_backoff * (2 ** (attempt - 1))) + random.uniform(-0.5, 0.5)
        return max(0.1, raw)

    @staticmethod
    def _classify_error(
        exc: Exception, err_msg: str
    ) -> Tuple[type, str]:
        """Maps an exception to the appropriate AIServiceUnavailable subclass and message."""
        if isinstance(exc, google_exceptions.ResourceExhausted) or any(
            k in err_msg for k in ("429", "quota", "rate limit")
        ):
            return AIServiceUnavailable, f"Gemini API quota exceeded: {exc}"
        if isinstance(exc, google_exceptions.ServiceUnavailable) or "503" in err_msg or "unavailable" in err_msg:
            return AIServiceUnavailable, f"Gemini API temporarily unavailable: {exc}"
        if "timeout" in err_msg or isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
            return AIServiceUnavailable, f"AI service network timeout: {exc}"
        if "connection" in err_msg or "network" in err_msg or isinstance(exc, (ConnectionError, OSError)):
            return AIServiceUnavailable, f"AI service connection failure: {exc}"
        if isinstance(exc, (google_exceptions.PermissionDenied, google_exceptions.Unauthenticated)):
            return AIServiceUnavailable, f"Gemini API authentication failed: {exc}"
        return AIServiceUnavailable, f"Gemini API extraction failed: {exc}"
