"""What the job ad explicitly asks for (experience, languages, work mode, location, degree)."""

from __future__ import annotations

import re
from datetime import date

from cv_ats_check.checks.date_checks import find_dates
from cv_ats_check.checks.heading_checks import heading_section
from cv_ats_check.models import CheckResult, ExtractedDocument, Fact, JobAd, Status
from cv_ats_check.nlp.jobad import mentions_language, parse_job_requirements
from cv_ats_check.nlp.stopwords import detect_language

NAME = "Job ad requirements"

_YEAR = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")
_OPEN_END = re.compile(r"\b(?:nu|nuvarande|pågående|idag|present|current|now|ongoing)\b", re.I)
_MAX_HEADING_WORDS = 5


def _experience_text(doc: ExtractedDocument) -> str:
    """Text under the Experience heading, or the whole CV if there is no such heading."""
    section = None
    lines: list[str] = []
    for block in doc.blocks:
        found = (
            heading_section(block.text) if len(block.text.split()) <= _MAX_HEADING_WORDS else None
        )
        if found:
            section = found
        elif section == "experience":
            lines.append(block.text)
    return "\n".join(lines) if lines else doc.text


def estimate_experience_years(doc: ExtractedDocument, today_year: int | None = None) -> int | None:
    """Span from the earliest start to the latest end of dated ranges in the experience section.

    This is a rough, field-agnostic estimate: gaps and unrelated jobs are counted.
    """
    today = today_year or date.today().year
    starts: list[int] = []
    ends: list[int] = []
    for match in find_dates(_experience_text(doc)):
        if not match.is_range:
            continue
        years = [int(y) for y in _YEAR.findall(match.text)]
        if not years:
            continue
        starts.append(years[0])
        if len(years) > 1:
            ends.append(years[1])
        else:
            ends.append(today if _OPEN_END.search(match.text) else years[0])
    if not starts:
        return None
    return max(0, min(max(ends), today) - min(starts))


def check_job_requirements(
    doc: ExtractedDocument, job: JobAd | None = None, *, today_year: int | None = None
) -> CheckResult | None:
    """List what the ad explicitly requires and compare it with what the CV shows."""
    if job is None:
        return None
    requirements = parse_job_requirements(job.text)
    facts: list[Fact] = []
    problems: list[str] = []
    suggestions: list[str] = []

    if requirements.experience:
        headline = max(requirements.experience, key=lambda r: r.years)
        span = estimate_experience_years(doc, today_year)
        if span is None:
            note = "Could not estimate your experience from the dates in the CV."
        else:
            note = f"Your CV's dated roles span about {span} year(s), in any field."
            if span < headline.years:
                note += " That is shorter than the ad asks; make relevant experience stand out."
        facts.append(
            Fact(
                "Experience asked for",
                f'{headline.label} ("{headline.line}")',
                None,
                note,
            )
        )

    if requirements.languages:
        cv_language = detect_language(doc.text)
        missing = [
            lang
            for lang in requirements.languages
            if not mentions_language(doc.text, lang, cv_language)
        ]
        if missing:
            problems.append(f"the ad asks for {', '.join(missing)}, which the CV does not mention")
            suggestions.append(
                f"If you speak {' / '.join(missing)}, say so (for example in a Languages section)."
            )
        facts.append(
            Fact(
                "Languages asked for",
                ", ".join(requirements.languages),
                Status.WARN if missing else Status.PASS,
                f"Not mentioned in your CV: {', '.join(missing)}."
                if missing
                else "All of them are mentioned in, or match the language of, your CV.",
            )
        )

    if requirements.work_modes:
        facts.append(Fact("Work mode", ", ".join(requirements.work_modes), None))

    if requirements.locations:
        text = doc.text.casefold()
        in_cv = [p for p in requirements.locations if p.casefold() in text]
        absent = [p for p in requirements.locations if p not in in_cv]
        parts = []
        if in_cv:
            parts.append(f"In your CV: {', '.join(in_cv)}.")
        if absent:
            parts.append(f"Not mentioned in your CV: {', '.join(absent)}.")
        facts.append(Fact("Location", ", ".join(requirements.locations), None, " ".join(parts)))

    if requirements.education:
        facts.append(Fact("Education asked for", "; ".join(requirements.education), None))

    if not facts:
        return CheckResult(
            NAME,
            Status.PASS,
            "No explicit experience, language, work-mode, location or degree requirements "
            "were detected in the ad.",
        )
    if problems:
        return CheckResult(
            NAME,
            Status.WARN,
            "Found: " + "; ".join(problems) + ".",
            " ".join(suggestions),
            facts=facts,
        )
    return CheckResult(
        NAME,
        Status.PASS,
        f"Read {len(facts)} requirement(s) from the ad; none conflicts with your CV "
        "(see the list).",
        facts=facts,
    )
