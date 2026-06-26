import hashlib
import logging
from app.models.schemas import NABHDischargeSummaryExtraction

logger = logging.getLogger(__name__)


def _deterministic_id(prefix: str, content_key: str) -> str:
    """
    Generates a deterministic 12-character SHA-256 based identifier.
    The same normalized clinical fact always receives the same ID,
    while different facts generate different IDs.
    """
    digest = hashlib.sha256(content_key.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def _norm(value) -> str:
    """
    Safely normalize values before hashing.
    Prevents NoneType errors and ensures stable IDs.
    """
    if value is None:
        return "not_documented"

    value = str(value).strip()

    if not value:
        return "not_documented"

    return value.lower()


class ClinicalClaimIdService:
    """
    Generates deterministic, unique, and traceable claim IDs.

    IDs are based on the normalized clinical content rather than random UUIDs,
    ensuring reproducibility across repeated pipeline executions.
    """

    def generate_claim_ids(
        self,
        extraction: NABHDischargeSummaryExtraction
    ) -> NABHDischargeSummaryExtraction:

        # -----------------------------
        # Diagnoses
        # -----------------------------
        for item in extraction.diagnoses:
            if not item.claim_id:

                content_key = (
                    f"DIAG:"
                    f"{_norm(item.diagnosis)}"
                )

                item.claim_id = _deterministic_id(
                    "CLM_DIAG",
                    content_key
                )

        # -----------------------------
        # Symptoms / Observations
        # -----------------------------
        for item in extraction.symptoms:
            if not item.claim_id:

                content_key = (
                    f"OBS:"
                    f"{_norm(item.observation)}"
                )

                item.claim_id = _deterministic_id(
                    "CLM_OBS",
                    content_key
                )

        # -----------------------------
        # Investigations
        # Investigation name alone is
        # insufficient because different
        # notes may report different results.
        # -----------------------------
        for item in extraction.investigations:
            if not item.claim_id:

                content_key = (
                    f"INV:"
                    f"{_norm(item.investigation)}:"
                    f"{_norm(item.result)}"
                )

                item.claim_id = _deterministic_id(
                    "CLM_INV",
                    content_key
                )

        # -----------------------------
        # Medications
        #
        # Name + dosage alone causes
        # collisions when frequency or
        # duration differs.
        # -----------------------------
        for item in extraction.prescribed_medications:
            if not item.claim_id:

                content_key = (
                    f"MED:"
                    f"{_norm(item.name)}:"
                    f"{_norm(item.dosage)}:"
                    f"{_norm(item.frequency)}:"
                    f"{_norm(item.duration)}"
                )

                item.claim_id = _deterministic_id(
                    "CLM_MED",
                    content_key
                )

        # -----------------------------
        # Follow-up Instructions
        #
        # Recommended follow-up alone
        # can collide if dates differ.
        # -----------------------------
        if (
            extraction.follow_up_instructions
            and not extraction.follow_up_instructions.claim_id
        ):

            follow = extraction.follow_up_instructions

            content_key = (
                f"FOL:"
                f"{_norm(follow.recommended_follow_up)}:"
                f"{_norm(follow.next_follow_up_date)}:"
                f"{_norm(follow.lifestyle_dietary_instructions)}"
            )

            follow.claim_id = _deterministic_id(
                "CLM_FOL",
                content_key
            )

        return extraction