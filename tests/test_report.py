"""Markdown and HTML report generation."""

from __future__ import annotations

import base64

import pytest

from cv_ats_check.checks import run_all_checks
from cv_ats_check.extraction import extract_document
from cv_ats_check.models import CheckResult, JobAd, Status
from cv_ats_check.reporting import build_report, download_links, render_html, render_markdown
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


def test_html_shows_extracted_text_in_reading_order(report):
    html = render_html(report)
    assert "What an ATS sees" in html
    text = html[html.index('<pre class="ats-text">') :]
    assert text.index("Anna Testsson") < text.index("Experience") < text.index("Education")
    assert "Page 1" in html


def test_markdown_does_not_embed_the_cv_text(report):
    assert "What an ATS sees" not in render_markdown(report)


def test_docx_text_view_has_no_page_labels(fixtures_dir):
    doc = extract_document(fixtures_dir / "cv_normal.docx")
    html = render_html(build_report(doc, run_all_checks(doc), job_provided=False))
    assert "What an ATS sees" in html
    assert "Page 1" not in html


def test_extracted_text_is_escaped():
    doc = make_doc(["Anna Testsson", "<b>bold</b> <script>alert(1)</script>"])
    html = render_html(build_report(doc, [], job_provided=False))
    assert "<script>alert(1)" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_download_links_decode_to_the_reports(report):
    links = download_links(report)
    assert [name for _, name, _ in links] == [
        "cv_normal_en-ats-report.md",
        "cv_normal_en-ats-report.html",
    ]
    decoded = [_decode(href) for _, _, href in links]
    assert decoded[0] == render_markdown(report)
    assert decoded[1] == render_html(report)
    assert "Download" not in decoded[1]


def test_page_shows_download_links_only_when_asked(report):
    assert "download=" not in render_html(report)
    page = render_html(report, downloads=download_links(report))
    assert page.count("download=") == 2
    assert "data:text/markdown;charset=utf-8;base64," in page


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("cv.pdf", "cv-ats-report.md"),
        ("Åsa Öberg CV (final).docx", "Åsa_Öberg_CV_final-ats-report.md"),
        ('"><img src=x>.pdf', "img_src_x-ats-report.md"),
        ("...", "cv-ats-report.md"),
    ],
)
def test_download_file_names_are_sanitised(report, source, expected):
    report.source = source
    assert download_links(report)[0][1] == expected


def _decode(data_url: str) -> str:
    return base64.b64decode(data_url.split("base64,", 1)[1]).decode()


def test_html_has_status_badges(report):
    html = render_html(report)
    assert 'class="badge PASS"' in html
    assert "<title>CV ATS Check" in html
