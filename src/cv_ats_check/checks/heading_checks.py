"""Section headings: are the usual sections present, distinct and unique?"""

from __future__ import annotations

import re
import statistics

from cv_ats_check.models import CheckResult, ExtractedDocument, JobAd, Status, TextBlock

NAME = "Section headings"

SECTION_SYNONYMS: dict[str, tuple[str, ...]] = {
    "summary": (
        "summary",
        "profile",
        "professional summary",
        "personal profile",
        "about me",
        "profil",
        "sammanfattning",
        "om mig",
        "personlig profil",
    ),
    "skills": (
        "skills",
        "key skills",
        "technical skills",
        "core competencies",
        "competencies",
        "kompetenser",
        "kompetens",
        "tekniska färdigheter",
        "färdigheter",
        "teknisk kompetens",
        "tekniska kompetenser",
    ),
    "experience": (
        "experience",
        "work experience",
        "professional experience",
        "employment",
        "employment history",
        "work history",
        "arbetslivserfarenhet",
        "arbetserfarenhet",
        "yrkeserfarenhet",
        "erfarenhet",
        "anställningar",
    ),
    "education": ("education", "studies", "utbildning", "utbildningar"),
    "projects": ("projects", "personal projects", "projekt", "egna projekt"),
}
LABELS = {
    "summary": "Summary/Profil",
    "skills": "Skills/Kompetenser",
    "experience": "Experience/Arbetslivserfarenhet",
    "education": "Education/Utbildning",
    "projects": "Projects/Projekt",
}
REQUIRED = ("skills", "experience", "education")
RECOMMENDED = ("summary", "projects")

_LOOKUP = {syn: canon for canon, syns in SECTION_SYNONYMS.items() for syn in syns}
_PARTIAL = re.compile(
    r"\b(?:" + "|".join(sorted(map(re.escape, _LOOKUP), key=len, reverse=True)) + r")\b"
)
_MAX_HEADING_WORDS = 5


def normalize_heading(text: str) -> str:
    """Lower-case, strip decoration such as ':' or '|' and collapse whitespace."""
    return re.sub(r"\s+", " ", text.casefold().strip(" :.-–—•|*#\t"))


def is_section_heading_text(text: str) -> bool:
    """True if the line, taken alone, is one of the known section names."""
    return normalize_heading(text) in _LOOKUP


def _is_distinct(block: TextBlock, body_size: float | None) -> bool:
    """Does the line look like a heading (styled, bold, larger or ALL CAPS)?"""
    if block.heading_style or block.bold:
        return True
    if block.size and body_size and block.size >= body_size * 1.1:
        return True
    letters = [c for c in block.text if c.isalpha()]
    return len(letters) >= 3 and block.text.isupper()


def find_sections(blocks: list[TextBlock]) -> dict[str, list[bool]]:
    """Map section -> one 'looks like a heading' flag per occurrence."""
    sizes = [b.size for b in blocks if b.size]
    body_size = statistics.median(sizes) if sizes else None
    found: dict[str, list[bool]] = {}
    for block in blocks:
        norm = normalize_heading(block.text)
        if not norm or len(norm.split()) > _MAX_HEADING_WORDS:
            continue
        distinct = _is_distinct(block, body_size)
        section = _LOOKUP.get(norm)
        if section is None and distinct and (m := _PARTIAL.search(norm)):
            section = _LOOKUP[m.group(0)]
        if section:
            found.setdefault(section, []).append(distinct)
    return found


def check_headings(doc: ExtractedDocument, job: JobAd | None = None) -> CheckResult:
    """Look for Summary, Skills, Experience, Education and Projects headings."""
    found = find_sections(doc.blocks)
    recognised = [s for s, flags in found.items() if any(flags)]
    unclear = [s for s, flags in found.items() if not any(flags)]
    duplicated = [s for s, flags in found.items() if sum(flags) > 1]
    missing_required = [s for s in REQUIRED if s not in found]
    missing_recommended = [s for s in RECOMMENDED if s not in found]

    problems: list[str] = []
    suggestions: list[str] = []
    for s in missing_required:
        problems.append(f"no clear {LABELS[s]} section")
        suggestions.append(f"Add a heading named '{SECTION_SYNONYMS[s][0].title()}'.")
    for s in unclear:
        problems.append(f"'{LABELS[s]}' is not visually distinct from body text")
        suggestions.append(f"Make the {LABELS[s]} heading bold or larger than the body text.")
    for s in duplicated:
        problems.append(f"'{LABELS[s]}' appears more than once")
        suggestions.append(f"Merge the repeated {LABELS[s]} sections into one.")

    if len(missing_required) >= 2:
        status = Status.FAIL
    elif problems:
        status = Status.WARN
    else:
        status = Status.PASS

    parts = []
    if recognised:
        parts.append("Recognised: " + ", ".join(LABELS[s] for s in recognised) + ".")
    if problems:
        parts.append("Issues: " + "; ".join(problems) + ".")
    if missing_recommended:
        parts.append(
            "Optional sections not found: "
            + ", ".join(LABELS[s] for s in missing_recommended)
            + "."
        )
    return CheckResult(
        NAME,
        status,
        " ".join(parts) or "No section headings recognised.",
        " ".join(suggestions),
        details={"found": found},
    )
