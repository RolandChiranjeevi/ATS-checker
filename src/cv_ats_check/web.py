"""Local web UI: upload a CV, paste a job ad, read the report in your browser.

The server binds to 127.0.0.1 only and keeps nothing: the upload lives in a temporary
directory for the duration of one request.
"""

from __future__ import annotations

import argparse
import re
import tempfile
from pathlib import Path

from flask import Flask, abort, request

from cv_ats_check import __version__
from cv_ats_check.extraction import ExtractionError
from cv_ats_check.models import JobAd
from cv_ats_check.reporting import render_form, render_html
from cv_ats_check.service import JobAdError, decode_job_ad, run_check

HOST = "127.0.0.1"
DEFAULT_PORT = 8765
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
_ALLOWED_HOSTNAMES = {"127.0.0.1", "localhost", "[::1]"}
_CSP = "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'"


def _hostname(host_header: str) -> str:
    return host_header if host_header.endswith("]") else host_header.rsplit(":", 1)[0]


def _safe_suffix(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return suffix if re.fullmatch(r"\.[a-z0-9]{1,8}", suffix) else ".bin"


def _read_job(text: str, upload) -> JobAd | None:
    if text.strip():
        return JobAd(text=text)
    if upload is not None and upload.filename:
        return decode_job_ad(upload.read(), Path(upload.filename).name)
    return None


def _form_error(message: str, job_text: str = "", status: int = 400):
    return render_form(error=message, job_text=job_text), status


def create_app() -> Flask:
    """Build the Flask app (a factory so tests get a fresh instance)."""
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

    @app.before_request
    def _guard() -> None:
        # Reject DNS-rebinding (foreign Host) and cross-site form posts (foreign Origin).
        if _hostname(request.host) not in _ALLOWED_HOSTNAMES:
            abort(400)
        origin = request.headers.get("Origin")
        if (
            request.method == "POST"
            and origin
            and origin.rstrip("/") != request.host_url.rstrip("/")
        ):
            abort(403)

    @app.after_request
    def _headers(response):
        response.headers["Content-Security-Policy"] = _CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(413)
    def _too_large(_error):
        return _form_error(f"File too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB).", "", 413)

    @app.get("/")
    def index():
        return render_form()

    @app.post("/check")
    def check():
        upload = request.files.get("cv")
        job_text = request.form.get("job_text", "")
        if upload is None or not upload.filename:
            return _form_error("Choose a CV file (.pdf or .docx).", job_text)
        name = Path(upload.filename).name
        try:
            job = _read_job(job_text, request.files.get("job_file"))
        except JobAdError as exc:
            return _form_error(str(exc), job_text)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / f"upload{_safe_suffix(name)}"
            upload.save(path)
            try:
                report = run_check(path, job, source=name)
            except ExtractionError as exc:
                return _form_error(str(exc).replace(str(path), name), job_text)
        return render_html(report, back_link="/")

    return app


def main(argv: list[str] | None = None) -> None:
    """Start the local server (loopback only)."""
    parser = argparse.ArgumentParser(prog="cv-check-web", description="Local web UI for cv-check.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)
    print(f"cv-check web UI: http://{HOST}:{args.port}  (local only, Ctrl+C to stop)")
    create_app().run(host=HOST, port=args.port, debug=False)


if __name__ == "__main__":
    main()
