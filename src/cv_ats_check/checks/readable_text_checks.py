"""Is there a real text layer, or is the file a scanned image?"""

from __future__ import annotations

from cv_ats_check.models import CheckResult, ExtractedDocument, JobAd, Status

NAME = "Readable text"
MIN_CHARS_PER_PAGE = 100
_IMAGE_ONLY_PAGE_CHARS = 20


def check_readable_text(doc: ExtractedDocument, job: JobAd | None = None) -> CheckResult:
    """FAIL for scanned/empty-text files, WARN for garbled or partly image-only files."""
    chars_per_page = doc.total_chars / max(doc.page_count, 1)
    if chars_per_page < MIN_CHARS_PER_PAGE:
        if doc.image_count > 0:
            return CheckResult(
                NAME,
                Status.FAIL,
                f"Only {doc.total_chars} text characters found but {doc.image_count} image(s): "
                "this looks like a scanned or image-based file. An ATS cannot read it.",
                "Export the CV as a text-based PDF from Word, Google Docs or LaTeX instead of "
                "scanning or printing to an image.",
            )
        return CheckResult(
            NAME,
            Status.FAIL,
            f"Almost no extractable text ({doc.total_chars} characters).",
            "Re-export the file from the original editor and make sure text is not "
            "converted to outlines or images.",
        )

    image_only = [
        p.number for p in doc.pages if p.char_count < _IMAGE_ONLY_PAGE_CHARS and p.image_count > 0
    ]
    if image_only:
        pages = ", ".join(map(str, image_only))
        return CheckResult(
            NAME,
            Status.WARN,
            f"Page(s) {pages} contain images but no text; that content is invisible to an ATS.",
            "Replace image-only pages with real text.",
        )

    garbled = doc.text.count("�") + doc.text.count("(cid:")
    if garbled:
        return CheckResult(
            NAME,
            Status.WARN,
            f"Found {garbled} unreadable character marker(s) in the extracted text.",
            "Use a standard font and re-export the PDF; embedded custom fonts can break "
            "text extraction.",
        )

    return CheckResult(
        NAME,
        Status.PASS,
        f"Real text found: {doc.total_chars} characters on {doc.page_count} page(s).",
    )
