"""Swedish/English alias matching, compound words, contractions and boilerplate."""

from __future__ import annotations

import pytest

from cv_ats_check.extraction import extract_document
from cv_ats_check.nlp.keywords import analyze_keywords, extract_job_keywords
from cv_ats_check.nlp.normalize import tokenize


def terms(keywords) -> set[str]:
    return {k.term for k in keywords}


def analyze(job_term: str, cv_text: str):
    return analyze_keywords(cv_text, f"Requirements\n- {job_term}\n")


@pytest.mark.parametrize(
    ("job_term", "cv_text"),
    [
        ("test automation", "Erfarenhet av testautomatisering"),
        ("automated testing", "automatiserad testning av webb"),
        ("manual testing", "manuell testning"),
        ("test cases", "skrev testfall"),
        ("quality assurance", "arbetade med kvalitetssäkring"),
        ("agile", "agila arbetssätt"),
        ("cross functional", "tvärfunktionella team"),
        ("performance testing", "prestandatester"),
        ("test strategy", "teststrategi"),
        ("unit testing", "enhetstester"),
        ("testing", "mjukvarutestare"),
        ("regressionstest", "regression testing"),
        ("testfall", "test cases"),
        ("teststrategi", "test strategy"),
    ],
)
def test_alias_pairs_match_across_languages(job_term, cv_text):
    assert job_term in terms(analyze(job_term, cv_text).found)


@pytest.mark.parametrize(
    ("job_term", "cv_text"),
    [
        ("testing", "Jag ska attestera fakturor"),
        ("testing", "the latest release"),
        ("agile", "I enjoy gardening"),
        ("quality assurance", "kvalitet"),
        ("test automation", "automation of invoices"),
    ],
)
def test_unrelated_words_do_not_match(job_term, cv_text):
    assert job_term in terms(analyze(job_term, cv_text).missing)


def test_a_word_is_counted_once_even_if_several_variants_match():
    analysis = analyze("agile", "agila agila")
    assert analysis.found[0].cv_count == 2


def test_swedish_cv_matches_english_ad(fixtures_dir, job_en):
    doc = extract_document(fixtures_dir / "cv_swedish.pdf")
    analysis = analyze_keywords(doc.text, job_en.read_text(encoding="utf-8"))
    assert {"api testing", "test strategy", "regression testing", "agile", "playwright"} <= terms(
        analysis.found
    )
    assert analysis.match_pct >= 40


def test_english_cv_matches_swedish_ad(fixtures_dir, job_sv):
    doc = extract_document(fixtures_dir / "cv_normal_en.pdf")
    analysis = analyze_keywords(doc.text, job_sv.read_text(encoding="utf-8"))
    assert {"teststrategi", "api testning", "regressionstester", "agila metoder"} <= terms(
        analysis.found
    )


def test_contractions_do_not_leak_into_tokens():
    assert tokenize("You'll don't it’s we're") == ["you", "do", "it", "we"]


def test_contraction_fragments_are_not_keywords():
    keywords = terms(extract_job_keywords("Requirements\n- You'll work with Selenium\n"))
    assert "ll" not in keywords
    assert "selenium" in keywords


@pytest.mark.parametrize(
    ("job_term", "cv_text"),
    [
        ("testing", "Jag har testat och testar webbapplikationer"),
        ("testing", "Testerna kördes varje natt"),
        ("testing", "Testningen tog två dagar"),
        ("quality", "Kvaliteten är viktig"),
        ("project", "Projektet levererades"),
        ("documentation", "Dokumentationen uppdaterades"),
        ("database", "Databaserna migrerades"),
        ("agile", "Vi arbetar agilt"),
        ("kvalitet", "quality"),
        ("testning", "testing"),
        ("projektet", "project"),
    ],
)
def test_swedish_inflections_match_across_languages(job_term, cv_text):
    assert job_term in terms(analyze(job_term, cv_text).found)


@pytest.mark.parametrize(
    ("job_term", "cv_text"),
    [
        ("testing", "Han var en testimonial"),
        ("testing", "attestering av fakturor"),
        ("quality", "kvalificerad"),
        ("project", "projektil"),
        ("database", "datastruktur"),
    ],
)
def test_words_that_only_look_similar_do_not_inflect_into_a_match(job_term, cv_text):
    assert job_term in terms(analyze(job_term, cv_text).missing)


def test_inflected_forms_are_counted_once_each():
    analysis = analyze("testing", "test tester testning")
    assert analysis.found[0].cv_count == 3


def test_generic_adjectives_are_not_keywords():
    ad = "Requirements\n- Clear analytical thinking and relevant qualifications\n- Selenium\n"
    keywords = terms(extract_job_keywords(ad))
    assert not keywords & {"clear", "analytical", "qualifications"}
    assert "selenium" in keywords
