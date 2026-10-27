"""Contact details: name, e-mail, phone, LinkedIn/GitHub."""

from __future__ import annotations

import re

from cv_ats_check.checks.heading_checks import is_section_heading_text
from cv_ats_check.models import CheckResult, ExtractedDocument, JobAd, Status

NAME = "Contact details"

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Swedish/international numbers start with 0, 00 or +; also US style "(555) 123-4567".
PHONE_RE = re.compile(r"(?<![\w/])(?:\+|00|0|\(\d{3}\))[\d () .\-]{6,}\d")
LINKEDIN_RE = re.compile(r"linkedin\.com/(?:in|pub)/[\w%.\-]+", re.IGNORECASE)
GITHUB_RE = re.compile(r"github\.com/[\w.\-]+", re.IGNORECASE)
_YEAR_RE = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")
_NAME_TOKEN_RE = re.compile(r"[^\W\d_](?:[^\W\d_]|['’])*(?:-[^\W\d_]+)*")
_NOT_NAMES = {"curriculum", "vitae", "resume", "résumé", "cv"}


def find_emails(text: str) -> list[str]:
    return EMAIL_RE.findall(text)


def find_phones(text: str) -> list[str]:
    """Return phone-number candidates with 8-15 digits that are not date ranges."""
    phones = []
    for match in PHONE_RE.finditer(text):
        candidate = match.group(0).strip()
        digits = sum(c.isdigit() for c in candidate)
        if not 8 <= digits <= 15:
            continue
        if not candidate.startswith("+") and _YEAR_RE.search(candidate):
            continue
        phones.append(candidate)
    return phones


def _is_name_token(word: str) -> bool:
    return word[0].isupper() and _NAME_TOKEN_RE.fullmatch(word) is not None


def find_name(lines: list[str]) -> str | None:
    """Find a 2-4 word capitalised line near the top of the document."""
    for line in lines[:6]:
        words = line.split()
        if (
            2 <= len(words) <= 4
            and all(_is_name_token(w) for w in words)
            and not is_section_heading_text(line)
            and not ({w.casefold() for w in words} & _NOT_NAMES)
        ):
            return line
    return None


def check_contact_details(doc: ExtractedDocument, job: JobAd | None = None) -> CheckResult:
    """Check that an ATS can find name, e-mail and phone as literal text."""
    haystack = doc.text + "\n" + "\n".join(doc.links)
    has_name = find_name(doc.lines) is not None
    has_email = bool(find_emails(doc.text))
    has_phone = bool(find_phones(doc.text))
    email_only_as_link = not has_email and any(u.lower().startswith("mailto:") for u in doc.links)
    has_linkedin = bool(LINKEDIN_RE.search(haystack))
    has_github = bool(GITHUB_RE.search(haystack))

    found = [
        label
        for label, ok in (
            ("name", has_name),
            ("email", has_email),
            ("phone", has_phone),
            ("LinkedIn", has_linkedin),
            ("GitHub", has_github),
        )
        if ok
    ]
    missing_core = [
        label
        for label, ok in (("name", has_name), ("email", has_email), ("phone", has_phone))
        if not ok
    ]

    suggestions = [f"Write your {label} as plain text near the top." for label in missing_core]
    if email_only_as_link:
        suggestions.append(
            "Your e-mail only exists as a clickable link; also write the address as plain text."
        )
    if not has_linkedin and not has_github:
        suggestions.append("Optional: add a LinkedIn and/or GitHub URL as plain text.")

    if not has_email and not has_phone:
        status = Status.FAIL
    elif missing_core or email_only_as_link:
        status = Status.WARN
    else:
        status = Status.PASS

    message = f"Found: {', '.join(found) or 'nothing'}."
    if missing_core:
        message += f" Missing: {', '.join(missing_core)}."
    return CheckResult(NAME, status, message, " ".join(suggestions))
