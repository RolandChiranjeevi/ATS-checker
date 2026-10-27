"""Section heading detection."""

from __future__ import annotations

import pytest

from cv_ats_check.checks.heading_checks import (
    check_headings,
    find_sections,
    is_section_heading_text,
    normalize_heading,
)
from cv_ats_check.extraction import extract_document
from cv_ats_check.models import Status, TextBlock
from tests.helpers import make_doc


def heading(text: str) -> TextBlock:
    return TextBlock(text, 1, size=13.0, bold=True)


def body(text: str) -> TextBlock:
    return TextBlock(text, 1, size=10.0)


def test_english_cv_has_all_sections(fixtures_dir):
    result = check_headings(extract_document(fixtures_dir / "cv_normal_en.pdf"))
    assert result.status is Status.PASS
    assert set(result.details["found"]) == {
        "summary",
        "skills",
        "experience",
        "education",
        "projects",
    }


def test_swedish_headings_are_recognised(fixtures_dir):
    result = check_headings(extract_document(fixtures_dir / "cv_swedish.pdf"))
    assert result.status is Status.PASS


def test_docx_heading_styles_are_recognised(fixtures_dir):
    assert check_headings(extract_document(fixtures_dir / "cv_normal.docx")).status is Status.PASS


def test_one_missing_required_section_warns():
    doc = make_doc([heading("Experience"), body("x"), heading("Education"), body("y")])
    result = check_headings(doc)
    assert result.status is Status.WARN
    assert "Skills" in result.message
    assert "Add a heading" in result.suggestion


def test_two_missing_required_sections_fail():
    doc = make_doc([heading("Education"), body("y")])
    assert check_headings(doc).status is Status.FAIL


def test_no_headings_at_all_fails():
    result = check_headings(make_doc([body("Just a paragraph of text without sections.")]))
    assert result.status is Status.FAIL


def test_duplicate_heading_warns():
    blocks = [heading(h) for h in ("Skills", "Experience", "Education", "Experience")]
    result = check_headings(make_doc(blocks))
    assert result.status is Status.WARN
    assert "more than once" in result.message


def test_heading_in_body_style_is_flagged_as_unclear():
    blocks = [heading("Skills"), heading("Education"), body("Experience"), body("Worked at X")]
    result = check_headings(make_doc(blocks))
    assert result.status is Status.WARN
    assert "not visually distinct" in result.message


def test_decorated_compound_heading_matches_when_distinct():
    found = find_sections([heading("Education and Certifications")])
    assert "education" in found


def test_long_bold_sentence_is_not_a_heading():
    found = find_sections([heading("Experience in building large scale test automation systems")])
    assert found == {}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Skills", True),
        ("SKILLS:", True),
        ("  Kompetenser ", True),
        ("Arbetslivserfarenhet", True),
        ("Utbildning –", True),
        ("Om mig", True),
        ("Hobbies", False),
        ("", False),
    ],
)
def test_is_section_heading_text(text, expected):
    assert is_section_heading_text(text) is expected


def test_normalize_heading_strips_decoration():
    assert normalize_heading("  **Work   Experience:** ") == "work experience"
