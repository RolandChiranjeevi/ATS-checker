"""End-to-end tests through the CLI entry point."""

from __future__ import annotations

import pytest

from cv_ats_check.cli import JobAdError, main, read_job_ad


def run(tmp_path, *args):
    out = tmp_path / "out" / "report.md"
    code = main([*args, "--output", str(out)])
    return code, out


def test_full_run_writes_markdown_and_html(tmp_path, fixtures_dir, job_en, capsys):
    html = tmp_path / "report.html"
    code, out = run(
        tmp_path,
        "--cv",
        str(fixtures_dir / "cv_normal_en.pdf"),
        "--job",
        str(job_en),
        "--html",
        str(html),
    )
    assert code == 0
    assert out.read_text(encoding="utf-8").startswith("# CV ATS Check")
    html_text = html.read_text(encoding="utf-8")
    assert "<html" in html_text and "What an ATS sees" in html_text
    assert "download=" not in html_text
    assert "PASS" in capsys.readouterr().out


def test_run_without_job_skips_keyword_checks(tmp_path, fixtures_dir):
    code, out = run(tmp_path, "--cv", str(fixtures_dir / "cv_normal_en.pdf"))
    assert code == 0
    assert "Keyword repetition" not in out.read_text(encoding="utf-8")


def test_docx_is_supported(tmp_path, fixtures_dir):
    code, _ = run(tmp_path, "--cv", str(fixtures_dir / "cv_normal.docx"))
    assert code == 0


def test_fail_result_gives_exit_code_1(tmp_path, fixtures_dir):
    code, out = run(tmp_path, "--cv", str(fixtures_dir / "cv_no_contact.pdf"))
    assert code == 1
    assert "FAIL" in out.read_text(encoding="utf-8")


def test_scanned_pdf_gives_exit_code_1(tmp_path, fixtures_dir):
    code, out = run(tmp_path, "--cv", str(fixtures_dir / "cv_scanned.pdf"))
    assert code == 1
    assert "scanned" in out.read_text(encoding="utf-8")


@pytest.mark.parametrize("name", ["cv_corrupt.pdf", "cv_empty.pdf", "missing.pdf"])
def test_bad_input_gives_exit_code_2_and_no_report(tmp_path, fixtures_dir, capsys, name):
    code, out = run(tmp_path, "--cv", str(fixtures_dir / name))
    assert code == 2
    assert not out.exists()
    assert capsys.readouterr().err.startswith("Error:")


def test_wrong_file_type_gives_exit_code_2(tmp_path, capsys):
    bad = tmp_path / "cv.txt"
    bad.write_text("hello")
    code, _ = run(tmp_path, "--cv", str(bad))
    assert code == 2
    assert "Unsupported file type" in capsys.readouterr().err


def test_missing_job_file_gives_exit_code_2(tmp_path, fixtures_dir):
    code, _ = run(
        tmp_path,
        "--cv",
        str(fixtures_dir / "cv_normal_en.pdf"),
        "--job",
        str(tmp_path / "nope.txt"),
    )
    assert code == 2


def test_empty_job_file_gives_exit_code_2(tmp_path, fixtures_dir):
    empty = tmp_path / "job.txt"
    empty.write_text("  \n")
    code, _ = run(tmp_path, "--cv", str(fixtures_dir / "cv_normal_en.pdf"), "--job", str(empty))
    assert code == 2


def test_missing_required_argument_exits_with_usage_error():
    with pytest.raises(SystemExit) as info:
        main([])
    assert info.value.code == 2


def test_job_ad_encodings(tmp_path):
    utf8 = tmp_path / "utf8.txt"
    utf8.write_text("Vi söker en Göteborgs-testare", encoding="utf-8")
    legacy = tmp_path / "legacy.txt"
    legacy.write_bytes("Vi söker en Göteborgs-testare".encode("cp1252"))
    bom = tmp_path / "bom.txt"
    bom.write_bytes(b"\xef\xbb\xbf" + "Vi söker".encode())
    assert "söker" in read_job_ad(utf8).text
    assert "Göteborgs" in read_job_ad(legacy).text
    assert read_job_ad(bom).text == "Vi söker"


def test_read_job_ad_missing(tmp_path):
    with pytest.raises(JobAdError):
        read_job_ad(tmp_path / "nope.txt")
