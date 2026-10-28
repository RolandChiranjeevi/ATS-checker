"""Must-have vs nice-to-have tiers and the weighted keyword score."""

from __future__ import annotations

import pytest

from cv_ats_check.checks.keyword_checks import check_keyword_match
from cv_ats_check.models import JobAd, Status
from cv_ats_check.nlp.keywords import analyze_keywords, extract_job_keywords, tier_texts
from cv_ats_check.reporting import build_report, render_markdown
from tests.helpers import make_doc

AD = "Requirements\n- Python\n- Selenium\n\nNice to have\n- Docker\n"


def tiers(ad: str) -> dict[str, str]:
    return {k.term: k.tier for k in extract_job_keywords(ad)}


def test_requirements_are_must_and_nice_to_have_is_nice():
    assert tiers(AD) == {"python": "must", "selenium": "must", "docker": "nice"}


def test_ad_without_headings_has_only_general_keywords():
    result = tiers("We use Python and Selenium and Docker every day.")
    assert set(result.values()) == {"general"}


def test_inline_markers_make_a_line_nice_to_have_even_outside_a_section():
    ad = "Requirements\n- Python\n\nAbout us\nExperience with Docker is a plus.\n"
    assert tiers(ad)["docker"] == "nice"
    assert tiers(ad)["python"] == "must"


@pytest.mark.parametrize(
    "line",
    ["- Docker (meriterande)", "- Docker, gärna", "- Docker är en fördel", "- Docker, preferably"],
)
def test_inline_nice_markers_in_both_languages(line):
    ad = f"Krav\n- Python\n{line}\n"
    assert tiers(ad)["docker"] == "nice"


def test_a_term_in_both_sections_counts_as_must():
    ad = "Requirements\n- Python\n\nNice to have\n- Python advanced\n"
    assert tiers(ad)["python"] == "must"


def test_tier_texts_split_the_fixture_ads(job_en, job_sv):
    must, nice = tier_texts(job_en.read_text(encoding="utf-8"))
    assert "Playwright" in must and "friendly team" not in must
    assert "ISTQB" in nice and "Docker" in nice
    must_sv, nice_sv = tier_texts(job_sv.read_text(encoding="utf-8"))
    assert "Playwright" in must_sv
    assert "ISTQB" in nice_sv and "Docker" in nice_sv


def test_weights_make_a_missing_must_have_cost_more_than_a_missing_nice_to_have():
    only_must = analyze_keywords("Python Selenium", AD)
    only_nice = analyze_keywords("Docker", AD)
    assert only_must.score_pct == 86  # (3 + 3) / (3 + 3 + 1)
    assert only_nice.score_pct == 14  # 1 / 7
    assert only_must.match_pct == 67 and only_nice.match_pct == 33  # the plain share


def test_without_tiers_the_score_equals_the_plain_share():
    analysis = analyze_keywords("Python", "We use Python and Selenium and Docker daily.")
    assert not analysis.has_tiers
    assert analysis.score_pct == analysis.match_pct


def test_tier_counts():
    counts = analyze_keywords("Python Docker", AD).tier_counts()
    assert counts["must"] == (1, 2)
    assert counts["nice"] == (1, 1)
    assert counts["general"] == (0, 0)


@pytest.mark.parametrize(
    ("cv_text", "expected"),
    [("Python Selenium Docker", Status.PASS), ("Docker", Status.FAIL), ("Python", Status.WARN)],
)
def test_status_follows_the_weighted_score(cv_text, expected):
    assert check_keyword_match(make_doc([cv_text]), JobAd(AD)).status is expected


def test_message_explains_the_weighting():
    result = check_keyword_match(make_doc(["Docker"]), JobAd(AD))
    assert "weights must-have terms x3" in result.message
    assert "must-have 0/2" in result.message and "nice-to-have 1/1" in result.message


def test_message_stays_plain_when_the_ad_has_no_tiers():
    result = check_keyword_match(make_doc(["Python"]), JobAd("We use Python and Selenium."))
    assert "weights" not in result.message


def test_report_lists_missing_must_and_nice_separately():
    doc = make_doc(["Python"])
    result = check_keyword_match(doc, JobAd(AD))
    md = render_markdown(build_report(doc, [result], job_provided=True))
    assert "Missing must-have: selenium" in md
    assert "Missing nice-to-have: docker" in md
    assert "- Job keyword match: 43% (WARN)" in md  # the weighted score, not the plain 33 %
