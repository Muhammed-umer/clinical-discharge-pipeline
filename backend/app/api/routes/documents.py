"""
Document upload routes — /api/documents/*

Handles:
  - POST /api/documents/upload  → Ingest a clinical note with embedding
"""

import datetime
import logging
import string
from typing import Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_pipeline_service
from app.core.exceptions import DocumentValidationError, UnsupportedFileType
from app.db.database import get_db
from app.services.pipeline_service import PipelineService

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Request model ────────────────────────────────────────────────────────────

class DocumentUploadRequest(BaseModel):
    stay_id: str
    patient_name: str
    author_role: Optional[str] = "UNKNOWN_CLINICIAN"
    recorded_at: datetime.datetime
    content: str
    filename: Optional[str] = None


# ─── Input validators ─────────────────────────────────────────────────────────

_UNSUPPORTED_EXTENSIONS = (
    ".pdf", ".docx", ".png", ".jpg", ".jpeg",
    ".gif", ".xls", ".xlsx", ".zip", ".tar", ".gz",
)


def validate_filename(filename: Optional[str]) -> None:
    """Rejects non-TXT file uploads based on file extension."""
    if not filename:
        return
    lower = filename.lower()
    for ext in _UNSUPPORTED_EXTENSIONS:
        if lower.endswith(ext):
            raise UnsupportedFileType(
                "This demonstration currently supports UTF-8 encoded TXT clinical notes."
            )


def validate_text_content(content: str) -> None:
    """
    Validates that the content is a genuine UTF-8 text document:
      - Not empty
      - No null bytes (binary data)
      - Valid UTF-8 encoding
      - Non-printable character ratio < 15%
    """
    if not content or not content.strip():
        raise DocumentValidationError(
            "No clinical content detected. Supported file type: UTF-8 TXT clinical notes."
        )

    if "\x00" in content:
        raise DocumentValidationError(
            "Binary files renamed as txt are not supported. "
            "Please upload valid text documents."
        )

    try:
        content.encode("utf-8")
    except UnicodeEncodeError:
        raise DocumentValidationError(
            "Invalid UTF-8 encoding. Please upload UTF-8 encoded text clinical notes."
        )

    printable_chars = set(string.printable + string.whitespace)
    non_printable_count = sum(1 for c in content if c not in printable_chars)
    if non_printable_count / len(content) > 0.15:
        raise DocumentValidationError(
            "High ratio of non-printable characters. "
            "Binary files renamed as txt are not supported."
        )


# ─── Route handler ────────────────────────────────────────────────────────────

@router.post("/documents/upload", status_code=status.HTTP_201_CREATED)
async def upload_clinical_document(
    payload: DocumentUploadRequest,
    db: AsyncSession = Depends(get_db),
    svc: PipelineService = Depends(get_pipeline_service),
) -> dict:
    """
    Ingests an unstructured clinical note, generates a 768-dimensional semantic
    embedding via gemini-embedding-001, and stores the document in PostgreSQL.

    Deduplication:  Notes with identical (stay_id, role, timestamp, content)
                    are silently accepted as idempotent.
    """
    validate_filename(payload.filename)
    validate_text_content(payload.content)

    return await svc.upload_document(
        stay_id=payload.stay_id,
        patient_name=payload.patient_name,
        author_role=payload.author_role or "UNKNOWN_CLINICIAN",
        recorded_at=payload.recorded_at,
        content=payload.content,
        db=db,
    )
