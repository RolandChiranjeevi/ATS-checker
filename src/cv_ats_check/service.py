"""The check pipeline shared by the CLI and the local web UI."""

from __future__ import annotations

from pathlib import Path

from cv_ats_check.checks import run_all_checks
from cv_ats_check.extraction import extract_document
from cv_ats_check.models import JobAd
from cv_ats_check.reporting import Report, build_report


class JobAdError(Exception):
    """The job ad could not be read or is empty."""


def decode_job_ad(raw: bytes, label: str) -> JobAd:
    """Decode job ad bytes (UTF-8, falling back to Windows-1252) and reject empty ads."""
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252", errors="replace")
    if not text.strip():
        raise JobAdError(f"Job ad file is empty: {label}")
    return JobAd(text=text)


def run_check(cv_path: Path, job: JobAd | None, source: str | None = None) -> Report:
    """Extract the CV, run every applicable check and assemble a report.

    ``source`` overrides the file name shown in the report (used for uploads).
    Raises an ``ExtractionError`` subclass if the CV cannot be read.
    """
    doc = extract_document(cv_path)
    results = run_all_checks(doc, job)
    return build_report(doc, results, job_provided=job is not None, source=source)
