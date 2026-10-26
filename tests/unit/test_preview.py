"""Tests for the chunk preview command (python -m app.ingestion.preview)."""

from pathlib import Path

import pytest

from app.ingestion.preview import main

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "sample_docs"


def test_preview_prints_chunks(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(
        [str(SAMPLES / "orbit_troubleshooting.pdf"), "--chunk-size", "200", "--overlap", "20"]
    )
    output = capsys.readouterr().out
    assert exit_code == 0
    assert "pages=2" in output
    assert "page=2" in output


def test_preview_reports_files_it_cannot_ingest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "data.csv"
    path.write_text("a,b")
    assert main([str(path)]) == 1
    assert "Cannot ingest" in capsys.readouterr().out


def test_preview_rejects_overlap_larger_than_chunk() -> None:
    with pytest.raises(SystemExit) as exit_info:
        main([str(SAMPLES / "orbit_faq.txt"), "--chunk-size", "50", "--overlap", "60"])
    assert exit_info.value.code == 2
