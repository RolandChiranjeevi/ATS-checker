"""Shared data models used by extraction, checks and reporting."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class Status(StrEnum):
    """Outcome of a single check."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"

    @property
    def severity(self) -> int:
        return {"PASS": 0, "WARN": 1, "FAIL": 2}[self.value]


def worst(statuses: Iterable[Status]) -> Status:
    """Return the most severe status (PASS if the iterable is empty)."""
    return max(statuses, key=lambda s: s.severity, default=Status.PASS)


@dataclass(frozen=True)
class TextBlock:
    """One visual line of text with the styling hints we can recover."""

    text: str
    page: int
    size: float | None = None
    bold: bool = False
    heading_style: bool = False  # True for DOCX "Heading N" / "Title" paragraphs
    bbox: tuple[float, float, float, float] | None = None  # (x0, y0, x1, y1) in PDF points
    region: str = "body"  # "header" / "footer" for DOCX header and footer text


@dataclass(frozen=True)
class PageInfo:
    """Per-page facts used to detect scanned documents."""

    number: int
    char_count: int
    image_count: int
    width: float = 0.0  # page size in PDF points (0 when unknown, e.g. DOCX)
    height: float = 0.0
    image_area_ratio: float = 0.0  # share of the page covered by images


@dataclass
class ExtractedDocument:
    """Everything the checks need to know about a CV file."""

    path: Path
    file_type: str  # "pdf" or "docx"
    text: str
    pages: list[PageInfo]
    blocks: list[TextBlock]
    links: list[str] = field(default_factory=list)
    paginated: bool = True  # DOCX has no fixed pagination
    metadata: dict[str, str] = field(default_factory=dict)  # title, author, ...
    file_size: int = 0  # bytes
    table_count: int = 0
    display_name: str = ""  # original file name (differs from path for uploads)

    @property
    def name(self) -> str:
        return self.display_name or self.path.name

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def total_chars(self) -> int:
        return sum(p.char_count for p in self.pages)

    @property
    def image_count(self) -> int:
        return sum(p.image_count for p in self.pages)

    @property
    def word_count(self) -> int:
        return len(self.text.split())

    @property
    def lines(self) -> list[str]:
        return [b.text for b in self.blocks]


@dataclass(frozen=True)
class JobAd:
    """A job advertisement read from a local text file."""

    text: str


@dataclass(frozen=True)
class Fact:
    """One itemised observation shown under a check (what was looked at, and how it fared)."""

    label: str
    value: str
    status: Status | None = None  # None = informational only
    note: str = ""
    links: tuple[str, ...] = ()  # safe, clickable URLs (http, https, mailto) shown with the fact


@dataclass
class CheckResult:
    """The verdict of one check, with an explanation and a concrete fix."""

    name: str
    status: Status
    message: str
    suggestion: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    facts: list[Fact] = field(default_factory=list)
