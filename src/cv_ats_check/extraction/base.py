"""Dispatch a file path to the right extractor."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from cv_ats_check.extraction.docx_extractor import extract_docx
from cv_ats_check.extraction.errors import EmptyFile, MissingFile, UnsupportedFileType
from cv_ats_check.extraction.pdf_extractor import extract_pdf
from cv_ats_check.models import ExtractedDocument

EXTRACTORS: dict[str, Callable[[Path], ExtractedDocument]] = {
    ".pdf": extract_pdf,
    ".docx": extract_docx,
}


def extract_document(path: str | Path) -> ExtractedDocument:
    """Extract text and layout facts from a CV file.

    Raises an ``ExtractionError`` subclass for missing, unsupported, empty or
    corrupt files so callers can show a clear message instead of a traceback.
    """
    p = Path(path)
    if not p.is_file():
        raise MissingFile(f"File not found: {p}")
    suffix = p.suffix.lower()
    if suffix not in EXTRACTORS:
        supported = ", ".join(sorted(EXTRACTORS))
        raise UnsupportedFileType(
            f"Unsupported file type '{suffix or '(none)'}'. Supported: {supported}"
        )
    if p.stat().st_size == 0:
        raise EmptyFile(f"File is empty (0 bytes): {p}")
    return EXTRACTORS[suffix](p)
