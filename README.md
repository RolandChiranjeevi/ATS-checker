# cv-ats-check

A **local**, explainable ATS/CV checker. It reads your CV (PDF or DOCX) and, optionally, a job ad,
and produces a checklist of `PASS` / `WARN` / `FAIL` results with concrete suggestions.
It also works as a portfolio project for software testing: every check is a small pure function
with its own tests.

> Detta är en heuristisk lokal kontroll, inte en garanti för hur en specifik arbetsgivares ATS
> tolkar CV:t.
> *(This is a heuristic local check, not a guarantee of how a specific employer's ATS will
> interpret the CV.)*

## What it does

| Check | What it looks at |
|---|---|
| Readable text | Real text layer vs. scanned/image-only pages, garbled characters |
| Contact details | Name, e-mail, phone (as literal text), LinkedIn/GitHub |
| Section headings | Summary/Profil, Skills/Kompetenser, Experience/Arbetslivserfarenhet, Education/Utbildning, Projects/Projekt: missing, duplicated or not visually distinct |
| Date consistency | Mixed formats (`2023–2025` vs `Jan 2023 - Mar 2025`), mixed dashes, ambiguous `2023/2025` |
| Length and density | Extremely short or long CVs |
| Job keyword match | Keywords from the ad that are found / missing in the CV (Swedish and English) |
| Keyword repetition | Keywords repeated more than a length-scaled limit (over-optimisation) |

## What it does not do

- It does **not** imitate any specific ATS (Workday, Greenhouse, Teamtailor, ...). Results are heuristics.
- It does not give a single "ATS score". Each result is explained.
- It does not rewrite your CV and does not use any AI/LLM service.
- Keyword matching is literal (with plural-`s` folding). It does not understand synonyms or Swedish inflection (e.g. `testning` vs `testa`).
- Scanned PDFs are detected, not OCR'd.

## Privacy

All processing happens **on your computer**. The package has no networking code and no
dependency on any API or cloud service. A test (`tests/test_privacy.py`) blocks sockets during
the whole test run and scans the source for network/AI-client imports. Reports are written only
to the path you choose.

## Install

Requires Python 3.11+.

```bash
git clone <your-repo-url> cv-ats-check
cd cv-ats-check
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Note: PyMuPDF is licensed AGPL-3.0; keep that in mind if you redistribute this tool.

## Usage

```bash
cv-check --cv cv.pdf --job job_ad.txt --output report.md --html report.html
# or without installing the console script:
python cv_check.py --cv cv.pdf --job job_ad.txt --output report.md
```

`--job` is optional; without it the keyword checks are skipped.

Exit codes: `0` no FAIL, `1` at least one FAIL, `2` input error (missing/empty/corrupt/unsupported file).

### Example output

```
# CV ATS Check
## Summary
- Parser status: PASS
- Contact details: PASS
- Readable text: PASS
- Section headings: WARN
- Date consistency: WARN
- Job keyword match: 68% (PASS)

## Details
### Section headings
WARN – Issues: no clear Skills/Kompetenser section.
Suggestion: Add a heading named 'Skills'.

### Job keyword match
Found: playwright, selenium, api testing, ci/cd
Missing: performance testing, jmeter, test strategy
Frequent: testing (14 times)
```

## Architecture

```
src/cv_ats_check/
├── models.py              dataclasses: ExtractedDocument, CheckResult, Status, JobAd
├── extraction/            PDF (PyMuPDF) and DOCX (python-docx) -> ExtractedDocument
├── checks/                one module per check; each is f(doc, job) -> CheckResult | None
├── nlp/                   normalisation, stop words (sv/en), keyword extraction
├── reporting/             Markdown + HTML (Jinja2, autoescaped)
└── cli.py                 argparse, exit codes
```

Design rules: extraction is the only layer that touches files; checks are pure and individually
testable; reporting only knows `CheckResult`. Add a check by writing a function and listing it
in `checks/__init__.py`.

### Keyword method

1. Normalise (Unicode NFC, case-fold, dashes to spaces), tokenise, drop Swedish/English stop
   words and job-ad boilerplate.
2. Count 1-3 word phrases plus a curated list of testing/tech terms.
3. Keep a phrase if it is a tech term, repeats, or sits under a "requirements" heading; rank by
   count × weight (tech ×3, multi-word ×1.5).
4. Drop phrases always contained in a longer kept phrase.
5. Match % = keywords found in the CV / keywords extracted from the ad.
6. Repetition limit = `max(10, ceil(1.2 % of the CV's word count))`.

## Test strategy

- `pytest`, with fixtures generated programmatically (`tests/helpers.py`) from synthetic data, so
  no real personal data is committed.
- Positive and negative cases: normal CV, no contact details, mixed dates, Swedish characters
  (Å Ä Ö), scanned PDF, corrupt PDF, empty file, wrong file type, DOCX.
- Parametrised tests for date formats, phone numbers, section-name synonyms and length limits.
- Keyword matching is tested with Swedish and English job ads.
- CLI end-to-end tests check exit codes and generated reports; HTML output is checked for escaping.
- CI (`.github/workflows/ci.yml`): `ruff check`, `ruff format --check` and `pytest --cov` on
  Python 3.11 and 3.12 for every push and pull request.

```bash
ruff check . && ruff format --check . && pytest --cov=cv_ats_check
```

## Roadmap

See the end of the project hand-off for suggested next improvements: OCR fallback, Swedish
lemmatisation, ATS-parser simulation profiles, multi-column layout detection, a weighted match
score, config file for thresholds, JSON output, and a small web UI.

## License

MIT
