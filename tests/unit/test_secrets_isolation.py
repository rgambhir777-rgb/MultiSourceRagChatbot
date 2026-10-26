"""Secrets in .env must never leak into the process environment (os.environ).

Child processes inherit os.environ, so a leaked OPENAI_API_KEY would be handed to every tool we
start (including `git clone` of untrusted repos in Session 5). Settings read .env directly
through app/config.py; nothing else may copy it into the environment.
"""

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _env_after_importing(module: str, tmp_path: Path) -> str:
    """Import `module` in a fresh Python process that runs next to a fake .env file."""
    (tmp_path / ".env").write_text("LEAK_CANARY=secret-value\n")
    clean_env = {k: v for k, v in os.environ.items() if k != "LEAK_CANARY"}
    clean_env["PYTHONPATH"] = str(PROJECT_ROOT)
    script = f"import os, {module}; print(os.environ.get('LEAK_CANARY', 'not-leaked'))"
    result = subprocess.run(  # noqa: S603 - fixed command, no user input
        [sys.executable, "-c", script],
        cwd=tmp_path,  # libraries search for .env starting from the working directory
        env=clean_env,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def test_importing_the_loader_does_not_leak_dotenv_into_environ(tmp_path: Path) -> None:
    assert _env_after_importing("app.ingestion.loaders", tmp_path) == "not-leaked"


def test_creating_the_app_does_not_leak_dotenv_into_environ(tmp_path: Path) -> None:
    assert _env_after_importing("app.main", tmp_path) == "not-leaked"
