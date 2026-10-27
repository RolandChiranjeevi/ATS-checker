"""Markdown and HTML report generation."""

from __future__ import annotations

import pytest

from cv_ats_check.checks import run_all_checks
from cv_ats_check.extraction import extract_document
from cv_ats_check.models import CheckResult, JobAd, Status
from cv_ats_check.reporting import build_report, render_html, render_markdown
from cv_ats_check.reporting.report_generator import DISCLAIMER_SV
from tests.helpers import make_doc


@pytest.fixture
def report(fixtures_dir, job_en):
    doc = extract_document(fixtures_dir / "cv_normal_en.pdf")
    job = JobAd(job_en.read_text(encoding="utf-8"))
    return build_report(doc, run_all_checks(doc, job), job_provided=True)


def test_markdown_structure(report):
    md = render_markdown(report)
    assert md.startswith("# CV ATS Check")
    assert md.index("## Summary") < md.index("## Details")
    for heading in ("Contact details", "Readable text", "Section headings", "Date consistency"):
        assert f"- {heading}: PASS" in md
    assert "- Job keyword match:" in md and "%" in md
    assert "Found:" in md and "Missing:" in md and "Frequent:" in md


def test_disclaimer_is_present_verbatim(report):
    assert DISCLAIMER_SV in render_markdown(report)
    assert DISCLAIMER_SV in render_html(report)


def test_summary_comes_before_details_and_lists_totals(report):
    md = render_markdown(report)
    assert "**Totals:**" in md
    assert md.index("**Totals:**") < md.index("## Details")


def test_warnings_include_suggestions(fixtures_dir):
    doc = extract_document(fixtures_dir / "cv_no_contact.pdf")
    md = render_markdown(build_report(doc, run_all_checks(doc), job_provided=False))
    assert "FAIL – " in md
    assert "Suggestion:" in md
    assert "not run (no --job given)" in md


def test_non_ascii_survives_in_markdown(fixtures_dir):
    doc = extract_document(fixtures_dir / "cv_swedish.pdf")
    md = render_markdown(build_report(doc, run_all_checks(doc), job_provided=False))
    assert "Arbetslivserfarenhet" in md or "Kompetenser" in md


def test_html_escapes_untrusted_text():
    doc = make_doc(["x"])
    evil = CheckResult("<script>alert(1)</script>", Status.WARN, "<img src=x onerror=alert(1)>")
    html = render_html(build_report(doc, [evil], job_provided=False))
    assert "<script>alert(1)" not in html
    assert "&lt;script&gt;" in html
    assert "<img src=x" not in html


def test_html_has_status_badges(report):
    html = render_html(report)
    assert 'class="badge PASS"' in html
    assert "<title>CV ATS Check" in html
