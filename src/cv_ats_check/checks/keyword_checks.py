"""Job-ad keyword coverage and over-optimisation (keyword stuffing)."""

from __future__ import annotations

from cv_ats_check.models import CheckResult, ExtractedDocument, JobAd, Status
from cv_ats_check.nlp.keywords import analyze_keywords

MATCH_NAME = "Job keyword match"
REPETITION_NAME = "Keyword repetition"
PASS_AT_PCT = 60
WARN_AT_PCT = 30


def check_keyword_match(doc: ExtractedDocument, job: JobAd | None = None) -> CheckResult | None:
    """Share of the ad's keywords that also appear in the CV."""
    if job is None:
        return None
    analysis = analyze_keywords(doc.text, job.text)
    if analysis.total == 0:
        return CheckResult(
            MATCH_NAME,
            Status.WARN,
            "No usable keywords could be extracted from the job ad.",
            "Check that the job ad file contains the full ad text.",
            details={"analysis": analysis},
        )

    pct = analysis.match_pct
    status = (
        Status.PASS if pct >= PASS_AT_PCT else Status.WARN if pct >= WARN_AT_PCT else Status.FAIL
    )
    message = (
        f"{len(analysis.found)} of {analysis.total} keywords from the job ad appear in the CV "
        f"({pct}%)."
    )
    if analysis.job_language != analysis.cv_language:
        message += (
            f" The ad looks {analysis.job_language.upper()} but the CV looks "
            f"{analysis.cv_language.upper()}; matching is literal, so terms in the other language "
            "count as missing."
        )
    suggestion = ""
    if analysis.missing:
        suggestion = (
            "Add the missing terms you genuinely have experience with, using the ad's wording."
        )
    return CheckResult(MATCH_NAME, status, message, suggestion, details={"analysis": analysis})


def check_keyword_repetition(
    doc: ExtractedDocument, job: JobAd | None = None
) -> CheckResult | None:
    """Warn when a job keyword is repeated far more often than the CV length justifies."""
    if job is None:
        return None
    analysis = analyze_keywords(doc.text, job.text)
    if analysis.total == 0:
        return None
    if not analysis.frequent:
        return CheckResult(
            REPETITION_NAME,
            Status.PASS,
            f"No keyword is repeated more than {analysis.threshold} times.",
            details={"analysis": analysis},
        )
    listed = ", ".join(f"{k.term} ({k.cv_count} times)" for k in analysis.frequent)
    return CheckResult(
        REPETITION_NAME,
        Status.WARN,
        f"Possible over-optimisation (limit {analysis.threshold} for {analysis.cv_word_count} "
        f"words): {listed}.",
        "Use each keyword where it is natural; keyword stuffing can be penalised by "
        "recruiters and some ATS filters.",
        details={"analysis": analysis},
    )
