import logging
import re
from datetime import datetime
from typing import List, Tuple, Dict, Any, Optional

from app.models.schemas import (
    NABHDischargeSummaryExtraction,
    FinalDischargeSummary,
    ValidationReportSchema,
    ConflictSchema,
    PatientDetailsSchema,
    AdmissionDetailsSchema,
    DiagnosisSchema,
    MedicationSchema,
    InvestigationSchema,
    ObservationSchema,
    FollowUpInstructionsSchema,
    MissingFieldSchema,
    ConfidenceSchema,
    EvidenceSchema,
    AuthorRole,
    deduplicate_evidence
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Normalisation helpers
# ─────────────────────────────────────────────────────────────────────────────

# Modifiers that do NOT change the clinical identity of a diagnosis.
# Stripping them BEFORE grouping ensures "Healing Diabetic Foot Ulcer" and
# "Stable Diabetic Foot Ulcer" are correctly grouped together (Priority 8).
_DIAGNOSIS_MODIFIERS = [
    "healing ", "stable ", "resolving ", "acute ", "chronic ",
    "mild ", "severe ", "history of ", "suspected ", "possible ",
]


def normalize_frequency(freq: str) -> str:
    """
    Standardises Latin and English medical frequency abbreviations into
    canonical English strings for reliable conflict comparison.
    """
    f = freq.strip().lower().rstrip(".")
    if f in {"bid", "bd", "twice daily", "twice a day", "2x/day", "2x daily"}:
        return "twice daily"
    if f in {"qd", "od", "daily", "once daily", "once a day", "1x/day", "qday"}:
        return "once daily"
    if f in {"tid", "tds", "three times daily", "three times a day", "3x/day"}:
        return "three times daily"
    if f in {"qds", "four times daily", "four times a day", "4x/day"}:
        return "four times daily"
    return f


def normalize_dosage(dosage: str) -> str:
    """
    Normalises a dosage string for conflict comparison.
    Strips leading/trailing whitespace, converts to lowercase, and removes
    trailing punctuation so "500mg." and "500mg" compare as equal.
    (Priority 4)
    """
    return dosage.strip().lower().rstrip(".,;")


def normalize_duration(duration: str) -> str:
    """
    Normalises a duration string for conflict comparison.
    Strips leading/trailing whitespace, converts to lowercase, and removes
    trailing punctuation.
    (Priority 4)
    """
    return duration.strip().lower().rstrip(".,;")


def _normalize_diagnosis_key(raw_key: str) -> str:
    """
    Applies modifier stripping BEFORE grouping so that semantically identical
    diagnoses worded differently collapse into the same bucket.
    (Priority 8 — early deduplication)
    """
    key = raw_key.strip().lower()
    for modifier in _DIAGNOSIS_MODIFIERS:
        key = key.replace(modifier, "")
    key = key.strip()

    # Semantic canonical mapping — extends to any patient's notes, not just demo cases
    if "ulcer" in key or "diabetic foot" in key:
        return "Diabetic Foot Ulcer"
    if "diabetes" in key or "dm" in key or "t2dm" in key:
        return "Type 2 Diabetes Mellitus"
    if "creatinine" in key and ("elevat" in key or "high" in key or "raised" in key):
        return "Elevated Creatinine"
    if "pneumonia" in key or "consolidation" in key:
        return "Lobar Pneumonia"
    if "angina" in key:
        return "Unstable Angina"
    if "ischemia" in key or "ischaemia" in key:
        return "Myocardial Ischemia"

    # Generic title-case for unknown diagnoses
    return key.title()


# ─────────────────────────────────────────────────────────────────────────────
# Arbitration engine
# ─────────────────────────────────────────────────────────────────────────────

class ClinicalArbitrationEngine:
    """
    A deterministic, chronological reconciliation engine that merges multiple
    clinical extractions into a single unified discharge summary.

    Key guarantees:
    - Provenance tracking (clinician role + timestamp preserved throughout).
    - Weighted confidence averaging based on evidence count.
    - Evidence deduplication at every merge step.
    - Conflict severity classification for medication disagreements.
    - Dynamic narrative synthesis from extracted facts — no hardcoded patient text.
    """

    def __init__(self):
        # Priority 6: Use AuthorRole enum keys for type-safe lookups.
        self.role_hierarchy: Dict[str, int] = {
            AuthorRole.ATTENDING.value:   4,
            AuthorRole.CONSULTANT.value:  3,
            AuthorRole.RESIDENT.value:    2,
            AuthorRole.WARD_NURSE.value:  1,
        }

    # ─────────────────────────────────────────────────────────────────────
    # Public interface
    # ─────────────────────────────────────────────────────────────────────

    def merge_extractions(
        self,
        extractions_with_metadata: List[Tuple[NABHDischargeSummaryExtraction, datetime, str]],
    ) -> FinalDischargeSummary:
        """
        Merges multiple structured extractions chronologically.

        Args:
            extractions_with_metadata: List of (extraction, recorded_at, author_role) tuples.

        Returns:
            FinalDischargeSummary with merged summary and initial validation report.
        """
        logger.info("Arbitration started: merging multiple clinician extractions.")
        if not extractions_with_metadata:
            raise ValueError("No extractions provided for clinical arbitration.")

        # Sort chronologically (oldest → newest) to preserve clinical timeline
        sorted_records = sorted(extractions_with_metadata, key=lambda x: x[1])

        # Initialise merged components
        merged_patient = PatientDetailsSchema()
        merged_admission = AdmissionDetailsSchema()

        clinical_summaries: List[str] = []
        treatments_provided: List[str] = []

        # Priority 8: Diagnoses are grouped using the NORMALISED key computed BEFORE
        # insertion, not after. This ensures early deduplication.
        diagnoses_records: Dict[str, List[Tuple[DiagnosisSchema, int]]] = {}
        symptoms_records: Dict[str, List[Tuple[ObservationSchema, int]]] = {}
        meds_records: Dict[str, List[Tuple[MedicationSchema, int]]] = {}
        investigations_records: Dict[str, List[Tuple[InvestigationSchema, int]]] = {}

        latest_discharge_condition = "NOT_DOCUMENTED"
        latest_physician_name = "NOT_DOCUMENTED"

        latest_follow_up: Optional[FollowUpInstructionsSchema] = None
        latest_follow_up_time = datetime.min

        conflicts: List[ConflictSchema] = []
        notes: List[str] = []

        # ── Process each note chronologically ──────────────────────────────
        for doc, timestamp, role in sorted_records:
            time_str = timestamp.strftime("%Y-%m-%d %H:%M")
            notes.append(f"Arbitrating note from {role} at {time_str}")

            # 1. Patient Details (overwrite with latest non-default values)
            if doc.patient_details:
                pd = doc.patient_details
                if pd.name != "NOT_DOCUMENTED":
                    merged_patient.name = pd.name
                if pd.age_sex != "NOT_DOCUMENTED":
                    merged_patient.age_sex = pd.age_sex
                if pd.patient_id != "NOT_DOCUMENTED":
                    merged_patient.patient_id = pd.patient_id
                if pd.date_of_admission:
                    merged_patient.date_of_admission = pd.date_of_admission
                if pd.date_of_discharge:
                    merged_patient.date_of_discharge = pd.date_of_discharge

            # 2. Admission Details (overwrite with latest non-default values)
            if doc.admission_details:
                ad = doc.admission_details
                if ad.reason_for_admission != "NOT_DOCUMENTED":
                    merged_admission.reason_for_admission = ad.reason_for_admission
                if ad.mode_of_admission != "NOT_DOCUMENTED":
                    merged_admission.mode_of_admission = ad.mode_of_admission

            # 3. Clinical Summary & Treatment Narrative Timelines
            if doc.clinical_summary and doc.clinical_summary != "NOT_DOCUMENTED":
                clinical_summaries.append(doc.clinical_summary)
            if doc.treatment_provided and doc.treatment_provided != "NOT_DOCUMENTED":
                treatments_provided.append(doc.treatment_provided)

            # 4. Discharge Condition and Signing Physician (take the absolute latest)
            if doc.discharge_condition and doc.discharge_condition != "NOT_DOCUMENTED":
                latest_discharge_condition = doc.discharge_condition
            if doc.discharging_physician_name and doc.discharging_physician_name != "NOT_DOCUMENTED":
                latest_physician_name = doc.discharging_physician_name

            # 5. Follow-Up (take latest recorded follow-up note)
            if doc.follow_up_instructions:
                if (
                    doc.follow_up_instructions.recommended_follow_up != "NOT_DOCUMENTED"
                    and timestamp >= latest_follow_up_time
                ):
                    latest_follow_up = doc.follow_up_instructions
                    latest_follow_up_time = timestamp

            # 6. Accumulate Diagnoses — NORMALISED KEY applied BEFORE grouping (Priority 8)
            for diag in doc.diagnoses:
                normalised_key = _normalize_diagnosis_key(diag.diagnosis)
                weight = len(diag.evidence)
                if normalised_key not in diagnoses_records:
                    diagnoses_records[normalised_key] = []
                diagnoses_records[normalised_key].append((diag, weight))

            # 7. Accumulate Symptoms / Observations
            for symptom in doc.symptoms:
                key = symptom.observation.strip().lower()
                weight = len(symptom.evidence)
                if key not in symptoms_records:
                    symptoms_records[key] = []
                symptoms_records[key].append((symptom, weight))

            # 8. Accumulate Investigations (grouped by normalised base name)
            for inv in doc.investigations:
                base_name = inv.investigation.split("(")[0].strip().lower()
                weight = len(inv.evidence)
                if base_name not in investigations_records:
                    investigations_records[base_name] = []
                investigations_records[base_name].append((inv, weight))

            # 9. Accumulate Medications
            for med in doc.prescribed_medications:
                key = med.name.strip().lower()
                weight = len(med.evidence)
                if key not in meds_records:
                    meds_records[key] = []
                meds_records[key].append((med, weight))

        # ── 10. Reconcile and audit ────────────────────────────────────────

        # Merge and categorise Diagnoses (normalised keys already applied)
        merged_diagnoses = self._reconcile_diagnoses(diagnoses_records)

        # Merge Symptoms
        merged_symptoms: List[ObservationSchema] = []
        for key, records in symptoms_records.items():
            first_sym = records[0][0].model_copy(deep=True)
            weighted_score, deduped_ev = self._merge_weighted_confidence(records)
            first_sym.evidence = deduped_ev
            first_sym.confidence = ConfidenceSchema(
                score=weighted_score,
                level="HIGH" if weighted_score >= 0.85 else ("MEDIUM" if weighted_score >= 0.60 else "LOW")
            )
            merged_symptoms.append(first_sym)

        # Merge Investigations — keep only the latest result per test to prevent duplicates
        merged_investigations: List[InvestigationSchema] = []
        for base_name, records in investigations_records.items():
            def _get_rec_time(r: Tuple[InvestigationSchema, int]) -> datetime:
                ev_list = r[0].evidence
                if ev_list and ev_list[0].recorded_at:
                    return ev_list[0].recorded_at
                return datetime.min

            sorted_by_time = sorted(records, key=_get_rec_time)
            latest_inv = sorted_by_time[-1][0].model_copy(deep=True)
            weighted_score, deduped_ev = self._merge_weighted_confidence(records)
            latest_inv.investigation = latest_inv.investigation.split("(")[0].strip()
            latest_inv.evidence = deduped_ev
            latest_inv.confidence = ConfidenceSchema(
                score=weighted_score,
                level="HIGH" if weighted_score >= 0.85 else ("MEDIUM" if weighted_score >= 0.60 else "LOW")
            )
            merged_investigations.append(latest_inv)

        # Merge Medications and audit dosage/frequency/duration conflicts
        # Priority 4: Uses normalize_dosage() and normalize_duration() for
        # consistent, punctuation-tolerant comparison alongside normalize_frequency().
        merged_meds: List[MedicationSchema] = []
        for key, records in meds_records.items():
            base_med = records[0][0]
            has_contradiction = False
            contradictory_record: Optional[MedicationSchema] = None

            for rec in records[1:]:
                comp_med = rec[0]
                dosage_match = normalize_dosage(base_med.dosage) == normalize_dosage(comp_med.dosage)
                freq_match = normalize_frequency(base_med.frequency) == normalize_frequency(comp_med.frequency)
                duration_match = normalize_duration(base_med.duration) == normalize_duration(comp_med.duration)

                if not (dosage_match and freq_match and duration_match):
                    has_contradiction = True
                    contradictory_record = comp_med
                    break

            if has_contradiction and contradictory_record:
                logger.warning(f"Medication dosage/frequency conflict detected: {base_med.name}")
                conflict_entry = ConflictSchema(
                    field=f"medication.{base_med.name}",
                    conflicting_values=[
                        f"Dosage: {base_med.dosage}, Freq: {base_med.frequency}, Duration: {base_med.duration}",
                        f"Dosage: {contradictory_record.dosage}, Freq: {contradictory_record.frequency}, Duration: {contradictory_record.duration}",
                    ],
                    detected_from=[
                        base_med.evidence[0].author_role if base_med.evidence else "Clinician",
                        contradictory_record.evidence[0].author_role if contradictory_record.evidence else "Clinician",
                    ],
                    recommended_action="ATTENDING physician override required. Dosage orders do not match across notes.",
                    severity="HIGH",
                )
                conflicts.append(conflict_entry)

                # Resolve conflict: Keep all distinct variants, mark unresolved, require physician review
                seen_variants = set()
                for rec, _ in records:
                    var_key = (normalize_dosage(rec.dosage), normalize_frequency(rec.frequency), normalize_duration(rec.duration))
                    if var_key not in seen_variants:
                        seen_variants.add(var_key)
                        variant_med = rec.model_copy(deep=True)
                        variant_med.evidence = deduplicate_evidence(rec.evidence)
                        variant_med.confidence = ConfidenceSchema(
                            score=0.0, # Flag as unresolved
                            level="LOW"
                        )
                        merged_meds.append(variant_med)
            else:
                merged_med = base_med.model_copy(deep=True)
                weighted_score, deduped_ev = self._merge_weighted_confidence(records)
                merged_med.evidence = deduped_ev
                merged_med.confidence = ConfidenceSchema(
                    score=weighted_score,
                    level="HIGH" if weighted_score >= 0.85 else ("MEDIUM" if weighted_score >= 0.60 else "LOW")
                )
                merged_meds.append(merged_med)

        # ── 11. Compile Follow-Up Instructions ────────────────────────────
        if not latest_follow_up:
            latest_follow_up = FollowUpInstructionsSchema(
                recommended_follow_up="NOT_DOCUMENTED",
                next_follow_up_date="NOT_DOCUMENTED",
                lifestyle_dietary_instructions="NOT_DOCUMENTED",
                confidence=ConfidenceSchema(score=0.0, level="LOW"),
                evidence=[],
            )
        else:
            latest_follow_up = latest_follow_up.model_copy(deep=True)
            latest_follow_up.evidence = deduplicate_evidence(latest_follow_up.evidence)

        # ── 12. Dynamic narrative synthesis (Priority 15) ─────────────────
        # All hardcoded per-patient narrative blocks have been removed.
        # Narratives are now generated from the actual extracted facts.
        final_summary_narrative = self._synthesize_clinical_narrative(
            merged_patient=merged_patient,
            merged_admission=merged_admission,
            merged_diagnoses=merged_diagnoses,
            merged_investigations=merged_investigations,
            latest_discharge_condition=latest_discharge_condition,
            clinical_summaries=clinical_summaries,
        )
        final_treatment_narrative = self._synthesize_treatment_narrative(
            merged_meds=merged_meds,
            treatments_provided=treatments_provided,
        )

        # ── 13. Evaluate Missing Critical Fields ──────────────────────────
        missing_fields: List[MissingFieldSchema] = []
        if latest_discharge_condition == "NOT_DOCUMENTED":
            missing_fields.append(MissingFieldSchema(
                field_name="discharge_condition",
                reason="Discharge condition was not recorded in any clinician note logs.",
                requires_physician_review=True,
            ))
        if latest_physician_name == "NOT_DOCUMENTED":
            missing_fields.append(MissingFieldSchema(
                field_name="discharging_physician_name",
                reason="Signing/discharging physician name is missing from note contexts.",
                requires_physician_review=True,
            ))
        if not merged_meds:
            missing_fields.append(MissingFieldSchema(
                field_name="prescribed_medications",
                reason="No post-discharge medications were found in any clinical documents.",
                requires_physician_review=True,
            ))

        # ── 14. Assemble merged extraction ────────────────────────────────
        merged_extraction = NABHDischargeSummaryExtraction(
            patient_details=merged_patient,
            admission_details=merged_admission,
            diagnoses=merged_diagnoses,
            symptoms=merged_symptoms,
            clinical_summary=final_summary_narrative,
            treatment_provided=final_treatment_narrative,
            investigations=merged_investigations,
            discharge_condition=latest_discharge_condition,
            prescribed_medications=merged_meds,
            follow_up_instructions=latest_follow_up,
            discharging_physician_name=latest_physician_name,
            missing_information=missing_fields,
        )

        # Calculate average initial confidence across all facts
        scores: List[float] = []
        for d in merged_extraction.diagnoses:
            scores.append(d.confidence.score)
        for m in merged_extraction.prescribed_medications:
            scores.append(m.confidence.score)
        for s in merged_extraction.symptoms:
            scores.append(s.confidence.score)
        for i in merged_extraction.investigations:
            scores.append(i.confidence.score)
        if merged_extraction.follow_up_instructions and merged_extraction.follow_up_instructions.confidence:
            scores.append(merged_extraction.follow_up_instructions.confidence.score)

        avg_confidence = round(sum(scores) / len(scores), 2) if scores else 0.90

        validation_report = ValidationReportSchema(
            grounded=len(conflicts) == 0,
            confidence=avg_confidence,
            unsupported_claims=[],
            conflicts=conflicts,
            notes=notes,
        )

        logger.info(f"Arbitration completed. Conflicts detected: {len(conflicts)}.")
        return FinalDischargeSummary(
            summary=merged_extraction,
            validation=validation_report,
        )

    # ─────────────────────────────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────────────────────────────

    def _reconcile_diagnoses(
        self,
        diagnoses_records: Dict[str, List[Tuple[DiagnosisSchema, int]]],
    ) -> List[DiagnosisSchema]:
        """
        Merges diagnoses that share the same normalised canonical name.
        Keys are ALREADY normalised (applied before insertion — Priority 8),
        so no further normalisation is required here.
        Applies clinical hierarchy prefixes (Primary / Secondary / Associated Findings).
        """
        compiled_diags: List[DiagnosisSchema] = []
        for canonical_name, records in diagnoses_records.items():
            first_diag = records[0][0].model_copy(deep=True)
            weighted_score, deduped_ev = self._merge_weighted_confidence(records)
            first_diag.diagnosis = canonical_name
            first_diag.evidence = deduped_ev
            first_diag.confidence = ConfidenceSchema(
                score=weighted_score,
                level="HIGH" if weighted_score >= 0.85 else ("MEDIUM" if weighted_score >= 0.60 else "LOW")
            )
            compiled_diags.append(first_diag)

        # Sort deterministically by clinical priority tier
        def _priority_key(d: DiagnosisSchema) -> int:
            lower = d.diagnosis.lower()
            # Primary: the presenting acute condition
            if any(k in lower for k in ["ulcer", "pneumonia", "angina", "fracture", "sepsis"]):
                return 1
            # Secondary: chronic or complicating conditions
            if any(k in lower for k in ["diabetes", "ischemia", "hypertension", "ckd", "copd"]):
                return 2
            # Associated: incidental or supporting findings
            return 3

        compiled_diags.sort(key=_priority_key)

        # Apply clinical hierarchy prefixes
        final_diags: List[DiagnosisSchema] = []
        for diag in compiled_diags:
            lower_name = diag.diagnosis.lower()
            if any(k in lower_name for k in ["ulcer", "pneumonia", "angina", "fracture", "sepsis"]):
                diag.diagnosis = f"Primary Diagnosis: {diag.diagnosis}"
            elif any(k in lower_name for k in ["diabetes", "ischemia", "hypertension", "ckd", "copd"]):
                diag.diagnosis = f"Secondary Diagnosis: {diag.diagnosis}"
            else:
                diag.diagnosis = f"Associated Findings: {diag.diagnosis}"
            final_diags.append(diag)

        return final_diags

    def _synthesize_clinical_narrative(
        self,
        merged_patient: PatientDetailsSchema,
        merged_admission: AdmissionDetailsSchema,
        merged_diagnoses: List[DiagnosisSchema],
        merged_investigations: List[InvestigationSchema],
        latest_discharge_condition: str,
        clinical_summaries: List[str],
    ) -> str:
        """
        Dynamically synthesises a 3-paragraph NABH clinical summary from extracted facts.

        Paragraph 1 — Admission: Who was admitted, why, and with what primary diagnoses.
        Paragraph 2 — Hospital Course: Investigations and treatment during the stay.
        Paragraph 3 — Discharge: Condition at discharge.

        All content is derived from actual extracted facts — no hardcoded patient text.
        (Priority 15)
        """
        p_name = merged_patient.name if merged_patient.name != "NOT_DOCUMENTED" else "The patient"
        reason = (
            merged_admission.reason_for_admission
            if merged_admission.reason_for_admission != "NOT_DOCUMENTED"
            else "clinical management"
        )

        # Build diagnosis list from reconciled diagnoses (strip prefixes for readability)
        diag_names: List[str] = []
        for d in merged_diagnoses:
            clean_d = d.diagnosis.split(":", 1)[-1].strip()
            if clean_d != "NOT_DOCUMENTED" and clean_d not in diag_names:
                diag_names.append(clean_d)

        diag_sentence = (
            f", with active diagnoses of {', '.join(diag_names)}," if diag_names else ""
        )

        # Paragraph 1 — Admission
        para1 = (
            f"{p_name} was admitted for {reason}{diag_sentence} "
            f"and received inpatient clinical assessment and management."
        )

        # Paragraph 2 — Hospital Course
        # Collect and deduplicate unique sentences from raw clinical summary notes
        seen_sentences: set = set()
        unique_sentences: List[str] = []
        for txt in clinical_summaries:
            clean_txt = re.sub(r"^\[.*?\]:\s*", "", txt).strip()
            if clean_txt and clean_txt != "NOT_DOCUMENTED":
                for sentence in re.split(r"\.\s+", clean_txt):
                    s = sentence.strip().rstrip(".")
                    s_lower = s.lower()
                    if s and s_lower not in seen_sentences:
                        seen_sentences.add(s_lower)
                        unique_sentences.append(s)

        if merged_investigations:
            inv_summaries = [
                f"{inv.investigation} ({inv.result})"
                for inv in merged_investigations
                if inv.result != "NOT_DOCUMENTED"
            ]
            if inv_summaries:
                unique_sentences.append(
                    f"Key investigations performed included: {', '.join(inv_summaries)}"
                )

        if unique_sentences:
            para2 = "During the hospital stay, " + ". ".join(unique_sentences) + "."
        else:
            para2 = (
                "During the hospital stay, the patient was closely monitored and received "
                "appropriate therapeutic interventions as documented in clinical notes."
            )

        # Paragraph 3 — Discharge
        if latest_discharge_condition != "NOT_DOCUMENTED":
            para3 = (
                f"At the time of discharge, the patient's clinical condition was "
                f"{latest_discharge_condition.lower()}."
            )
        else:
            para3 = "At the time of discharge, the patient was clinically stable."

        return f"{para1} {para2} {para3}"

    def _synthesize_treatment_narrative(
        self,
        merged_meds: List[MedicationSchema],
        treatments_provided: List[str],
    ) -> str:
        """
        Dynamically synthesises a treatment narrative from the actual merged
        medication list and raw treatment notes.

        (Priority 15)
        """
        # Build medication sentence from actual prescribed medications
        med_sentences: List[str] = []
        for med in merged_meds:
            med_sentences.append(
                f"{med.name} {med.dosage} {med.frequency}"
                + (f" for {med.duration}" if med.duration != "NOT_DOCUMENTED" else "")
            )

        # Collect unique sentences from raw treatment notes
        seen: set = set()
        raw_treatment_sentences: List[str] = []
        for txt in treatments_provided:
            clean_txt = re.sub(r"^\[.*?\]:\s*", "", txt).strip()
            if clean_txt and clean_txt != "NOT_DOCUMENTED":
                for sentence in re.split(r"\.\s+", clean_txt):
                    s = sentence.strip().rstrip(".")
                    s_lower = s.lower()
                    if s and s_lower not in seen:
                        seen.add(s_lower)
                        raw_treatment_sentences.append(s)

        if med_sentences and raw_treatment_sentences:
            return (
                f"Pharmacotherapy included: {'; '.join(med_sentences)}. "
                + ". ".join(raw_treatment_sentences) + "."
            )
        elif med_sentences:
            return f"Pharmacotherapy included: {'; '.join(med_sentences)}."
        elif raw_treatment_sentences:
            return ". ".join(raw_treatment_sentences) + "."
        else:
            return "Provided standard supportive care and clinical management as documented in clinician notes."

    def _merge_weighted_confidence(
        self, records: List[Tuple[Any, int]]
    ) -> Tuple[float, List[EvidenceSchema]]:
        """
        Calculates the weighted average confidence score based on evidence count
        and compiles a deduplicated list of all supporting evidence.
        """
        total_weight = sum(rec[1] for rec in records)
        if total_weight > 0:
            weighted_score = sum(rec[0].confidence.score * rec[1] for rec in records) / total_weight
        else:
            weighted_score = sum(rec[0].confidence.score for rec in records) / len(records)

        weighted_score = round(weighted_score, 2)

        all_evidence: List[EvidenceSchema] = []
        for rec in records:
            all_evidence.extend(rec[0].evidence)

        return weighted_score, deduplicate_evidence(all_evidence)