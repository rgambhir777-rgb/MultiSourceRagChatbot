"""Turn JUnit XML test results into one Markdown report (used by the CI pipeline).

pytest, Vitest and Playwright can all write "JUnit XML", a common test-result format. This
script reads those files and prints a summary table plus the failures, which the CI pipeline
appends to the run's summary page on GitHub ($GITHUB_STEP_SUMMARY).

    python scripts/ci_summary.py reports/              # every *.xml below reports/
    python scripts/ci_summary.py a.xml b.xml --expect backend-unit,e2e

Exit code is always 0: the test jobs themselves decide whether the pipeline fails; this script
only reports.
"""

import argparse
import sys
import xml.etree.ElementTree as ET  # noqa: S405 - parses our own CI's result files only
from dataclasses import dataclass, field
from pathlib import Path

# Friendly names for the result files the pipeline produces (by file stem).
SUITE_NAMES = {
    "backend-unit": "Backend unit tests (pytest)",
    "frontend-unit": "Frontend unit tests (Vitest)",
    "integration": "Integration tests (real Qdrant, Postgres, MLflow)",
    "e2e": "End-to-end browser tests (Playwright)",
}
MAX_FAILURES_LISTED = 20


@dataclass
class SuiteResult:
    key: str
    tests: int = 0
    failed: int = 0
    skipped: int = 0
    seconds: float = 0.0
    failures: list[tuple[str, str]] = field(default_factory=list)  # (test name, first line)

    @property
    def passed(self) -> int:
        return self.tests - self.failed - self.skipped


def parse_junit(path: Path) -> SuiteResult:
    """Count tests, failures and skips by looking at every <testcase> in the file."""
    root = ET.parse(path).getroot()  # noqa: S314 - trusted, CI-generated file
    result = SuiteResult(key=path.stem)
    for case in root.iter("testcase"):
        result.tests += 1
        result.seconds += float(case.get("time") or 0)
        problem = case.find("failure")
        if problem is None:
            problem = case.find("error")
        if problem is not None:
            result.failed += 1
            name = " › ".join(part for part in (case.get("classname"), case.get("name")) if part)
            message = (problem.get("message") or problem.text or "").strip().splitlines()
            result.failures.append((name, message[0][:200] if message else ""))
        elif case.find("skipped") is not None:
            result.skipped += 1
    return result


def render(results: list[SuiteResult], missing: list[str]) -> str:
    """Markdown summary: verdict, one row per suite, then the failures."""
    total_failed = sum(r.failed for r in results)
    total_tests = sum(r.tests for r in results)
    verdict = "✅ All tests passed" if total_failed == 0 else f"❌ {total_failed} test(s) failed"
    lines = [
        "# Test report",
        "",
        f"**{verdict}** ({total_tests} tests in {len(results)} suites)",
        "",
        "| Suite | Result | Passed | Failed | Skipped | Time |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for r in results:
        icon = "✅" if r.failed == 0 else "❌"
        name = SUITE_NAMES.get(r.key, r.key)
        lines.append(
            f"| {name} | {icon} | {r.passed} | {r.failed} | {r.skipped} | {r.seconds:.1f} s |"
        )
    for key in missing:
        lines.append(f"| {SUITE_NAMES.get(key, key)} | ⚪ not run | – | – | – | – |")

    failed = [(r, f) for r in results for f in r.failures]
    if failed:
        lines += ["", "## Failures", ""]
        for r, (name, message) in failed[:MAX_FAILURES_LISTED]:
            lines.append(f"- **{SUITE_NAMES.get(r.key, r.key)}**: `{name}`: {message}")
        if len(failed) > MAX_FAILURES_LISTED:
            lines.append(f"- … and {len(failed) - MAX_FAILURES_LISTED} more")
    lines += [
        "",
        "Detailed reports (Playwright HTML report with screenshots, JUnit XML, API log) are in "
        "this run's **Artifacts** section.",
    ]
    return "\n".join(lines) + "\n"


def find_xml(paths: list[Path]) -> list[Path]:
    found: list[Path] = []
    for path in paths:
        found.extend(sorted(path.rglob("*.xml")) if path.is_dir() else [path])
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarise JUnit XML results as Markdown.")
    parser.add_argument("paths", nargs="+", type=Path, help="JUnit XML files or folders")
    parser.add_argument(
        "--expect", default="", help="comma-separated suite keys that should be present"
    )
    args = parser.parse_args(argv)
    results = [parse_junit(path) for path in find_xml(args.paths) if path.exists()]
    present = {r.key for r in results}
    missing = [key for key in args.expect.split(",") if key and key not in present]
    order = list(SUITE_NAMES)
    results.sort(key=lambda r: order.index(r.key) if r.key in order else len(order))
    sys.stdout.reconfigure(encoding="utf-8")
    print(render(results, missing), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
