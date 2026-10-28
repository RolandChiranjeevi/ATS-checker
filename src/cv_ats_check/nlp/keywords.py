"""Explainable keyword extraction and matching.

Method (no ML, no external services):

1. Normalise and tokenise the job ad; drop stop words and job-ad boilerplate.
2. Count 1-3 word phrases; add curated tech/testing terms from ``TECH_TERMS``.
3. Keep a phrase if it is a tech term, repeats in the ad, or sits in a
   "requirements" section. Score = count (+ half the requirement-section count)
   x weight (tech x3, multi-word x1.5).
4. Drop a phrase when a longer kept phrase always contains it.
5. Count each keyword in the CV with the same normalisation. Keywords that belong to a
   Swedish/English equivalence group (``nlp/aliases.py``) also count their translations and
   Swedish compound forms, so "test automation" matches "testautomatisering".
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, replace

from cv_ats_check.nlp.aliases import ALIAS_GROUPS, INFLECTIONS
from cv_ats_check.nlp.normalize import stem, tokenize
from cv_ats_check.nlp.stopwords import STOPWORDS, detect_language

MAX_KEYWORDS = 25
MIN_REPETITION_THRESHOLD = 10
REPETITION_RATIO = 0.012  # of the CV's word count

TECH_TERMS: tuple[str, ...] = (
    # languages and tooling
    "python",
    "java",
    "javascript",
    "typescript",
    "c#",
    "c++",
    "sql",
    "bash",
    "git",
    "docker",
    "kubernetes",
    "linux",
    "jenkins",
    "gitlab",
    "github actions",
    "azure devops",
    "ci/cd",
    "jira",
    "confluence",
    "postman",
    "swagger",
    "rest api",
    "api",
    "graphql",
    # test tools
    "playwright",
    "selenium",
    "cypress",
    "appium",
    "junit",
    "testng",
    "pytest",
    "cucumber",
    "robot framework",
    "jmeter",
    "k6",
    "gatling",
    "sonarqube",
    "testrail",
    "xray",
    "browserstack",
    # practices (English)
    "test automation",
    "automated testing",
    "manual testing",
    "api testing",
    "regression testing",
    "exploratory testing",
    "performance testing",
    "load testing",
    "integration testing",
    "unit testing",
    "acceptance testing",
    "end to end",
    "test strategy",
    "test plan",
    "test cases",
    "test design",
    "bdd",
    "tdd",
    "istqb",
    "agile",
    "scrum",
    "kanban",
    "devops",
    "accessibility",
    "security testing",
    "mobile testing",
    # practices (Swedish)
    "testautomatisering",
    "automatiserad testning",
    "manuell testning",
    "api testning",
    "regressionstest",
    "regressionstester",
    "prestandatest",
    "prestandatester",
    "teststrategi",
    "testplan",
    "testfall",
    "acceptanstest",
    "agila metoder",
    "systemtest",
    "integrationstest",
)

_REQ_HEADINGS = (
    "requirements",
    "qualifications",
    "krav",
    "kvalifikationer",
    "meriterande",
    "nice to have",
    "you have",
    "about you",
    "what you bring",
    "your profile",
    "who you are",
    "must have",
    "vi söker dig som",
    "din profil",
    "du har",
    "önskvärt",
    "för dig som",
    "skills",
)
_STOP_HEADINGS = (
    "about us",
    "om oss",
    "we offer",
    "vi erbjuder",
    "what we offer",
    "benefits",
    "how to apply",
    "ansökan",
    "apply",
    "responsibilities",
    "arbetsuppgifter",
    "about the role",
    "om tjänsten",
)


_NICE_HEADINGS = (
    "nice to have",
    "meriterande",
    "önskvärt",
    "good to have",
    "preferred",
    "bonus",
    "det är meriterande",
)
_NICE_INLINE = re.compile(
    r"\b(?:nice to have|a plus|is a plus|are a plus|preferably|preferred|bonus|meriterande"
    r"|önskvärt|en fördel|är ett plus|gärna)\b",
    re.IGNORECASE,
)
# Weights of the keyword score: a missing must-have costs three times a missing nice-to-have.
TIER_WEIGHTS = {"must": 3, "general": 2, "nice": 1}


@dataclass(frozen=True)
class Keyword:
    """A keyword taken from the job ad, with its counts."""

    term: str
    keys: tuple[str, ...]
    job_count: int
    cv_count: int = 0
    is_tech: bool = False
    tier: str = "general"  # "must" (requirements), "nice" (nice-to-have) or "general"


@dataclass
class KeywordAnalysis:
    """Result of comparing a CV against a job ad."""

    found: list[Keyword]
    missing: list[Keyword]
    frequent: list[Keyword]
    threshold: int
    cv_word_count: int
    job_language: str
    cv_language: str

    @property
    def total(self) -> int:
        return len(self.found) + len(self.missing)

    @property
    def match_pct(self) -> int:
        """Plain share of keywords found (every keyword counts the same)."""
        return round(100 * len(self.found) / self.total) if self.total else 0

    @property
    def score_pct(self) -> int:
        """Weighted share: must-have x3, general x2, nice-to-have x1."""
        total = sum(TIER_WEIGHTS[k.tier] for k in self.found + self.missing)
        got = sum(TIER_WEIGHTS[k.tier] for k in self.found)
        return round(100 * got / total) if total else 0

    def tier_counts(self) -> dict[str, tuple[int, int]]:
        """``{tier: (found, total)}`` for must / general / nice."""
        return {
            tier: (
                sum(k.tier == tier for k in self.found),
                sum(k.tier == tier for k in self.found + self.missing),
            )
            for tier in TIER_WEIGHTS
        }

    @property
    def has_tiers(self) -> bool:
        """True when the ad separates requirements or nice-to-haves from the rest."""
        return any(k.tier != "general" for k in self.found + self.missing)


def frequency_threshold(word_count: int) -> int:
    """Max occurrences of one keyword before it looks over-optimised; scales with CV length."""
    return max(MIN_REPETITION_THRESHOLD, math.ceil(REPETITION_RATIO * word_count))


def count_sequence(haystack: list[str], needle: tuple[str, ...]) -> int:
    """Count non-overlapping occurrences of ``needle`` as a contiguous run in ``haystack``."""
    n = len(needle)
    if n == 0:
        return 0
    count = i = 0
    while i <= len(haystack) - n:
        if tuple(haystack[i : i + n]) == needle:
            count += 1
            i += n
        else:
            i += 1
    return count


_SEGMENT_RE = re.compile(r"[\n\r,;:!?()•]+|\.(?=\s|$)")


@dataclass(frozen=True)
class _AliasGroup:
    """One compiled equivalence group (see ``nlp/aliases.py``)."""

    phrases: tuple[tuple[str, ...], ...]  # exact multi-word variants (stemmed)
    singles: frozenset[str]  # exact one-word variants (stemmed)
    prefixes: tuple[str, ...]
    suffixes: tuple[str, ...]
    inflect: tuple[str, ...] = ()  # stems that take Swedish/English endings ("test+")


def _inflects(token: str, stem_: str) -> bool:
    """True if ``token`` is ``stem_`` plus one of the known endings (testet, testning, ...)."""
    return token.startswith(stem_) and token[len(stem_) :] in INFLECTIONS


def _compile_group(variants: tuple[str, ...]) -> tuple[_AliasGroup, list[tuple[str, ...]]]:
    phrases: list[tuple[str, ...]] = []
    singles: set[str] = set()
    prefixes: list[str] = []
    suffixes: list[str] = []
    inflect: list[str] = []
    exact: list[tuple[str, ...]] = []
    for variant in variants:
        if variant.startswith("*"):
            suffixes.append(variant[1:])
        elif variant.endswith("*"):
            prefixes.append(variant[:-1])
        elif variant.endswith("+"):
            inflect.append(variant[:-1])
        else:
            key = tuple(stem(t) for t in tokenize(variant))
            exact.append(key)
            if len(key) == 1:
                singles.add(key[0])
            else:
                phrases.append(key)
    group = _AliasGroup(
        tuple(phrases), frozenset(singles), tuple(prefixes), tuple(suffixes), tuple(inflect)
    )
    return group, exact


def _build_alias_index() -> tuple[
    dict[tuple[str, ...], list[_AliasGroup]], list[tuple[str, _AliasGroup]]
]:
    index: dict[tuple[str, ...], list[_AliasGroup]] = {}
    inflect_index: list[tuple[str, _AliasGroup]] = []
    for variants in ALIAS_GROUPS:
        group, exact = _compile_group(variants)
        for key in exact:
            index.setdefault(key, []).append(group)
        inflect_index += [(stem_, group) for stem_ in group.inflect]
    return index, inflect_index


_ALIAS_INDEX, _INFLECT_INDEX = _build_alias_index()


def _count_group(raw: list[str], keys: list[str], group: _AliasGroup) -> int:
    """Occurrences of any variant; a single word is counted once even if several match."""
    total = sum(count_sequence(keys, phrase) for phrase in group.phrases)
    for token, key in zip(raw, keys, strict=True):
        if (
            key in group.singles
            or any(token.startswith(p) and len(token) > len(p) for p in group.prefixes)
            or any(token.endswith(s) and len(token) > len(s) for s in group.suffixes)
            or any(_inflects(token, s) for s in group.inflect)
        ):
            total += 1
    return total


def count_with_aliases(raw: list[str], keys: list[str], needle: tuple[str, ...]) -> int:
    """Count ``needle`` in the CV, including every equivalent variant (sv/en) of its group."""
    literal = count_sequence(keys, needle)
    groups = list(_ALIAS_INDEX.get(needle, ()))
    if len(needle) == 1:  # a single word may also belong to a group through an inflected stem
        for stem_, group in _INFLECT_INDEX:
            if _inflects(needle[0], stem_) and not any(group is g for g in groups):
                groups.append(group)
    if not groups:
        return literal
    return max(literal, sum(_count_group(raw, keys, group) for group in groups))


def _is_heading(norm: str, vocabulary: tuple[str, ...]) -> bool:
    return len(norm.split()) <= 6 and any(norm.startswith(h) for h in vocabulary)


def requirement_text(job_text: str) -> str:
    """Return the lines of the ad that sit under a requirements-style heading."""
    selected: list[str] = []
    active = False
    for line in job_text.splitlines():
        norm = line.casefold().strip(" :-•*#\t")
        if not norm:
            continue
        if _is_heading(norm, _REQ_HEADINGS):
            active = True
        elif _is_heading(norm, _STOP_HEADINGS):
            active = False
        if active:
            selected.append(line)
    return "\n".join(selected)


def tier_texts(job_text: str) -> tuple[str, str]:
    """Split the ad into (must-have text, nice-to-have text).

    A line is nice-to-have if it sits under a nice-to-have heading or says so itself
    ("... is a plus", "meriterande"); must-have if it sits under a requirements heading.
    """
    must: list[str] = []
    nice: list[str] = []
    tier: str | None = None
    for line in job_text.splitlines():
        norm = line.casefold().strip(" :-•*#\t")
        if not norm:
            continue
        if _is_heading(norm, _NICE_HEADINGS):
            tier = "nice"
        elif _is_heading(norm, _REQ_HEADINGS):
            tier = "must"
        elif _is_heading(norm, _STOP_HEADINGS):
            tier = None
        line_tier = "nice" if _NICE_INLINE.search(line) else tier
        if line_tier == "must":
            must.append(line)
        elif line_tier == "nice":
            nice.append(line)
    return "\n".join(must), "\n".join(nice)


def _contains(longer: tuple[str, ...], shorter: tuple[str, ...]) -> bool:
    n = len(shorter)
    return any(longer[i : i + n] == shorter for i in range(len(longer) - n + 1))


def extract_job_keywords(job_text: str, max_keywords: int = MAX_KEYWORDS) -> list[Keyword]:
    """Pick the most relevant keywords and phrases from a job ad."""
    keys = [stem(t) for t in tokenize(job_text)]

    counts: Counter[tuple[str, ...]] = Counter()
    surface: dict[tuple[str, ...], str] = {}
    # Phrases never span a line break or punctuation, so list items stay separate.
    for segment in _SEGMENT_RE.split(job_text):
        raw = tokenize(segment)
        seg_keys = [stem(t) for t in raw]
        skip = [t in STOPWORDS or len(t) < 2 for t in raw]
        for n in (1, 2, 3):
            for i in range(len(raw) - n + 1):
                if any(skip[i : i + n]):
                    continue
                key = tuple(seg_keys[i : i + n])
                counts[key] += 1
                surface.setdefault(key, " ".join(raw[i : i + n]))

    tech_keys: set[tuple[str, ...]] = set()
    for term in TECH_TERMS:
        key = tuple(stem(t) for t in tokenize(term))
        found = count_sequence(keys, key)
        if found:
            counts[key] = found
            surface[key] = term
            tech_keys.add(key)

    req_keys = [stem(t) for t in tokenize(requirement_text(job_text))]
    scored: list[tuple[float, tuple[str, ...]]] = []
    for key, count in counts.items():
        in_req = count_sequence(req_keys, key)
        is_tech = key in tech_keys
        if not (is_tech or count >= 2 or in_req >= 1):
            continue
        weight = 3.0 if is_tech else (1.5 if len(key) > 1 else 1.0)
        scored.append((weight * (count + 0.5 * in_req), key))

    candidate_counts = {key: counts[key] for _, key in scored}
    kept: list[tuple[float, tuple[str, ...]]] = []
    for score, key in scored:
        # A tech term is only absorbed by a longer tech phrase, never by generic word runs.
        subsumed = any(
            len(other) > len(key)
            and other_count == counts[key]
            and (key not in tech_keys or other in tech_keys)
            and _contains(other, key)
            for other, other_count in candidate_counts.items()
        )
        if not subsumed:
            kept.append((score, key))

    kept.sort(key=lambda item: (-item[0], surface[item[1]]))

    must_text, nice_text = tier_texts(job_text)
    must_keys = [stem(t) for t in tokenize(must_text)]
    nice_keys = [stem(t) for t in tokenize(nice_text)]

    def tier_of(key: tuple[str, ...]) -> str:
        if count_sequence(must_keys, key):
            return "must"
        return "nice" if count_sequence(nice_keys, key) else "general"

    return [
        Keyword(
            term=surface[key],
            keys=key,
            job_count=counts[key],
            is_tech=key in tech_keys,
            tier=tier_of(key),
        )
        for _, key in kept[:max_keywords]
    ]


def analyze_keywords(cv_text: str, job_text: str) -> KeywordAnalysis:
    """Compare CV text against a job ad: found, missing and over-repeated keywords."""
    cv_raw = tokenize(cv_text)
    cv_keys = [stem(t) for t in cv_raw]
    cv_words = len(cv_text.split())
    threshold = frequency_threshold(cv_words)

    found: list[Keyword] = []
    missing: list[Keyword] = []
    for keyword in extract_job_keywords(job_text):
        keyword = replace(keyword, cv_count=count_with_aliases(cv_raw, cv_keys, keyword.keys))
        (found if keyword.cv_count else missing).append(keyword)

    frequent = sorted(
        (k for k in found if k.cv_count > threshold), key=lambda k: (-k.cv_count, k.term)
    )
    return KeywordAnalysis(
        found=found,
        missing=missing,
        frequent=frequent,
        threshold=threshold,
        cv_word_count=cv_words,
        job_language=detect_language(job_text),
        cv_language=detect_language(cv_text),
    )
