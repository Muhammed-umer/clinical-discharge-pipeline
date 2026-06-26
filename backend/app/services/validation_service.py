"""
ClinicalValidationLayer — Gemini-powered grounding validation.

Refactoring changes vs original:
  - Removed module-level genai.configure() side effect (now called once in startup_event)
  - Removed module-level GEMINI_API_KEY check (now in config.py)
  - Removed duplicate logging.basicConfig() call
  - Removed dead _run_gemini_judge mock fallback code (hardcoded patient names)
  - Removed traceback.print_exc() and print(type(e)) debug statements
  - Added missing `from typing import Any` import
  - ClaimService injected via constructor (no longer instantiated internally)
  - All constants sourced from config.py
  - verify_summary_grounding signature changed: db: AsyncSession → raw_notes: List
    This eliminates N per-claim pgvector round-trip queries entirely.
  - Embeddings now generated in a single batch API call (_batch_embed_claims)
  - Cosine similarity computed in-memory via NoteRepository.compute_similarity_scores
  - All behavior (grounding scores, warnings, citation checks) is identical
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import google.generativeai as genai

from app.core.config import (
    EMBEDDING_DIMENSIONS,
    GEMINI_EMBEDDING_MODEL,
    GEMINI_JUDGE_MODEL,
    GROUNDING_WARN_THRESHOLD,
)
from app.core.exceptions import ValidationServiceUnavailable
from app.core.prompts import BATCH_JUDGE_PROMPT, JUDGE_PROMPT
from app.db.repositories.note_repository import NoteRepository
from app.models.models import RawDocumentNode
from app.models.schemas import (
    ClinicalWarningSchema,
    ConfidenceSchema,
    FinalDischargeSummary,
    GroundingMetricsSchema,
    ValidationReportSchema,
)
from app.services.claim_service import ClaimService

logger = logging.getLogger(__name__)

# Re-exported for backwards compat with any existing imports
_note_repo = NoteRepository()


class ClinicalValidationLayer:
    """
    The Clinical Safety Layer of the pipeline.

    Responsibilities:
      - Convert merged summary into atomic claims
      - Generate claim embeddings in a single batch API call
      - Compute cosine similarity in-memory (no N DB queries)
      - Verify all claims against source notes using batch Gemini Judge (1 LLM call)
      - Compute grounding metrics and propagate confidence back to the summary
    """

    def __init__(self, claim_service: Optional[ClaimService] = None) -> None:
        self.embedding_model = GEMINI_EMBEDDING_MODEL
        self.judge_model_name = GEMINI_JUDGE_MODEL
        # Accept injected dependency or fall back to a default instance
        self.claim_service = claim_service or ClaimService()

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def get_embedding(self, text_content: str) -> List[float]:
        """
        Generates a 768-dimensional text embedding vector using gemini-embedding-001.
        Used for single-text embedding (e.g., document upload).
        Returns a zero vector on failure so the pipeline can continue safely.
        """
        if not text_content.strip():
            return [0.0] * EMBEDDING_DIMENSIONS
        try:
            result = genai.embed_content(
                model=self.embedding_model,
                content=text_content,
                task_type="retrieval_document",
                output_dimensionality=EMBEDDING_DIMENSIONS,
            )
            return result["embedding"]
        except Exception as exc:
            logger.error("Failed to generate text embedding: %s", str(exc))
            return [0.0] * EMBEDDING_DIMENSIONS

    async def verify_summary_grounding(
        self,
        stay_id: str,
        merged_summary: FinalDischargeSummary,
        raw_notes: List[RawDocumentNode],
    ) -> FinalDischargeSummary:
        """
        Performs citation verification and batch Gemini Judge grounding checks.
        Computes grounding scores, generates warnings, and updates validation metrics.

        Performance improvements vs original:
          - Embeddings generated in ONE batch API call (was N sequential calls)
          - Cosine similarity computed in Python from pre-fetched notes (was N DB queries)
          - Notes are passed in — no DB access from within this service

        Args:
            stay_id:        Patient stay identifier (for logging).
            merged_summary: The merged FinalDischargeSummary to validate.
            raw_notes:      Pre-fetched RawDocumentNode list (with embeddings).
        """
        logger.info("Clinical Safety Layer validation started for stay: %s", stay_id)

        # 1. Convert merged summary into atomic claims
        claims = self.claim_service.generate_claims(
            extraction=merged_summary.summary,
            author="RECONCILED_PIPELINE",
            timestamp=datetime.utcnow(),
        )

        total_claims = len(claims)

        if not total_claims:
            logger.info("[Grounding] No claims to validate.")
            merged_summary.validation = self._empty_validation_report(merged_summary)
            return merged_summary

        # 2. Pre-compute citation metadata per claim (synchronous, O(n) in Python)
        claims_evidence_coverage: Dict[str, bool] = {}
        claims_citation_completeness: Dict[str, bool] = {}
        for claim in claims:
            has_evidence = len(claim.evidence) > 0 and any(
                bool(e.extracted_text.strip()) for e in claim.evidence
            )
            claims_evidence_coverage[claim.claim_id] = has_evidence

            has_complete = all(
                ev.source_document and ev.author_role and ev.extracted_text
                for ev in claim.evidence
            ) and len(claim.evidence) > 0
            claims_citation_completeness[claim.claim_id] = has_complete

        # 3. Batch embed all claim texts in a single API call
        claim_embeddings = await self._batch_embed_claims(claims)

        # 4. Compute cosine similarity in-memory against pre-fetched notes
        # Eliminates N pgvector round-trip queries
        similarity_scores = _note_repo.compute_similarity_scores(
            claims, claim_embeddings, raw_notes
        )

        # 5. Build evidence text for the judge (deduplicated note content)
        combined_evidence = self._build_evidence_text(raw_notes)

        # 6. Invoke batch Gemini Judge (1 LLM call for ALL claims)
        claims_payload = [
            {"claim_id": c.claim_id, "category": c.category, "value": c.value}
            for c in claims
        ]
        claims_text = json.dumps(claims_payload, indent=2)
        verdicts_map = await self._run_gemini_judge_batch(
            claims_text=claims_text, evidence_text=combined_evidence
        )

        # 7. Score each claim
        conflict_fields = {
            c.field.lower() for c in merged_summary.validation.conflicts
        }

        unsupported_claims_list: List[str] = []
        validation_notes: List[str] = list(merged_summary.validation.notes or [])
        warnings_list: List[ClinicalWarningSchema] = []
        verified_scores: List[float] = []
        claims_with_evidence = 0
        complete_citations = 0
        accumulated_grounding_score = 0.0

        for claim in claims:
            verdict_data = verdicts_map.get(claim.claim_id)
            verdict = verdict_data.get("supported", "NOT_SUPPORTED") if verdict_data else "NOT_SUPPORTED"
            reasoning = (
                verdict_data.get("explanation", "No explanation provided.")
                if verdict_data
                else "Verdict missing from batch validation response."
            )

            has_evidence = claims_evidence_coverage.get(claim.claim_id, False)
            if has_evidence:
                claims_with_evidence += 1

            has_complete = claims_citation_completeness.get(claim.claim_id, False)
            if has_complete:
                complete_citations += 1

            max_similarity = similarity_scores.get(claim.claim_id, 0.80)

            # Mathematical grounding score
            verdict_score = (
                1.0 if verdict == "SUPPORTED"
                else (0.5 if verdict == "PARTIALLY_SUPPORTED" else 0.0)
            )
            unique_roles = len({ev.author_role for ev in claim.evidence})
            is_conflicted = any(
                claim.category.lower() in f
                or (claim.value.lower() in f)
                for f in conflict_fields
            )
            grounding_score = self._calculate_grounding_score(
                verdict_score=verdict_score,
                similarity_score=max_similarity,
                evidence_count=len(claim.evidence),
                unique_roles=unique_roles,
                is_conflicted=is_conflicted,
            )

            # Force 0.0 if citation verification completely fails
            if not has_evidence:
                grounding_score = 0.0
                verdict = "NOT_SUPPORTED"
                reasoning = (
                    "Explicit citation verification failed: "
                    "Claim lacks supporting evidence references."
                )

            accumulated_grounding_score += grounding_score

            # Categorize claim
            if verdict == "SUPPORTED" and grounding_score >= GROUNDING_WARN_THRESHOLD:
                validation_notes.append(
                    f"Claim {claim.claim_id} validated as SUPPORTED. "
                    f"Score: {grounding_score}. Reasoning: {reasoning}"
                )
            elif verdict == "PARTIALLY_SUPPORTED" or grounding_score >= 0.40:
                unsupported_claims_list.append(
                    f"[{claim.category}] {claim.value} "
                    f"(PARTIALLY SUPPORTED - Score: {grounding_score}. {reasoning})"
                )
                validation_notes.append(
                    f"Claim {claim.claim_id} validated as PARTIALLY_SUPPORTED. "
                    f"Score: {grounding_score}. Reasoning: {reasoning}"
                )
            else:
                unsupported_claims_list.append(
                    f"[{claim.category}] {claim.value} "
                    f"(UNSUPPORTED - Score: {grounding_score}. {reasoning})"
                )
                validation_notes.append(
                    f"Claim {claim.claim_id} validated as NOT_SUPPORTED. "
                    f"Score: {grounding_score}. Reasoning: {reasoning}"
                )

            # Emit physician warning for sub-threshold claims
            if grounding_score < GROUNDING_WARN_THRESHOLD:
                warnings_list.append(
                    ClinicalWarningSchema(
                        field=claim.category,
                        severity="HIGH" if grounding_score < 0.40 else "MEDIUM",
                        message=(
                            f"Claim '{claim.value[:40]}...' has sub-optimal grounding score "
                            f"({grounding_score}). Reason: {reasoning}"
                        ),
                    )
                )

            # Update claim confidence in summary
            final_score = grounding_score
            claim.confidence = ConfidenceSchema(
                score=final_score,
                level="HIGH" if final_score >= 0.85 else ("MEDIUM" if final_score >= 0.60 else "LOW"),
            )
            verified_scores.append(final_score)
            self._update_original_fact_confidence(merged_summary.summary, claim.claim_id, final_score)

        # 8. Compute overall metrics
        supported_count = total_claims - len(unsupported_claims_list)
        overall_grounding = round(supported_count / total_claims, 2) if total_claims > 0 else 1.0
        evidence_coverage = round(claims_with_evidence / total_claims, 2) if total_claims > 0 else 1.0
        citation_completeness = round(complete_citations / total_claims, 2) if total_claims > 0 else 1.0
        overall_confidence = round(sum(verified_scores) / len(verified_scores), 2) if verified_scores else 0.0

        overall_grounded = (
            len(unsupported_claims_list) == 0
            and len(merged_summary.validation.conflicts) == 0
            and overall_grounding >= GROUNDING_WARN_THRESHOLD
        )

        citation_summary = (
            f"Total claims evaluated: {total_claims}. "
            f"Grounded claims: {supported_count}. "
            f"Unsupported/Hallucinated: {len(unsupported_claims_list)}."
        )

        # Track prompt versions inside the validation report notes (as requested in req 9)
        from app.core.config import EXTRACTION_PROMPT_VERSION, JUDGE_PROMPT_VERSION
        validation_notes.append(
            f"Prompt Versions: extraction={EXTRACTION_PROMPT_VERSION}, judge={JUDGE_PROMPT_VERSION}"
        )

        merged_summary.validation = ValidationReportSchema(
            grounded=overall_grounded,
            confidence=overall_confidence,
            unsupported_claims=unsupported_claims_list,
            conflicts=merged_summary.validation.conflicts,
            notes=validation_notes,
            grounding_metrics=GroundingMetricsSchema(
                grounding_score=overall_grounding,
                evidence_coverage=evidence_coverage,
                citation_completeness=citation_completeness,
            ),
            warnings=warnings_list,
            citation_summary=citation_summary,
            historical_medications=merged_summary.validation.historical_medications,
            merged_duplicates=merged_summary.validation.merged_duplicates,
            clinical_audit=merged_summary.validation.clinical_audit,
        )

        logger.info(
            "Clinical Safety Layer completed for stay %s. Grounding score: %.2f",
            stay_id,
            overall_grounding,
        )
        return merged_summary

    # ─────────────────────────────────────────────────────────────────────────
    # Batch embedding (1 API call for all claims)
    # ─────────────────────────────────────────────────────────────────────────

    async def _batch_embed_claims(self, claims: list) -> Dict[str, List[float]]:
        """
        Generates embeddings for ALL claim texts in a single Gemini API call.

        Replaces N sequential get_embedding() calls with one batched call,
        significantly reducing latency and API quota usage.

        Falls back to sequential embedding if the batch call fails.
        """
        if not claims:
            return {}

        texts = [c.value for c in claims]
        loop = asyncio.get_running_loop()

        try:
            result = await loop.run_in_executor(
                None,
                lambda: genai.embed_content(
                    model=self.embedding_model,
                    content=texts,
                    task_type="retrieval_query",
                    output_dimensionality=EMBEDDING_DIMENSIONS,
                ),
            )
            embeddings = result["embedding"]

            # embed_content returns List[List[float]] for list input
            if embeddings and isinstance(embeddings[0], list):
                return {claims[i].claim_id: embeddings[i] for i in range(len(claims))}

            # Single embedding returned (shouldn't happen for list input)
            if len(claims) == 1:
                return {claims[0].claim_id: embeddings}

            logger.warning(
                "[Grounding] Unexpected batch embedding shape — falling back to sequential."
            )

        except Exception as exc:
            logger.warning(
                "[Grounding] Batch embedding failed (%s) — falling back to sequential.", exc
            )

        # Sequential fallback
        result: Dict[str, List[float]] = {}
        for claim in claims:
            result[claim.claim_id] = self.get_embedding(claim.value)
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # Batch Gemini Judge (1 LLM call for all claims)
    # ─────────────────────────────────────────────────────────────────────────

    async def _run_gemini_judge_batch(
        self, claims_text: str, evidence_text: str
    ) -> Dict[str, Dict[str, Any]]:
        """
        Calls Gemini Judge in a single batch call to verify grounding for all claims.
        Returns a dict mapping claim_id → {"supported": str, "confidence": float, "explanation": str}.
        Raises ValidationServiceUnavailable on failure (safe-fail behavior preserved).
        """
        logger.info("[Grounding] Starting batch validation")
        prompt = BATCH_JUDGE_PROMPT.format(
            claims_text=claims_text, evidence_text=evidence_text
        )
        try:
            model = genai.GenerativeModel(self.judge_model_name)
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: model.generate_content(
                    prompt,
                    generation_config={
                        "response_mime_type": "application/json",
                        "temperature": 0.0,
                    },
                ),
            )

            if not response or not response.text:
                raise ValueError("Gemini Judge returned empty text response.")

            clean_text = response.text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            clean_text = clean_text.strip()

            parsed_list = json.loads(clean_text)
            if not isinstance(parsed_list, list):
                raise ValueError("Batch validation response is not a JSON list.")

            verdicts_map: Dict[str, Dict[str, Any]] = {}
            for item in parsed_list:
                if isinstance(item, dict) and "claim_id" in item:
                    verdict_str = (
                        item.get("supported") or item.get("verdict") or "NOT_SUPPORTED"
                    )
                    verdicts_map[str(item["claim_id"])] = {
                        "supported": verdict_str.upper(),
                        "confidence": float(item.get("confidence") or 0.0),
                        "explanation": (
                            item.get("explanation") or item.get("reasoning") or "No explanation provided."
                        ),
                    }
            return verdicts_map

        except Exception as exc:
            logger.error("[Grounding] Gemini Judge batch call failed: %s", str(exc))
            raise ValidationServiceUnavailable(
                f"Grounding verification service unavailable: {exc}"
            ) from exc

    # ─────────────────────────────────────────────────────────────────────────
    # Scoring helpers
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _calculate_grounding_score(
        verdict_score: float,
        similarity_score: float,
        evidence_count: int,
        unique_roles: int,
        is_conflicted: bool,
    ) -> float:
        """
        Deterministic grounding score formula.
        Verdict is weighted most heavily; evidence diversity and similarity
        provide small increments. Conflicts apply a penalty.
        """
        if verdict_score == 0.0:
            return 0.0
        base = 0.85
        evidence_factor = min(evidence_count, 2) * 0.04
        diversity_factor = min(unique_roles, 2) * 0.04
        similarity_factor = (similarity_score - 0.5) * 0.1 if similarity_score > 0.5 else 0.0
        penalty = 0.10 if is_conflicted else 0.0
        score = base + evidence_factor + diversity_factor + similarity_factor - penalty
        return max(0.0, min(1.0, round(score, 2)))

    @staticmethod
    def _update_original_fact_confidence(
        extraction: Any, claim_id: str, final_score: float
    ) -> None:
        """
        Locates the original extracted fact by its claim_id within the nested
        extraction structure and updates its confidence score in-place.
        """
        level = "HIGH" if final_score >= 0.85 else ("MEDIUM" if final_score >= 0.60 else "LOW")
        new_conf = ConfidenceSchema(score=final_score, level=level)

        for collection in (
            extraction.diagnoses,
            extraction.symptoms,
            extraction.investigations,
            extraction.prescribed_medications,
        ):
            for item in collection:
                if item.claim_id == claim_id:
                    item.confidence = new_conf
                    return

        if (
            extraction.follow_up_instructions
            and extraction.follow_up_instructions.claim_id == claim_id
        ):
            extraction.follow_up_instructions.confidence = new_conf

    # ─────────────────────────────────────────────────────────────────────────
    # Utility
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_evidence_text(raw_notes: List[RawDocumentNode]) -> str:
        """
        Builds the combined evidence string from raw notes for the judge prompt.
        Deduplicates notes by (author_role, content) to avoid repeated context.
        """
        seen: set = set()
        evidence_texts: List[str] = []
        for note in raw_notes:
            key = (note.author_role, note.content.strip())
            if key not in seen:
                seen.add(key)
                evidence_texts.append(
                    f"[{note.author_role} Note recorded at {note.recorded_at}]:\n{note.content}"
                )
        return "\n\n".join(evidence_texts)

    @staticmethod
    def _empty_validation_report(
        merged_summary: FinalDischargeSummary,
    ) -> ValidationReportSchema:
        """Returns a perfect validation report when no claims are generated."""
        return ValidationReportSchema(
            grounded=True,
            confidence=1.0,
            unsupported_claims=[],
            conflicts=merged_summary.validation.conflicts,
            notes=["No claims generated for validation."],
            grounding_metrics=GroundingMetricsSchema(
                grounding_score=1.0,
                evidence_coverage=1.0,
                citation_completeness=1.0,
            ),
            warnings=[],
            citation_summary="No claims to evaluate.",
        )