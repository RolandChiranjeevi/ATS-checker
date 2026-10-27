"""Length and density of the CV."""

from __future__ import annotations

from cv_ats_check.models import CheckResult, ExtractedDocument, JobAd, Status

NAME = "Length and density"
FAIL_BELOW_WORDS = 150
WARN_BELOW_WORDS = 250
WARN_ABOVE_WORDS = 1500
WARN_ABOVE_PAGES = 3


def check_length(doc: ExtractedDocument, job: JobAd | None = None) -> CheckResult:
    """Warn for CVs that are extremely short or long."""
    words = doc.word_count
    size = f"{words} words" + (f" on {doc.page_count} page(s)" if doc.paginated else "")

    if words < FAIL_BELOW_WORDS:
        return CheckResult(
            NAME,
            Status.FAIL,
            f"Extremely short CV ({size}).",
            "Add concrete achievements, tools and responsibilities for each role.",
        )
    if words < WARN_BELOW_WORDS:
        return CheckResult(
            NAME,
            Status.WARN,
            f"Short CV ({size}, below the {WARN_BELOW_WORDS}-word guideline); there may not be "
            "enough text to match keywords.",
            "If this is a deliberately concise CV, make sure tools and technologies are named in "
            "a skills section; otherwise add tools used and measurable results to your bullets.",
        )
    if words > WARN_ABOVE_WORDS or (doc.paginated and doc.page_count > WARN_ABOVE_PAGES):
        return CheckResult(
            NAME,
            Status.WARN,
            f"Long CV ({size}).",
            "Aim for 1-2 pages; cut old or irrelevant roles and keep the most relevant "
            "achievements.",
        )
    return CheckResult(NAME, Status.PASS, f"Reasonable length ({size}).")
