"""The registry of all checks."""

from __future__ import annotations

from cv_ats_check.checks.base import CheckFn
from cv_ats_check.checks.contact_checks import check_contact_details
from cv_ats_check.checks.date_checks import check_dates
from cv_ats_check.checks.heading_checks import check_headings
from cv_ats_check.checks.hygiene_checks import check_hygiene
from cv_ats_check.checks.keyword_checks import check_keyword_match, check_keyword_repetition
from cv_ats_check.checks.layout_checks import (
    check_header_footer,
    check_layout,
    check_special_characters,
)
from cv_ats_check.checks.length_checks import check_length
from cv_ats_check.checks.readable_text_checks import check_readable_text
from cv_ats_check.models import CheckResult, ExtractedDocument, JobAd

ALL_CHECKS: tuple[CheckFn, ...] = (
    check_readable_text,
    check_layout,
    check_header_footer,
    check_special_characters,
    check_contact_details,
    check_headings,
    check_dates,
    check_length,
    check_hygiene,
    check_keyword_match,
    check_keyword_repetition,
)


def run_all_checks(doc: ExtractedDocument, job: JobAd | None = None) -> list[CheckResult]:
    """Run every applicable check, skipping those that return None."""
    results = (check(doc, job) for check in ALL_CHECKS)
    return [r for r in results if r is not None]
