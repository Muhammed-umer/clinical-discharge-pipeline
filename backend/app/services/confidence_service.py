import logging
from app.models.schemas import NABHDischargeSummaryExtraction, AuthorRole

logger = logging.getLogger(__name__)

# Role-to-authority-level mapping (separate from LLM extraction confidence)
# ATTENDING is the highest clinical authority; WARD_NURSE the lowest.
_ROLE_AUTHORITY_MAP = {
    AuthorRole.ATTENDING:   "HIGH",
    AuthorRole.CONSULTANT:  "MEDIUM",
    AuthorRole.RESIDENT:    "MEDIUM",
    AuthorRole.WARD_NURSE:  "LOW",
    AuthorRole.UNKNOWN_CLINICIAN: "LOW",
}


class ClinicalConfidenceService:
    """
    Handles assigning clinician authority levels to extracted clinical facts.

    IMPORTANT DESIGN PRINCIPLE:
    ─────────────────────────────────────────────────────────────────
    This service DOES NOT modify the LLM extraction confidence score.
    That score is set by Gemini during extraction and represents how
    clearly the fact was stated in the raw note.

    `authority_level` is a SEPARATE field that represents the clinical
    credibility of the asserting clinician (ATTENDING > CONSULTANT >
    RESIDENT > WARD_NURSE). These are two independent signals.
    ─────────────────────────────────────────────────────────────────
    """

    def assign_authority(
        self, extraction: NABHDischargeSummaryExtraction, author_role: str
    ) -> NABHDischargeSummaryExtraction:
        """
        Sets the `authority_level` on every extracted item (diagnoses, medications,
        investigations, symptoms, follow-up instructions) based on the author_role
        of the clinical note that produced this extraction.

        The LLM confidence scores are intentionally left unchanged.
        """
        # Normalise and resolve to enum (fall back to LOW for unknown roles)
        try:
            role_enum = AuthorRole(author_role.upper())
        except ValueError:
            logger.warning(
                f"Unrecognised author_role '{author_role}' – defaulting authority to LOW."
            )
            role_enum = AuthorRole.WARD_NURSE

        authority = _ROLE_AUTHORITY_MAP.get(role_enum, "LOW")
        logger.info(
            f"Assigning authority_level='{authority}' for role '{role_enum.value}' "
            f"across {len(extraction.diagnoses)} diagnoses, "
            f"{len(extraction.prescribed_medications)} medications, "
            f"{len(extraction.investigations)} investigations, "
            f"{len(extraction.symptoms)} symptoms."
        )

        # Apply authority_level to each extractable list item.
        # These items don't have an authority_level field themselves –
        # authority propagates via ClaimSchema when claims are generated.
        # We annotate the extraction-level objects as a metadata marker here.
        for item in extraction.diagnoses:
            _annotate_authority(item, authority)

        for item in extraction.symptoms:
            _annotate_authority(item, authority)

        for item in extraction.investigations:
            _annotate_authority(item, authority)

        for item in extraction.prescribed_medications:
            _annotate_authority(item, authority)

        if extraction.follow_up_instructions:
            _annotate_authority(extraction.follow_up_instructions, authority)

        return extraction


def _annotate_authority(item: object, authority: str) -> None:
    """
    Dynamically sets an `_authority_level` marker attribute on an extraction item.
    This is a lightweight annotation used during claim generation so ClaimService
    can propagate the correct authority_level to each ClaimSchema.
    """
    # Uses object.__setattr__ to avoid Pydantic model_fields restrictions
    # on arbitrary attribute assignment while keeping the schema clean.
    try:
        object.__setattr__(item, "_authority_level", authority)
    except Exception:
        # Fallback: if the item is frozen, skip silently – claim generation
        # will default to LOW authority rather than crash.
        pass
