"""Tests for scripts/ci_summary.py: JUnit XML in, Markdown report out."""

from pathlib import Path

from scripts.ci_summary import main, parse_junit, render

PYTEST_STYLE = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" tests="4">
  <testcase classname="tests.unit.test_a" name="test_ok" time="0.5"/>
  <testcase classname="tests.unit.test_a" name="test_bad" time="0.25">
    <failure message="AssertionError: 1 != 2">details</failure>
  </testcase>
  <testcase classname="tests.unit.test_b" name="test_skip" time="0"><skipped/></testcase>
  <testcase classname="tests.unit.test_b" name="test_crash" time="0.25">
    <error message="ConnectionError: qdrant down"/>
  </testcase>
</testsuite></testsuites>"""

ALL_PASSING = """<testsuites><testsuite>
  <testcase classname="chat.spec.js" name="answers a question" time="11.2"/>
  <testcase classname="chat.spec.js" name="deletes a conversation" time="4.8"/>
</testsuite></testsuites>"""


def _write(folder: Path, name: str, content: str) -> Path:
    path = folder / name
    path.write_text(content, encoding="utf-8")
    return path


def test_parse_counts_passes_failures_errors_and_skips(tmp_path: Path) -> None:
    result = parse_junit(_write(tmp_path, "backend-unit.xml", PYTEST_STYLE))
    assert (result.tests, result.passed, result.failed, result.skipped) == (4, 1, 2, 1)
    assert result.seconds == 1.0
    assert result.failures == [
        ("tests.unit.test_a › test_bad", "AssertionError: 1 != 2"),
        ("tests.unit.test_b › test_crash", "ConnectionError: qdrant down"),
    ]


def test_render_shows_verdict_table_failures_and_missing_suites(tmp_path: Path) -> None:
    results = [
        parse_junit(_write(tmp_path, "backend-unit.xml", PYTEST_STYLE)),
        parse_junit(_write(tmp_path, "e2e.xml", ALL_PASSING)),
    ]
    report = render(results, missing=["integration"])
    assert "❌ 2 test(s) failed" in report
    assert "| Backend unit tests (pytest) | ❌ | 1 | 2 | 1 | 1.0 s |" in report
    assert "| End-to-end browser tests (Playwright) | ✅ | 2 | 0 | 0 | 16.0 s |" in report
    assert "| Integration tests (real Qdrant, Postgres, MLflow) | ⚪ not run |" in report
    assert "`tests.unit.test_a › test_bad`: AssertionError: 1 != 2" in report


def test_all_green_report(tmp_path: Path) -> None:
    report = render([parse_junit(_write(tmp_path, "e2e.xml", ALL_PASSING))], missing=[])
    assert "✅ All tests passed" in report and "## Failures" not in report


def test_main_reads_folders_and_lists_expected_missing_suites(tmp_path: Path, capsys) -> None:  # noqa: ANN001
    (tmp_path / "nested").mkdir()
    _write(tmp_path / "nested", "frontend-unit.xml", ALL_PASSING)
    assert main([str(tmp_path), "--expect", "frontend-unit,e2e"]) == 0
    output = capsys.readouterr().out
    assert "Frontend unit tests (Vitest) | ✅" in output
    assert "End-to-end browser tests (Playwright) | ⚪ not run" in output
