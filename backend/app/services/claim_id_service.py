import hashlib
import logging
from app.models.schemas import NABHDischargeSummaryExtraction

logger = logging.getLogger(__name__)


def _deterministic_id(prefix: str, content_key: str) -> str:
    """
    Generates a deterministic 12-character hex ID from a SHA-256 hash of the
    content key. Running the pipeline twice on identical notes will always
    produce identical claim IDs, enabling reliable deduplication and traceability.

    Args:
        prefix:      Category prefix string (e.g., "CLM_DIAG").
        content_key: The normalised fact content to hash.

    Returns:
        A string like "CLM_DIAG_3f9a1c2b08e4"
    """
    digest = hashlib.sha256(content_key.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


class ClinicalClaimIdService:
    """
    Generates unique, deterministic, and traceable clinical claim IDs for every
    extracted clinical fact.

    IDs are computed as SHA-256 hashes of the normalised fact content so that:
    - The same fact always receives the same ID across pipeline runs.
    - Different facts (even with minor wording differences) get distinct IDs.
    - Deduplication logic in ClaimService can rely on stable IDs for merging.
    """

    def generate_claim_ids(
        self, extraction: NABHDischargeSummaryExtraction
    ) -> NABHDischargeSummaryExtraction:
        """
        Assigns deterministic SHA-256-based claim IDs to every extracted fact.
        Only assigns an ID if the item does not already have one.
        """
        for item in extraction.diagnoses:
            if not item.claim_id:
                # Key: category prefix + normalised diagnosis text
                content_key = f"DIAG:{item.diagnosis.strip().lower()}"
                item.claim_id = _deterministic_id("CLM_DIAG", content_key)

        for item in extraction.symptoms:
            if not item.claim_id:
                # Key: category prefix + normalised observation text
                content_key = f"OBS:{item.observation.strip().lower()}"
                item.claim_id = _deterministic_id("CLM_OBS", content_key)

        for item in extraction.investigations:
            if not item.claim_id:
                # Key: category prefix + normalised investigation name
                content_key = f"INV:{item.investigation.strip().lower()}"
                item.claim_id = _deterministic_id("CLM_INV", content_key)

        for item in extraction.prescribed_medications:
            if not item.claim_id:
                # Key: category prefix + name + dosage (dosage distinguishes
                # different strengths of the same drug)
                content_key = (
                    f"MED:{item.name.strip().lower()}:"
                    f"{item.dosage.strip().lower()}"
                )
                item.claim_id = _deterministic_id("CLM_MED", content_key)

        if extraction.follow_up_instructions and not extraction.follow_up_instructions.claim_id:
            follow_up_text = extraction.follow_up_instructions.recommended_follow_up
            content_key = f"FOL:{follow_up_text.strip().lower()}"
            extraction.follow_up_instructions.claim_id = _deterministic_id("CLM_FOL", content_key)

        return extraction
