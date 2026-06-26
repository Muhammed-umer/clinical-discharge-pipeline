import json
import logging
from typing import Dict
from app.models.schemas import NABHDischargeSummaryExtraction, MissingFieldSchema

logger = logging.getLogger(__name__)

class ClinicalValidationError(Exception):
    """Exception raised when extraction outputs fail Pydantic validation checks."""
    pass

class ClinicalSchemaValidator:
    """
    Handles manual parsing of Gemini responses, Pydantic schema validation,
    and factual evidence grounding/verification.
    """
    
    def parse_response(self, response_text: str) -> NABHDischargeSummaryExtraction:
        """
        Validates the Gemini JSON response structure against NABH Pydantic models.
        """
        try:
            clean_text = response_text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            clean_text = clean_text.strip()

            # Parse JSON manually
            parsed_dict = json.loads(clean_text)

            # Normalize common LLM key naming variations before validation
            if isinstance(parsed_dict, dict):
                # 1. Normalize symptoms list (ObservationSchema expects "observation")
                if "symptoms" in parsed_dict and isinstance(parsed_dict["symptoms"], list):
                    for item in parsed_dict["symptoms"]:
                        if isinstance(item, dict):
                            for alt_key in ["diagnosis", "symptom", "finding", "name"]:
                                if alt_key in item and "observation" not in item:
                                    item["observation"] = item[alt_key]
                                    break
                                    
                # 2. Normalize diagnoses list (DiagnosisSchema expects "diagnosis")
                if "diagnoses" in parsed_dict and isinstance(parsed_dict["diagnoses"], list):
                    for item in parsed_dict["diagnoses"]:
                        if isinstance(item, dict):
                            for alt_key in ["observation", "symptom", "name"]:
                                if alt_key in item and "diagnosis" not in item:
                                    item["diagnosis"] = item[alt_key]
                                    break

            # Validate using model_validate after Gemini returns
            return NABHDischargeSummaryExtraction.model_validate(parsed_dict)
        except json.JSONDecodeError as jde:
            logger.error(f"Raw response is not decodable JSON. Raw text: {response_text}")
            raise ClinicalValidationError(f"Gemini returned invalid JSON structure: {str(jde)}") from jde
        except Exception as e:
            logger.error(f"Response failed schema validation: {str(e)}")
            raise ClinicalValidationError(f"Gemini JSON response failed schema validation constraints: {str(e)}") from e

    def parse_batch_response(self, response_text: str) -> Dict[str, NABHDischargeSummaryExtraction]:
        """
        Validates the Gemini JSON response structure for batch extractions.
        """
        try:
            clean_text = response_text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            clean_text = clean_text.strip()

            parsed_dict = json.loads(clean_text)

            if "notes_extractions" not in parsed_dict:
                raise ClinicalValidationError("Missing 'notes_extractions' key in batch response.")

            extractions_dict = parsed_dict["notes_extractions"]
            result = {}

            for role, ext_dict in extractions_dict.items():
                if isinstance(ext_dict, dict):
                    # 1. Normalize symptoms list (ObservationSchema expects "observation")
                    if "symptoms" in ext_dict and isinstance(ext_dict["symptoms"], list):
                        for item in ext_dict["symptoms"]:
                            if isinstance(item, dict):
                                for alt_key in ["diagnosis", "symptom", "finding", "name"]:
                                    if alt_key in item and "observation" not in item:
                                        item["observation"] = item[alt_key]
                                        break
                                        
                    # 2. Normalize diagnoses list (DiagnosisSchema expects "diagnosis")
                    if "diagnoses" in ext_dict and isinstance(ext_dict["diagnoses"], list):
                        for item in ext_dict["diagnoses"]:
                            if isinstance(item, dict):
                                for alt_key in ["observation", "symptom", "name"]:
                                    if alt_key in item and "diagnosis" not in item:
                                        item["diagnosis"] = item[alt_key]
                                        break

                validated = NABHDischargeSummaryExtraction.model_validate(ext_dict)
                result[role.upper()] = validated

            return result
        except json.JSONDecodeError as jde:
            logger.error(f"Raw batch response is not decodable JSON. Raw text: {response_text}")
            raise ClinicalValidationError(f"Gemini returned invalid JSON structure: {str(jde)}") from jde
        except Exception as e:
            logger.error(f"Batch response failed schema validation: {str(e)}")
            raise ClinicalValidationError(f"Gemini JSON batch response failed schema validation constraints: {str(e)}") from e


    # Minimum number of characters required in extracted_text to be considered
    # a valid clinical citation. Single words or whitespace strings are not
    # meaningful evidence and are treated as missing.
    MIN_EVIDENCE_TEXT_LENGTH = 10

    def _has_valid_evidence(self, evidence_list: list) -> bool:
        """
        Returns True if at least one evidence item has extracted_text
        meeting the minimum length threshold.
        """
        return any(
            ev.extracted_text
            and len(ev.extracted_text.strip()) >= self.MIN_EVIDENCE_TEXT_LENGTH
            for ev in evidence_list
        )

    def _filter_facts_by_evidence(
        self, items: list, category_name: str, field_attr: str, missing_info: list
    ) -> list:
        """
        Generic helper to verify that each item in a list contains supporting evidence
        references with meaningful extracted text (≥ MIN_EVIDENCE_TEXT_LENGTH chars).
        Items without qualifying evidence are excluded and logged as missing information.
        """
        verified = []
        for item in items:
            val = getattr(item, field_attr, "Unknown")
            if item.evidence and self._has_valid_evidence(item.evidence):
                verified.append(item)
            else:
                logger.warning(
                    f"Filtering out {category_name} '{val}': "
                    f"evidence missing or text too short (< {self.MIN_EVIDENCE_TEXT_LENGTH} chars)."
                )
                missing_info.append(MissingFieldSchema(
                    field_name=f"{category_name}.{val}",
                    reason=(
                        f"{category_name.capitalize()} fact was extracted but lacked "
                        f"supporting text citations with sufficient content."
                    ),
                    requires_physician_review=True
                ))
        return verified

    def verify_and_reconcile_evidence(
        self, extraction: NABHDischargeSummaryExtraction
    ) -> NABHDischargeSummaryExtraction:
        """
        Verifies that every diagnosis, medication, investigation, and observation has
        evidence with meaningful extracted text (≥ MIN_EVIDENCE_TEXT_LENGTH chars).
        Items without qualifying evidence are excluded and logged under missing_information.
        """
        logger.info("Performing evidence citation check across all clinical segments.")

        extraction.diagnoses = self._filter_facts_by_evidence(
            extraction.diagnoses, "diagnoses", "diagnosis", extraction.missing_information
        )
        extraction.prescribed_medications = self._filter_facts_by_evidence(
            extraction.prescribed_medications, "medication", "name", extraction.missing_information
        )
        extraction.investigations = self._filter_facts_by_evidence(
            extraction.investigations, "investigations", "investigation", extraction.missing_information
        )
        extraction.symptoms = self._filter_facts_by_evidence(
            extraction.symptoms, "symptoms", "observation", extraction.missing_information
        )

        # Follow-Up Instructions (special schema, custom check)
        if extraction.follow_up_instructions:
            fol = extraction.follow_up_instructions
            if fol.recommended_follow_up != "NOT_DOCUMENTED":
                # Apply the same minimum-length guard to follow-up evidence
                has_ev = fol.evidence and self._has_valid_evidence(fol.evidence)
                if not has_ev:
                    logger.warning(
                        "Follow-up advice lacks qualifying evidence text "
                        f"(< {self.MIN_EVIDENCE_TEXT_LENGTH} chars). Marking as NOT_DOCUMENTED."
                    )
                    extraction.missing_information.append(MissingFieldSchema(
                        field_name="follow_up_instructions",
                        reason="Follow-up instructions lacked corresponding note source references with sufficient detail.",
                        requires_physician_review=True
                    ))
                    fol.recommended_follow_up = "NOT_DOCUMENTED"
                    fol.next_follow_up_date = "NOT_DOCUMENTED"
                    fol.lifestyle_dietary_instructions = "NOT_DOCUMENTED"

        return extraction
