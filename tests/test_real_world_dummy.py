"""Regression tests on a real Word export, saved both as PDF (macOS) and as DOCX.

``CV-dummy.pdf`` and ``CV-dummy.docx`` are the same Swedish two-column Word template with a
made-up person ("Jan Jansson"). Unlike the generated fixtures they carry real-world quirks:
bullets that extract as separate lines, a no-break space in the phone number, a section with two
columns, template-leftover authors and a ``file:///`` hyperlink.
"""

from __future__ import annotations

import re
import zipfile

import pytest

from cv_ats_check.checks import run_all_checks
from cv_ats_check.checks.contact_checks import find_emails, find_phones
from cv_ats_check.checks.date_checks import find_dates
from cv_ats_check.checks.heading_checks import find_sections
from cv_ats_check.extraction import ExtractionError, extract_document
from cv_ats_check.models import JobAd, Status

FORMATS = ["CV-dummy.pdf", "CV-dummy.docx"]


@pytest.fixture(params=FORMATS)
def dummy(request, fixtures_dir):
    return extract_document(fixtures_dir / request.param)


def results(doc, job=None):
    return {r.name: r for r in run_all_checks(doc, job)}


def facts(result):
    return {f.label: f for f in result.facts}


# --- the same CV gives the same answers in both formats --------------------------------------


def test_contact_details_are_found_in_both_formats(dummy):
    assert find_emails(dummy.text) == ["jan.jansson@gma1l.com"]
    assert [re.sub(r"\D", "", p) for p in find_phones(dummy.text)] == ["0781141469"]
    contact = results(dummy)["Contact details"]
    assert contact.status is Status.PASS
    assert contact.message == "Found: name, email, phone."


def test_both_formats_have_the_same_sections(fixtures_dir):
    found = [set(find_sections(extract_document(fixtures_dir / name).blocks)) for name in FORMATS]
    assert found[0] == found[1] >= {"skills", "education", "experience"}


def test_dates_are_one_consistent_iso_style_in_both_formats(dummy):
    matches = find_dates(dummy.text)
    assert [m.label for m in matches] == ["YYYY-MM – YYYY-MM"] * 5
    assert results(dummy)["Date consistency"].status is Status.PASS


def test_the_text_is_identical_once_bullets_and_line_breaks_are_ignored(fixtures_dir):
    def lines(name):
        doc = extract_document(fixtures_dir / name)
        parts = (part for block in doc.blocks for part in block.text.split("\n"))
        return {p.replace("\xa0", " ").strip() for p in parts} - {"•", ""}

    pdf, docx = lines("CV-dummy.pdf"), lines("CV-dummy.docx")
    assert pdf == docx, pdf ^ docx


def test_both_formats_are_flagged_as_two_column(dummy):
    layout = results(dummy)["Layout"]
    assert layout.status is Status.WARN
    assert "column" in layout.message
    assert "single column" in layout.suggestion


def test_both_formats_are_short_cvs(dummy):
    length = results(dummy)["Length and density"]
    assert length.status is Status.WARN
    assert "below the 250-word guideline" in length.message


# --- format-specific real-world behaviour -------------------------------------------------------


def test_word_to_pdf_extracts_each_bullet_as_its_own_line(fixtures_dir):
    pdf = extract_document(fixtures_dir / "CV-dummy.pdf")
    docx = extract_document(fixtures_dir / "CV-dummy.docx")
    assert [b.text for b in pdf.blocks].count("•") >= 10
    assert "•" not in [b.text for b in docx.blocks]


def test_the_pdf_columns_are_found_where_the_template_puts_them(fixtures_dir):
    from cv_ats_check.checks.layout_checks import find_columns

    pdf = extract_document(fixtures_dir / "CV-dummy.pdf")
    gutter, left, right = find_columns(pdf.blocks, pdf.pages[0].width)
    sidebar_x = min(b.bbox[0] for b in pdf.blocks if b.text == "Kontakt")
    main_x = min(b.bbox[0] for b in pdf.blocks if b.text == "Arbetslivserfarenhet")
    assert sidebar_x < gutter < main_x
    assert left >= 4 and right >= 4


def test_the_pdf_leftover_author_is_reported_with_the_tool_that_made_it(fixtures_dir):
    hygiene = results(extract_document(fixtures_dir / "CV-dummy.pdf"))["Document hygiene"]
    items = facts(hygiene)
    assert hygiene.status is Status.WARN
    assert "does not match the name 'Jan Jansson'" in hygiene.message
    assert items["Page format"].value.startswith("A4")
    assert "Word" in items["Created with"].value and "Quartz" in items["Created with"].value


def test_the_docx_file_link_is_listed_but_never_clickable(fixtures_dir):
    docx = extract_document(fixtures_dir / "CV-dummy.docx")
    hygiene = results(docx)["Document hygiene"]
    assert docx.links == ["file:///Users/jan/Documents/portfolio"]
    assert "a link uses a non-web scheme (file)" in hygiene.message
    assert facts(hygiene)["Links"].links == ()
    assert docx.column_count == 2


# --- against a job ad ---------------------------------------------------------------------------


def test_an_unrelated_cv_scores_zero_against_a_testing_ad(dummy, job_sv):
    checks = results(dummy, JobAd(job_sv.read_text(encoding="utf-8")))
    match = checks["Job keyword match"]
    assert match.status is Status.FAIL
    assert match.details["analysis"].score_pct == 0
    assert "must-have 0/14" in match.message


# --- guard: nothing personal in any fixture -------------------------------------------------------

# The fixtures may only mention the made-up persona: home folder /Users/jan/ and the e-mail
# domains gma1l.com / example.com. Anything else that looks like a real person's data is a leak.
PERSONAL = re.compile(
    rb"/Users/(?!jan/)[^/\s\"'<>]+"  # someone else's home folder
    rb"|CloudStorage|ProtonDrive|OneDrive|Dropbox"  # cloud-sync folders live inside home folders
    rb"|[\w.+-]+@(?!(?:gma1l|example)\.com\b)[\w-]+\.[\w.-]+",  # any other e-mail address
    re.IGNORECASE,
)


@pytest.mark.parametrize(
    "leak",
    [
        b"file:///Users/alice/Documents/cv",
        b"/Users/alice/Library/CloudStorage/ProtonDrive-alice-folder",
        b"alice@proton.me",
        b"bob.smith@real-company.se",
        b"C:/Dropbox/cv",
    ],
)
def test_the_guard_catches_planted_personal_data(leak):
    assert PERSONAL.search(leak)


@pytest.mark.parametrize(
    "fine",
    [b"file:///Users/jan/Documents/portfolio", b"jan.jansson@gma1l.com", b"anna@example.com"],
)
def test_the_guard_allows_the_made_up_persona(fine):
    assert not PERSONAL.search(fine)


def visible_content(path) -> list[bytes]:
    """What someone opening the file could read: text, properties and links (PDF), the XML
    parts (DOCX) or the bytes themselves (plain text). Compressed streams are not scanned raw:
    random bytes can look like an e-mail address by chance."""
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            return [archive.read(n) for n in archive.namelist() if n.endswith((".xml", ".rels"))]
    if path.suffix.lower() == ".pdf":
        try:
            doc = extract_document(path)
        except ExtractionError:  # the deliberately corrupt/empty fixtures are tiny plain files
            return [path.read_bytes()]
        return [part.encode() for part in (doc.text, *doc.metadata.values(), *doc.links)]
    return [path.read_bytes()]


def test_no_fixture_contains_personal_data(fixtures_dir):
    offenders = [
        path.name
        for path in sorted(fixtures_dir.iterdir())
        if path.is_file() and any(PERSONAL.search(blob) for blob in visible_content(path))
    ]
    assert offenders == [], f"personal data in fixtures: {offenders}"
