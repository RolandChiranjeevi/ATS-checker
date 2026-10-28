"""The logo and brand colours: safe to embed, present on both pages, accessible."""

from __future__ import annotations

import base64
import re
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from cv_ats_check.reporting import report_generator
from cv_ats_check.reporting.report_generator import (
    build_report,
    download_links,
    logo_data_uri,
    render_form,
    render_html,
)
from cv_ats_check.web import create_app
from tests.helpers import make_doc

ROOT = Path(__file__).parent.parent
ASSETS = ROOT / "src" / "cv_ats_check" / "reporting" / "assets"
TEMPLATES = ROOT / "src" / "cv_ats_check" / "reporting" / "templates"
LOGO = ASSETS / "logo.svg"


def decoded(uri: str) -> bytes:
    return base64.b64decode(uri.split("base64,", 1)[1])


# --- the file itself ----------------------------------------------------------------------------


def test_the_logo_is_a_well_formed_svg_of_reasonable_size():
    root = ET.fromstring(LOGO.read_bytes())
    assert root.tag.endswith("}svg")
    assert LOGO.stat().st_size < 50_000  # every downloaded report carries a copy


@pytest.mark.parametrize(
    "forbidden",
    [
        r"<script",
        r"\son\w+\s*=",
        r"href\s*=\s*[\"']https?:",
        r"<image",
        r"<foreignObject",
        r"javascript:",
    ],
)
def test_the_logo_has_no_scripts_event_handlers_or_external_references(forbidden):
    assert not re.search(forbidden, LOGO.read_text(encoding="utf-8"), re.IGNORECASE)


def test_the_logo_ships_with_the_package():
    package_data = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["setuptools"][
        "package-data"
    ]
    assert "reporting/assets/*" in package_data["cv_ats_check"]


def test_the_data_uri_is_the_file_byte_for_byte():
    uri = logo_data_uri()
    assert uri.startswith("data:image/svg+xml;base64,")
    assert decoded(uri) == LOGO.read_bytes()


# --- both pages and the download -----------------------------------------------------------------


@pytest.fixture
def report():
    return build_report(make_doc(["Anna Testsson"]), [], job_provided=False)


def test_the_form_shows_the_logo_and_uses_it_as_the_tab_icon():
    html = render_form()
    assert '<img class="logo"' in html and 'alt=""' in html
    assert re.search(
        r'<link rel="icon" type="image/svg\+xml" href="data:image/svg\+xml;base64,', html
    )


def test_the_report_shows_the_logo_and_uses_it_as_the_tab_icon(report):
    html = render_html(report)
    assert '<img class="logo"' in html
    assert 'rel="icon"' in html


def test_a_downloaded_html_report_is_self_contained(report):
    html_download = next(href for label, _, href in download_links(report) if "HTML" in label)
    assert b"data:image/svg+xml;base64," in decoded(html_download)
    assert b'src="http' not in decoded(html_download)


def test_pages_still_render_without_a_logo(monkeypatch, report):
    monkeypatch.setattr(report_generator, "_LOGO_PATH", ASSETS / "does-not-exist.svg")
    logo_data_uri.cache_clear()
    try:
        assert logo_data_uri() == ""
        assert "<img" not in render_form()
        assert "CV ATS Check" in render_html(report)
        assert "<img" not in render_html(report)
    finally:
        logo_data_uri.cache_clear()


# --- the policy only opens what the logo needs ------------------------------------------------


def test_the_policy_allows_inline_images_and_nothing_external():
    csp = create_app().test_client().get("/").headers["Content-Security-Policy"]
    assert "img-src data:" in csp
    assert "default-src 'none'" in csp
    assert "http" not in csp and "*" not in csp and "unsafe-eval" not in csp


# --- accessible colours ---------------------------------------------------------------------------


def luminance(hex_colour: str) -> float:
    r, g, b = (int(hex_colour.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4))
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a: str, b: str) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def tokens(template: str, name: str) -> list[str]:
    """The light and the dark value of a CSS variable (light comes first in the file)."""
    text = (TEMPLATES / template).read_text(encoding="utf-8")
    return re.findall(rf"{name}:\s*(#[0-9a-fA-F]{{6}})", text)


@pytest.mark.parametrize("mode", [0, 1], ids=["light", "dark"])
def test_button_and_step_numbers_meet_text_contrast(mode):
    accent, on_accent = tokens("index.html.j2", "--accent"), tokens("index.html.j2", "--on-accent")
    assert contrast(accent[mode], on_accent[mode]) >= 4.5


@pytest.mark.parametrize("template", ["index.html.j2", "report.html.j2"])
@pytest.mark.parametrize("mode", [0, 1], ids=["light", "dark"])
def test_the_brand_green_is_visible_against_the_page_background(template, mode):
    brand, background = tokens(template, "--brand"), tokens(template, "--bg")
    assert contrast(brand[mode], background[mode]) >= 3.0  # non-text contrast (WCAG 1.4.11)


def test_both_templates_use_the_same_brand_colours():
    assert tokens("index.html.j2", "--brand") == tokens("report.html.j2", "--brand")
