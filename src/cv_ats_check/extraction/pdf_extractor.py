"""PDF extraction with PyMuPDF (runs fully offline)."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pymupdf

from cv_ats_check.extraction.errors import CorruptFile
from cv_ats_check.models import ExtractedDocument, PageInfo, TextBlock

_BOLD_FLAG = 16  # PyMuPDF span flag bit for bold
_METADATA_KEYS = ("title", "author", "creator", "producer")


_PDF_DATE = re.compile(r"D:(\d{4})(\d{2})(\d{2})")


def pdf_date(raw: str) -> str:
    """Turn a PDF date string such as ``D:20260102030405+01'00'`` into ``2026-01-02``."""
    match = _PDF_DATE.match(raw)
    return f"{match[1]}-{match[2]}-{match[3]}" if match else ""


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def _line_to_block(line: dict, page_number: int) -> TextBlock | None:
    spans = [s for s in line.get("spans", []) if s.get("text", "").strip()]
    if not spans:
        return None
    text = _nfc("".join(s["text"] for s in line["spans"]).strip())
    size = max(s["size"] for s in spans)
    bold = all(bool(s["flags"] & _BOLD_FLAG) or "bold" in s["font"].lower() for s in spans)
    bbox = tuple(round(v, 1) for v in line["bbox"])
    return TextBlock(text=text, page=page_number, size=round(size, 1), bold=bold, bbox=bbox)


def _image_area_ratio(page) -> float:
    """Share of the page covered by images (0 if it cannot be determined)."""
    page_area = page.rect.width * page.rect.height
    if page_area <= 0:
        return 0.0
    try:
        covered = sum(pymupdf.Rect(info["bbox"]).get_area() for info in page.get_image_info())
    except Exception:
        return 0.0
    return min(1.0, covered / page_area)


def _count_tables(page) -> int:
    """Count ruled tables with at least 2 rows and 2 columns (borderless ones are invisible)."""
    try:
        tables = page.find_tables().tables
    except Exception:
        return 0
    return sum(1 for t in tables if t.row_count >= 2 and t.col_count >= 2)


def _is_protected(doc) -> bool:
    """True if the PDF has an encryption dictionary (e.g. owner-password restrictions).

    ``doc.is_encrypted`` turns False once PyMuPDF has opened the file with an empty user
    password, so the trailer's ``Encrypt`` entry is the reliable signal.
    """
    try:
        return doc.is_encrypted or doc.xref_get_key(-1, "Encrypt")[0] != "null"
    except Exception:
        return False


def extract_pdf(path: Path) -> ExtractedDocument:
    """Extract text, styled lines with positions, page facts, metadata and links from a PDF."""
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
        table_count = 0
        raw_meta = doc.metadata or {}
        metadata = {k: (raw_meta.get(k) or "").strip() for k in _METADATA_KEYS}
        metadata["created"] = pdf_date(raw_meta.get("creationDate") or "")
        metadata["modified"] = pdf_date(raw_meta.get("modDate") or "")
        metadata["encrypted"] = "yes" if _is_protected(doc) else "no"
        try:
            for index, page in enumerate(doc, start=1):
                page_text = _nfc(page.get_text("text"))
                texts.append(page_text)
                pages.append(
                    PageInfo(
                        number=index,
                        char_count=len(page_text.strip()),
                        image_count=len(page.get_images()),
                        width=page.rect.width,
                        height=page.rect.height,
                        image_area_ratio=_image_area_ratio(page),
                    )
                )
                table_count += _count_tables(page)
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
        metadata=metadata,
        file_size=path.stat().st_size,
        table_count=table_count,
    )
