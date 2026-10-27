"""Contact detail detection."""

from __future__ import annotations

import pytest

from cv_ats_check.checks.contact_checks import (
    check_contact_details,
    find_emails,
    find_name,
    find_phones,
)
from cv_ats_check.extraction import extract_document
from cv_ats_check.models import Status
from tests.helpers import make_doc


def test_normal_cv_passes(fixtures_dir):
    result = check_contact_details(extract_document(fixtures_dir / "cv_normal_en.pdf"))
    assert result.status is Status.PASS
    assert "email" in result.message and "phone" in result.message


def test_cv_without_contact_fails(fixtures_dir):
    result = check_contact_details(extract_document(fixtures_dir / "cv_no_contact.pdf"))
    assert result.status is Status.FAIL
    assert "email" in result.message and "phone" in result.message
    assert result.suggestion


def test_only_email_is_a_warning():
    doc = make_doc(["Anna Testsson", "anna@example.com", "Experience"])
    result = check_contact_details(doc)
    assert result.status is Status.WARN
    assert "phone" in result.message


def test_email_only_as_mailto_link_is_a_warning():
    doc = make_doc(["Anna Testsson", "+46 70 123 45 67"])
    doc.links.append("mailto:anna@example.com")
    result = check_contact_details(doc)
    assert result.status is Status.WARN
    assert "clickable link" in result.suggestion


def test_linkedin_found_in_hyperlink_only():
    doc = make_doc(["Anna Testsson", "anna@example.com", "070 123 45 67"])
    doc.links.append("https://www.linkedin.com/in/anna-testsson")
    assert "LinkedIn" in check_contact_details(doc).message


@pytest.mark.parametrize(
    "text",
    [
        "070-270 93 57",
        "+46 70 270 93 57",
        "0702709357",
        "08-123 456 78",
        "(555) 123-4567",
        "0046 70 270 93 57",
    ],
)
def test_phone_formats_are_found(text):
    assert find_phones(f"Phone: {text} ") != []


@pytest.mark.parametrize(
    ("label", "text"),
    [
        ("thin space", "070 270 93 57"),
        ("narrow no-break space", "070 270 93 57"),
        ("figure space", "070 270 93 57"),
        ("en dash", "070–270–93–57"),
        ("minus sign", "070−270 93 57"),
        ("label glued on", "Tel070 270 93 57"),
        ("icon glyph glued on", "070 270 93 57"),
        ("icon extracted as a letter", "Ï070 270 93 57"),
        ("international thin spaces", "+46 70 270 93 57"),
    ],
)
def test_phone_numbers_with_pdf_style_separators_are_found(label, text):
    assert find_phones(f"x {text} y") != [], label


def test_phone_with_thin_spaces_counts_as_a_phone_in_the_contact_check():
    doc = make_doc(["Anna Testsson", "anna@example.com", "070 270 93 57"])
    result = check_contact_details(doc)
    assert result.status is Status.PASS
    assert "phone" in result.message


def test_missing_phone_points_to_the_extracted_text_view():
    result = check_contact_details(make_doc(["Anna Testsson", "anna@example.com"]))
    assert result.status is Status.WARN
    assert "What an ATS sees" in result.suggestion


@pytest.mark.parametrize(
    "text",
    ["Ref2024 0101 2025", "ISO27001 certified", "ID0123", "Version 3.10.2024 rev"],
)
def test_digits_glued_to_letters_do_not_create_false_phones(text):
    assert find_phones(f"x {text} y") == []


@pytest.mark.parametrize(
    "text",
    ["2023–2025", "2018-01 – 2019-06", "12345", "Orgnr 1234", "Jan 2023 - Mar 2025", "2019/2021"],
)
def test_dates_and_short_numbers_are_not_phones(text):
    assert find_phones(f"Worked {text} at X") == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("mail anna.testsson@example.com now", ["anna.testsson@example.com"]),
        ("åsa.öberg@exempel.se", ["åsa.öberg@exempel.se"]),
        ("not an email @ here", []),
        ("a@b", []),
    ],
)
def test_email_detection(text, expected):
    assert find_emails(text) == expected


@pytest.mark.parametrize(
    ("lines", "expected"),
    [
        (["Anna Testsson", "QA Engineer"], "Anna Testsson"),
        (["Åsa Öberg-Ängström"], "Åsa Öberg-Ängström"),
        (["ANNA TESTSSON"], "ANNA TESTSSON"),
        (["Curriculum Vitae", "Anna Testsson"], "Anna Testsson"),
        (["Work Experience"], None),
        (["anna testsson"], None),
        (["+46 70 123 45 67"], None),
    ],
)
def test_name_detection(lines, expected):
    assert find_name(lines) == expected
