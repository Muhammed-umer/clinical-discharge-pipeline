from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum


class AuthorRole(str, Enum):
    """
    Enumeration of recognised clinical author roles in the system.
    Using str-Enum keeps these compatible with Pydantic string fields.
    """
    ATTENDING = "ATTENDING"
    CONSULTANT = "CONSULTANT"
    RESIDENT = "RESIDENT"
    WARD_NURSE = "WARD_NURSE"
    SYSTEM = "SYSTEM"
    RECONCILED_PIPELINE = "RECONCILED_PIPELINE"


class ConfidenceLevel(str, Enum):
    """
    Qualitative confidence tiers for extracted clinical facts.
    """
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class EvidenceSchema(BaseModel):
    """
    Schema representing the physical source evidence grounding a clinical fact.
    Enables absolute traceability to raw notes.
    """
    source_document: str = Field(
        ...,
        description="The source identifier of the clinical note (e.g., 'Ward Note 1', 'Consultation Log')"
    )
    extracted_text: str = Field(
        ...,
        description="The exact text snippet/sentence extracted from the raw clinical notes"
    )
    author_role: str = Field(
        ...,
        description="The role of the author who logged the fact (e.g., 'ATTENDING', 'CONSULTANT', 'RESIDENT', 'WARD_NURSE')"
    )
    recorded_at: Optional[datetime] = Field(
        None,
        description="Timestamp of when the note was recorded in the database"
    )


class CitationSchema(BaseModel):
    """
    Represents a verified, structured clinical citation indicating the exact provenance of a claim.
    """
    source_note_id: Optional[str] = Field(
        None,
        description="The database unique identifier for the source document node"
    )
    source_document: str = Field(
        ...,
        description="The identifier of the clinical document or role (e.g., 'Resident Log')"
    )
    extracted_text: str = Field(
        ...,
        description="The exact literal sentence or clinical text segment from the source note"
    )
    author_role: str = Field(
        ...,
        description="Role of the clinician asserting the claim (e.g., 'ATTENDING', 'CONSULTANT')"
    )
    recorded_at: Optional[datetime] = Field(
        None,
        description="Timestamp of when this clinical note was originally authored"
    )


class ConfidenceSchema(BaseModel):
    """
    Score metrics representing the reliability of the clinical claim extraction.
    """
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Numerical confidence score between 0.0 (unsupported) and 1.0 (fully grounded)"
    )
    level: str = Field(
        ...,
        description="Qualitative categorization: HIGH, MEDIUM, or LOW"
    )


class ClaimSchema(BaseModel):
    """
    Represents an atomic, individual clinical assertion that needs to be verified.
    """
    claim_id: str = Field(
        ...,
        description="A unique identifier for the specific clinical claim"
    )
    category: str = Field(
        ...,
        description="Clinical claim classification (e.g., 'DIAGNOSIS', 'MEDICATION', 'INVESTIGATION', 'OBSERVATION')"
    )
    value: str = Field(
        ...,
        description="The core semantic statement or assertion of the clinical fact"
    )
    confidence: ConfidenceSchema = Field(
        ...,
        description="Extraction confidence associated with the claim"
    )
    evidence: List[EvidenceSchema] = Field(
        default_factory=list,
        description="Supporting documentation sources grounding this claim"
    )
    author: str = Field(
        ...,
        description="The role of the professional asserting the claim"
    )
    timestamp: datetime = Field(
        ...,
        description="The clinical note recording timestamp"
    )
    claim_hash: Optional[str] = Field(
        None,
        description="Deterministic hash of the claim contents to detect duplicates"
    )
    source_note_ids: List[str] = Field(
        default_factory=list,
        description="A list of document node IDs that support this claim"
    )
    authority_level: Optional[str] = Field(
        None,
        description="Clinician authority tier for the asserting author: HIGH (ATTENDING), MEDIUM (CONSULTANT/RESIDENT), LOW (WARD_NURSE). Separate from LLM extraction confidence."
    )


class PatientDetailsSchema(BaseModel):
    """
    Demographics and metadata for the patient.
    """
    name: str = Field(
        default="NOT_DOCUMENTED",
        description="The patient's full name"
    )
    age_sex: str = Field(
        default="NOT_DOCUMENTED",
        description="The age and gender of the patient (e.g., '45/Male')"
    )
    patient_id: str = Field(
        default="NOT_DOCUMENTED",
        description="Unique patient registration identifier"
    )
    date_of_admission: Optional[datetime] = Field(
        None,
        description="Date and time when the patient was admitted"
    )
    date_of_discharge: Optional[datetime] = Field(
        None,
        description="Date and time when the patient was discharged"
    )


class AdmissionDetailsSchema(BaseModel):
    """
    Information captured at the time of patient stay admission.
    """
    reason_for_admission: str = Field(
        default="NOT_DOCUMENTED",
        description="Clinical presentation or chief complaints leading to admission"
    )
    mode_of_admission: str = Field(
        default="NOT_DOCUMENTED",
        description="Method of arrival (e.g., EMERGENCY, OUTPATIENT, REFERRAL)"
    )


class DiagnosisSchema(BaseModel):
    """
    Structured diagnosis asserted by the clinical team.
    """
    diagnosis: str = Field(
        ...,
        description="Active diagnosis code, title, or clinical description"
    )
    confidence: ConfidenceSchema = Field(
        ...,
        description="Confidence metrics computed for this diagnosis extraction"
    )
    evidence: List[EvidenceSchema] = Field(
        ...,
        description="Verification points from the clinical history"
    )
    claim_id: Optional[str] = Field(
        None,
        description="Unique claim ID mapped for downstream arbitration and validation"
    )


class MedicationSchema(BaseModel):
    """
    Medication details prescribed to the patient on discharge.
    """
    name: str = Field(
        ...,
        description="Generic or brand name of the drug"
    )
    dosage: str = Field(
        ...,
        description="Dosage amount/weight (e.g., 500mg, 1 tablet)"
    )
    frequency: str = Field(
        ...,
        description="Intake frequency (e.g., OD, BD, TID, QDS, PRN, ONCE DAILY)"
    )
    duration: str = Field(
        ...,
        description="Total duration of treatment (e.g., 5 days, 1 month, life-long)"
    )
    confidence: ConfidenceSchema = Field(
        ...,
        description="Confidence metrics associated with this medication"
    )
    evidence: List[EvidenceSchema] = Field(
        ...,
        description="Document context supporting this prescription"
    )
    claim_id: Optional[str] = Field(
        None,
        description="Unique claim ID mapped for downstream arbitration and validation"
    )


class InvestigationSchema(BaseModel):
    """
    Laboratory or radiological tests conducted during the hospital stay.
    """
    investigation: str = Field(
        ...,
        description="The type of investigation performed (e.g., Complete Blood Count, Chest X-Ray)"
    )
    result: str = Field(
        ...,
        description="Quantitative or qualitative result obtained"
    )
    confidence: ConfidenceSchema = Field(
        ...,
        description="Validation confidence for this investigation entry"
    )
    evidence: List[EvidenceSchema] = Field(
        ...,
        description="Underlying source notes where the results are detailed"
    )
    claim_id: Optional[str] = Field(
        None,
        description="Unique claim ID mapped for downstream arbitration and validation"
    )


class ObservationSchema(BaseModel):
    """
    Specific objective clinical findings, symptoms, or physical observations.
    """
    observation: str = Field(
        ...,
        description="Clinical finding or symptomatology reported"
    )
    confidence: ConfidenceSchema = Field(
        ...,
        description="System confidence in this observation"
    )
    evidence: List[EvidenceSchema] = Field(
        ...,
        description="Factual clinical note citations for this observation"
    )
    claim_id: Optional[str] = Field(
        None,
        description="Unique claim ID mapped for downstream arbitration and validation"
    )


class FollowUpInstructionsSchema(BaseModel):
    """
    Advice given to the patient on discharge regarding outpatient visits and care.
    """
    recommended_follow_up: str = Field(
        default="NOT_DOCUMENTED",
        description="Advice regarding future clinical checkups"
    )
    next_follow_up_date: str = Field(
        default="NOT_DOCUMENTED",
        description="Target date or timeline for the next consultation"
    )
    lifestyle_dietary_instructions: str = Field(
        default="NOT_DOCUMENTED",
        description="Diet, physical exercise, or general recovery guidelines"
    )
    confidence: Optional[ConfidenceSchema] = Field(
        None,
        description="Extraction confidence level"
    )
    evidence: List[EvidenceSchema] = Field(
        default_factory=list,
        description="Source grounding citations for follow up advice"
    )
    claim_id: Optional[str] = Field(
        None,
        description="Unique claim ID mapped for downstream arbitration and validation"
    )


class MissingFieldSchema(BaseModel):
    """
    Required fields that could not be verified or located in the source text.
    """
    field_name: str = Field(
        ...,
        description="Name of the missing field in NABH template"
    )
    reason: str = Field(
        ...,
        description="Reason or logic explaining the absence"
    )
    requires_physician_review: bool = Field(
        default=True,
        description="Indicates if clinical review is required to resolve this missing fact"
    )


class ConflictSchema(BaseModel):
    """
    Discrepancy detected between multiple documentation logs.
    """
    field: str = Field(
        ...,
        description="The field or item where discrepancy is detected (e.g., 'medication.Metformin')"
    )
    conflicting_values: List[str] = Field(
        ...,
        description="Array of conflicting values logged by different providers"
    )
    detected_from: List[str] = Field(
        ...,
        description="Roles or timestamps of authors logged in disagreement"
    )
    recommended_action: str = Field(
        ...,
        description="Suggested action for clinical arbiter"
    )
    severity: str = Field(
        default="MEDIUM",
        description="The clinical severity rating of the conflict (LOW, MEDIUM, HIGH, CRITICAL)"
    )


class GroundingMetricsSchema(BaseModel):
    """
    Calculated factual grounding compliance metrics.
    """
    grounding_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Aggregated medical grounding consistency score (0.0 to 1.0)"
    )
    evidence_coverage: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Fraction of claims containing at least one valid supporting evidence quote"
    )
    citation_completeness: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Percent of citations referencing an active clinician role and timestamp"
    )


class ClinicalWarningSchema(BaseModel):
    """
    Warnings generated by the safety layer when factual coverage fails safety guidelines.
    """
    field: str = Field(
        ...,
        description="Field or context category where warning was raised"
    )
    severity: str = Field(
        ...,
        description="Warning priority level: LOW, MEDIUM, HIGH, CRITICAL"
    )
    message: str = Field(
        ...,
        description="Actionable guidance details for clinical reviewer"
    )


class ValidationReportSchema(BaseModel):
    """
    Safety report from the Clinical Safety Layer checking factual consistency.
    """
    grounded: bool = Field(
        ...,
        description="True if all claims are successfully verified, False if unsupported elements exist"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="System aggregate score of validation consistency"
    )
    unsupported_claims: List[str] = Field(
        default_factory=list,
        description="Claims flagged by the Safety Layer as unsupported or hallucinated"
    )
    conflicts: List[ConflictSchema] = Field(
        default_factory=list,
        description="Discrepancies identified between clinical sources"
    )
    notes: List[str] = Field(
        default_factory=list,
        description="Audit logs and execution observations compiled during validation"
    )
    
    # New production audit fields (maintaining backwards compatibility)
    grounding_metrics: Optional[GroundingMetricsSchema] = Field(
        default_factory=lambda: GroundingMetricsSchema(),
        description="Mathematical factual grounding scores"
    )
    warnings: List[ClinicalWarningSchema] = Field(
        default_factory=list,
        description="Clinical warning alerts triggered for sub-optimal grounding"
    )
    citation_summary: str = Field(
        default="",
        description="Textual overview audit log of citations verified"
    )


class NABHDischargeSummaryExtraction(BaseModel):
    """
    Structured discharge summary extraction output conforming to NABH standards.
    """
    patient_details: PatientDetailsSchema = Field(
        ...,
        description="Extracted patient demographic metadata"
    )
    admission_details: AdmissionDetailsSchema = Field(
        ...,
        description="Reason and parameters of patient stay admission"
    )
    diagnoses: List[DiagnosisSchema] = Field(
        default_factory=list,
        description="List of diagnosed clinical conditions"
    )
    symptoms: List[ObservationSchema] = Field(
        default_factory=list,
        description="List of documented observations and active symptoms"
    )
    clinical_summary: str = Field(
        default="NOT_DOCUMENTED",
        description="Synthesized clinical background narrative of the stay"
    )
    treatment_provided: str = Field(
        default="NOT_DOCUMENTED",
        description="Narrative outline of surgeries, therapies, and clinical treatments"
    )
    investigations: List[InvestigationSchema] = Field(
        default_factory=list,
        description="Key diagnostic test investigations and findings"
    )
    discharge_condition: str = Field(
        default="NOT_DOCUMENTED",
        description="The physical status of the patient at the exact discharge window"
    )
    prescribed_medications: List[MedicationSchema] = Field(
        default_factory=list,
        description="Discharge medications list"
    )
    follow_up_instructions: FollowUpInstructionsSchema = Field(
        ...,
        description="Instructions for outpatient tracking"
    )
    discharging_physician_name: str = Field(
        default="NOT_DOCUMENTED",
        description="Name of the physician executing the discharge summary"
    )
    missing_information: List[MissingFieldSchema] = Field(
        default_factory=list,
        description="Factual gaps mapped during clinical note reading"
    )


class FinalDischargeSummary(BaseModel):
    """
    The final output combining structure, safety, and validation flags.
    """
    summary: NABHDischargeSummaryExtraction = Field(
        ...,
        description="Reconciled structured discharge summary details"
    )
    validation: ValidationReportSchema = Field(
        ...,
        description="Factual grounding audit reports and contradictions logged by the Safety Layer"
    )


def deduplicate_evidence(evidence_list: List[EvidenceSchema]) -> List[EvidenceSchema]:
    """
    Utility function to de-duplicate a list of EvidenceSchema objects based on the
    source document, extracted text, and clinician author role.
    """
    seen = set()
    deduped = []
    for ev in evidence_list:
        key = (
            ev.source_document.strip().lower(),
            ev.extracted_text.strip().lower(),
            ev.author_role.strip().lower()
        )
        if key not in seen:
            seen.add(key)
            deduped.append(ev)
    return deduped