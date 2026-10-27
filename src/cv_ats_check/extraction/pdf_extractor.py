"""PDF extraction with PyMuPDF (runs fully offline)."""

from __future__ import annotations

import unicodedata
from pathlib import Path

import pymupdf

from cv_ats_check.extraction.errors import CorruptFile
from cv_ats_check.models import ExtractedDocument, PageInfo, TextBlock

_BOLD_FLAG = 16  # PyMuPDF span flag bit for bold


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def _line_to_block(line: dict, page_number: int) -> TextBlock | None:
    spans = [s for s in line.get("spans", []) if s.get("text", "").strip()]
    if not spans:
        return None
    text = _nfc("".join(s["text"] for s in line["spans"]).strip())
    size = max(s["size"] for s in spans)
    bold = all(bool(s["flags"] & _BOLD_FLAG) or "bold" in s["font"].lower() for s in spans)
    return TextBlock(text=text, page=page_number, size=round(size, 1), bold=bold)


def extract_pdf(path: Path) -> ExtractedDocument:
    """Extract text, styled lines, per-page stats and hyperlinks from a PDF."""
    try:
        doc = pymupdf.open(path)
    except Exception as exc:  # PyMuPDF raises several unrelated types for bad files
        raise CorruptFile(f"Could not open PDF (damaged or not a real PDF): {path}") from exc

    with doc:
        if doc.needs_pass:
            raise CorruptFile("PDF is password-protected; remove the password and retry.")
        if doc.page_count == 0:
            raise CorruptFile(f"PDF has no pages: {path}")

        texts: list[str] = []
        pages: list[PageInfo] = []
        blocks: list[TextBlock] = []
        links: list[str] = []
        try:
            for index, page in enumerate(doc, start=1):
                page_text = _nfc(page.get_text("text"))
                texts.append(page_text)
                pages.append(
                    PageInfo(
                        number=index,
                        char_count=len(page_text.strip()),
                        image_count=len(page.get_images()),
                    )
                )
                for block in page.get_text("dict")["blocks"]:
                    if block.get("type") != 0:
                        continue
                    for line in block["lines"]:
                        parsed = _line_to_block(line, index)
                        if parsed:
                            blocks.append(parsed)
                links.extend(link["uri"] for link in page.get_links() if link.get("uri"))
        except Exception as exc:
            raise CorruptFile(f"PDF content could not be read: {path}") from exc

    return ExtractedDocument(
        path=path,
        file_type="pdf",
        text="\n".join(texts),
        pages=pages,
        blocks=blocks,
        links=links,
    )
