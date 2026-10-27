"""Document hygiene: an itemised review of file name, properties, size, format and links."""

from __future__ import annotations

import re
from pathlib import Path

from cv_ats_check.checks.contact_checks import find_name
from cv_ats_check.models import CheckResult, ExtractedDocument, Fact, JobAd, Status

NAME = "Document hygiene"
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_NAME_LENGTH = 100

_GENERIC_NAME = re.compile(
    r"(?:cv|resume|résumé|curriculum vitae|document|untitled|scan|img|image|file|mitt cv|min cv)"
    r"\s*\d*",
    re.IGNORECASE,
)
_COPY_MARKER = re.compile(
    r"\(\d+\)|\b(?:copy|kopia|final|slutlig|new|ny)\b|\bv\d+\b", re.IGNORECASE
)
_UNUSUAL_CHARS = re.compile(r"[^\w .()\-]")
_EMPTY_METADATA = {"", "(anonymous)", "anonymous"}
_NO_TOOL = {"", "(unspecified)", "(anonymous)", "anonymous", "unknown"}
_TEMPLATE_HINTS = (
    "microsoft word -",
    "document1",
    "untitled",
    "canva",
    "template",
    "lorem ipsum",
    "john doe",
    "jane doe",
    "your name",
    "namn efternamn",
)
_FILE_LIKE_TITLE = re.compile(r"\.(?:docx?|tex|pdf|odt)$", re.IGNORECASE)
_LINK_HOST = re.compile(r"^[a-z][a-z0-9+.-]*://(?:[^/@]*@)?([^/:?#]+)", re.IGNORECASE)
_SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "lnkd.in", "goo.gl", "ow.ly", "buff.ly", "is.gd"}
_PAGE_SIZES = {"A4": (595.0, 842.0), "US Letter": (612.0, 792.0)}  # PDF points
_PAGE_TOLERANCE = 4.0


def _filename_problems(name: str) -> list[str]:
    stem = Path(name).stem
    spaced = re.sub(r"[_\-.]+", " ", stem).strip()
    problems = []
    if _GENERIC_NAME.fullmatch(spaced):
        problems.append(f"the file name '{name}' does not identify you")
    elif _COPY_MARKER.search(spaced):
        problems.append(f"the file name '{name}' looks like a draft or copy")
    if _UNUSUAL_CHARS.search(stem):
        problems.append(f"the file name '{name}' contains unusual characters")
    if len(name) > MAX_NAME_LENGTH:
        problems.append(f"the file name is {len(name)} characters long")
    return problems


def _words(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.casefold()))


def _title_problems(title: str) -> list[str]:
    if title.casefold() in _EMPTY_METADATA:
        return []
    if any(hint in title.casefold() for hint in _TEMPLATE_HINTS) or _FILE_LIKE_TITLE.search(title):
        return [f"the document title is '{title}', a leftover default or file name"]
    return []


def _author_problems(author: str, cv_name: str | None) -> list[str]:
    if author.casefold() in _EMPTY_METADATA:
        return []
    if any(hint in author.casefold() for hint in _TEMPLATE_HINTS):
        return [f"the document author is '{author}', a template placeholder"]
    if cv_name and not _words(author) & _words(cv_name):
        return [f"the document author '{author}' does not match the name '{cv_name}' in the CV"]
    return []


def _page_format(doc: ExtractedDocument) -> tuple[str, str, bool] | None:
    """(description, note, ok) for the first page, or None when the size is unknown."""
    if not doc.paginated or not doc.pages or doc.pages[0].width <= 0:
        return None
    width, height = doc.pages[0].width, doc.pages[0].height
    pages = f"{doc.page_count} page(s)"
    for label, (w, h) in _PAGE_SIZES.items():
        if (abs(width - w) <= _PAGE_TOLERANCE and abs(height - h) <= _PAGE_TOLERANCE) or (
            abs(width - h) <= _PAGE_TOLERANCE and abs(height - w) <= _PAGE_TOLERANCE
        ):
            note = "Standard in Sweden and Europe." if label == "A4" else "Common in the US."
            return f"{label}, {pages}", note, True
    mm = f"{width / 72 * 25.4:.0f} x {height / 72 * 25.4:.0f} mm"
    return (
        f"{mm}, {pages}",
        "Unusual page size; use A4 so it prints and previews as expected.",
        False,
    )


_SCHEME = re.compile(r"^([a-z][a-z0-9+.-]*):", re.IGNORECASE)
_SAFE_SCHEMES = {"http", "https", "mailto"}
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def _scheme(url: str) -> str:
    match = _SCHEME.match(url)
    return match.group(1).lower() if match else "unknown"


def _clickable(url: str) -> str | None:
    """The URL if it is safe to render as a link (http, https, mailto), otherwise None.

    A PDF can hold ``javascript:`` or ``file:`` links; those are listed but never clickable.
    """
    if _scheme(url) not in _SAFE_SCHEMES or _CONTROL_CHARS.search(url):
        return None
    return url.replace(" ", "%20").replace("<", "%3C").replace(">", "%3E").replace('"', "%22")


def _link_hosts(links: list[str]) -> list[str]:
    hosts = []
    for url in links:
        match = _LINK_HOST.match(url)
        if match:
            host = match.group(1).lower().removeprefix("www.")
            if host not in hosts:
                hosts.append(host)
    return hosts


def check_hygiene(doc: ExtractedDocument, job: JobAd | None = None) -> CheckResult:
    """Review file name, properties, size, page format, links and encryption item by item."""
    problems: list[str] = []
    suggestions: list[str] = []
    facts: list[Fact] = []

    name_problems = _filename_problems(doc.name)
    problems += name_problems
    facts.append(
        Fact(
            "File name",
            doc.name,
            Status.WARN if name_problems else Status.PASS,
            "; ".join(name_problems) or "Descriptive, with no copy or draft markers.",
        )
    )

    title = doc.metadata.get("title", "").strip()
    author = doc.metadata.get("author", "").strip()
    cv_name = find_name(doc.lines)
    title_problems = _title_problems(title)
    author_problems = _author_problems(author, cv_name)
    problems += title_problems + author_problems

    if title_problems:
        facts.append(Fact("Title property", title, Status.WARN, "; ".join(title_problems)))
    elif title.casefold() in _EMPTY_METADATA:
        facts.append(
            Fact(
                "Title property", "(not set)", None, "Optional; 'Firstname Lastname - CV' is good."
            )
        )
    else:
        facts.append(Fact("Title property", title, Status.PASS, "Looks intentional."))

    if author_problems:
        facts.append(Fact("Author property", author, Status.WARN, "; ".join(author_problems)))
    elif author.casefold() in _EMPTY_METADATA:
        facts.append(Fact("Author property", "(not set)", None, "Optional."))
    elif cv_name is None:
        facts.append(
            Fact("Author property", author, None, "No name found in the CV to compare with.")
        )
    else:
        facts.append(Fact("Author property", author, Status.PASS, "Matches the name in the CV."))

    if doc.file_size:
        size_mb = doc.file_size / (1024 * 1024)
        too_big = doc.file_size > MAX_FILE_BYTES
        if too_big:
            problems.append(f"the file is {size_mb:.1f} MB")
        facts.append(
            Fact(
                "File size",
                f"{doc.file_type.upper()}, {size_mb:.2f} MB",
                Status.WARN if too_big else Status.PASS,
                "Over the 2 MB many job portals accept." if too_big else "Under 2 MB.",
            )
        )

    page_format = _page_format(doc)
    if page_format:
        description, note, ok = page_format
        if not ok:
            problems.append("the page size is not A4 or US Letter")
        facts.append(Fact("Page format", description, Status.PASS if ok else Status.WARN, note))

    tools = [
        v
        for v in (doc.metadata.get("creator", ""), doc.metadata.get("producer", ""))
        if v.casefold() not in _NO_TOOL
    ]
    if tools:
        made_with = " / ".join(dict.fromkeys(tools))
        if "canva" in made_with.casefold():
            problems.append("the file was exported from Canva")
            facts.append(
                Fact(
                    "Created with",
                    made_with,
                    Status.WARN,
                    "Canva exports often turn text into graphics; check 'What an ATS sees'.",
                )
            )
        else:
            facts.append(Fact("Created with", made_with, None))

    modified = doc.metadata.get("modified") or doc.metadata.get("created")
    if modified:
        facts.append(Fact("Last modified", modified, None))

    all_links = list(dict.fromkeys(u.strip() for u in doc.links if u.strip()))
    clickable = [c for u in all_links if (c := _clickable(u))]
    unsupported = [u for u in all_links if _clickable(u) is None]
    web_urls = [u for u in clickable if not u.lower().startswith("mailto:")]
    mail_urls = [u for u in clickable if u.lower().startswith("mailto:")]
    if all_links:
        hosts = _link_hosts(web_urls)
        shortened = [h for h in hosts if h in _SHORTENERS]
        notes = []
        if shortened:
            problems.append("a shortened link hides its destination")
            suggestions.append(
                "Write out full URLs; shortened links (bit.ly, lnkd.in ...) hide where they go."
            )
            notes.append(f"Shortened link: {', '.join(shortened)}.")
        if unsupported:
            schemes = ", ".join(sorted({_scheme(u) for u in unsupported}))
            problems.append(f"a link uses a non-web scheme ({schemes})")
            suggestions.append("Remove links that are not normal web or e-mail links.")
            notes.append(f"Not shown as clickable: {schemes} link(s).")
        if not notes:
            notes.append("Click each link to check that it goes where you expect.")

        parts = []
        if web_urls:
            parts.append(f"{len(web_urls)} link(s): {', '.join(hosts) or 'unknown host'}")
        if mail_urls:
            parts.append(f"{len(mail_urls)} e-mail link(s)")
        if unsupported:
            parts.append(f"{len(unsupported)} unsupported link(s)")
        facts.append(
            Fact(
                "Links",
                "; ".join(parts),
                Status.WARN if shortened or unsupported else None,
                " ".join(notes),
                links=tuple(clickable),
            )
        )

    if doc.metadata.get("encrypted") == "yes":
        problems.append("the PDF is protected with an owner password")
        suggestions.append(
            "Export the PDF without password protection or copy restrictions; some parsers "
            "refuse or garble restricted files."
        )
        facts.append(Fact("Encryption", "owner-password protected", Status.WARN, "Restricted PDF."))
    elif doc.metadata.get("encrypted") == "no":
        facts.append(Fact("Encryption", "none", Status.PASS, "No restrictions."))

    if any("file name" in p for p in problems):
        suggestions.insert(0, "Name the file like Firstname_Lastname_CV.pdf, without copy markers.")
    if any("document title" in p or "document author" in p for p in problems):
        suggestions.append(
            "Fix the file's title/author properties (File > Properties) so recruiters and "
            "parsers do not see leftovers from a template."
        )
    if doc.file_size > MAX_FILE_BYTES:
        suggestions.append(
            "Keep the file under 2 MB; some job portals reject larger uploads. Remove or "
            "compress images."
        )
    if any("page size" in p for p in problems):
        suggestions.append("Export the CV on an A4 page.")

    if not problems:
        return CheckResult(
            NAME,
            Status.PASS,
            f"Checked {len(facts)} items; none need attention (see the list below).",
            facts=facts,
        )
    return CheckResult(
        NAME,
        Status.WARN,
        "Found: " + "; ".join(problems) + ".",
        " ".join(suggestions),
        facts=facts,
    )
