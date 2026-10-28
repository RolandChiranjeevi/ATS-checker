"""Turn check results into a Markdown or HTML report."""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from cv_ats_check.checks.keyword_checks import MATCH_NAME
from cv_ats_check.models import CheckResult, ExtractedDocument, Status
from cv_ats_check.nlp.keywords import KeywordAnalysis

DISCLAIMER_SV = (
    "Detta är en heuristisk lokal kontroll, inte en garanti för hur en specifik "
    "arbetsgivares ATS tolkar CV:t."
)
DISCLAIMER_EN = (
    "This is a heuristic local check, not a guarantee of how a specific employer's ATS "
    "will interpret the CV."
)
PRIVACY_NOTE = "All processing happened locally; no data left your computer."
_TEMPLATE_DIR = Path(__file__).parent / "templates"


@dataclass
class SummaryRow:
    name: str
    status: Status
    note: str = ""


@dataclass
class Report:
    """Everything needed to render a report."""

    source: str
    parser_message: str
    results: list[CheckResult]
    job_provided: bool
    extracted_pages: list[tuple[int, str]] = field(default_factory=list)  # (page, text)
    paginated: bool = True

    @property
    def parser_status(self) -> Status:
        return Status.PASS

    def counts(self) -> dict[Status, int]:
        return {s: sum(r.status is s for r in self.results) for s in Status}

    def summary_rows(self) -> list[SummaryRow]:
        rows = [SummaryRow("Parser status", self.parser_status)]
        for r in self.results:
            analysis = r.details.get("analysis")
            note = f"{analysis.score_pct}%" if r.name == MATCH_NAME and analysis else ""
            rows.append(SummaryRow(r.name, r.status, note))
        if not self.job_provided:
            rows.append(SummaryRow("Job keyword match", Status.PASS, "not run (no --job given)"))
        return rows


def build_report(
    doc: ExtractedDocument,
    results: list[CheckResult],
    job_provided: bool,
    source: str | None = None,
) -> Report:
    """Assemble a Report for a checked document (``source`` overrides the shown file name)."""
    pages = f" ({doc.page_count} page(s))" if doc.paginated else ""
    parser_message = f"Extracted {doc.word_count} words from {doc.file_type.upper()}{pages}."
    by_page: dict[int, list[str]] = {}
    for block in doc.blocks:
        by_page.setdefault(block.page, []).append(block.text)
    extracted_pages = [(page, "\n".join(lines)) for page, lines in sorted(by_page.items())]
    return Report(
        source or doc.path.name,
        parser_message,
        results,
        job_provided,
        extracted_pages=extracted_pages,
        paginated=doc.paginated,
    )


def keyword_lines(analysis: KeywordAnalysis) -> list[str]:
    """The Found / Missing / Frequent lines of the keyword section."""

    def terms(keywords) -> str:
        return ", ".join(k.term for k in keywords) or "-"

    frequent = ", ".join(f"{k.term} ({k.cv_count} times)" for k in analysis.frequent) or "-"
    lines = [
        f"Found: {terms(analysis.found)}",
        f"Missing: {terms(analysis.missing)}",
        f"Frequent: {frequent}",
    ]
    if analysis.has_tiers:
        missing_must = [k for k in analysis.missing if k.tier == "must"]
        missing_nice = [k for k in analysis.missing if k.tier == "nice"]
        lines += [
            f"Missing must-have: {terms(missing_must)}",
            f"Missing nice-to-have: {terms(missing_nice)}",
        ]
    return lines


def _extra_lines(result: CheckResult) -> list[str]:
    analysis = result.details.get("analysis")
    return keyword_lines(analysis) if result.name == MATCH_NAME and analysis else []


def _summary_line(row: SummaryRow) -> str:
    if row.note and row.note.endswith("%"):
        return f"- {row.name}: {row.note} ({row.status.value})"
    if row.note:
        return f"- {row.name}: {row.note}"
    return f"- {row.name}: {row.status.value}"


def render_markdown(report: Report) -> str:
    """Render the report as Markdown."""
    counts = report.counts()
    lines = [
        "# CV ATS Check",
        "",
        f"**File:** {report.source}",
        "",
        f"> {DISCLAIMER_SV}",
        f"> {DISCLAIMER_EN}",
        "",
        "## Summary",
        *(_summary_line(row) for row in report.summary_rows()),
        "",
        f"**Totals:** {counts[Status.PASS]} PASS, {counts[Status.WARN]} WARN, "
        f"{counts[Status.FAIL]} FAIL",
        "",
        "## Details",
        "### Parser status",
        f"PASS – {report.parser_message}",
        "",
    ]
    for r in report.results:
        lines += [f"### {r.name}", f"{r.status.value} – {r.message}"]
        if r.suggestion:
            lines.append(f"Suggestion: {r.suggestion}")
        extra = _extra_lines(r)
        if extra:
            lines.append("")
            lines += [f"{line}  " for line in extra]
        if r.facts:
            lines += ["", "Checked:"]
            for fact in r.facts:
                label = fact.status.value if fact.status else "INFO"
                note = f" ({fact.note})" if fact.note else ""
                lines.append(f"- {fact.label}: {fact.value} – {label}{note}")
                lines += [f"  - <{url}>" for url in fact.links]
        lines.append("")
    lines += ["## Disclaimer", DISCLAIMER_SV, "", DISCLAIMER_EN, "", f"_{PRIVACY_NOTE}_", ""]
    return "\n".join(lines)


def _env() -> Environment:
    return Environment(loader=FileSystemLoader(_TEMPLATE_DIR), autoescape=True)


def render_form(error: str = "", job_text: str = "") -> str:
    """Render the upload form of the local web UI (autoescaped)."""
    return (
        _env()
        .get_template("index.html.j2")
        .render(error=error, job_text=job_text, privacy_note=PRIVACY_NOTE)
    )


def _slug(name: str) -> str:
    """A safe download file name stem (keeps letters incl. å/ä/ö, digits, dot, dash)."""
    return re.sub(r"[^\w.-]+", "_", Path(name).stem).strip("_.") or "cv"


def _data_url(mime: str, content: str) -> str:
    return f"data:{mime};charset=utf-8;base64,{base64.b64encode(content.encode()).decode()}"


def download_links(report: Report) -> list[tuple[str, str, str]]:
    """(label, file name, data: URL) for the Markdown and HTML versions of the report.

    Data URLs are built into the page, so the server never stores the report.
    """
    stem = _slug(report.source)
    return [
        (
            "Download Markdown (.md)",
            f"{stem}-ats-report.md",
            _data_url("text/markdown", render_markdown(report)),
        ),
        (
            "Download HTML (.html)",
            f"{stem}-ats-report.html",
            _data_url("text/html", render_html(report)),
        ),
    ]


def render_html(
    report: Report,
    back_link: str | None = None,
    downloads: list[tuple[str, str, str]] | None = None,
) -> str:
    """Render the report as a standalone HTML page (autoescaped)."""
    return (
        _env()
        .get_template("report.html.j2")
        .render(
            back_link=back_link,
            downloads=downloads,
            report=report,
            counts={s.value: n for s, n in report.counts().items()},
            rows=[(row.name, row.status.value, row.note) for row in report.summary_rows()],
            results=[(r, _extra_lines(r)) for r in report.results],
            disclaimer_sv=DISCLAIMER_SV,
            disclaimer_en=DISCLAIMER_EN,
            privacy_note=PRIVACY_NOTE,
        )
    )
