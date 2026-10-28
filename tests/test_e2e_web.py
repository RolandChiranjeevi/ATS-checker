"""End-to-end tests of the local web UI in a real browser (Playwright + Chromium).

They start the real server on a free loopback port, so nothing is mocked. If Chromium is not
installed the tests are skipped; install it with ``playwright install chromium``.
"""

from __future__ import annotations

import re
import threading
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")
expect = sync_api.expect

from reportlab.pdfgen import canvas  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

from cv_ats_check.web import create_app  # noqa: E402

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def server():
    httpd = make_server("127.0.0.1", 0, create_app(), threaded=True)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()
    thread.join(timeout=5)


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as playwright:
        try:
            instance = playwright.chromium.launch()
        except Exception as exc:  # browser binaries missing
            pytest.skip(f"Chromium unavailable ({type(exc).__name__}): playwright install chromium")
        yield instance
        instance.close()


@pytest.fixture
def page(browser, server):
    context = browser.new_context(accept_downloads=True, viewport={"width": 1000, "height": 900})
    page = context.new_page()
    page.problems = []  # console errors, uncaught exceptions and CSP violations
    page.on("console", lambda msg: page.problems.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda err: page.problems.append(str(err)))
    page.goto(server)
    yield page
    context.close()


def submit(page, cv: Path, job_text: str = ""):
    page.set_input_files("#cv", str(cv))
    if job_text:
        page.fill("#job_text", job_text)
    page.get_by_role("button", name="Check CV").click()


def run_report(page, fixtures_dir, job_en):
    submit(page, fixtures_dir / "cv_normal_en.pdf", job_en.read_text(encoding="utf-8"))
    expect(page).to_have_url(re.compile(r"/check$"))
    expect(page.locator("h1")).to_have_text("CV ATS Check")


# --- the form --------------------------------------------------------------------------------


def test_form_is_labelled_and_explains_privacy(page):
    assert page.title() == "CV ATS Check"
    assert page.locator("html").get_attribute("lang") == "en"
    expect(page.get_by_label("CV file")).to_be_visible()
    expect(page.get_by_label(re.compile(r"^Job ad"))).to_be_visible()  # not the file upload
    expect(page.get_by_role("button", name="Check CV")).to_be_enabled()
    expect(page.get_by_text("All processing happened locally")).to_be_visible()


def test_submitting_without_a_file_is_stopped_by_the_browser(page, server):
    page.get_by_role("button", name="Check CV").click()
    assert page.locator("#cv").evaluate("el => el.validity.valueMissing") is True
    assert page.url.rstrip("/") == server


def test_the_server_sends_security_headers(browser, server):
    context = browser.new_context()
    response = context.new_page().goto(server)
    headers = response.headers
    assert "default-src 'none'" in headers["content-security-policy"]
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["referrer-policy"] == "same-origin"
    assert headers["cache-control"] == "no-store"
    context.close()


# --- the report ------------------------------------------------------------------------------


def test_a_cv_and_a_pasted_ad_give_a_full_report(page, fixtures_dir, job_en):
    run_report(page, fixtures_dir, job_en)
    expect(page.locator("ul.summary li", has_text="Contact details")).to_be_visible()
    expect(page.locator("ul.summary li", has_text="Job keyword match")).to_be_visible()
    expect(page.locator("ul.summary .badge.PASS").first).to_be_visible()
    expect(page.get_by_role("heading", name="Document hygiene")).to_be_visible()
    expect(page.locator("table.facts").first).to_be_visible()
    assert page.problems == []


def test_the_extracted_text_view_opens_and_shows_reading_order(page, fixtures_dir, job_en):
    run_report(page, fixtures_dir, job_en)
    expect(page.locator("pre.ats-text")).to_be_hidden()
    page.get_by_text("Show extracted text").click()
    text = page.locator("pre.ats-text").first
    expect(text).to_be_visible()
    shown = text.inner_text()
    assert shown.index("Anna Testsson") < shown.index("Experience") < shown.index("Education")


def test_the_download_buttons_deliver_real_files(page, fixtures_dir, job_en):
    run_report(page, fixtures_dir, job_en)
    with page.expect_download() as info:
        page.get_by_role("link", name="Download Markdown (.md)").click()
    markdown = info.value
    assert markdown.suggested_filename == "cv_normal_en-ats-report.md"
    assert Path(markdown.path()).read_text(encoding="utf-8").startswith("# CV ATS Check")

    with page.expect_download() as info:
        page.get_by_role("link", name="Download HTML (.html)").click()
    html = info.value
    assert html.suggested_filename == "cv_normal_en-ats-report.html"
    assert Path(html.path()).read_text(encoding="utf-8").startswith("<!doctype html>")


def test_the_back_link_returns_to_an_empty_form(page, fixtures_dir, job_en):
    run_report(page, fixtures_dir, job_en)
    page.get_by_role("link", name="Check another CV").click()
    expect(page.get_by_role("button", name="Check CV")).to_be_visible()
    assert page.locator("#job_text").input_value() == ""


def test_a_docx_file_works_too(page, fixtures_dir):
    submit(page, fixtures_dir / "cv_normal.docx")
    expect(page.locator("h1")).to_have_text("CV ATS Check")
    expect(page.locator("pre.ats-text")).to_have_count(1)


# --- errors ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fixture", "message"),
    [
        ("cv_corrupt.pdf", "Could not open PDF"),
        ("cv_empty.pdf", "File is empty"),
        ("job_ad_en.txt", "Unsupported file type"),
    ],
)
def test_bad_files_show_a_readable_error_and_keep_the_job_text(
    page, fixtures_dir, fixture, message
):
    submit(page, fixtures_dir / fixture, "Requirements Playwright")
    alert = page.get_by_role("alert")
    expect(alert).to_contain_text(message)
    assert page.locator("#job_text").input_value() == "Requirements Playwright"
    assert "/tmp" not in alert.inner_text() and "/var/folders" not in alert.inner_text()


# --- hardening in a real browser -----------------------------------------------------------------


def test_a_hostile_file_name_is_shown_as_text_and_never_runs(page, fixtures_dir):
    page.set_input_files(
        "#cv",
        files=[
            {
                "name": "<img src=x onerror=window.__pwned=1>.pdf",
                "mimeType": "application/pdf",
                "buffer": (fixtures_dir / "cv_normal_en.pdf").read_bytes(),
            }
        ],
    )
    page.get_by_role("button", name="Check CV").click()
    expect(page.locator("h1")).to_have_text("CV ATS Check")
    assert page.evaluate("window.__pwned") is None
    assert page.locator("img[src='x']").count() == 0
    assert "<img src=x" in page.locator("body").inner_text()


def test_report_links_are_clickable_hardened_and_never_javascript(page, tmp_path):
    pdf = tmp_path / "links.pdf"
    sheet = canvas.Canvas(str(pdf))
    sheet.setFont("Helvetica", 11)
    for i, (label, url) in enumerate(
        [
            ("LinkedIn", "https://www.linkedin.com/in/anna-testsson"),
            ("Mail", "mailto:anna@example.com"),
            ("Evil", "javascript:alert(1)"),
        ]
    ):
        sheet.drawString(50, 780 - 20 * i, label)
        sheet.linkURL(url, (50, 778 - 20 * i, 120, 792 - 20 * i))
    sheet.save()

    submit(page, pdf)
    links = page.locator("table.facts ul.links a")
    expect(links).to_have_count(2)
    first = links.first
    assert first.get_attribute("href") == "https://www.linkedin.com/in/anna-testsson"
    assert first.get_attribute("target") == "_blank"
    assert "noopener" in first.get_attribute("rel")
    assert page.locator("a[href^='javascript:']").count() == 0


# --- layout ------------------------------------------------------------------------------------


@pytest.mark.parametrize("width", [375, 768])
def test_pages_do_not_scroll_sideways_on_small_screens(
    browser, server, fixtures_dir, job_en, width
):
    context = browser.new_context(viewport={"width": width, "height": 800})
    page = context.new_page()
    page.goto(server)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    submit(page, fixtures_dir / "cv_normal_en.pdf", job_en.read_text(encoding="utf-8"))
    expect(page.locator("h1")).to_have_text("CV ATS Check")
    overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    assert overflow <= 0, f"report scrolls sideways by {overflow}px at {width}px"
    context.close()
