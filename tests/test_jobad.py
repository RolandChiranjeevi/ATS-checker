"""Job ad requirements: experience, languages, work mode, location, degree."""

from __future__ import annotations

import pytest

from cv_ats_check.checks import run_all_checks
from cv_ats_check.checks.jobad_checks import check_job_requirements, estimate_experience_years
from cv_ats_check.extraction import extract_document
from cv_ats_check.models import JobAd, Status
from cv_ats_check.nlp.jobad import (
    find_education_requirements,
    find_experience_requirements,
    find_language_requirements,
    find_locations,
    find_work_modes,
    mentions_language,
    parse_job_requirements,
)
from tests.helpers import make_doc

# --- parsing ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("line", "years", "upper"),
    [
        ("3+ years of experience in QA", 3, None),
        ("At least 5 years' experience with test automation", 5, None),
        ("3-5 years experience of testing", 3, 5),
        ("2 yrs experience", 2, None),
        ("Minst 3 års erfarenhet av testning", 3, None),
        ("2–4 års erfarenhet", 2, 4),
        ("Erfarenhet: 5+ år", 5, None),
    ],
)
def test_experience_requirements(line, years, upper):
    (found,) = find_experience_requirements(line)
    assert (found.years, found.upper) == (years, upper)


@pytest.mark.parametrize(
    "line",
    [
        "Founded 10 years ago",
        "We have 20 years of history",
        "0 years of experience",
        "100 years of experience",
        "45 years experience",
        "Experience with Python",
    ],
)
def test_lines_that_are_not_experience_requirements_are_ignored(line):
    assert find_experience_requirements(line) == []


def test_several_requirements_and_labels():
    found = find_experience_requirements("3+ years QA experience, 1 year automation")
    assert [r.years for r in found] == [3, 1]
    assert find_experience_requirements("3-5 years experience")[0].label == "3-5 years"
    assert found[0].label == "3+ years"


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("Fluent in English and Swedish", ["Swedish", "English"]),
        ("Flytande svenska och engelska i tal och skrift", ["Swedish", "English"]),
        ("Norwegian is required", ["Norwegian"]),
        ("You speak German", ["German"]),
        ("Goda kunskaper i danska", ["Danish"]),
        ("We are a Swedish company", []),
        ("No languages here", []),
    ],
)
def test_language_requirements(line, expected):
    assert find_language_requirements(line) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Hybrid work, two days remote", ["remote", "hybrid"]),
        ("Arbetet sker på plats i Karlstad", ["on-site"]),
        ("Fully remote position", ["remote"]),
        ("Hemarbete möjligt", ["remote"]),
        ("Nothing about where", []),
    ],
)
def test_work_modes(text, expected):
    assert find_work_modes(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Location: Stockholm", ["Stockholm"]),
        ("Plats: Karlstad", ["Karlstad"]),
        ("Arbetsplats - Göteborg", ["Göteborg"]),
        ("We are based in Stockholm and Malmö.", ["Stockholm"]),
        ("Baserad i Göteborg", ["Göteborg"]),
        ("Office in New York", ["New York"]),
        ("We sit based in the city centre", []),
        ("Location: Stockholm\nbased in Stockholm", ["Stockholm"]),
    ],
)
def test_locations(text, expected):
    assert find_locations(text) == expected


def test_education_requirements_are_limited_and_deduplicated():
    ad = (
        "Bachelor's degree in IT\nHögskoleutbildning inom IT\n"
        "University degree\nBachelor's degree in IT"
    )
    found = find_education_requirements(ad)
    assert found == ["Bachelor's degree in IT", "Högskoleutbildning inom IT"]
    assert find_education_requirements("Experience with Python") == []


@pytest.mark.parametrize(
    ("cv_text", "language", "cv_language", "expected"),
    [
        ("Jag talar svenska", "Swedish", "en", True),
        ("English fluent", "English", "sv", True),
        ("Python only", "Norwegian", "en", False),
        ("Python only", "Swedish", "sv", True),  # a Swedish CV is itself evidence
        ("Python only", "English", "sv", False),
        ("Python only", "English", "en", True),
    ],
)
def test_mentions_language(cv_text, language, cv_language, expected):
    assert mentions_language(cv_text, language, cv_language) is expected


def test_parse_job_requirements_and_is_empty():
    assert parse_job_requirements("We build software.").is_empty
    parsed = parse_job_requirements("Location: Stockholm\n3+ years of experience\nHybrid work")
    assert not parsed.is_empty
    assert parsed.locations == ("Stockholm",)
    assert parsed.work_modes == ("hybrid",)
    assert parsed.experience[0].years == 3


# --- experience estimate ---------------------------------------------------------------------


def test_estimate_uses_only_the_experience_section():
    doc = make_doc(["Experience", "Acme 2022–2025", "Beta 2019–2022", "Education", "Uni 2010–2014"])
    assert estimate_experience_years(doc, today_year=2026) == 6


def test_estimate_handles_open_ended_ranges():
    doc = make_doc(["Experience", "Acme Jan 2023 – Present"])
    assert estimate_experience_years(doc, today_year=2026) == 3


def test_estimate_falls_back_to_the_whole_cv_without_an_experience_heading():
    assert estimate_experience_years(make_doc(["Acme 2018–2020"]), today_year=2026) == 2


def test_estimate_caps_future_dates_and_returns_none_without_dates():
    assert estimate_experience_years(make_doc(["Acme 2020–2040"]), today_year=2026) == 6
    assert estimate_experience_years(make_doc(["Worked at Acme"]), today_year=2026) is None


# --- the check -------------------------------------------------------------------------------

CV = [
    "Anna Testsson",
    "Experience",
    "Acme AB 2019–2025",
    "Education",
    "Uni 2015–2018",
    "English and Swedish fluent",
]
RICH_AD = (
    "QA Engineer\nLocation: Stockholm\nHybrid work\n3+ years of experience in testing\n"
    "Fluent in English and Norwegian\nBachelor's degree\n"
)


def facts_by_label(result):
    return {fact.label: fact for fact in result.facts}


def test_check_is_skipped_without_a_job_ad():
    assert check_job_requirements(make_doc(CV), None) is None


def test_ad_without_explicit_requirements_passes_with_an_explanation():
    result = check_job_requirements(make_doc(CV), JobAd("We build software for logistics."))
    assert result.status is Status.PASS
    assert "No explicit" in result.message
    assert result.facts == []


def test_rich_ad_is_itemised_and_a_missing_language_warns():
    result = check_job_requirements(make_doc(CV), JobAd(RICH_AD), today_year=2026)
    facts = facts_by_label(result)
    assert set(facts) == {
        "Experience asked for",
        "Languages asked for",
        "Work mode",
        "Location",
        "Education asked for",
    }
    assert result.status is Status.WARN
    assert "Norwegian" in result.message and "Swedish" not in result.message
    assert facts["Languages asked for"].status is Status.WARN
    assert "Not mentioned in your CV: Norwegian" in facts["Languages asked for"].note
    assert facts["Work mode"].value == "hybrid"
    assert "Not mentioned in your CV: Stockholm" in facts["Location"].note
    assert facts["Experience asked for"].value.startswith("3+ years")
    assert "about 6 year(s)" in facts["Experience asked for"].note
    assert "Languages section" in result.suggestion


def test_experience_shorter_than_the_ad_asks_is_explained_but_not_a_warning():
    ad = "8+ years of experience in testing"
    result = check_job_requirements(make_doc(CV), JobAd(ad), today_year=2026)
    assert result.status is Status.PASS
    assert "shorter than the ad asks" in result.facts[0].note


def test_satisfied_requirements_pass():
    result = check_job_requirements(make_doc(CV), JobAd("Fluent in English"))
    assert result.status is Status.PASS
    assert result.facts[0].status is Status.PASS
    assert "Read 1 requirement(s)" in result.message


def test_location_found_in_the_cv_is_noted():
    doc = make_doc([*CV, "Stockholm"])
    result = check_job_requirements(doc, JobAd("Location: Stockholm"))
    assert result.facts[0].note == "In your CV: Stockholm."
    assert result.status is Status.PASS


def test_swedish_cv_counts_as_swedish_but_not_as_english(fixtures_dir):
    doc = extract_document(fixtures_dir / "cv_swedish.pdf")
    result = check_job_requirements(doc, JobAd("Svenska och engelska krävs i tal och skrift"))
    assert result.status is Status.WARN
    assert "English" in result.message and "Swedish" not in result.message


def test_the_check_is_part_of_the_normal_run_only_with_a_job_ad(fixtures_dir):
    doc = extract_document(fixtures_dir / "cv_normal_en.pdf")
    assert "Job ad requirements" not in [r.name for r in run_all_checks(doc)]
    names = [r.name for r in run_all_checks(doc, JobAd("Location: Stockholm"))]
    assert "Job ad requirements" in names
