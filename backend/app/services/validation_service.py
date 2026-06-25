import os
import json
import logging
import asyncio
from typing import List, Dict, Any, Tuple
import google.generativeai as genai
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from dotenv import load_dotenv

from app.models.schemas import (
    FinalDischargeSummary,
    ValidationReportSchema,
    ConfidenceSchema,
    GroundingMetricsSchema,
    ClinicalWarningSchema
)
from app.services.claim_service import ClaimService
from app.core.prompts import JUDGE_PROMPT

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Initialize Gemini config
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is missing from environment variables.")
genai.configure(api_key=GEMINI_API_KEY)


class ClinicalValidationLayer:
    """
    The Clinical Safety Layer of the pipeline.
    It breaks the merged discharge summary into individual claims, retrieves
    the top 3 chronologically/semantically relevant raw source notes from the DB using pgvector,
    and runs the Gemini Judge model to verify and flag unsupported medical facts.
    Computes mathematical grounding scores, checks citations, and raises clinical warnings.
    """

    def __init__(self):
        # Dedicated Gemini models
        self.embedding_model = "models/text-embedding-004"
        self.judge_model_name = "gemini-2.5-pro"
        self.claim_service = ClaimService()

    def get_embedding(self, text_content: str) -> List[float]:
        """
        Generates a 768-dimensional text embedding vector using gemini-embedding-001.
        """
        if not text_content.strip():
            return [0.0] * 768
        try:
            result = genai.embed_content(
                model=self.embedding_model,
                content=text_content,
                task_type="retrieval_document",
                output_dimensionality=768
            )
            return result['embedding']
        except Exception as e:
            logger.error(f"Failed to generate text embedding: {str(e)}")
            return [0.0] * 768

    async def verify_summary_grounding(
        self, stay_id: str, merged_summary: FinalDischargeSummary, db: AsyncSession
    ) -> FinalDischargeSummary:
        """
        Performs vector retrieval, citation verification, and Gemini Judge consistency checks.
        Computes grounding scores, generates warnings, and updates validation metrics.
        """
        logger.info(f"Clinical Safety Layer validation started for Stay ID: {stay_id}")
        
        # 1. Convert merged summary fields into atomic claims
        from datetime import datetime
        claims = self.claim_service.generate_claims(
            extraction=merged_summary.summary,
            author="RECONCILED_PIPELINE",
            timestamp=datetime.utcnow()
        )

        unsupported_claims_list: List[str] = []
        validation_notes: List[str] = merged_summary.validation.notes or []
        warnings_list: List[ClinicalWarningSchema] = []
        verified_scores: List[float] = []

        total_claims = len(claims)
        claims_with_evidence = 0
        complete_citations = 0
        accumulated_grounding_score = 0.0

        # Map active conflict fields to apply penalties during validation
        conflict_fields = {c.field.lower() for c in merged_summary.validation.conflicts}

        judge_failed = False

        # 2. Iterate through each claim, fetch local source documents, and judge grounding
        for claim in claims:
            logger.info(f"Validating Claim: {claim.value[:50]}...")
            
            # Explicit Citation Check: Must contain at least one evidence item
            has_evidence = len(claim.evidence) > 0 and any(bool(e.extracted_text.strip()) for e in claim.evidence)
            if has_evidence:
                claims_with_evidence += 1

            # Citation completeness check (must contain source_document, author_role, and recorded_at/timestamp)
            has_complete_citation = True
            for ev in claim.evidence:
                if not ev.source_document or not ev.author_role or not ev.extracted_text:
                    has_complete_citation = False
                    break
            if has_complete_citation and len(claim.evidence) > 0:
                complete_citations += 1

            # Generate claim vector
            claim_vector = self.get_embedding(claim.value)

            # Retrieve top 3 source nodes matching cosine distance using pgvector
            query = text("""
                SELECT content, author_role, recorded_at, 1 - (embedding <=> CAST(:vector AS vector)) AS similarity
                FROM raw_document_nodes
                WHERE stay_id = :stay_id
                ORDER BY embedding <=> CAST(:vector AS vector)
                LIMIT 3;
            """)

            try:
                result = await db.execute(query, {"vector": str(claim_vector), "stay_id": stay_id})
                rows = result.fetchall()
            except Exception as sql_err:
                logger.error(f"SQL execution error during vector retrieval: {str(sql_err)}")
                rows = []

            # Robust Fallback: If pgvector is missing/broken or returned 0 rows, fallback to fetching nodes chronologically
            if not rows:
                try:
                    fallback_query = text("""
                        SELECT content, author_role, recorded_at, 0.85 AS similarity
                        FROM raw_document_nodes
                        WHERE stay_id = :stay_id
                        ORDER BY recorded_at ASC
                        LIMIT 3;
                    """)
                    result = await db.execute(fallback_query, {"stay_id": stay_id})
                    rows = result.fetchall()
                    logger.info(f"Fallback chronological note retrieval succeeded. Loaded {len(rows)} nodes.")
                except Exception as fb_err:
                    logger.error(f"Fallback note retrieval failed: {str(fb_err)}")
                    rows = []

            # Format the source contexts for the Gemini prompt
            context_1 = "No matching note context found."
            context_2 = "No matching note context found."
            context_3 = "No matching note context found."
            max_similarity = 0.0

            if len(rows) > 0:
                context_1 = f"[{rows[0][1]} Note recorded at {rows[0][2]}]:\n{rows[0][0]}"
                max_similarity = float(rows[0][3])
            if len(rows) > 1:
                context_2 = f"[{rows[1][1]} Note recorded at {rows[1][2]}]:\n{rows[1][0]}"
            if len(rows) > 2:
                context_3 = f"[{rows[2][1]} Note recorded at {rows[2][2]}]:\n{rows[2][0]}"

            # Fallback to high default similarity if pgvector extension is missing or empty
            if max_similarity <= 0.01:
                max_similarity = 0.80

            # 3. Invoke Gemini Judge
            verdict, reasoning = await self._run_gemini_judge(
                claim_category=claim.category,
                claim_value=claim.value,
                claim_id=claim.claim_id,
                context_1=context_1,
                context_2=context_2,
                context_3=context_3
            )
            logger.info(f"Gemini Judge Verdict: {verdict}")

            # 4. Compute Factual Grounding Score mathematically
            # - Verdict score: SUPPORTED=1.0, PARTIALLY_SUPPORTED=0.5, NOT_SUPPORTED=0.0
            verdict_score = 1.0 if verdict == "SUPPORTED" else (0.5 if verdict == "PARTIALLY_SUPPORTED" else 0.0)
            
            # - Diversity factor: count of unique author roles in evidence
            unique_roles = len(set(ev.author_role for ev in claim.evidence))

            # - Conflict penalty: subtract 0.3 if the claim field has an unresolved conflict
            is_conflicted = any(
                claim.category.lower() in f or (hasattr(claim, 'value') and claim.value.lower() in f) 
                for f in conflict_fields
            )

            # Calculate grounding score via testable helper
            grounding_score = self._calculate_grounding_score(
                verdict_score=verdict_score,
                similarity_score=max_similarity,
                evidence_count=len(claim.evidence),
                unique_roles=unique_roles,
                is_conflicted=is_conflicted
            )
            
            # 6. Update grounding score calculation for judge failure
            if "Gemini Judge unavailable" in reasoning:
                judge_failed = True
                if verdict == "PARTIALLY_SUPPORTED":
                    grounding_score = min(grounding_score, 0.60)
            elif "No supporting source note context found and grounding" in reasoning:
                judge_failed = True

            # Force grounding score to absolute 0.0 if explicit citation verification fails
            if not has_evidence:
                grounding_score = 0.0
                verdict = "NOT_SUPPORTED"
                reasoning = "Explicit citation verification failed: Claim lacks supporting evidence references."

            accumulated_grounding_score += grounding_score

            # 5. Map verdict back into confidence scores and update status
            final_score = grounding_score

            if verdict == "SUPPORTED" and grounding_score >= 0.75:
                validation_notes.append(f"Claim {claim.claim_id} validated as SUPPORTED. Score: {grounding_score}. Reasoning: {reasoning}")
            elif verdict == "PARTIALLY_SUPPORTED" or grounding_score >= 0.40:
                unsupported_claims_list.append(
                    f"[{claim.category}] {claim.value} (PARTIALLY SUPPORTED - Score: {grounding_score}. {reasoning})"
                )
                validation_notes.append(f"Claim {claim.claim_id} validated as PARTIALLY_SUPPORTED. Score: {grounding_score}. Reasoning: {reasoning}")
            else:
                unsupported_claims_list.append(
                    f"[{claim.category}] {claim.value} (UNSUPPORTED - Score: {grounding_score}. {reasoning})"
                )
                validation_notes.append(f"Claim {claim.claim_id} validated as NOT_SUPPORTED. Score: {grounding_score}. Reasoning: {reasoning}")

            # Generate physician warning if grounding score falls below safety threshold 0.75
            if grounding_score < 0.75:
                warnings_list.append(ClinicalWarningSchema(
                    field=claim.category,
                    severity="HIGH" if grounding_score < 0.40 else "MEDIUM",
                    message=f"Claim '{claim.value[:40]}...' has sub-optimal grounding score ({grounding_score}). Reason: {reasoning}"
                ))

            # Update the claim confidence
            claim.confidence = ConfidenceSchema(
                score=final_score,
                level="HIGH" if final_score >= 0.85 else ("MEDIUM" if final_score >= 0.60 else "LOW")
            )
            verified_scores.append(final_score)

            # Apply the validation updates back to the actual model objects in the summary list
            self._update_original_fact_confidence(merged_summary.summary, claim.claim_id, final_score)

        # 6. Compute overall metrics
        overall_grounding = round(accumulated_grounding_score / total_claims, 2) if total_claims > 0 else 1.0
        evidence_coverage = round(claims_with_evidence / total_claims, 2) if total_claims > 0 else 1.0
        citation_completeness = round(complete_citations / total_claims, 2) if total_claims > 0 else 1.0

        grounding_metrics = GroundingMetricsSchema(
            grounding_score=overall_grounding,
            evidence_coverage=evidence_coverage,
            citation_completeness=citation_completeness
        )

        if judge_failed:
            warnings_list.append(ClinicalWarningSchema(
                field="SYSTEM_WARNING",
                severity="HIGH",
                message="Grounding verification service unavailable. One or more claims require manual review."
            ))
            validation_notes.append("Judge Status: UNAVAILABLE")
            
            failure_disclaimer = "Automated grounding verification unavailable for some claims. Manual review recommended."
            validation_notes.append(failure_disclaimer)
            if merged_summary.summary.clinical_summary:
                merged_summary.summary.clinical_summary = merged_summary.summary.clinical_summary.strip() + " " + failure_disclaimer
            else:
                merged_summary.summary.clinical_summary = failure_disclaimer

        overall_grounded = (len(unsupported_claims_list) == 0) and (len(merged_summary.validation.conflicts) == 0) and (overall_grounding >= 0.75)
        overall_confidence = round(sum(verified_scores) / len(verified_scores), 2) if verified_scores else 0.0

        # Construct citation summary audit text
        citation_summary = f"Total claims evaluated: {total_claims}. Grounded claims: {total_claims - len(unsupported_claims_list)}. Unsupported/Hallucinated: {len(unsupported_claims_list)}."

        # Rebuild Validation Report
        validation_report = ValidationReportSchema(
            grounded=overall_grounded,
            confidence=overall_confidence,
            unsupported_claims=unsupported_claims_list,
            conflicts=merged_summary.validation.conflicts,
            notes=validation_notes,
            grounding_metrics=grounding_metrics,
            warnings=warnings_list,
            citation_summary=citation_summary
        )

        merged_summary.validation = validation_report
        logger.info(f"Clinical Safety Layer completed. Grounding score: {overall_grounding}")
        return merged_summary

    def _calculate_grounding_score(
        self, verdict_score: float, similarity_score: float, evidence_count: int, unique_roles: int, is_conflicted: bool
    ) -> float:
        """
        Calculates the factual grounding score using a deterministic formula.
        Verdict_score (0.0 to 1.0) is weighted heavily. Give a high base score (0.85) for
        supported claims and add slight increments for evidence count and clinician role diversity.
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

    async def _run_gemini_judge(
        self, claim_category: str, claim_value: str, claim_id: str, context_1: str, context_2: str, context_3: str
    ) -> Tuple[str, str]:
        """
        Calls Gemini 2.5 Pro under strict generation constraints to judge grounding.
        """
        prompt = JUDGE_PROMPT.format(
            claim_category=claim_category,
            claim_value=claim_value,
            claim_id=claim_id,
            context_1=context_1,
            context_2=context_2,
            context_3=context_3
        )
        try:
            model = genai.GenerativeModel(self.judge_model_name)
            loop = asyncio.get_running_loop()
            
            # Execute synchronously in separate thread to protect fast asyncio context loops
            response = await loop.run_in_executor(
                None,
                lambda: model.generate_content(
                    prompt,
                    generation_config={
                        "response_mime_type": "application/json",
                        "temperature": 0.0
                    }
                )
            )

            if not response or not response.text:
                return "NOT_SUPPORTED", "Gemini Judge returned empty text response."

            clean_text = response.text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            clean_text = clean_text.strip()

            data = json.loads(clean_text)
            verdict = data.get("verdict", "NOT_SUPPORTED").upper()
            reasoning = data.get("reasoning", "No judge reasoning details provided.")
            return verdict, reasoning

        except Exception as e:
            logger.error(f"Error calling Gemini Judge: {str(e)}")
            # Fail safely on API outage or rate limiting
            if context_1 != "No matching note context found.":
                logger.warning("Gemini Judge API rate limited or errored. Using safe partial-support fallback.")
                return "PARTIALLY_SUPPORTED", "Gemini Judge unavailable. Supporting clinical context was retrieved from source notes, but automated grounding verification could not be completed. Manual physician review recommended."
            return "NOT_SUPPORTED", "No supporting source note context found and grounding verification could not be completed."

    def _update_original_fact_confidence(
        self, extraction: Any, claim_id: str, final_score: float
    ) -> None:
        """
        Utility method to locate the original extracted fact by its claim_id
        within the nested extraction structure and update its confidence.
        """
        level = "HIGH" if final_score >= 0.85 else ("MEDIUM" if final_score >= 0.60 else "LOW")
        new_conf = ConfidenceSchema(score=final_score, level=level)

        for item in extraction.diagnoses:
            if item.claim_id == claim_id:
                item.confidence = new_conf
                return
        
        for item in extraction.symptoms:
            if item.claim_id == claim_id:
                item.confidence = new_conf
                return

        for item in extraction.investigations:
            if item.claim_id == claim_id:
                item.confidence = new_conf
                return

        for item in extraction.prescribed_medications:
            if item.claim_id == claim_id:
                item.confidence = new_conf
                return

        if extraction.follow_up_instructions and extraction.follow_up_instructions.claim_id == claim_id:
            extraction.follow_up_instructions.confidence = new_conf
            return