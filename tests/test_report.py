"""Markdown and HTML report generation."""

from __future__ import annotations

import base64
import re

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


def test_markdown_lists_the_checked_hygiene_items(report):
    md = render_markdown(report)
    section = md[md.index("### Document hygiene") :]
    assert "Checked:" in section
    assert "- File name: cv_normal_en.pdf – PASS" in section
    assert "- Author property: Anna Testsson – PASS (Matches the name in the CV.)" in section
    assert "- Encryption: none – PASS" in section


def test_html_renders_facts_as_a_table_with_info_badges(report):
    html = render_html(report)
    assert '<table class="facts">' in html
    assert '<span class="badge INFO">INFO</span>' in html
    assert (
        '<td data-label="Item">File name</td><td data-label="Value">cv_normal_en.pdf</td>' in html
    )


def _with_one_warning(report):
    from cv_ats_check.models import CheckResult

    warning = CheckResult("Length and density", Status.FAIL, "Extremely short CV.", "Add more.")
    return build_report(make_doc(["Anna Testsson"]), [*report.results, warning], job_provided=True)


def test_html_lists_what_needs_attention_before_what_passed(report):
    html = render_html(_with_one_warning(report))
    assert html.index('id="attention-heading"') < html.index('id="passed-heading"')
    attention = html[html.index('id="attention-heading"') : html.index('id="passed-heading"')]
    assert "Length and density" in attention and "Extremely short CV." in attention
    assert "Contact details" not in attention  # passed checks are collapsed further down


def test_failures_are_listed_before_warnings():
    from cv_ats_check.models import CheckResult

    results = [
        CheckResult("Warned", Status.WARN, "w"),
        CheckResult("Failed", Status.FAIL, "f"),
    ]
    html = render_html(build_report(make_doc(["x"]), results, job_provided=False))
    attention = html[html.index('id="attention-heading"') : html.index('id="passed-heading"')]
    assert attention.index("Failed") < attention.index("Warned")


def test_a_clean_report_says_nothing_needs_attention(report):
    passed = [r for r in report.results if r.status is Status.PASS]
    html = render_html(build_report(make_doc(["Anna Testsson"]), passed, job_provided=True))
    assert "Nothing needs attention." in html
    assert 'id="attention-heading"' not in html


def test_job_card_shows_score_tiers_and_missing_terms(report):
    html = render_html(report)
    assert 'aria-labelledby="job-heading"' in html
    assert "Match against the job ad" in html
    assert 'class="num"' in html and "weighted keyword score" in html
    assert "Missing must-have" in html and 'class="chips missing-must"' in html
    assert "Found in your CV (" in html


def test_a_check_that_was_not_run_is_skipped_not_passed(fixtures_dir):
    doc = extract_document(fixtures_dir / "cv_normal_en.pdf")
    report = build_report(doc, run_all_checks(doc), job_provided=False)
    row = next(r for r in report.summary_rows() if r.name == "Job keyword match")
    assert row.status is None

    html = render_html(report)
    badge = re.search(r'<li><span class="badge (\w+)">(\w+)</span> Job keyword match', html)
    assert badge and badge.groups() == ("SKIPPED", "SKIPPED")
    assert "- Job keyword match: not run (no --job given)" in render_markdown(report)
    # the totals only count checks that actually ran
    assert f"{report.counts()[Status.PASS]} PASS" in html


def test_no_job_card_without_an_ad(fixtures_dir):
    doc = extract_document(fixtures_dir / "cv_normal_en.pdf")
    html = render_html(build_report(doc, run_all_checks(doc), job_provided=False))
    assert "Match against the job ad" not in html
    assert "not run (no --job given)" in html


def test_every_check_has_an_anchor_that_the_overview_links_to(report):
    html = render_html(report)
    for name in ("Contact details", "Document hygiene", "Job keyword match"):
        anchor = "check-" + name.casefold().replace(" ", "-")
        assert f'id="{anchor}"' in html, name
        assert f'href="#{anchor}"' in html, name


def test_html_ids_are_unique(report):
    from cv_ats_check.models import CheckResult

    extra = CheckResult("Extra failing check", Status.FAIL, "Broken.", "Fix it.")
    doc = make_doc(["Anna Testsson"])
    html = render_html(build_report(doc, [*report.results, extra], job_provided=True))
    ids = re.findall(r'\sid="([^"]+)"', html)
    assert "check-extra-failing-check" in ids
    assert len(ids) == len(set(ids)), sorted({i for i in ids if ids.count(i) > 1})


def test_the_job_card_owns_the_keyword_check(report):
    html = render_html(report)
    assert html.count('id="check-job-keyword-match"') == 1
    assert html.count("keywords from the job ad appear in the CV") == 1  # not repeated below
    passed = html[html.index('id="passed-heading"') :]
    assert "Job keyword match" not in passed


def test_a_failing_job_match_counts_as_needing_attention():
    from cv_ats_check.checks.keyword_checks import check_keyword_match

    doc = make_doc(["Gardening only"])
    result = check_keyword_match(doc, JobAd("Requirements\n- Python\n- Selenium\n"))
    html = render_html(build_report(doc, [result], job_provided=True))
    assert result.status is Status.FAIL
    assert "1 check needs attention" in html
    assert 'id="attention-heading"' not in html  # the card itself shows the failure


def test_the_parser_message_sits_next_to_the_file_name(report):
    html = render_html(report)
    assert report.parser_message in html[: html.index("</header>")]
    assert 'id="check-parser-status"' not in html


def test_the_report_supports_dark_mode_and_print():
    html = render_html(build_report(make_doc(["x"]), [], job_provided=False))
    assert "prefers-color-scheme: dark" in html and "@media print" in html
    assert 'name="color-scheme"' in html


def test_facts_values_are_escaped():
    from cv_ats_check.checks.hygiene_checks import check_hygiene

    doc = make_doc(["Anna Testsson"])
    doc.display_name = "<img src=x onerror=alert(1)>.pdf"
    html = render_html(build_report(doc, [check_hygiene(doc)], job_provided=False))
    assert "<img src=x" not in html
    assert "&lt;img src=x" in html


def _report_with_links(*links: str):
    from cv_ats_check.checks.hygiene_checks import check_hygiene

    doc = make_doc(["Anna Testsson"])
    doc.display_name = "Anna_Testsson_CV.pdf"
    doc.links = list(links)
    return build_report(doc, [check_hygiene(doc)], job_provided=False)


def test_html_links_are_clickable_and_hardened():
    html = render_html(_report_with_links("https://www.linkedin.com/in/anna?a=1&b=2"))
    assert 'href="https://www.linkedin.com/in/anna?a=1&amp;b=2"' in html
    assert 'target="_blank" rel="noopener noreferrer nofollow" referrerpolicy="no-referrer"' in html


def test_markdown_lists_links_as_autolinks():
    md = render_markdown(_report_with_links("https://github.com/anna", "mailto:anna@example.com"))
    assert "  - <https://github.com/anna>" in md
    assert "  - <mailto:anna@example.com>" in md


def test_unsafe_links_never_become_href():
    report = _report_with_links("javascript:alert(1)", "https://github.com/anna")
    html, md = render_html(report), render_markdown(report)
    assert 'href="javascript:' not in html and "<javascript:" not in md
    assert 'href="https://github.com/anna"' in html
    assert "1 unsupported link(s)" in html


def test_html_has_status_badges(report):
    html = render_html(report)
    assert 'class="badge PASS"' in html
    assert "<title>CV ATS Check" in html
