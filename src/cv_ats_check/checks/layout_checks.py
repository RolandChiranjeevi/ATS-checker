"""Layout checks: columns, tables, large images, header/footer content, special characters."""

from __future__ import annotations

import re

from cv_ats_check.checks.contact_checks import find_emails, find_name, find_phones
from cv_ats_check.checks.readable_text_checks import MIN_CHARS_PER_PAGE
from cv_ats_check.models import CheckResult, ExtractedDocument, JobAd, Status, TextBlock

LAYOUT_NAME = "Layout"
HEADER_FOOTER_NAME = "Header/footer content"
CHARS_NAME = "Special characters"

_MIN_COLUMN_WORDS = 4  # short fragments such as right-aligned dates are not column text
_MIN_COLUMN_LINES = 4
_MAX_CROSSING_RATIO = 0.1  # share of lines allowed to straddle the gutter
_MIN_VERTICAL_OVERLAP = 0.5  # the two columns must occupy the same part of the page
_LARGE_IMAGE_RATIO = 0.02  # photos/graphics covering >= 2 % of a page
_PRIVATE_USE = re.compile(r"[-]")  # icon fonts (Font Awesome, Wingdings, ...)
_INVISIBLE = re.compile(r"[​-‍⁠﻿­]")


def _vertical_range(lines: list[TextBlock]) -> tuple[float, float]:
    return min(b.bbox[1] for b in lines), max(b.bbox[3] for b in lines)


def find_columns(blocks: list[TextBlock], page_width: float) -> tuple[float, int, int] | None:
    """Detect a vertical gutter with real text on both sides.

    Returns ``(gutter_x, lines_left, lines_right)`` or None. A single-column page has long
    lines crossing every candidate gutter; short right-aligned dates are ignored because they
    are not substantial text.
    """
    lines = [b for b in blocks if b.bbox and len(b.text.split()) >= _MIN_COLUMN_WORDS]
    if page_width <= 0 or len(lines) < 2 * _MIN_COLUMN_LINES:
        return None
    for percent in range(20, 81):
        gutter = page_width * percent / 100
        left = [b for b in lines if b.bbox[2] <= gutter]
        right = [b for b in lines if b.bbox[0] >= gutter]
        if len(left) < _MIN_COLUMN_LINES or len(right) < _MIN_COLUMN_LINES:
            continue
        if len(lines) - len(left) - len(right) > _MAX_CROSSING_RATIO * len(lines):
            continue
        left_top, left_bottom = _vertical_range(left)
        right_top, right_bottom = _vertical_range(right)
        shorter = min(left_bottom - left_top, right_bottom - right_top)
        overlap = min(left_bottom, right_bottom) - max(left_top, right_top)
        if shorter > 0 and overlap >= _MIN_VERTICAL_OVERLAP * shorter:
            return gutter, len(left), len(right)
    return None


def check_layout(doc: ExtractedDocument, job: JobAd | None = None) -> CheckResult:
    """Warn about multi-column pages, tables and large images that confuse ATS parsers."""
    problems: list[str] = []
    suggestions: list[str] = []

    if doc.file_type == "pdf":
        column_pages = [
            page.number
            for page in doc.pages
            if find_columns([b for b in doc.blocks if b.page == page.number], page.width)
        ]
        if column_pages:
            pages = ", ".join(map(str, column_pages))
            problems.append(f"multi-column layout on page(s) {pages}")
            suggestions.append(
                "Use a single column: parsers read line by line across the page and can mix "
                "the columns together. Check 'What an ATS sees' to see the resulting order."
            )

    if doc.table_count:
        problems.append(f"{doc.table_count} table(s)")
        suggestions.append(
            "Avoid tables for layout; parsers often read table cells in an unpredictable "
            "order. Use plain paragraphs and bullet lists."
        )

    if doc.total_chars / max(doc.page_count, 1) >= MIN_CHARS_PER_PAGE:
        image_pages = [p.number for p in doc.pages if p.image_area_ratio >= _LARGE_IMAGE_RATIO]
        if image_pages:
            pages = ", ".join(map(str, image_pages))
            problems.append(f"photo or graphic on page(s) {pages}")
            suggestions.append(
                "ATS parsers ignore images. Make sure no information (skills charts, "
                "contact details) exists only as an image; a photo adds nothing for an ATS."
            )

    if not problems:
        return CheckResult(
            LAYOUT_NAME, Status.PASS, "No multi-column layout, tables or large images found."
        )
    return CheckResult(
        LAYOUT_NAME, Status.WARN, "Found: " + "; ".join(problems) + ".", " ".join(suggestions)
    )


def check_header_footer(doc: ExtractedDocument, job: JobAd | None = None) -> CheckResult | None:
    """DOCX only: contact details that live only in the Word header/footer may be skipped."""
    if doc.file_type != "docx":
        return None
    outside = [b for b in doc.blocks if b.region != "body"]
    if not outside:
        return None

    body = [b for b in doc.blocks if b.region == "body"]
    outside_text = "\n".join(b.text for b in outside)
    body_text = "\n".join(b.text for b in body)
    contact_outside = bool(find_emails(outside_text) or find_phones(outside_text))
    contact_in_body = bool(find_emails(body_text) or find_phones(body_text))
    name_outside_only = bool(
        find_name([b.text for b in outside]) and not find_name([b.text for b in body])
    )

    if (contact_outside and not contact_in_body) or name_outside_only:
        return CheckResult(
            HEADER_FOOTER_NAME,
            Status.WARN,
            "Your name or contact details appear only in the Word header/footer; many ATS "
            "parsers skip headers and footers.",
            "Move your name, e-mail and phone number into the main document body.",
        )
    return CheckResult(
        HEADER_FOOTER_NAME,
        Status.PASS,
        f"Header/footer text found ({len(outside)} line(s)); nothing essential depends on it.",
    )


def check_special_characters(doc: ExtractedDocument, job: JobAd | None = None) -> CheckResult:
    """Icon-font glyphs and invisible characters extract as junk or break keyword matching."""
    icons = len(_PRIVATE_USE.findall(doc.text))
    invisible = len(_INVISIBLE.findall(doc.text))
    if not icons and not invisible:
        return CheckResult(CHARS_NAME, Status.PASS, "No icon-font or invisible characters found.")

    found = []
    if icons:
        found.append(f"{icons} icon-font glyph(s) (private-use characters, e.g. Font Awesome)")
    if invisible:
        found.append(f"{invisible} invisible character(s) (zero-width or soft hyphen)")
    return CheckResult(
        CHARS_NAME,
        Status.WARN,
        "Found " + " and ".join(found) + "; an ATS reads these as junk or broken words.",
        "Replace icons with plain text labels such as 'E-mail:' and 'Phone:', and retype "
        "text that was pasted from a web page.",
    )
