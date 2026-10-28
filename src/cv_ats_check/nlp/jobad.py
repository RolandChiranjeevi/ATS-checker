"""Parse explicit requirements from a job ad: experience, languages, work mode, location, degree.

Everything here is regex-based and deliberately conservative: it only reports what the ad says
in so many words, together with the sentence it came from, so the user can verify it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from cv_ats_check.nlp.normalize import tokenize

_EXPERIENCE_WORD = re.compile(r"\b(?:experience|erfarenhet|erfaren|exp)\b", re.IGNORECASE)
_YEARS_EN = re.compile(
    r"(?<![\d.])(\d{1,2})\s*(?:[-–]\s*(\d{1,2}))?\s*\+?\s*(?:years?|yrs?)\b", re.IGNORECASE
)
_YEARS_SV = re.compile(r"(?<![\d.])(\d{1,2})\s*(?:[-–]\s*(\d{1,2}))?\s*\+?\s*års?\b", re.IGNORECASE)

LANGUAGE_NAMES: dict[str, tuple[str, ...]] = {
    "Swedish": ("swedish", "svenska", "svensk"),
    "English": ("english", "engelska", "engelsk"),
    "Norwegian": ("norwegian", "norska", "norsk"),
    "Danish": ("danish", "danska", "dansk"),
    "Finnish": ("finnish", "finska", "finsk"),
    "German": ("german", "tyska", "tysk"),
    "French": ("french", "franska", "fransk"),
    "Spanish": ("spanish", "spanska", "spansk"),
}
_LANGUAGE_CUE = re.compile(
    r"fluen|flytande|proficien|native|mother tongue|modersm[åa]l|spoken|written|verbal|speak"
    r"|talar|tal och skrift|muntlig|skriftlig|goda kunskaper|kunskaper i|beh[äa]rska|language"
    r"|språk|required|krav|must|ska kunna",
    re.IGNORECASE,
)

_WORK_MODES: dict[str, re.Pattern[str]] = {
    "remote": re.compile(
        r"\bremote\b|\bdistans\b|work from home|hemarbete|hemifrån|helt på distans", re.IGNORECASE
    ),
    "hybrid": re.compile(r"\bhybrid\w*|delvis på distans", re.IGNORECASE),
    "on-site": re.compile(
        r"\bon-?site\b|på plats|på kontoret|in the office|in-office|kontorsbaserad", re.IGNORECASE
    ),
}

_LOCATION_LABEL = re.compile(
    r"^\s*(?:location|plats|ort|arbetsplats|place of work|workplace|stad|city)\s*[:\-–]\s*"
    r"(.{2,60}?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_LOCATION_PHRASE = re.compile(
    r"(?i:\b(?:based in|located in|office in|baserad i|placerad i|placering i|kontor i))\s+"
    r"([A-ZÅÄÖ][\wåäöÅÄÖ-]*(?:\s+[A-ZÅÄÖ][\wåäöÅÄÖ-]*)?)"
)

_DEGREE = re.compile(
    r"\b(?:bachelor|master(?:'s|s)?|b\.?sc|m\.?sc|degree|university|högskoleutbildning"
    r"|högskoleexamen|universitetsutbildning|eftergymnasial|yrkeshögskola|civilingenjör"
    r"|kandidatexamen|examen)\b",
    re.IGNORECASE,
)


def snippet(line: str, limit: int = 90) -> str:
    """A short, single-line excerpt of an ad line for display."""
    text = re.sub(r"\s+", " ", line.strip(" \t-•*·–")).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


@dataclass(frozen=True)
class ExperienceRequirement:
    """A years-of-experience requirement and the ad line it came from."""

    years: int
    upper: int | None
    line: str

    @property
    def label(self) -> str:
        return f"{self.years}-{self.upper} years" if self.upper else f"{self.years}+ years"


@dataclass(frozen=True)
class JobRequirements:
    """Explicit requirements found in a job ad."""

    experience: tuple[ExperienceRequirement, ...] = ()
    languages: tuple[str, ...] = ()
    work_modes: tuple[str, ...] = ()
    locations: tuple[str, ...] = ()
    education: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not (
            self.experience or self.languages or self.work_modes or self.locations or self.education
        )


def find_experience_requirements(job_text: str) -> list[ExperienceRequirement]:
    """Years of experience, only on lines that also mention experience ("3+ years experience")."""
    found: list[ExperienceRequirement] = []
    seen: set[tuple[int, int | None]] = set()
    for line in job_text.splitlines():
        if not _EXPERIENCE_WORD.search(line):
            continue
        for pattern in (_YEARS_EN, _YEARS_SV):
            for match in pattern.finditer(line):
                low = int(match.group(1))
                high = int(match.group(2)) if match.group(2) else None
                if not 0 < low <= 40 or (low, high) in seen:
                    continue
                seen.add((low, high))
                found.append(ExperienceRequirement(low, high, snippet(line)))
    return found


def find_language_requirements(job_text: str) -> list[str]:
    """Languages named on lines that look like a language requirement."""
    languages: list[str] = []
    for line in job_text.splitlines():
        if not _LANGUAGE_CUE.search(line):
            continue
        for name, variants in LANGUAGE_NAMES.items():
            pattern = r"\b(?:" + "|".join(variants) + r")\b"
            if name not in languages and re.search(pattern, line, re.IGNORECASE):
                languages.append(name)
    return languages


def mentions_language(cv_text: str, language: str, cv_language: str) -> bool:
    """True if the CV names the language, or is itself written in it (sv/en)."""
    tokens = set(tokenize(cv_text))
    if any(variant in tokens for variant in LANGUAGE_NAMES[language]):
        return True
    return {"sv": "Swedish", "en": "English"}.get(cv_language) == language


def find_work_modes(job_text: str) -> list[str]:
    """Remote / hybrid / on-site mentions."""
    return [mode for mode, pattern in _WORK_MODES.items() if pattern.search(job_text)]


def find_locations(job_text: str) -> list[str]:
    """Places named by a label ("Plats: Karlstad") or a phrase ("based in Stockholm")."""
    places: list[str] = []
    candidates = _LOCATION_LABEL.findall(job_text) + _LOCATION_PHRASE.findall(job_text)
    for candidate in candidates:
        place = candidate.strip(" .,;:")
        if place and place not in places:
            places.append(place)
    return places


def find_education_requirements(job_text: str, limit: int = 2) -> list[str]:
    """Lines that mention a degree or higher education."""
    lines = [snippet(line) for line in job_text.splitlines() if _DEGREE.search(line)]
    return list(dict.fromkeys(lines))[:limit]


def parse_job_requirements(job_text: str) -> JobRequirements:
    """Collect every explicit requirement the ad states."""
    return JobRequirements(
        experience=tuple(find_experience_requirements(job_text)),
        languages=tuple(find_language_requirements(job_text)),
        work_modes=tuple(find_work_modes(job_text)),
        locations=tuple(find_locations(job_text)),
        education=tuple(find_education_requirements(job_text)),
    )
