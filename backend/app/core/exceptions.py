from fastapi import status

class ClinicalPipelineException(Exception):
    """
    Base exception for all clinical discharge pipeline errors.
    Standardized payload helps create structured API responses.
    """
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        status_str: str = "INTERNAL_SERVER_ERROR",
        safe_state: bool = True,
        requires_manual_review: bool = True,
        retry_available: bool = False,
        documents_preserved: bool = True,
        summary_generated: bool = False
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.status_str = status_str
        self.safe_state = safe_state
        self.requires_manual_review = requires_manual_review
        self.retry_available = retry_available
        self.documents_preserved = documents_preserved
        self.summary_generated = summary_generated


class AIServiceUnavailable(ClinicalPipelineException):
    """Raised when Gemini returns 429, 500, 503, rate limits or timeouts."""
    def __init__(self, message: str, retry_available: bool = True):
        super().__init__(
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            status_str="AI_SERVICE_UNAVAILABLE",
            safe_state=True,
            requires_manual_review=True,
            retry_available=retry_available,
            documents_preserved=True,
            summary_generated=False
        )


class DatabaseUnavailable(ClinicalPipelineException):
    """Raised when the database connection or query fails."""
    def __init__(self, message: str):
        super().__init__(
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            status_str="DATABASE_UNAVAILABLE",
            safe_state=True,
            requires_manual_review=True,
            retry_available=True,
            documents_preserved=True,
            summary_generated=False
        )


class DocumentValidationError(ClinicalPipelineException):
    """Raised when the note's text content is empty or contains binary data."""
    def __init__(self, message: str):
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            status_str="DOCUMENT_VALIDATION_ERROR",
            safe_state=True,
            requires_manual_review=True,
            retry_available=True,
            documents_preserved=True,
            summary_generated=False
        )


class PipelineSafeFailure(ClinicalPipelineException):
    """Raised for clean, safe stopping of the pipeline execution."""
    def __init__(self, message: str):
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            status_str="PIPELINE_SAFE_FAILURE",
            safe_state=True,
            requires_manual_review=True,
            retry_available=True,
            documents_preserved=True,
            summary_generated=False
        )


class PDFGenerationFailure(ClinicalPipelineException):
    """Raised when PDF generation fails."""
    def __init__(self, message: str):
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            status_str="PDF_GENERATION_FAILURE",
            safe_state=True,
            requires_manual_review=True,
            retry_available=True,
            documents_preserved=True,
            summary_generated=True  # Discharge summary structured data remains safe!
        )


class UnsupportedFileType(ClinicalPipelineException):
    """Raised when an unsupported file type is uploaded."""
    def __init__(self, message: str):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            status_str="UNSUPPORTED_FILE_TYPE",
            safe_state=True,
            requires_manual_review=True,
            retry_available=True,
            documents_preserved=True,
            summary_generated=False
        )


class ClinicalExtractionError(ClinicalPipelineException):
    """Raised when extraction returns empty results or fails schema parsing."""
    def __init__(self, message: str):
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            status_str="NO_STRUCTURED_DATA_EXTRACTED",
            safe_state=True,
            requires_manual_review=True,
            retry_available=True,
            documents_preserved=True,
            summary_generated=False
        )


class ValidationServiceUnavailable(ClinicalPipelineException):
    """Raised when the grounding validation fails or is unavailable."""
    def __init__(self, message: str, retry_available: bool = True):
        super().__init__(
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            status_str="VALIDATION_SERVICE_UNAVAILABLE",
            safe_state=True,
            requires_manual_review=True,
            retry_available=retry_available,
            documents_preserved=True,
            summary_generated=False
        )

