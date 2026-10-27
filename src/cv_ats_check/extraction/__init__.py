"""Document extraction (PDF, DOCX)."""

from cv_ats_check.extraction.base import extract_document
from cv_ats_check.extraction.errors import (
    CorruptFile,
    EmptyFile,
    ExtractionError,
    MissingFile,
    UnsupportedFileType,
)

__all__ = [
    "CorruptFile",
    "EmptyFile",
    "ExtractionError",
    "MissingFile",
    "UnsupportedFileType",
    "extract_document",
]
