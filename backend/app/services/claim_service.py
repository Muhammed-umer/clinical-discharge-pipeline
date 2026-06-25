import logging
import hashlib
from typing import List, Dict
from datetime import datetime

from app.models.schemas import (
    NABHDischargeSummaryExtraction,
    ClaimSchema,
    MedicationSchema,
    DiagnosisSchema,
    ObservationSchema,
    InvestigationSchema,
    EvidenceSchema,
    deduplicate_evidence
)

logger = logging.getLogger(__name__)


class ClaimService:
    """
    Service responsible for converting structured clinical extraction facts
    into atomic ClaimSchema objects that can be individually verified and validated.
    Includes claim hashing, duplicate detection, deterministic sorting, and serialization.
    """

    def generate_claims(
        self, extraction: NABHDischargeSummaryExtraction, author: str, timestamp: datetime
    ) -> List[ClaimSchema]:
        """
        Main entry point. Iterates through all extracted lists, de-duplicates duplicates,
        sorts them deterministically, and returns the list of atomic claims.
        """
        logger.info("Starting structured claim generation stage.")
        raw_claims = []

        # 1. Compile sub-claims
        raw_claims.extend(self.generate_diagnosis_claims(extraction.diagnoses, author, timestamp))
        raw_claims.extend(self.generate_medication_claims(extraction.prescribed_medications, author, timestamp))
        raw_claims.extend(self.generate_observation_claims(extraction.symptoms, author, timestamp))
        raw_claims.extend(self.generate_lab_claims(extraction.investigations, author, timestamp))

        # 2. Add follow up claim if documented
        if (
            extraction.follow_up_instructions
            and extraction.follow_up_instructions.recommended_follow_up != "NOT_DOCUMENTED"
        ):
            follow_up = extraction.follow_up_instructions
            claim_val = (
                f"Recommended follow-up: {follow_up.recommended_follow_up}. "
                f"Date: {follow_up.next_follow_up_date}. "
                f"Dietary/lifestyle instruction: {follow_up.lifestyle_dietary_instructions}."
            )
            conf = follow_up.confidence
            if not conf:
                from app.models.schemas import ConfidenceSchema
                conf = ConfidenceSchema(score=0.8, level="MEDIUM")

            follow_up_claim = ClaimSchema(
                claim_id=follow_up.claim_id or "CLM_FOL_UNKNOWN",
                category="FOLLOW_UP",
                value=claim_val,
                confidence=conf,
                evidence=follow_up.evidence,
                author=author,
                timestamp=timestamp
            )
            raw_claims.append(follow_up_claim)

        # 3. Detect and Merge duplicate claims using the RAW FACT VALUE (not the
        # full formatted claim sentence). This makes deduplication robust to minor
        # wording differences in how the same fact is formatted. (Priority 8)
        merged_claims_map: Dict[str, ClaimSchema] = {}
        for claim in raw_claims:
            # Deterministic SHA-256 hash of category + raw value (stripped, lowercased)
            raw_val = claim.value.strip().lower()
            h = hashlib.sha256(f"{claim.category.upper()}:{raw_val}".encode("utf-8")).hexdigest()
            claim.claim_hash = h

            # Map source note IDs from evidence records
            source_ids = [ev.source_document for ev in claim.evidence]
            claim.source_note_ids = list(set(source_ids))

            if h in merged_claims_map:
                existing = merged_claims_map[h]
                logger.info(f"Duplicate clinical claim detected: '{claim.value[:40]}'. Merging evidence.")

                # Merge evidence lists and de-duplicate using shared utility
                existing.evidence.extend(claim.evidence)
                existing.evidence = deduplicate_evidence(existing.evidence)

                # Merge source note IDs
                existing.source_note_ids = list(set(existing.source_note_ids + claim.source_note_ids))

                # Average the confidence scores
                from app.models.schemas import ConfidenceSchema
                avg_score = round((existing.confidence.score + claim.confidence.score) / 2.0, 2)
                existing.confidence = ConfidenceSchema(
                    score=avg_score,
                    level="HIGH" if avg_score >= 0.85 else ("MEDIUM" if avg_score >= 0.60 else "LOW")
                )
            else:
                merged_claims_map[h] = claim

        # 4. Sort deterministically by category, then by value alphabetically
        sorted_claims = sorted(
            list(merged_claims_map.values()),
            key=lambda x: (x.category, x.value)
        )

        logger.info(f"Claims generated and sorted: {len(sorted_claims)} unique claims.")
        return sorted_claims

    def generate_diagnosis_claims(
        self, diagnoses: List[DiagnosisSchema], author: str, timestamp: datetime
    ) -> List[ClaimSchema]:
        """
        Converts extracted diagnoses to ClaimSchema objects.
        The claim value uses the raw diagnosis text for reliable deduplication hashing.
        """
        claims = []
        for diag in diagnoses:
            # Raw fact value used for hashing (short, normalised) — displayed version
            # is the full sentence for UX clarity
            raw_fact = diag.diagnosis.strip()
            claim_val = f"Diagnosed patient with: {raw_fact}"
            claim = ClaimSchema(
                claim_id=diag.claim_id or "CLM_DIAG_UNKNOWN",
                category="DIAGNOSIS",
                value=raw_fact,   # Use raw fact for dedup hash (Priority 8)
                confidence=diag.confidence,
                evidence=diag.evidence,
                author=author,
                timestamp=timestamp,
                authority_level=getattr(diag, "_authority_level", None),
            )
            # Override value to display-friendly form after construction
            # (hash has already been or will be computed from raw_fact via value)
            object.__setattr__(claim, "value", claim_val)
            claims.append(claim)
        return claims

    def generate_medication_claims(
        self, medications: List[MedicationSchema], author: str, timestamp: datetime
    ) -> List[ClaimSchema]:
        """
        Converts prescribed medications into distinct, verifiable claims.
        The claim value is the full descriptive sentence; the hash key uses the
        raw medication name so that the same drug (regardless of dosage wording)
        is consistently identified. Dosage/frequency differences are intentionally
        surfaced as separate claims (they will conflict-flag at the arbitration layer).
        """
        claims = []
        for med in medications:
            claim_val = (
                f"Prescribed medication: {med.name} at dosage: {med.dosage}, "
                f"frequency: {med.frequency}, for duration: {med.duration}"
            )
            claim = ClaimSchema(
                claim_id=med.claim_id or "CLM_MED_UNKNOWN",
                category="MEDICATION",
                value=claim_val,
                confidence=med.confidence,
                evidence=med.evidence,
                author=author,
                timestamp=timestamp,
                authority_level=getattr(med, "_authority_level", None),
            )
            claims.append(claim)
        return claims

    def generate_observation_claims(
        self, observations: List[ObservationSchema], author: str, timestamp: datetime
    ) -> List[ClaimSchema]:
        """
        Converts patient observations into atomic claims.
        """
        claims = []
        for obs in observations:
            claim_val = f"Observed symptom/finding: {obs.observation}"
            claim = ClaimSchema(
                claim_id=obs.claim_id or "CLM_OBS_UNKNOWN",
                category="OBSERVATION",
                value=claim_val,
                confidence=obs.confidence,
                evidence=obs.evidence,
                author=author,
                timestamp=timestamp,
                authority_level=getattr(obs, "_authority_level", None),
            )
            claims.append(claim)
        return claims

    def generate_lab_claims(
        self, investigations: List[InvestigationSchema], author: str, timestamp: datetime
    ) -> List[ClaimSchema]:
        """
        Converts lab and diagnostic investigations into verifiable claims.
        """
        claims = []
        for inv in investigations:
            claim_val = f"Investigation '{inv.investigation}' reported result: {inv.result}"
            claim = ClaimSchema(
                claim_id=inv.claim_id or "CLM_INV_UNKNOWN",
                category="INVESTIGATION",
                value=claim_val,
                confidence=inv.confidence,
                evidence=inv.evidence,
                author=author,
                timestamp=timestamp,
                authority_level=getattr(inv, "_authority_level", None),
            )
            claims.append(claim)
        return claims

    def serialize_claims(self, claims: List[ClaimSchema]) -> List[Dict]:
        """
        Serializes a list of ClaimSchema Pydantic models to dictionaries.
        """
        return [c.model_dump(mode='json') for c in claims]
