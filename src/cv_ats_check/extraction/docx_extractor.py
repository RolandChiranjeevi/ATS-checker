"""DOCX extraction with python-docx."""

from __future__ import annotations

import unicodedata
from pathlib import Path

from docx import Document

from cv_ats_check.extraction.errors import CorruptFile
from cv_ats_check.models import ExtractedDocument, PageInfo, TextBlock


def _paragraph_to_block(paragraph) -> TextBlock | None:
    text = unicodedata.normalize("NFC", paragraph.text.strip())
    if not text:
        return None
    style_name = (paragraph.style.name or "") if paragraph.style is not None else ""
    runs = [r for r in paragraph.runs if r.text.strip()]
    bold = bool(runs) and all(r.bold for r in runs)
    size = next((r.font.size.pt for r in runs if r.font.size), None)
    return TextBlock(
        text=text,
        page=1,
        size=size,
        bold=bold,
        heading_style=style_name.startswith("Heading") or style_name == "Title",
    )


def extract_docx(path: Path) -> ExtractedDocument:
    """Extract paragraphs (body first, then table cells) and hyperlinks from a DOCX."""
    try:
        document = Document(str(path))
    except Exception as exc:  # BadZipFile, PackageNotFoundError, KeyError, ...
        raise CorruptFile(f"Could not open DOCX (damaged or not a real DOCX): {path}") from exc

    paragraphs = list(document.paragraphs)
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                paragraphs.extend(cell.paragraphs)

    blocks = [b for p in paragraphs if (b := _paragraph_to_block(p))]
    text = "\n".join(b.text for b in blocks)

    rels = document.part.rels.values()
    links = [r.target_ref for r in rels if r.reltype.endswith("/hyperlink") and r.is_external]
    images = sum(1 for r in rels if r.reltype.endswith("/image"))

    return ExtractedDocument(
        path=path,
        file_type="docx",
        text=text,
        pages=[PageInfo(number=1, char_count=len(text), image_count=images)],
        blocks=blocks,
        links=links,
        paginated=False,
    )
