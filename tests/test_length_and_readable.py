"""Length/density and readable-text checks."""

from __future__ import annotations

import pytest

from cv_ats_check.checks.length_checks import check_length
from cv_ats_check.checks.readable_text_checks import check_readable_text
from cv_ats_check.extraction import extract_document
from cv_ats_check.models import ExtractedDocument, PageInfo, Status
from tests.helpers import make_doc


def doc_with_words(count: int, pages: int = 1) -> ExtractedDocument:
    doc = make_doc([" ".join(["word"] * count)])
    doc.pages = [PageInfo(i + 1, 500, 0) for i in range(pages)]
    return doc


@pytest.mark.parametrize(
    ("words", "pages", "expected"),
    [
        (50, 1, Status.FAIL),
        (149, 1, Status.FAIL),
        (150, 1, Status.WARN),
        (249, 1, Status.WARN),
        (250, 1, Status.PASS),
        (800, 2, Status.PASS),
        (1500, 3, Status.PASS),
        (1501, 3, Status.WARN),
        (900, 4, Status.WARN),
    ],
)
def test_length_thresholds(words, pages, expected):
    assert check_length(doc_with_words(words, pages)).status is expected


def test_docx_page_count_is_ignored(fixtures_dir):
    doc = extract_document(fixtures_dir / "cv_normal.docx")
    assert "page" not in check_length(doc).message


def test_text_pdf_is_readable(fixtures_dir):
    result = check_readable_text(extract_document(fixtures_dir / "cv_normal_en.pdf"))
    assert result.status is Status.PASS


def test_scanned_pdf_fails_with_actionable_advice(fixtures_dir):
    result = check_readable_text(extract_document(fixtures_dir / "cv_scanned.pdf"))
    assert result.status is Status.FAIL
    assert "scanned" in result.message
    assert "Export" in result.suggestion


def test_empty_text_without_images_fails():
    doc = make_doc([""])
    doc.pages = [PageInfo(1, 0, 0)]
    result = check_readable_text(doc)
    assert result.status is Status.FAIL
    assert "Almost no extractable text" in result.message


def test_garbled_text_warns():
    doc = make_doc(["Anna �� Testsson (cid:12) " + "text " * 60])
    result = check_readable_text(doc)
    assert result.status is Status.WARN


def test_partly_image_only_document_warns():
    doc = make_doc(["text " * 100])
    doc.pages = [PageInfo(1, 600, 0), PageInfo(2, 0, 1)]
    result = check_readable_text(doc)
    assert result.status is Status.WARN
    assert "2" in result.message
