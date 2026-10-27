"""Layout: columns, tables, images, header/footer content, special characters."""

from __future__ import annotations

import pytest

from cv_ats_check.checks.layout_checks import (
    check_header_footer,
    check_layout,
    check_special_characters,
    find_columns,
)
from cv_ats_check.extraction import extract_document
from cv_ats_check.models import Status, TextBlock
from tests.helpers import make_doc


def line(text: str, x0: float, x1: float, y: float) -> TextBlock:
    return TextBlock(text, 1, bbox=(x0, y, x1, y + 10))


# --- columns ------------------------------------------------------------------------------


def test_two_column_pdf_is_flagged(fixtures_dir):
    result = check_layout(extract_document(fixtures_dir / "cv_two_column.pdf"))
    assert result.status is Status.WARN
    assert "multi-column layout on page(s) 1" in result.message
    assert "single column" in result.suggestion


@pytest.mark.parametrize(
    "fixture",
    ["cv_normal_en.pdf", "cv_swedish.pdf", "cv_right_aligned_dates.pdf", "cv_mixed_dates.pdf"],
)
def test_single_column_pdfs_pass(fixtures_dir, fixture):
    result = check_layout(extract_document(fixtures_dir / fixture))
    assert result.status is Status.PASS, result.message


def test_find_columns_reports_gutter_and_counts():
    left = [line(f"left column line number {i} here", 40, 200, 700 - 16 * i) for i in range(5)]
    right = [line(f"right column line number {i} here", 260, 520, 700 - 16 * i) for i in range(5)]
    gutter, n_left, n_right = find_columns(left + right, 595)
    assert 200 <= gutter <= 260
    assert (n_left, n_right) == (5, 5)


@pytest.mark.parametrize(
    ("blocks", "width"),
    [
        ([], 595),
        ([line("only four words here", 40, 200, 700)] * 3, 595),
        ([line("one two three four five six", 50, 500, 700 - 16 * i) for i in range(10)], 595),
        ([line("one two three four five six", 50, 500, 700 - 16 * i) for i in range(10)], 0),
    ],
)
def test_find_columns_negative_cases(blocks, width):
    assert find_columns(blocks, width) is None


def test_columns_that_do_not_share_vertical_space_are_not_columns():
    top_left = [line(f"top left words line {i} text", 40, 200, 780 - 16 * i) for i in range(5)]
    bottom_right = [line(f"bottom right words line {i}", 260, 520, 300 - 16 * i) for i in range(5)]
    assert find_columns(top_left + bottom_right, 595) is None


# --- tables and images ----------------------------------------------------------------------


def test_docx_with_table_is_flagged(fixtures_dir):
    result = check_layout(extract_document(fixtures_dir / "cv_table.docx"))
    assert result.status is Status.WARN
    assert "1 table(s)" in result.message


def test_docx_without_table_passes(fixtures_dir):
    assert check_layout(extract_document(fixtures_dir / "cv_normal.docx")).status is Status.PASS


def test_photo_is_flagged_when_text_is_readable(fixtures_dir):
    doc = extract_document(fixtures_dir / "cv_photo.pdf")
    result = check_layout(doc)
    assert 0.02 <= doc.pages[0].image_area_ratio <= 0.1
    assert result.status is Status.WARN
    assert "photo or graphic on page(s) 1" in result.message


def test_scanned_pdf_is_left_to_the_readable_text_check(fixtures_dir):
    doc = extract_document(fixtures_dir / "cv_scanned.pdf")
    assert check_layout(doc).status is Status.PASS


# --- header/footer ---------------------------------------------------------------------------


def test_contact_only_in_docx_header_warns(fixtures_dir):
    result = check_header_footer(extract_document(fixtures_dir / "cv_header_contact.docx"))
    assert result.status is Status.WARN
    assert "body" in result.suggestion


def test_contact_in_header_and_body_passes():
    doc = make_doc(["Anna Testsson", "anna@example.com", "x"])
    doc.file_type = "docx"
    doc.blocks = [
        TextBlock("anna@example.com", 1, region="header"),
        *doc.blocks,
    ]
    assert check_header_footer(doc).status is Status.PASS


def test_name_only_in_footer_warns():
    doc = make_doc(["Experience", "Worked at Acme"])
    doc.file_type = "docx"
    doc.blocks = [*doc.blocks, TextBlock("Anna Testsson", 1, region="footer")]
    assert check_header_footer(doc).status is Status.WARN


def test_header_footer_check_is_skipped_when_not_applicable(fixtures_dir):
    assert check_header_footer(extract_document(fixtures_dir / "cv_normal_en.pdf")) is None
    assert check_header_footer(extract_document(fixtures_dir / "cv_normal.docx")) is None


# --- special characters ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        (" anna@example.com  070 123 45 67", "2 icon-font glyph(s)"),
        ("Pla​ywright", "1 invisible character(s)"),
        ("Selen­ium and ﻿Jira", "2 invisible character(s)"),
        (" bullet ​", "icon-font glyph(s)"),
    ],
)
def test_special_characters_warn(text, fragment):
    result = check_special_characters(make_doc([text]))
    assert result.status is Status.WARN
    assert fragment in result.message
    assert "plain text" in result.suggestion


@pytest.mark.parametrize("text", ["Åsa Öberg söker jobb i Göteborg", "• Bullet – dash — em", ""])
def test_ordinary_text_has_no_special_characters(text):
    assert check_special_characters(make_doc([text])).status is Status.PASS
