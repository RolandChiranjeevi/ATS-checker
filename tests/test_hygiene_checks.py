"""Document hygiene: file name, metadata, size."""

from __future__ import annotations

import pytest

from cv_ats_check.checks.hygiene_checks import check_hygiene
from cv_ats_check.extraction import extract_document
from cv_ats_check.extraction.pdf_extractor import pdf_date
from cv_ats_check.models import PageInfo, Status
from tests.helpers import make_doc


def hygiene_doc(name="Anna_Testsson_CV.pdf", *, title="", author="", size=100_000):
    doc = make_doc(["Anna Testsson", "anna@example.com", "QA Engineer"])
    doc.display_name = name
    doc.metadata = {"title": title, "author": author}
    doc.file_size = size
    return doc


@pytest.mark.parametrize(
    "fixture",
    ["cv_normal_en.pdf", "cv_swedish.pdf", "cv_normal.docx", "cv_scanned.pdf", "cv_two_column.pdf"],
)
def test_fixtures_have_clean_hygiene(fixtures_dir, fixture):
    result = check_hygiene(extract_document(fixtures_dir / fixture))
    assert result.status is Status.PASS, result.message


def test_clean_document_passes():
    assert check_hygiene(hygiene_doc()).status is Status.PASS


@pytest.mark.parametrize(
    ("name", "fragment"),
    [
        ("cv.pdf", "does not identify you"),
        ("CV.PDF", "does not identify you"),
        ("resume 2.pdf", "does not identify you"),
        ("Mitt CV.docx", "does not identify you"),
        ("Document1.pdf", "does not identify you"),
        ("Anna CV (1).pdf", "draft or copy"),
        ("Anna_CV_final.pdf", "draft or copy"),
        ("Anna-CV-v2.pdf", "draft or copy"),
        ("Anna CV kopia.pdf", "draft or copy"),
        ("Anna<>CV.pdf", "unusual characters"),
        ("Anna&CV.pdf", "unusual characters"),
        (("A" * 120) + ".pdf", "characters long"),
    ],
)
def test_bad_file_names_warn(name, fragment):
    result = check_hygiene(hygiene_doc(name))
    assert result.status is Status.WARN
    assert fragment in result.message
    assert "Firstname_Lastname_CV.pdf" in result.suggestion


@pytest.mark.parametrize(
    "name",
    [
        "Anna_Testsson_CV.pdf",
        "Åsa Öberg CV.docx",
        "Anna Testsson - CV 2026.pdf",
        "cv_normal_en.pdf",
    ],
)
def test_good_file_names_pass(name):
    assert check_hygiene(hygiene_doc(name)).status is Status.PASS


@pytest.mark.parametrize(
    "title",
    ["Microsoft Word - cv.docx", "Untitled", "Document1", "CV template", "cv.docx", "thesis.tex"],
)
def test_leftover_titles_warn(title):
    result = check_hygiene(hygiene_doc(title=title))
    assert result.status is Status.WARN
    assert "document title" in result.message
    assert "File > Properties" in result.suggestion


@pytest.mark.parametrize("author", ["John Doe", "Your Name", "Namn Efternamn"])
def test_placeholder_authors_warn(author):
    result = check_hygiene(hygiene_doc(author=author))
    assert result.status is Status.WARN
    assert "template placeholder" in result.message


def test_author_not_matching_the_cv_name_warns():
    result = check_hygiene(hygiene_doc(author="Maria Svensson"))
    assert result.status is Status.WARN
    assert "does not match the name 'Anna Testsson'" in result.message


@pytest.mark.parametrize(
    ("author", "title"),
    [
        ("Anna Testsson", "Anna Testsson – CV"),
        ("anna", ""),
        ("Testsson, Anna", ""),
        ("(anonymous)", "(anonymous)"),
        ("", ""),
    ],
)
def test_matching_or_empty_metadata_passes(author, title):
    assert check_hygiene(hygiene_doc(author=author, title=title)).status is Status.PASS


@pytest.mark.parametrize(
    ("size", "expected"),
    [(2 * 1024 * 1024, Status.PASS), (2 * 1024 * 1024 + 1, Status.WARN), (6_000_000, Status.WARN)],
)
def test_file_size_limit(size, expected):
    assert check_hygiene(hygiene_doc(size=size)).status is expected


def test_several_problems_are_reported_together():
    result = check_hygiene(
        hygiene_doc("cv.pdf", title="Untitled", author="John Doe", size=5_000_000)
    )
    assert result.status is Status.WARN
    for fragment in ("file name", "document title", "document author", "MB"):
        assert fragment in result.message


def facts_by_label(result):
    return {fact.label: fact for fact in result.facts}


def test_passing_result_lists_every_item_that_was_checked(fixtures_dir):
    result = check_hygiene(extract_document(fixtures_dir / "cv_normal_en.pdf"))
    facts = facts_by_label(result)
    assert {"File name", "Title property", "Author property", "File size", "Page format"} <= set(
        facts
    )
    assert {"Created with", "Encryption"} <= set(facts)
    assert all(f.status in (Status.PASS, None) for f in result.facts)
    assert f"Checked {len(result.facts)} items" in result.message
    assert facts["Author property"].value == "Anna Testsson"
    assert facts["Page format"].value.startswith("A4, 1 page(s)")
    assert facts["File size"].value.startswith("PDF, 0.")
    assert facts["Encryption"].value == "none"


def test_each_problem_marks_its_own_item():
    doc = hygiene_doc("cv.pdf", title="Untitled", author="Maria Svensson", size=5_000_000)
    facts = facts_by_label(check_hygiene(doc))
    assert facts["File name"].status is Status.WARN
    assert facts["Title property"].status is Status.WARN
    assert facts["Author property"].status is Status.WARN
    assert facts["File size"].status is Status.WARN
    assert "does not match the name 'Anna Testsson'" in facts["Author property"].note


def test_unset_properties_are_informational():
    facts = facts_by_label(check_hygiene(hygiene_doc()))
    for label in ("Title property", "Author property"):
        assert facts[label].value == "(not set)"
        assert facts[label].status is None


def test_author_is_not_compared_when_the_cv_has_no_name():
    doc = make_doc(["anna@example.com", "worked as a tester"])
    doc.display_name = "Anna_Testsson_CV.pdf"
    doc.metadata = {"author": "Maria Svensson"}
    fact = facts_by_label(check_hygiene(doc))["Author property"]
    assert fact.status is None
    assert "No name found" in fact.note


@pytest.mark.parametrize(
    ("width", "height", "label", "status"),
    [
        (595.3, 841.9, "A4", Status.PASS),
        (841.9, 595.3, "A4", Status.PASS),
        (612.0, 792.0, "US Letter", Status.PASS),
        (500.0, 700.0, "176 x 247 mm", Status.WARN),
    ],
)
def test_page_format(width, height, label, status):
    doc = hygiene_doc()
    doc.pages = [PageInfo(1, 500, 0, width=width, height=height)]
    fact = facts_by_label(check_hygiene(doc))["Page format"]
    assert fact.status is status
    assert fact.value.startswith(label)


def test_page_format_is_omitted_for_docx_and_unknown_sizes(fixtures_dir):
    assert "Page format" not in facts_by_label(check_hygiene(hygiene_doc()))
    docx = check_hygiene(extract_document(fixtures_dir / "cv_normal.docx"))
    assert "Page format" not in facts_by_label(docx)


def test_links_are_listed_by_host_and_mailto_is_counted_separately():
    doc = hygiene_doc()
    doc.links = [
        "https://www.linkedin.com/in/anna",
        "https://github.com/anna",
        "https://github.com/anna/repo",
        "mailto:anna@example.com",
    ]
    fact = facts_by_label(check_hygiene(doc))["Links"]
    assert fact.value == "3 link(s): linkedin.com, github.com; 1 e-mail link(s)"
    assert fact.status is None
    assert fact.links == tuple(doc.links)  # every link is listed so it can be clicked
    assert "Click each link" in fact.note


def test_duplicate_links_are_listed_once():
    doc = hygiene_doc()
    doc.links = ["https://github.com/anna", " https://github.com/anna ", "https://github.com/anna"]
    fact = facts_by_label(check_hygiene(doc))["Links"]
    assert fact.links == ("https://github.com/anna",)
    assert fact.value == "1 link(s): github.com"


@pytest.mark.parametrize(
    "bad", ["javascript:alert(1)", "file:///etc/passwd", "data:text/html,<b>x</b>", "ftp://x/y"]
)
def test_unsafe_link_schemes_are_never_clickable(bad):
    doc = hygiene_doc()
    doc.links = [bad, "https://github.com/anna"]
    result = check_hygiene(doc)
    fact = facts_by_label(result)["Links"]
    assert fact.links == ("https://github.com/anna",)
    assert fact.status is Status.WARN
    assert "non-web scheme" in result.message
    assert "1 unsupported link(s)" in fact.value


def test_link_characters_that_break_markup_are_encoded():
    doc = hygiene_doc()
    doc.links = ['https://example.com/a b"c<d>e']
    assert facts_by_label(check_hygiene(doc))["Links"].links == (
        "https://example.com/a%20b%22c%3Cd%3Ee",
    )


def test_control_characters_make_a_link_unsafe():
    doc = hygiene_doc()
    doc.links = ["https://example.com/\nx"]
    assert facts_by_label(check_hygiene(doc))["Links"].links == ()


def test_informational_items_have_no_filler_note():
    doc = hygiene_doc()
    doc.metadata |= {"creator": "LaTeX", "modified": "2026-01-02"}
    facts = facts_by_label(check_hygiene(doc))
    assert facts["Created with"].note == ""
    assert facts["Last modified"].note == ""


def test_shortened_links_warn():
    doc = hygiene_doc()
    doc.links = ["https://bit.ly/abc123", "https://linkedin.com/in/anna"]
    result = check_hygiene(doc)
    assert result.status is Status.WARN
    assert "shortened link" in result.message
    assert facts_by_label(result)["Links"].status is Status.WARN


def test_no_links_means_no_links_item():
    assert "Links" not in facts_by_label(check_hygiene(hygiene_doc()))


def test_canva_exports_warn():
    doc = hygiene_doc()
    doc.metadata["creator"] = "Canva"
    result = check_hygiene(doc)
    assert result.status is Status.WARN
    assert facts_by_label(result)["Created with"].status is Status.WARN


def test_creator_and_dates_are_informational():
    doc = hygiene_doc()
    doc.metadata |= {"creator": "LaTeX", "producer": "LuaTeX", "modified": "2026-01-02"}
    facts = facts_by_label(check_hygiene(doc))
    assert facts["Created with"].value == "LaTeX / LuaTeX"
    assert facts["Created with"].status is None
    assert facts["Last modified"].value == "2026-01-02"


def test_owner_protected_pdf_warns(fixtures_dir):
    doc = extract_document(fixtures_dir / "cv_owner_protected.pdf")
    assert "Anna Testsson" in doc.text  # still readable here, but not for every parser
    result = check_hygiene(doc)
    assert result.status is Status.WARN
    assert facts_by_label(result)["Encryption"].status is Status.WARN
    assert "password protection" in result.suggestion


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("D:20260102030405+01'00'", "2026-01-02"),
        ("D:20260102", "2026-01-02"),
        ("", ""),
        ("garbage", ""),
        ("D:2026", ""),
    ],
)
def test_pdf_date_parsing(raw, expected):
    assert pdf_date(raw) == expected


def test_docx_dates_are_extracted(fixtures_dir):
    metadata = extract_document(fixtures_dir / "cv_normal.docx").metadata
    assert metadata["created"] and metadata["modified"]


def test_extraction_reads_metadata_size_and_tables(fixtures_dir):
    pdf = extract_document(fixtures_dir / "cv_normal_en.pdf")
    assert pdf.metadata["author"] == "Anna Testsson"
    assert pdf.file_size == (fixtures_dir / "cv_normal_en.pdf").stat().st_size
    docx = extract_document(fixtures_dir / "cv_table.docx")
    assert docx.metadata["author"] == "Anna Testsson"
    assert docx.table_count == 1
    header = extract_document(fixtures_dir / "cv_header_contact.docx")
    assert header.blocks[0].region == "header"
    assert extract_document(fixtures_dir / "cv_normal.docx").table_count == 0
