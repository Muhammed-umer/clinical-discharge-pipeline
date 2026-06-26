"""
Dependency Injection container for the Clinical Discharge Pipeline.

All services and repositories are instantiated as singletons at module load.
FastAPI route handlers receive them via Depends() — making every handler
testable in isolation by simply overriding the provider in app.dependency_overrides.

Usage in routes:
    from app.core.dependencies import get_pipeline_service
    from fastapi import Depends

    @router.post("/process/{stay_id}")
    async def process(stay_id: str, svc = Depends(get_pipeline_service)):
        ...
"""

from app.db.repositories.claim_repository import ClaimRepository
from app.db.repositories.note_repository import NoteRepository
from app.db.repositories.patient_repository import PatientRepository
from app.db.repositories.summary_repository import SummaryRepository
from app.db.repositories.validation_repository import ValidationRepository
from app.services.arbitration_service import ClinicalArbitrationEngine
from app.services.claim_id_service import ClinicalClaimIdService
from app.services.claim_service import ClaimService
from app.services.clinical_rules_service import ClinicalRulesEngine
from app.services.confidence_service import ClinicalConfidenceService
from app.services.extraction_service import ClinicalExtractionService
from app.services.pipeline_service import PipelineService
from app.services.schema_validator import ClinicalSchemaValidator
from app.services.validation_service import ClinicalValidationLayer

# ─── Leaf services (no dependencies) ─────────────────────────────────────────
_schema_validator = ClinicalSchemaValidator()
_claim_id_service = ClinicalClaimIdService()
_confidence_service = ClinicalConfidenceService()
_claim_service = ClaimService()
_arbitration_engine = ClinicalArbitrationEngine()
_rules_engine = ClinicalRulesEngine()

# ─── Domain services (injected dependencies) ──────────────────────────────────
_extraction_service = ClinicalExtractionService(
    schema_validator=_schema_validator,
    claim_id_service=_claim_id_service,
    confidence_service=_confidence_service,
)

_validation_layer = ClinicalValidationLayer(
    claim_service=_claim_service,
)

# ─── Repositories (stateless — accept db session per method call) ─────────────
_patient_repo = PatientRepository()
_note_repo = NoteRepository()
_claim_repo = ClaimRepository()
_summary_repo = SummaryRepository()
_validation_repo = ValidationRepository()

# ─── Top-level orchestrator ───────────────────────────────────────────────────
_pipeline_service = PipelineService(
    extraction=_extraction_service,
    arbitration=_arbitration_engine,
    validation=_validation_layer,
    rules=_rules_engine,
    claims=_claim_service,
    claim_ids=_claim_id_service,
    patient_repo=_patient_repo,
    note_repo=_note_repo,
    claim_repo=_claim_repo,
    summary_repo=_summary_repo,
    validation_repo=_validation_repo,
)


# ─── FastAPI dependency provider functions ────────────────────────────────────

def get_pipeline_service() -> PipelineService:
    """Provides the singleton PipelineService to route handlers."""
    return _pipeline_service


def get_validation_layer() -> ClinicalValidationLayer:
    """Provides the singleton ClinicalValidationLayer to route handlers."""
    return _validation_layer
