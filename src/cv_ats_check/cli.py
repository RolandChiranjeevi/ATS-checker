"""Command line interface: ``cv-check --cv cv.pdf --job job_ad.txt --output report.md``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cv_ats_check import __version__
from cv_ats_check.extraction import ExtractionError
from cv_ats_check.models import JobAd, Status
from cv_ats_check.reporting import render_html, render_markdown
from cv_ats_check.service import JobAdError, decode_job_ad, run_check

EXIT_OK = 0
EXIT_FAIL_FOUND = 1
EXIT_USAGE = 2


def read_job_ad(path: Path) -> JobAd:
    """Read a job ad from a local text file (UTF-8, falling back to Windows-1252)."""
    if not path.is_file():
        raise JobAdError(f"Job ad file not found: {path}")
    return decode_job_ad(path.read_bytes(), str(path))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cv-check",
        description="Local, explainable ATS check of a CV (PDF or DOCX). "
        "Nothing leaves your computer.",
    )
    parser.add_argument("--cv", required=True, type=Path, help="CV file (.pdf or .docx)")
    parser.add_argument(
        "--job", type=Path, help="job ad as a local text file (enables keyword checks)"
    )
    parser.add_argument(
        "--output", type=Path, default=Path("report.md"), help="Markdown report path"
    )
    parser.add_argument("--html", type=Path, help="also write an HTML report to this path")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the checker. Returns 0 (no FAIL), 1 (at least one FAIL) or 2 (usage/input error)."""
    args = build_parser().parse_args(argv)
    try:
        job = read_job_ad(args.job) if args.job else None
        report = run_check(args.cv, job)
    except (ExtractionError, JobAdError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_markdown(report), encoding="utf-8")
    if args.html:
        args.html.parent.mkdir(parents=True, exist_ok=True)
        args.html.write_text(render_html(report), encoding="utf-8")

    counts = report.counts()
    print(
        f"{counts[Status.PASS]} PASS, {counts[Status.WARN]} WARN, {counts[Status.FAIL]} FAIL "
        f"-> {args.output}"
    )
    return EXIT_FAIL_FOUND if counts[Status.FAIL] else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
