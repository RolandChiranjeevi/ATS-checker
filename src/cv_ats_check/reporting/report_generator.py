"""Turn check results into a Markdown or HTML report."""

from __future__ import annotations

from dataclasses import dataclass
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

    @property
    def parser_status(self) -> Status:
        return Status.PASS

    def counts(self) -> dict[Status, int]:
        return {s: sum(r.status is s for r in self.results) for s in Status}

    def summary_rows(self) -> list[SummaryRow]:
        rows = [SummaryRow("Parser status", self.parser_status)]
        for r in self.results:
            analysis = r.details.get("analysis")
            note = f"{analysis.match_pct}%" if r.name == MATCH_NAME and analysis else ""
            rows.append(SummaryRow(r.name, r.status, note))
        if not self.job_provided:
            rows.append(SummaryRow("Job keyword match", Status.PASS, "not run (no --job given)"))
        return rows


def build_report(doc: ExtractedDocument, results: list[CheckResult], job_provided: bool) -> Report:
    """Assemble a Report for a checked document."""
    parser_message = (
        f"Extracted {doc.word_count} words from {doc.file_type.upper()} ({doc.page_count} page(s))."
    )
    return Report(doc.path.name, parser_message, results, job_provided)


def keyword_lines(analysis: KeywordAnalysis) -> list[str]:
    """The Found / Missing / Frequent lines of the keyword section."""

    def terms(keywords) -> str:
        return ", ".join(k.term for k in keywords) or "-"

    frequent = ", ".join(f"{k.term} ({k.cv_count} times)" for k in analysis.frequent) or "-"
    return [
        f"Found: {terms(analysis.found)}",
        f"Missing: {terms(analysis.missing)}",
        f"Frequent: {frequent}",
    ]


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
        lines.append("")
    lines += ["## Disclaimer", DISCLAIMER_SV, "", DISCLAIMER_EN, "", f"_{PRIVACY_NOTE}_", ""]
    return "\n".join(lines)


def render_html(report: Report) -> str:
    """Render the report as a standalone HTML page (autoescaped)."""
    env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR), autoescape=True)
    return env.get_template("report.html.j2").render(
        report=report,
        counts={s.value: n for s, n in report.counts().items()},
        rows=[(row.name, row.status.value, row.note) for row in report.summary_rows()],
        results=[(r, _extra_lines(r)) for r in report.results],
        disclaimer_sv=DISCLAIMER_SV,
        disclaimer_en=DISCLAIMER_EN,
        privacy_note=PRIVACY_NOTE,
    )
