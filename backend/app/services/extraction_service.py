import os
import logging
import asyncio
import google.generativeai as genai
from typing import Optional  # retained for any future optional returns
from dotenv import load_dotenv

from app.models.schemas import NABHDischargeSummaryExtraction
from app.core.prompts import EXTRACTION_PROMPT
from app.services.confidence_service import ClinicalConfidenceService
from app.services.claim_id_service import ClinicalClaimIdService
from app.services.schema_validator import ClinicalSchemaValidator, ClinicalValidationError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("CRITICAL ERROR: GEMINI_API_KEY is missing from environment variables.")

genai.configure(api_key=GEMINI_API_KEY)


class ClinicalPipelineException(Exception):
    """Base exception for all clinical pipeline processing errors."""
    pass


class ClinicalExtractionError(ClinicalPipelineException):
    """Exception raised when the clinical extraction service fails to query or obtain response from LLM."""
    pass


class ClinicalExtractionService:
    """
    A production-ready service that handles extracting clinical facts from raw clinical notes.
    Delegates concern layers (confidence scores, validation, claim IDs) to separate helper services.
    """

    def __init__(self):
        self.model_name = "gemini-2.5-pro"
        self.max_retries = 3
        self.initial_backoff = 2.0  # seconds
        
        # Instantiate concern services
        self.confidence_service = ClinicalConfidenceService()
        self.schema_validator = ClinicalSchemaValidator()
        self.claim_id_service = ClinicalClaimIdService()

    async def extract_structured_data(
        self, raw_note_content: str, author_role: str
    ) -> NABHDischargeSummaryExtraction:
        """
        Ingests unstructured text from a note, preprocesses it, sends it to Gemini 2.5 Pro,
        validates the response schema, filters out facts lacking evidence, generates claim IDs,
        assigns final extraction confidence, and returns the verified schema.
        """
        logger.info(f"Extraction started for clinician role: {author_role}")
        
        if not raw_note_content or not raw_note_content.strip():
            logger.warning("Empty raw note content provided for extraction.")
            return NABHDischargeSummaryExtraction(
                patient_details={},
                admission_details={},
                follow_up_instructions={}
            )

        # 1. Preprocess raw note (whitespace normalization and formatting artifact cleaning)
        cleaned_content = self._preprocess_note(raw_note_content)
        prompt = self._build_prompt(cleaned_content, author_role)
        response_text = ""
        
        # 2. Query Gemini with exponential backoff retries
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Querying Gemini 2.5 Pro (Attempt {attempt}/{self.max_retries})")
                
                model = genai.GenerativeModel(
                    model_name=self.model_name,
                    generation_config={
                        "response_mime_type": "application/json",
                        "temperature": 0.0,  # Strict factual determinism
                        "top_p": 0.1
                    }
                )

                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: model.generate_content(prompt)
                )

                if not response or not response.text:
                    raise ClinicalExtractionError("Gemini API returned an empty or invalid response.")

                response_text = response.text
                break

            except Exception as e:
                logger.error(f"LLM extraction error on attempt {attempt}: {str(e)}")
                if attempt == self.max_retries:
                    # Healthcare systems must fail safely. Never serve fabricated clinical data.
                    # Raise ClinicalExtractionError so the calling pipeline can handle it
                    # gracefully (skip this note, log the failure, check if other notes succeed).
                    raise ClinicalExtractionError(
                        f"Gemini API failed to extract clinical data after {self.max_retries} attempts: {str(e)}"
                    ) from e
                
                backoff_time = self.initial_backoff * (2 ** (attempt - 1))
                logger.info(f"Backing off for {backoff_time}s...")
                await asyncio.sleep(backoff_time)

        # 3. Parse and Validate Gemini response against Pydantic schema before claim generation
        extraction = self.schema_validator.parse_response(response_text)

        # 4. Strict evidence citation verification (every fact must have supporting evidence)
        extraction = self.schema_validator.verify_and_reconcile_evidence(extraction)

        # 5. Enrich with deterministic claim IDs and annotate clinician authority level
        extraction = self.claim_id_service.generate_claim_ids(extraction)
        # assign_authority sets _authority_level on each item; it does NOT modify
        # the LLM extraction confidence score (Priority 2 separation).
        extraction = self.confidence_service.assign_authority(extraction, author_role)

        logger.info(f"Extraction completed successfully for role: {author_role}")
        return extraction

    def _preprocess_note(self, text: str) -> str:
        """
        Normalizes spaces, carriage returns, tabs, and cleans up repeated formatting symbols
        (hyphens, dashes, asterisks, backticks) without altering clinical terms.
        """
        import re
        # Replace tabs, newlines, carriage returns with single space
        text = re.sub(r'[\r\t\v\f\n]', ' ', text)
        # Remove repeated dashes, stars, pipes, or underscores (formatting artifacts)
        text = re.sub(r'[#*\-`_\|]{2,}', ' ', text)
        # Collapse multiple spaces
        text = re.sub(r' +', ' ', text)
        return text.strip()

    def _build_prompt(self, raw_note_content: str, author_role: str) -> str:
        """
        Formats extraction prompt instructions with schema formatting guidelines.
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
      "confidence": {
        "score": number (0.0 to 1.0),
        "level": "string ('HIGH', 'MEDIUM', or 'LOW')"
      },
      "evidence": [
        {
          "source_document": "string (e.g. 'RESIDENT Note')",
          "extracted_text": "string (EXACT verbatim sentence/clause from original note)",
          "author_role": "string (e.g. 'RESIDENT')",
          "recorded_at": "string (ISO timestamp or null)"
        }
      ],
      "claim_id": null
    }
  ],
  "symptoms": [
    {
      "observation": "string",
      "confidence": {
        "score": number (0.0 to 1.0),
        "level": "string ('HIGH', 'MEDIUM', or 'LOW')"
      },
      "evidence": [
        {
          "source_document": "string",
          "extracted_text": "string (EXACT verbatim sentence/clause from original note)",
          "author_role": "string",
          "recorded_at": "string (ISO timestamp or null)"
        }
      ],
      "claim_id": null
    }
  ],
  "clinical_summary": "string or 'NOT_DOCUMENTED'",
  "treatment_provided": "string or 'NOT_DOCUMENTED'",
  "investigations": [
    {
      "investigation": "string",
      "result": "string",
      "confidence": {
        "score": number (0.0 to 1.0),
        "level": "string ('HIGH', 'MEDIUM', or 'LOW')"
      },
      "evidence": [
        {
          "source_document": "string",
          "extracted_text": "string (EXACT verbatim sentence/clause from original note)",
          "author_role": "string",
          "recorded_at": "string (ISO timestamp or null)"
        }
      ],
      "claim_id": null
    }
  ],
  "discharge_condition": "string or 'NOT_DOCUMENTED'",
  "prescribed_medications": [
    {
      "name": "string",
      "dosage": "string",
      "frequency": "string",
      "duration": "string",
      "confidence": {
        "score": number (0.0 to 1.0),
        "level": "string ('HIGH', 'MEDIUM', or 'LOW')"
      },
      "evidence": [
        {
          "source_document": "string",
          "extracted_text": "string (EXACT verbatim sentence/clause from original note)",
          "author_role": "string",
          "recorded_at": "string (ISO timestamp or null)"
        }
      ],
      "claim_id": null
    }
  ],
  "follow_up_instructions": {
    "recommended_follow_up": "string or 'NOT_DOCUMENTED'",
    "next_follow_up_date": "string or 'NOT_DOCUMENTED'",
    "lifestyle_dietary_instructions": "string or 'NOT_DOCUMENTED'",
    "confidence": {
      "score": number (0.0 to 1.0),
      "level": "string ('HIGH', 'MEDIUM', or 'LOW')"
    },
    "evidence": [
      {
        "source_document": "string",
        "extracted_text": "string (EXACT verbatim sentence/clause from original note)",
        "author_role": "string",
        "recorded_at": "string (ISO timestamp or null)"
      }
    ],
    "claim_id": null
  },
  "discharging_physician_name": "string or 'NOT_DOCUMENTED'",
  "missing_information": [
    {
      "field_name": "string",
      "reason": "string",
      "requires_physician_review": true
    }
  ]
}
"""
        return EXTRACTION_PROMPT.format(
            author_role=author_role.upper(),
            raw_note_content=raw_note_content
        ) + "\n\n" + schema_guidelines
