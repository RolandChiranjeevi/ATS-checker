"""Date format detection and consistency."""

from __future__ import annotations

import pytest

from cv_ats_check.checks.date_checks import check_dates, find_dates
from cv_ats_check.extraction import extract_document
from cv_ats_check.models import Status
from tests.helpers import make_doc


@pytest.mark.parametrize(
    ("text", "label"),
    [
        ("2023–2025", "YYYY – YYYY"),
        ("2023-2025", "YYYY – YYYY"),
        ("2023 - nu", "YYYY – YYYY"),
        ("2021 – pågående", "YYYY – YYYY"),
        ("2023/2025", "YYYY/YYYY"),
        ("Jan 2023 – Mar 2025", "Mon YYYY – Mon YYYY"),
        ("januari 2023 - present", "Mon YYYY – Mon YYYY"),
        ("Maj 2020 – Okt 2022", "Mon YYYY – Mon YYYY"),
        ("2023-01 – 2025-03", "YYYY-MM – YYYY-MM"),
        ("01/2023 – 03/2025", "MM/YYYY – MM/YYYY"),
        ("March 2024", "Mon YYYY"),
        ("2024-06", "YYYY-MM"),
    ],
)
def test_format_is_classified(text, label):
    matches = find_dates(f"Worked {text} at X")
    assert [m.label for m in matches] == [label]


@pytest.mark.parametrize("text", ["no dates here", "Version 12", "Orgnr 556677", "Room 1234"])
def test_non_dates_are_ignored(text):
    assert find_dates(text) == []


def test_each_text_span_is_counted_once():
    matches = find_dates("2018-01 – 2019-06")
    assert len(matches) == 1


def test_consistent_dates_pass():
    result = check_dates(make_doc(["Acme 2022–2025", "Beta 2019–2022", "Uni 2015–2018"]))
    assert result.status is Status.PASS


def test_consistent_month_style_passes_with_single_dates():
    doc = make_doc(["Acme Jan 2022 – Mar 2025", "Certificate Feb 2021"])
    assert check_dates(doc).status is Status.PASS


def test_mixed_formats_warn(fixtures_dir):
    result = check_dates(extract_document(fixtures_dir / "cv_mixed_dates.pdf"))
    assert result.status is Status.WARN
    assert "mixed date formats" in result.message
    assert "YYYY/YYYY" in result.message
    assert result.suggestion


def test_hyphen_and_en_dash_mix_warns():
    result = check_dates(make_doc(["Acme 2022-2025", "Beta 2019–2022"]))
    assert result.status is Status.WARN
    assert "hyphens" in result.message


def test_ambiguous_slash_range_warns_even_alone():
    result = check_dates(make_doc(["Acme 2019/2021"]))
    assert result.status is Status.WARN
    assert "ambiguous" in result.message


def test_no_dates_warns():
    result = check_dates(make_doc(["Worked at Acme", "Studied at Uni"]))
    assert result.status is Status.WARN
    assert "No dates" in result.message


def test_normal_fixture_is_consistent(fixtures_dir):
    result = check_dates(extract_document(fixtures_dir / "cv_normal_en.pdf"))
    assert result.status is Status.PASS
