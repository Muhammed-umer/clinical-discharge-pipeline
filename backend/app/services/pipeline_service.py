"""
PipelineService — the single orchestration layer of the clinical discharge pipeline.

This service replaces the 348-line execute_discharge_pipeline, 190-line
resolve_conflicts, and approve_discharge_summary functions that previously
lived inside main.py.

All domain services and repositories are injected via constructor; the service
itself is stateless and safe to use as a long-lived singleton.

Pipeline stages:
    upload_document    → Document ingestion + embedding
    execute_pipeline   → Extraction → Arbitration → Claims → Grounding → Persistence
    resolve_conflicts  → Conflict resolution + re-grounding + persistence
    approve_summary    → Human-in-the-Loop physician sign-off
"""

import datetime
import logging
import string
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import (
    GROUNDING_STAY_THRESHOLD,
    JUDGE_VERSION,
    PIPELINE_VERSION,
)
from app.core.exceptions import (
    AIServiceUnavailable,
    ClinicalExtractionError,
    ClinicalPipelineException,
    DatabaseUnavailable,
    DocumentValidationError,
    UnsupportedFileType,
    ValidationServiceUnavailable,
)
from app.core.logging import PipelineContext
from app.db.repositories.claim_repository import ClaimRepository
from app.db.repositories.note_repository import NoteRepository
from app.db.repositories.patient_repository import PatientRepository
from app.db.repositories.summary_repository import SummaryRepository
from app.db.repositories.validation_repository import ValidationRepository
from app.models.schemas import (
    AuthorRole,
    ConfidenceSchema,
    EvidenceSchema,
    FinalDischargeSummary as FinalDischargeSummarySchema,
    MedicationSchema,
)
from app.services.arbitration_service import ClinicalArbitrationEngine
from app.services.claim_id_service import ClinicalClaimIdService
from app.services.claim_service import ClaimService
from app.services.clinical_rules_service import ClinicalRulesEngine
from app.services.extraction_service import ClinicalExtractionService
from app.services.validation_service import ClinicalValidationLayer

logger = logging.getLogger(__name__)


class PipelineService:
    """
    Top-level orchestrator for the clinical discharge pipeline.

    Receives fully-constructed dependencies via constructor (dependency injection).
    Contains no SQLAlchemy queries directly — all DB access is delegated to
    the repository layer.
    """

    def __init__(
        self,
        extraction: ClinicalExtractionService,
        arbitration: ClinicalArbitrationEngine,
        validation: ClinicalValidationLayer,
        rules: ClinicalRulesEngine,
        claims: ClaimService,
        claim_ids: ClinicalClaimIdService,
        patient_repo: PatientRepository,
        note_repo: NoteRepository,
        claim_repo: ClaimRepository,
        summary_repo: SummaryRepository,
        validation_repo: ValidationRepository,
    ) -> None:
        self._extraction = extraction
        self._arbitration = arbitration
        self._validation = validation
        self._rules = rules
        self._claims = claims
        self._claim_ids = claim_ids
        self._patient_repo = patient_repo
        self._note_repo = note_repo
        self._claim_repo = claim_repo
        self._summary_repo = summary_repo
        self._validation_repo = validation_repo

    # ─────────────────────────────────────────────────────────────────────────
    # Document upload
    # ─────────────────────────────────────────────────────────────────────────

    async def upload_document(
        self,
        stay_id: str,
        patient_name: str,
        author_role: str,
        recorded_at: datetime.datetime,
        content: str,
        db: AsyncSession,
    ) -> Dict[str, str]:
        """
        Ingests an unstructured clinical note, vectorizes its content, and stores
        it in PostgreSQL with deduplication. Returns immediately on duplicates.
        """
        # Normalize and validate author role
        author_role = self._normalize_author_role(author_role)

        try:
            logger.info("Ingesting document for stay: %s", stay_id)

            # Upsert the PatientStay (creates if not exists, resets status to PROCESSING)
            stay = await self._patient_repo.get_or_create(db, stay_id, patient_name)
            stay.status = "PROCESSING"

            # Duplicate detection
            existing = await self._note_repo.find_duplicate(
                db, stay_id, author_role, recorded_at, content
            )
            if existing:
                logger.info("Duplicate document detected — skipping ingestion.")
                return {
                    "status": "success",
                    "message": f"Document already ingested for Stay ID {stay_id}",
                }

            # Compute semantic embedding
            embedding_vector = self._validation.get_embedding(content)

            await self._note_repo.create(
                db, stay_id, author_role, recorded_at, content, embedding_vector
            )

            await db.commit()
            logger.info(
                "Successfully ingested note from %s for stay %s", author_role, stay_id
            )
            return {
                "status": "success",
                "message": f"Document successfully ingested for Stay ID {stay_id}",
            }

        except Exception as exc:
            await db.rollback()
            if isinstance(exc, ClinicalPipelineException):
                raise
            logger.error("Document ingestion failed: %s", str(exc))
            raise DatabaseUnavailable(
                "Database write error occurred during document upload."
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Pipeline execution
    # ─────────────────────────────────────────────────────────────────────────

    async def execute_pipeline(
        self, stay_id: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Orchestrates the full pipeline:
          1. Fetch + deduplicate notes
          2. Batch extraction (1 LLM call)
          3. Arbitration + merge
          4. Claim generation + persistence
          5. Batch grounding validation (1 LLM call)
          6. Clinical rule engine
          7. Persist results
          8. Return structured response

        On AI service failures, saves safe state to DB and returns a 503
        JSONResponse payload (wrapped in a dict with _safe_failure=True so
        the route layer can return the correct HTTP status).
        """
        ctx = PipelineContext(stay_id=stay_id)
        start_time = time.time()
        validation_duration = 0.0

        try:
            # ── 1. Fetch and deduplicate raw notes ───────────────────────────
            ctx.info("FETCH", "Retrieving clinical notes from DB")
            raw_notes = await self._note_repo.get_by_stay(db, stay_id)
            if not raw_notes:
                raise HTTPException(
                    status_code=404,
                    detail=f"No clinical notes found matching stay reference: {stay_id}",
                )

            unique_notes = self._note_repo.deduplicate_in_memory(raw_notes)
            ctx.info("FETCH", f"Loaded {len(unique_notes)} unique notes")

            # ── 2. Batch extraction (1 LLM call for all notes) ───────────────
            extraction_start = time.time()
            ctx.info("EXTRACTION", "Starting batch Gemini extraction")
            try:
                extractions = await self._extraction.extract_structured_data_batch(
                    unique_raw_notes=unique_notes
                )
            except (AIServiceUnavailable, ValidationServiceUnavailable) as safe_err:
                ctx.error("EXTRACTION", f"Safe-stop: {safe_err}")
                raise
            extraction_duration = time.time() - extraction_start
            ctx.info("EXTRACTION", f"Completed in {extraction_duration:.2f}s")

            # Logging requirement: After extraction
            ext_meds_log = []
            for ext, timestamp, role in extractions:
                for m in ext.prescribed_medications:
                    ext_meds_log.append(f"  - {role}: {m.name} {m.dosage} {m.frequency}")
            meds_list_str = "\n".join(ext_meds_log) if ext_meds_log else "  - None"
            logger.info(f"\n[Extraction]\nMedications:\n{meds_list_str}")

            # ── 3. Arbitration + merge ────────────────────────────────────────
            ctx.info("ARBITRATION", "Merging extractions chronologically")
            all_notes_text = "\n\n".join(n.content for n in unique_notes)
            merged: FinalDischargeSummarySchema = self._arbitration.merge_extractions(
                extractions, all_notes_text=all_notes_text
            )
            merged.summary = self._claim_ids.generate_claim_ids(merged.summary)
            ctx.info(
                "ARBITRATION",
                f"Merged summary: {len(merged.summary.diagnoses)} diagnoses, "
                f"{len(merged.summary.prescribed_medications)} medications",
            )

            # Logging requirement: After arbitration
            arb_meds_log = [f"  - {m.name} {m.dosage} {m.frequency}" for m in merged.summary.prescribed_medications]
            arb_list_str = "\n".join(arb_meds_log) if arb_meds_log else "  - None"
            logger.info(f"\n[Arbitration]\nMerged medications:\n{arb_list_str}")

            # Guard against completely empty extraction
            if self._is_empty_extraction(merged):
                ctx.warning("ARBITRATION", "Merged extraction is completely empty")
                raise ClinicalExtractionError(
                    "No structured clinical information extracted."
                )

            # ── 4. Claim generation + persistence ────────────────────────────
            ctx.info("CLAIMS", "Generating atomic claims")
            claim_list = self._claims.generate_claims(
                extraction=merged.summary,
                author="SYSTEM_MERGE",
                timestamp=datetime.datetime.utcnow(),
            )
            await self._claim_repo.delete_by_stay(db, stay_id)
            await self._claim_repo.bulk_create(
                db, stay_id, claim_list, datetime.datetime.utcnow()
            )
            ctx.info("CLAIMS", f"Persisted {len(claim_list)} claims")

            # Logging requirement: After claim generation
            claim_meds_log = [f"  - {c.claim_id}: {c.value}" for c in claim_list if c.category == "MEDICATION"]
            claim_list_str = "\n".join(claim_meds_log) if claim_meds_log else "  - None"
            logger.info(f"\n[Claims]\nMedication Claims:\n{claim_list_str}")

            # ── 5. Batch grounding validation (1 LLM call) ───────────────────
            validation_start = time.time()
            ctx.info("GROUNDING", "Starting batch grounding validation")
            try:
                finalized = await self._validation.verify_summary_grounding(
                    stay_id=stay_id,
                    merged_summary=merged,
                    raw_notes=unique_notes,
                )
            except ValidationServiceUnavailable:
                ctx.error("GROUNDING", "Validation service unavailable")
                raise
            except Exception as ground_err:
                ctx.error("GROUNDING", f"Non-fatal grounding error: {ground_err}")
                finalized = self._build_degraded_summary(merged, ground_err)
            finally:
                validation_duration = time.time() - validation_start

            ctx.info("GROUNDING", f"Completed in {validation_duration:.2f}s")

            # Logging requirement: After validation
            val_conflicts_log = [
                f"  - {c.field}: {c.conflicting_values} (Severity: {c.severity})" 
                for c in finalized.validation.conflicts 
                if "medication" in c.field.lower()
            ]
            val_list_str = "\n".join(val_conflicts_log) if val_conflicts_log else "  - None"
            logger.info(f"\n[Validation]\nMedication Conflicts:\n{val_list_str}")

            # ── 6. Clinical rule engine ───────────────────────────────────────
            ctx.info("RULES", "Evaluating clinical safety rules")
            finalized = self._rules.evaluate_rules(finalized)
            ctx.info(
                "RULES",
                f"Rules evaluated — {len(finalized.validation.warnings)} warnings",
            )

            # ── 7. Determine pipeline status ─────────────────────────────────
            pipeline_status = self._compute_pipeline_status(finalized, unique_notes)
            ctx.info("STATUS", f"Pipeline status → {pipeline_status}")

            # Logging requirement: After summary generation
            sum_meds_log = [f"  - {m.name} {m.dosage} {m.frequency}" for m in finalized.summary.prescribed_medications]
            sum_list_str = "\n".join(sum_meds_log) if sum_meds_log else "  - None"
            logger.info(f"\n[Summary]\nPrescribed Medications:\n{sum_list_str}")

            # ── 8. Persist results ────────────────────────────────────────────
            grounding_score_val = finalized.validation.grounding_metrics.grounding_score
            summary_dict = finalized.model_dump(mode="json")

            # Update claim statuses
            await self._claim_repo.update_statuses_from_validation(
                db, stay_id, finalized.validation.unsupported_claims
            )

            # Upsert stay status
            await self._patient_repo.update_status(db, stay_id, pipeline_status)

            # Upsert validation report
            await self._validation_repo.delete_by_stay(db, stay_id)
            await self._validation_repo.create(
                db=db,
                stay_id=stay_id,
                grounded=finalized.validation.grounded,
                confidence=finalized.validation.confidence,
                unsupported_claims=finalized.validation.unsupported_claims,
                conflicts=finalized.validation.conflicts,
                notes=finalized.validation.notes,
            )

            # Upsert final summary
            await self._summary_repo.upsert(
                db=db,
                stay_id=stay_id,
                structured_data=summary_dict,
                grounding_score=grounding_score_val,
                pipeline_version=PIPELINE_VERSION,
                judge_version=JUDGE_VERSION,
                is_reconciled=0,
            )

            await db.commit()

            # ── 9. Emit structured metrics log ────────────────────────────────
            pipeline_duration = time.time() - start_time
            claim_count = len(claim_list)
            avg_latency = (validation_duration / claim_count) if claim_count > 0 else 0.0
            self._log_pipeline_metrics(
                ctx,
                unique_notes=unique_notes,
                claim_count=claim_count,
                pipeline_duration=pipeline_duration,
                extraction_duration=extraction_duration,
                validation_duration=validation_duration,
                avg_latency=avg_latency,
                conflict_count=len(finalized.validation.conflicts),
                grounding_score=grounding_score_val,
                pipeline_status=pipeline_status,
            )

            return {
                "stay_id": stay_id,
                "pipeline_status": pipeline_status,
                "data": summary_dict,
            }

        except (AIServiceUnavailable, ValidationServiceUnavailable) as safe_err:
            # Safe failure path — save state, return 503 payload via sentinel key
            await db.rollback()
            failure_payload = self._build_failure_payload(safe_err, start_time, validation_duration)
            await self._save_safe_failure_state(db, stay_id, failure_payload, safe_err)
            ctx.warning("SAFE_FAIL", f"Safe stop: {failure_payload['reason']}")
            return {"_safe_failure": True, "payload": failure_payload}

        except ClinicalPipelineException:
            await db.rollback()
            raise

        except HTTPException:
            raise

        except Exception as exc:
            await db.rollback()
            ctx.error("PIPELINE", f"Unexpected failure: {exc}")
            raise DatabaseUnavailable(
                "Critical database or pipeline execution failure."
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Conflict resolution
    # ─────────────────────────────────────────────────────────────────────────

    async def resolve_conflicts(
        self,
        stay_id: str,
        resolved_medications: List[Dict[str, str]],
        db: AsyncSession,
    ) -> Dict[str, str]:
        """
        Accepts a physician's resolved medication list, updates the discharge
        summary, re-runs grounding and rule evaluation, and re-persists all
        results. Transitions the stay to READY_FOR_REVIEW.
        """
        try:
            stay = await self._patient_repo.get_by_id(db, stay_id)
            if not stay:
                raise HTTPException(status_code=404, detail="Stay not found.")

            summary_orm = await self._summary_repo.get_by_stay(db, stay_id)
            if not summary_orm:
                raise HTTPException(
                    status_code=404, detail="Summary not found."
                )

            # Load into Pydantic for manipulation
            merged: FinalDischargeSummarySchema = (
                FinalDischargeSummarySchema.model_validate(summary_orm.structured_data)
            )

            # Build resolved medication objects
            resolved_meds = self._build_resolved_medications(
                resolved_medications, merged
            )
            merged.summary.prescribed_medications = resolved_meds
            merged.validation.conflicts = []
            merged.validation.grounded = True

            # Generate audit trail from existing conflict records (generalized)
            audit_trail = self._build_audit_trail(merged, resolved_meds, summary_orm)
            merged.validation.clinical_audit = audit_trail

            # Regenerate claims with resolved medications
            await self._claim_repo.delete_by_stay(db, stay_id)
            new_claims = self._claims.generate_claims(
                extraction=merged.summary,
                author="SYSTEM_MERGE",
                timestamp=datetime.datetime.utcnow(),
            )
            await self._claim_repo.bulk_create(
                db, stay_id, new_claims, datetime.datetime.utcnow()
            )

            # Re-run grounding with fresh notes
            raw_notes = await self._note_repo.get_by_stay(db, stay_id)
            unique_notes = self._note_repo.deduplicate_in_memory(raw_notes)
            finalized = await self._validation.verify_summary_grounding(
                stay_id=stay_id,
                merged_summary=merged,
                raw_notes=unique_notes,
            )

            # Re-run rule engine
            finalized = self._rules.evaluate_rules(finalized)

            # Update claim statuses
            await self._claim_repo.update_statuses_from_validation(
                db, stay_id, finalized.validation.unsupported_claims
            )

            # Update validation report
            await self._validation_repo.delete_by_stay(db, stay_id)
            await self._validation_repo.create(
                db=db,
                stay_id=stay_id,
                grounded=finalized.validation.grounded,
                confidence=finalized.validation.confidence,
                unsupported_claims=finalized.validation.unsupported_claims,
                conflicts=[],
                notes=finalized.validation.notes,
            )

            # Transition stay to READY_FOR_REVIEW
            await self._patient_repo.update_status(db, stay_id, "READY_FOR_REVIEW")

            # Upsert summary
            grounding_score = finalized.validation.grounding_metrics.grounding_score
            await self._summary_repo.upsert(
                db=db,
                stay_id=stay_id,
                structured_data=finalized.model_dump(mode="json"),
                grounding_score=grounding_score,
                pipeline_version=PIPELINE_VERSION,
                judge_version=JUDGE_VERSION,
                is_reconciled=0,
            )

            await db.commit()
            logger.info(
                "Stay %s conflicts resolved and summary updated (score=%.2f)",
                stay_id,
                grounding_score,
            )
            return {
                "status": "success",
                "message": "Discharge summary reconciled, conflicts resolved, and finalized.",
            }

        except (HTTPException, ClinicalPipelineException):
            raise
        except Exception as exc:
            await db.rollback()
            logger.error("Resolution endpoint failed: %s", str(exc))
            raise HTTPException(
                status_code=500,
                detail="Database write error occurred during conflict resolution.",
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Physician approval
    # ─────────────────────────────────────────────────────────────────────────

    async def approve_summary(
        self, stay_id: str, db: AsyncSession
    ) -> Dict[str, str]:
        """
        Applies Human-in-the-Loop physician approval. Marks the summary as
        reconciled, records the reviewer and timestamp, and transitions the
        stay to COMPLETED.
        """
        try:
            stay = await self._patient_repo.get_by_id(db, stay_id)
            if not stay:
                raise HTTPException(status_code=404, detail="Stay not found.")

            summary_orm = await self._summary_repo.get_by_stay(db, stay_id)
            if not summary_orm:
                raise HTTPException(
                    status_code=404,
                    detail="Summary not found. Process note first.",
                )

            reviewed_at = datetime.datetime.utcnow()
            stay.status = "COMPLETED"
            summary_orm.is_reconciled = 1
            summary_orm.reviewed_by = "Dr. Sarah Jenkins (Attending Physician)"
            summary_orm.reviewed_at = reviewed_at

            # Append approval annotation to validation notes
            struct_data = dict(summary_orm.structured_data)
            if "validation" in struct_data:
                struct_data["validation"]["grounded"] = True
                struct_data["validation"]["notes"].append(
                    f"Approved by attending physician Dr. Sarah Jenkins at "
                    f"{reviewed_at.isoformat()}"
                )
            summary_orm.structured_data = struct_data

            await db.commit()
            logger.info(
                "Stay %s manually approved and signed by Dr. Sarah Jenkins.", stay_id
            )
            return {
                "status": "success",
                "message": "Discharge summary approved, signed, and finalized.",
            }

        except (HTTPException, ClinicalPipelineException):
            raise
        except Exception as exc:
            await db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Database write error occurred during manual approval.",
            )

    async def reset_stay(self, stay_id: str, db: AsyncSession) -> None:
        """
        Completely deletes/resets a patient stay from the database.
        """
        try:
            logger.info("Resetting/deleting stay: %s", stay_id)
            await self._patient_repo.delete(db, stay_id)
            await db.commit()
        except Exception as exc:
            await db.rollback()
            logger.error("Failed to reset stay: %s", str(exc))
            raise DatabaseUnavailable("Database error occurred while resetting stay.")

    # ─────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────────────────────────────────


    @staticmethod
    def _normalize_author_role(author_role: str) -> str:
        """Normalizes and validates the author role against the AuthorRole enum."""
        if not author_role or not author_role.strip():
            return "UNKNOWN_CLINICIAN"
        role = author_role.upper()
        try:
            AuthorRole(role)
        except ValueError:
            return "UNKNOWN_CLINICIAN"
        return role

    @staticmethod
    def _is_empty_extraction(merged: FinalDischargeSummarySchema) -> bool:
        """Returns True if the merged summary contains no extractable clinical content."""
        s = merged.summary
        return (
            not s.diagnoses
            and not s.symptoms
            and not s.investigations
            and not s.prescribed_medications
            and (not s.clinical_summary or s.clinical_summary == "NOT_DOCUMENTED")
            and (not s.treatment_provided or s.treatment_provided == "NOT_DOCUMENTED")
            and (not s.discharge_condition or s.discharge_condition == "NOT_DOCUMENTED")
        )

    @staticmethod
    def _compute_pipeline_status(
        finalized: FinalDischargeSummarySchema,
        unique_notes: list,
    ) -> str:
        """Determines the pipeline status based on grounding, conflicts, and missing data."""
        has_conflicts = len(finalized.validation.conflicts) > 0
        has_unsupported = len(finalized.validation.unsupported_claims) > 0
        has_missing = len(finalized.summary.missing_information) > 0
        grounding_score = finalized.validation.grounding_metrics.grounding_score
        has_unknown_clinician = any(
            n.author_role == "UNKNOWN_CLINICIAN" for n in unique_notes
        )

        if (
            has_conflicts
            or has_unsupported
            or has_missing
            or grounding_score < GROUNDING_STAY_THRESHOLD
            or has_unknown_clinician
        ):
            return "NEEDS_RECONCILIATION"
        return "READY_FOR_REVIEW"

    @staticmethod
    def _build_degraded_summary(
        merged: FinalDischargeSummarySchema, error: Exception
    ) -> FinalDischargeSummarySchema:
        """
        Constructs a degraded summary when grounding validation fails non-fatally.
        Preserves all clinical data but marks grounding as failed.
        """
        from app.models.schemas import (
            ClinicalWarningSchema,
            GroundingMetricsSchema,
            ValidationReportSchema,
        )

        merged.validation = ValidationReportSchema(
            grounded=False,
            confidence=0.0,
            unsupported_claims=[],
            conflicts=merged.validation.conflicts,
            notes=[f"Grounding verification engine failed: {error}"],
            grounding_metrics=GroundingMetricsSchema(
                grounding_score=0.0,
                evidence_coverage=0.0,
                citation_completeness=0.0,
            ),
            warnings=[
                ClinicalWarningSchema(
                    field="SYSTEM_WARNING",
                    severity="HIGH",
                    message=(
                        "Grounding verification service unavailable. "
                        "Supporting context could not be verified automatically."
                    ),
                )
            ],
            citation_summary="Grounding verification unavailable.",
        )
        return merged

    @staticmethod
    def _build_failure_payload(
        error: Exception, start_time: float, validation_duration: float
    ) -> Dict[str, Any]:
        """Constructs the structured safe-failure response payload."""
        reason_str = str(error)
        if isinstance(error, ValidationServiceUnavailable):
            status_str = "VALIDATION_SERVICE_UNAVAILABLE"
            reason_str = "Gemini validation service temporarily unavailable."
        else:
            status_str = "AI_SERVICE_UNAVAILABLE"
            if "quota" in reason_str or "rate limit" in reason_str:
                reason_str = "Gemini API quota exceeded."
            elif "unavailable" in reason_str or "503" in reason_str:
                reason_str = "Gemini API temporarily unavailable."
            elif "schema validation" in reason_str or "parsing" in reason_str:
                reason_str = "Gemini API response parsing or validation failed."
            else:
                reason_str = "AI service network timeout or connection failure."

        return {
            "pipeline_status": status_str,
            "processing_status": "FAILED",
            "requires_manual_review": True,
            "documents_preserved": True,
            "summary_generated": False,
            "safe_state": True,
            "reason": reason_str,
            "retry_recommended": True,
            "retry_after": None,
        }

    async def _save_safe_failure_state(
        self,
        db: AsyncSession,
        stay_id: str,
        failure_payload: Dict[str, Any],
        error: Exception,
    ) -> None:
        """
        Persists the safe-failure state to DB after a pipeline abort.
        Uses a new implicit transaction (no explicit begin needed with AsyncSession).
        """
        status_str = failure_payload.get("pipeline_status", "AI_SERVICE_UNAVAILABLE")
        try:
            await self._patient_repo.update_status(db, stay_id, status_str)
            await self._summary_repo.upsert(
                db=db,
                stay_id=stay_id,
                structured_data=failure_payload,
                is_reconciled=0,
            )
            await db.commit()
            logger.info("Safe failure state saved to DB for stay %s", stay_id)
        except Exception as db_err:
            logger.error("Failed to save safe state to DB: %s", str(db_err))
            await db.rollback()

    def _build_resolved_medications(
        self,
        resolved_medications: List[Dict[str, str]],
        merged: FinalDischargeSummarySchema,
    ) -> List[MedicationSchema]:
        """
        Converts the physician's resolution payload into MedicationSchema objects,
        preserving evidence from existing medication records where the name matches.
        """
        resolved = []
        for index, item in enumerate(resolved_medications):
            name = item.get("name", "")
            dosage = item.get("dosage", "")
            frequency = item.get("frequency", "")
            duration = item.get("duration", "")

            # Preserve evidence from existing medication if name matches
            existing_med = next(
                (
                    m
                    for m in merged.summary.prescribed_medications
                    if m.name.strip().lower() == name.strip().lower()
                ),
                None,
            )

            if existing_med:
                med = existing_med.model_copy()
                med.dosage = dosage
                med.frequency = frequency
                med.duration = duration
                med.confidence = ConfidenceSchema(score=1.0, level="HIGH")
            else:
                med = MedicationSchema(
                    name=name,
                    dosage=dosage,
                    frequency=frequency,
                    duration=duration,
                    confidence=ConfidenceSchema(score=1.0, level="HIGH"),
                    evidence=[
                        EvidenceSchema(
                            source_document="Attending Physician Resolution Log",
                            extracted_text=(
                                f"Prescribed medication: {name} at dosage: {dosage}, "
                                f"frequency: {frequency}, for duration: {duration}"
                            ),
                            author_role="ATTENDING",
                            recorded_at=datetime.datetime.utcnow(),
                        )
                    ],
                    claim_id=f"CLM_MED_RESOLVED_{index}",
                )
            resolved.append(med)
        return resolved

    @staticmethod
    def _build_audit_trail(
        merged: FinalDischargeSummarySchema,
        resolved_meds: List[MedicationSchema],
        summary_orm: Any,
    ) -> Dict[str, Any]:
        """
        Builds a generic, case-agnostic clinical audit trail from the conflict
        records already in the summary. Works for any patient case.
        """
        original_recommendations = []
        reason = ""

        orig_conflicts = (
            summary_orm.structured_data.get("validation", {}).get("conflicts", [])
            if summary_orm.structured_data
            else []
        )
        for conf in orig_conflicts:
            if "medication" in conf.get("field", "").lower():
                med_name = conf.get("field", "").split(".")[-1]
                for idx, val in enumerate(conf.get("conflicting_values", [])):
                    role = (
                        conf.get("detected_from", [])[idx]
                        if idx < len(conf.get("detected_from", []))
                        else "Clinician"
                    )
                    original_recommendations.append(
                        {"role": role, "value": f"{med_name}: {val}"}
                    )
                reason = conf.get("recommended_action", "")

        decision_list = [
            f"{med.name} {med.dosage} {med.frequency}" for med in resolved_meds
        ]
        physician_decision = ", ".join(decision_list)
        if not reason:
            reason = "Physician selected preferred discharge dosage and frequency."

        return {
            "original_recommendations": original_recommendations,
            "physician_decision": physician_decision,
            "reason": reason,
        }

    @staticmethod
    def _log_pipeline_metrics(
        ctx: PipelineContext,
        unique_notes: list,
        claim_count: int,
        pipeline_duration: float,
        extraction_duration: float,
        validation_duration: float,
        avg_latency: float,
        conflict_count: int,
        grounding_score: float,
        pipeline_status: str,
    ) -> None:
        """Emits the structured pipeline metrics summary to the log."""
        ctx.info("PIPELINE", f"Merged {len(unique_notes)} notes")
        ctx.info("EXTRACTION", f"LLM Request Count: 1 | Generated {claim_count} claims")
        ctx.info("GROUNDING", f"LLM Request Count: 1 | Validated {claim_count} claims")
        ctx.info("COMPLETE", "Pipeline Complete")
        logger.info("Total LLM Calls: 2")
        logger.info("Pipeline Duration: %.4f seconds", pipeline_duration)
        logger.info("Extraction Duration: %.4f seconds", extraction_duration)
        logger.info("Validation Duration: %.4f seconds", validation_duration)
        logger.info("Average Validation Latency: %.4f seconds/claim", avg_latency)
        logger.info(
            "Pipeline metrics: stay_id=%s, duration=%f, provider=gemini, "
            "validation_duration=%f, conflict_count=%d, grounding_score=%f, result=%s",
            ctx.stay_id,
            pipeline_duration,
            validation_duration,
            conflict_count,
            grounding_score,
            pipeline_status,
        )
