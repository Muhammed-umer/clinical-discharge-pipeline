import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, Integer, Text, Float, Boolean
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.db.database import Base


class PatientStay(Base):
    """
    Tracks patient hospital stays, admission identifiers, status, and related records.
    """
    __tablename__ = "patient_stays"
    
    id = Column(String, primary_key=True, index=True)  # e.g., STAY_2026_9482
    patient_name = Column(String, nullable=False)
    status = Column(String, default="PROCESSING")  # PROCESSING, NEEDS_RECONCILIATION, READY_FOR_REVIEW, COMPLETED

    # Relationships
    raw_notes = relationship("RawDocumentNode", back_populates="stay", cascade="all, delete-orphan")
    claims = relationship("ClinicalClaim", back_populates="stay", cascade="all, delete-orphan")
    validation_reports = relationship("ValidationReport", back_populates="stay", cascade="all, delete-orphan")
    final_summary = relationship("FinalDischargeSummary", back_populates="stay", uselist=False, cascade="all, delete-orphan")


class RawDocumentNode(Base):
    """
    Stores individual unstructured notes, metadata (author, recorded_at),
    and their corresponding text-embedding-004 pgvector embedding.
    """
    __tablename__ = "raw_document_nodes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stay_id = Column(String, ForeignKey("patient_stays.id"), nullable=False)
    author_role = Column(String, nullable=False)  # ATTENDING, CONSULTANT, RESIDENT, WARD_NURSE
    recorded_at = Column(DateTime, nullable=False)  # Sorting criteria for chronologies
    content = Column(Text, nullable=False)  # Raw unformatted text of note
    
    # 768 dimensions for text-embedding-004
    embedding = Column(Vector(768), nullable=True)

    stay = relationship("PatientStay", back_populates="raw_notes")


class ClinicalClaim(Base):
    """
    Factual claims representing clinical statements extracted from raw notes.
    Stores confidence levels, evidence logs, and evaluation status.
    """
    __tablename__ = "clinical_claims"

    id = Column(String, primary_key=True)  # Mapped to Pydantic claim_id (e.g. CLM_MED_...)
    stay_id = Column(String, ForeignKey("patient_stays.id"), nullable=False)
    category = Column(String, nullable=False)  # DIAGNOSIS, MEDICATION, INVESTIGATION, OBSERVATION, etc.
    value = Column(Text, nullable=False)  # Factual statement content
    
    confidence_score = Column(Float, nullable=False)
    confidence_level = Column(String, nullable=False)
    
    evidence = Column(JSON, nullable=False)  # Serialized List[EvidenceSchema]
    author_role = Column(String, nullable=False)
    recorded_at = Column(DateTime, nullable=False)
    
    status = Column(String, default="UNVERIFIED")  # UNVERIFIED, SUPPORTED, PARTIALLY_SUPPORTED, NOT_SUPPORTED

    stay = relationship("PatientStay", back_populates="claims")


class ValidationReport(Base):
    """
    Audit validation reports detailing which claims failed groundedness checks,
    active conflicts, and safety execution notes.
    """
    __tablename__ = "validation_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stay_id = Column(String, ForeignKey("patient_stays.id"), nullable=False)
    
    grounded = Column(Boolean, nullable=False)
    confidence = Column(Float, nullable=False)
    
    unsupported_claims = Column(JSON, nullable=False)  # Serialized List[str]
    conflicts = Column(JSON, nullable=False)  # Serialized List[ConflictSchema]
    notes = Column(JSON, nullable=False)  # Serialized List[str]
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    stay = relationship("PatientStay", back_populates="validation_reports")


class FinalDischargeSummary(Base):
    """
    The finalized patient discharge summary, representing consolidated extractions,
    EHR manual reconciliation states, and audit tracking parameters.
    """
    __tablename__ = "final_discharge_summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stay_id = Column(String, ForeignKey("patient_stays.id"), unique=True, nullable=False)
    
    # Validated clinical JSON matching Pydantic FinalDischargeSummary (contains summary & validation)
    structured_data = Column(JSON, nullable=False)
    
    is_reconciled = Column(Integer, default=0)  # 1 if approved by physician, 0 if automated pass
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Audit Auditing Fields for Healthcare EHR standards
    reviewed_by = Column(String, nullable=True)  # Clinician signature identifier
    reviewed_at = Column(DateTime, nullable=True)  # Approval timestamp
    grounding_score = Column(Float, default=0.0)  # Factual grounding rating
    pipeline_version = Column(String, default="1.2.0")  # Software version tag
    judge_version = Column(String, default="gemini-2.5-pro")  # Model model label

    stay = relationship("PatientStay", back_populates="final_summary")