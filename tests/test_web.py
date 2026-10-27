"""Local web UI: behaviour and hardening."""

from __future__ import annotations

import base64
import io
import re
from pathlib import Path

import pytest

from cv_ats_check.web import HOST, MAX_UPLOAD_BYTES, create_app

SRC = Path(__file__).parent.parent / "src" / "cv_ats_check"


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def post_cv(client, path: Path, *, filename: str | None = None, job_text: str = "", **kwargs):
    data = {"cv": (io.BytesIO(path.read_bytes()), filename or path.name), "job_text": job_text}
    return client.post("/check", data=data, content_type="multipart/form-data", **kwargs)


def test_index_serves_the_form_with_security_headers(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b'name="cv"' in response.data and b'name="job_text"' in response.data
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "no-store"


def test_check_with_job_text_returns_full_report(client, fixtures_dir, job_en):
    response = post_cv(
        client, fixtures_dir / "cv_normal_en.pdf", job_text=job_en.read_text("utf-8")
    )
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Job keyword match" in body and "Contact details" in body
    assert "Check another CV" in body
    assert "cv_normal_en.pdf" in body


def test_report_page_has_text_view_and_working_downloads(client, fixtures_dir):
    body = post_cv(client, fixtures_dir / "cv_normal_en.pdf").get_data(as_text=True)
    assert "What an ATS sees" in body and "Anna Testsson" in body
    assert 'download="cv_normal_en-ats-report.md"' in body
    markdown_href = re.search(r'href="(data:text/markdown[^"]+)"', body).group(1)
    decoded = base64.b64decode(markdown_href.split("base64,", 1)[1]).decode()
    assert decoded.startswith("# CV ATS Check")
    assert "cv_normal_en.pdf" in decoded


def test_error_pages_have_no_downloads(client, fixtures_dir):
    body = post_cv(client, fixtures_dir / "cv_corrupt.pdf").get_data(as_text=True)
    assert "download=" not in body


def test_check_without_job_skips_keyword_checks(client, fixtures_dir):
    body = post_cv(client, fixtures_dir / "cv_normal_en.pdf").get_data(as_text=True)
    assert "not run (no --job given)" in body


def test_job_ad_from_uploaded_text_file(client, fixtures_dir, job_sv):
    data = {
        "cv": (io.BytesIO((fixtures_dir / "cv_swedish.pdf").read_bytes()), "cv.pdf"),
        "job_file": (io.BytesIO(job_sv.read_bytes()), "annons.txt"),
    }
    response = client.post("/check", data=data, content_type="multipart/form-data")
    assert response.status_code == 200
    assert "teststrategi" in response.get_data(as_text=True)


def test_docx_upload_works(client, fixtures_dir):
    assert post_cv(client, fixtures_dir / "cv_normal.docx").status_code == 200


def test_missing_cv_is_a_400_with_message(client):
    response = client.post("/check", data={"job_text": "x"}, content_type="multipart/form-data")
    assert response.status_code == 400
    assert "Choose a CV file" in response.get_data(as_text=True)


@pytest.mark.parametrize(
    ("fixture", "filename", "message"),
    [
        ("cv_corrupt.pdf", None, "Could not open PDF"),
        ("cv_empty.pdf", None, "File is empty"),
        ("job_ad_en.txt", "cv.txt", "Unsupported file type"),
    ],
)
def test_bad_uploads_give_400_without_temp_paths(client, fixtures_dir, fixture, filename, message):
    response = post_cv(client, fixtures_dir / fixture, filename=filename)
    body = response.get_data(as_text=True)
    assert response.status_code == 400
    assert message in body
    assert "/tmp" not in body and "/var/folders" not in body


def test_job_text_is_kept_in_the_form_after_an_error(client, fixtures_dir):
    response = post_cv(client, fixtures_dir / "cv_corrupt.pdf", job_text="Requirements Playwright")
    assert "Requirements Playwright" in response.get_data(as_text=True)


def test_empty_job_file_gives_400(client, fixtures_dir):
    data = {
        "cv": (io.BytesIO((fixtures_dir / "cv_normal_en.pdf").read_bytes()), "cv.pdf"),
        "job_file": (io.BytesIO(b"  \n"), "job.txt"),
    }
    response = client.post("/check", data=data, content_type="multipart/form-data")
    assert response.status_code == 400
    assert "empty" in response.get_data(as_text=True)


def test_uploaded_filename_is_escaped(client, fixtures_dir):
    payload = "<img src=x onerror=alert(1)>.pdf"
    response = post_cv(client, fixtures_dir / "cv_normal_en.pdf", filename=payload)
    body = response.get_data(as_text=True)
    assert "<img src=x" not in body
    assert "&lt;img src=x" in body


def test_oversized_upload_gives_413(fixtures_dir):
    app = create_app()
    app.config["MAX_CONTENT_LENGTH"] = 1000
    response = post_cv(app.test_client(), fixtures_dir / "cv_normal_en.pdf")
    assert response.status_code == 413
    assert "too large" in response.get_data(as_text=True)


def test_foreign_host_header_is_rejected(client):
    assert client.get("/", headers={"Host": "evil.example"}).status_code == 400


@pytest.mark.parametrize("host", ["localhost:8765", "127.0.0.1:8765", "[::1]:8765", "localhost"])
def test_loopback_host_headers_are_accepted(client, host):
    assert client.get("/", headers={"Host": host}).status_code == 200


def test_cross_site_post_is_rejected(client, fixtures_dir):
    response = post_cv(
        client, fixtures_dir / "cv_normal_en.pdf", headers={"Origin": "http://evil.example"}
    )
    assert response.status_code == 403


def test_same_origin_post_is_accepted(client, fixtures_dir):
    response = post_cv(
        client, fixtures_dir / "cv_normal_en.pdf", headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200


def test_unknown_route_and_wrong_method(client):
    assert client.get("/nope").status_code == 404
    assert client.get("/check").status_code == 405


def test_server_binds_to_loopback_only():
    source = (SRC / "web.py").read_text(encoding="utf-8")
    assert HOST == "127.0.0.1"
    assert "0.0.0.0" not in source
    assert "host=HOST" in source


def test_upload_limit_is_ten_megabytes():
    assert MAX_UPLOAD_BYTES == 10 * 1024 * 1024
