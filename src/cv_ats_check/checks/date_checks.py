"""Date formats: find them, classify them, flag inconsistency."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from cv_ats_check.models import CheckResult, ExtractedDocument, JobAd, Status

NAME = "Date consistency"

_Y = r"(?<!\d)(?:19|20)\d{2}(?!\d)"
_MM = r"(?:0[1-9]|1[0-2])(?!\d)"
_M = (
    r"(?:jan(?:uari|uary)?|feb(?:ruari|ruary)?|mar(?:s|ch)?|apr(?:il)?|maj|may|jun[ie]?|jul[iy]?"
    r"|aug(?:usti|ust)?|sep(?:t(?:ember)?)?|okt(?:ober)?|oct(?:ober)?|nov(?:ember)?"
    r"|dec(?:ember)?)\.?"
)
_OPEN = r"(?:nu|nuvarande|pågående|idag|present|current|now|ongoing)(?!\w)"
_SEP = r"\s*(?P<sep>[-–—])\s*"
_NUM_MONTH = r"(?:0?[1-9]|1[0-2])"


@dataclass(frozen=True)
class DatePattern:
    label: str
    family: str  # formats in the same family are considered consistent
    is_range: bool
    regex: re.Pattern[str]


def _p(label: str, family: str, is_range: bool, pattern: str) -> DatePattern:
    return DatePattern(label, family, is_range, re.compile(pattern, re.IGNORECASE))


# Order matters: longer/more specific patterns first so they consume their text.
PATTERNS: tuple[DatePattern, ...] = (
    _p("Mon YYYY – Mon YYYY", "month-name", True, rf"\b{_M}\s+{_Y}{_SEP}(?:{_M}\s+{_Y}|{_OPEN})"),
    _p("YYYY-MM – YYYY-MM", "iso", True, rf"{_Y}[-./]{_MM}{_SEP}(?:{_Y}[-./]{_MM}|{_OPEN})"),
    _p(
        "MM/YYYY – MM/YYYY",
        "slash",
        True,
        rf"(?<![\d/]){_NUM_MONTH}/{_Y}{_SEP}(?:{_NUM_MONTH}/{_Y}|{_OPEN})",
    ),
    _p("YYYY/YYYY", "ambiguous-slash", True, rf"{_Y}\s*/\s*{_Y}"),
    _p("YYYY – YYYY", "year", True, rf"{_Y}{_SEP}(?:{_Y}|{_OPEN})"),
    _p("Mon YYYY", "month-name", False, rf"\b{_M}\s+{_Y}"),
    _p("YYYY-MM", "iso", False, rf"{_Y}[-./]{_MM}"),
    _p("MM/YYYY", "slash", False, rf"(?<![\d/]){_NUM_MONTH}/{_Y}"),
)


@dataclass(frozen=True)
class DateMatch:
    label: str
    family: str
    is_range: bool
    separator: str | None
    text: str


def find_dates(text: str) -> list[DateMatch]:
    """Find date expressions; each character of the input is claimed by at most one match."""
    taken: list[tuple[int, int]] = []
    matches: list[DateMatch] = []
    for pattern in PATTERNS:
        for m in pattern.regex.finditer(text):
            if any(m.start() < end and start < m.end() for start, end in taken):
                continue
            taken.append((m.start(), m.end()))
            matches.append(
                DateMatch(
                    pattern.label,
                    pattern.family,
                    pattern.is_range,
                    m.groupdict().get("sep"),
                    m.group(0),
                )
            )
    return matches


def check_dates(doc: ExtractedDocument, job: JobAd | None = None) -> CheckResult:
    """Warn about mixed date styles, mixed dashes and ambiguous 'YYYY/YYYY'."""
    matches = find_dates(doc.text)
    if not matches:
        return CheckResult(
            NAME,
            Status.WARN,
            "No dates found; an ATS cannot build your work timeline.",
            "Add start and end dates to each role and education, e.g. 'Jan 2023 – Mar 2025'.",
        )

    labels = Counter(m.label for m in matches)
    families = {m.family for m in matches}
    separators = {m.separator for m in matches if m.separator}
    problems: list[str] = []
    if len(families) > 1:
        problems.append("mixed date formats (" + ", ".join(sorted(labels)) + ")")
    if "-" in separators and separators & {"–", "—"}:
        problems.append("both hyphens (-) and en/em dashes (–) are used in date ranges")
    if "ambiguous-slash" in families:
        problems.append("'YYYY/YYYY' is ambiguous and not a standard range format")

    summary = f"{len(matches)} date expression(s) in {len(labels)} format(s): " + ", ".join(
        f"{label} (x{n})" for label, n in sorted(labels.items())
    )
    if not problems:
        return CheckResult(NAME, Status.PASS, summary + ".", details={"formats": dict(labels)})
    return CheckResult(
        NAME,
        Status.WARN,
        summary + ". Problems: " + "; ".join(problems) + ".",
        "Pick one format for every date, e.g. 'Jan 2023 – Mar 2025' or '2023-01 – 2025-03', "
        "and use the same dash everywhere.",
        details={"formats": dict(labels)},
    )
