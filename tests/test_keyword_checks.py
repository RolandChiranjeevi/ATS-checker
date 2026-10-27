"""Keyword extraction, matching and over-optimisation."""

from __future__ import annotations

import pytest

from cv_ats_check.checks.keyword_checks import check_keyword_match, check_keyword_repetition
from cv_ats_check.extraction import extract_document
from cv_ats_check.models import JobAd, Status
from cv_ats_check.nlp.keywords import (
    analyze_keywords,
    count_sequence,
    extract_job_keywords,
    frequency_threshold,
    requirement_text,
)
from cv_ats_check.nlp.normalize import stem, tokenize
from cv_ats_check.nlp.stopwords import detect_language
from tests.helpers import make_doc


def terms(keywords) -> set[str]:
    return {k.term for k in keywords}


# --- tokenisation ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("CI/CD and Node.js", ["ci/cd", "and", "node.js"]),
        ("C++ och C#", ["c++", "och", "c#"]),
        ("Åsa söker tjänst i Göteborg", ["åsa", "söker", "tjänst", "i", "göteborg"]),
        ("API-testning 2024", ["api", "testning"]),
        ("end-to-end", ["end", "to", "end"]),
    ],
)
def test_tokenize(text, expected):
    assert tokenize(text) == expected


def test_unicode_normal_forms_match():
    decomposed = "Åsa"  # A + combining ring
    assert tokenize(decomposed) == tokenize("Åsa")


@pytest.mark.parametrize(
    ("word", "expected"), [("tests", "test"), ("class", "class"), ("aws", "aws"), ("api", "api")]
)
def test_stem(word, expected):
    assert stem(word) == expected


def test_count_sequence_is_non_overlapping():
    assert count_sequence(list("aaaa"), ("a", "a")) == 2
    assert count_sequence(["a"], ()) == 0
    assert count_sequence(["x", "api", "testing"], ("api", "testing")) == 1


# --- extraction from job ads ----------------------------------------------------------------


def test_english_ad_keywords(job_en):
    keywords = terms(extract_job_keywords(job_en.read_text(encoding="utf-8")))
    assert {"playwright", "selenium", "ci/cd", "jmeter", "jira", "istqb"} <= keywords
    assert not keywords & {"the", "and", "experience", "knowledge"}


def test_swedish_ad_keywords(job_sv):
    keywords = terms(extract_job_keywords(job_sv.read_text(encoding="utf-8")))
    assert {"playwright", "selenium", "ci/cd", "jmeter", "jira", "teststrategi"} <= keywords
    assert not keywords & {"och", "att", "erfarenhet", "kunskap"}


def test_requirement_section_is_isolated(job_en):
    section = requirement_text(job_en.read_text(encoding="utf-8"))
    assert "Playwright" in section
    assert "friendly team" not in section
    assert "logistics" not in section


def test_phrase_swallows_contained_unigram():
    keywords = terms(extract_job_keywords("We need regression testing. Regression testing daily."))
    assert "regression testing" in keywords
    assert "regression" not in keywords


def test_keyword_list_is_capped():
    ad = "Requirements\n" + "\n".join(f"- skill{i}tool" for i in range(80))
    assert len(extract_job_keywords(ad)) <= 25


def test_empty_ad_has_no_keywords():
    assert extract_job_keywords("") == []
    assert extract_job_keywords("the and of to") == []


# --- matching -------------------------------------------------------------------------------


def test_english_cv_against_english_ad(fixtures_dir, job_en):
    doc = extract_document(fixtures_dir / "cv_normal_en.pdf")
    analysis = analyze_keywords(doc.text, job_en.read_text(encoding="utf-8"))
    assert {"playwright", "selenium", "ci/cd", "jira", "istqb"} <= terms(analysis.found)
    assert {"jmeter", "k6", "docker"} <= terms(analysis.missing)
    assert 40 <= analysis.match_pct <= 90


def test_swedish_cv_against_swedish_ad(fixtures_dir, job_sv):
    doc = extract_document(fixtures_dir / "cv_swedish.pdf")
    analysis = analyze_keywords(doc.text, job_sv.read_text(encoding="utf-8"))
    assert {"playwright", "jira", "teststrategi"} <= terms(analysis.found)
    assert "jmeter" in terms(analysis.missing)
    assert analysis.job_language == analysis.cv_language == "sv"


def test_language_mismatch_is_reported(fixtures_dir, job_sv):
    doc = extract_document(fixtures_dir / "cv_normal_en.pdf")
    result = check_keyword_match(doc, JobAd(job_sv.read_text(encoding="utf-8")))
    assert "looks SV but the CV looks EN" in result.message


@pytest.mark.parametrize(
    ("cv_text", "expected"),
    [
        ("Python Playwright Selenium Jira " * 5, Status.PASS),
        ("Python Playwright", Status.WARN),
        ("I like gardening and cooking", Status.FAIL),
    ],
)
def test_match_status_thresholds(cv_text, expected):
    ad = JobAd("Requirements\n- Python\n- Playwright\n- Selenium\n- Jira\n")
    assert check_keyword_match(make_doc([cv_text]), ad).status is expected


def test_plural_forms_match():
    analysis = analyze_keywords("I write many tests", "Requirements\n- test\n")
    assert "test" in terms(analysis.found)


def test_check_is_skipped_without_job_ad(fixtures_dir):
    doc = extract_document(fixtures_dir / "cv_normal_en.pdf")
    assert check_keyword_match(doc, None) is None
    assert check_keyword_repetition(doc, None) is None


def test_unusable_ad_warns():
    result = check_keyword_match(make_doc(["Python"]), JobAd("the and of"))
    assert result.status is Status.WARN
    assert check_keyword_repetition(make_doc(["Python"]), JobAd("the and of")) is None


# --- over-optimisation ----------------------------------------------------------------------


def test_keyword_stuffing_is_flagged():
    ad = JobAd("Requirements\n- Playwright\n- Selenium\n")
    doc = make_doc(["Playwright " * 20 + "Selenium"])
    result = check_keyword_repetition(doc, ad)
    assert result.status is Status.WARN
    assert "playwright (20 times)" in result.message
    assert "selenium" not in result.message


def test_normal_repetition_passes():
    ad = JobAd("Requirements\n- Playwright\n- Selenium\n")
    doc = make_doc(["Playwright " * 5 + "Selenium " * 3])
    assert check_keyword_repetition(doc, ad).status is Status.PASS


@pytest.mark.parametrize(
    ("words", "expected"), [(0, 10), (300, 10), (833, 10), (1000, 12), (2000, 24)]
)
def test_threshold_scales_with_length(words, expected):
    assert frequency_threshold(words) == expected


def test_same_count_is_ok_in_a_long_cv_but_flagged_in_a_short_one():
    ad = JobAd("Requirements\n- Playwright\n")
    filler = "lorem " * 1500
    long_cv = make_doc(["Playwright " * 14 + filler])
    short_cv = make_doc(["Playwright " * 14])
    assert check_keyword_repetition(long_cv, ad).status is Status.PASS
    assert check_keyword_repetition(short_cv, ad).status is Status.WARN


def test_detect_language():
    assert detect_language("Vi söker en testare som har erfarenhet av att testa") == "sv"
    assert detect_language("We are looking for a tester with experience of the tools") == "en"
