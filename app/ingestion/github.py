"""Fetch a public GitHub repository safely and pick the files worth indexing.

Repos are untrusted input, so:
- only `https://github.com/<owner>/<repo>` URLs are accepted (the server can't be pointed at
  internal addresses or other protocols),
- the repo size is checked via the GitHub API *before* cloning,
- the clone is shallow (latest commit only), without tags or Git LFS files, with a timeout,
  and with symlinks disabled (a symlink could point at files outside the repo),
- only text/code files under the size limit are kept; binaries, vendored dependencies and
  build output are skipped,
- nothing from the repo is ever executed.
"""

import os
import re
import shutil
import stat
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import structlog

from app.config import Settings
from app.ingestion.models import CODE_LANGUAGES

log = structlog.get_logger(__name__)

_REPO_URL = re.compile(
    r"^https://github\.com/(?P<owner>[A-Za-z0-9-]{1,39})/(?P<name>[A-Za-z0-9._-]{1,100}?)(?:\.git)?/?$"
)
# Folders that hold dependencies, build output or tooling, not the project's own content.
SKIPPED_DIRS = {
    ".git", ".github", "node_modules", "vendor", "dist", "build", "target", "out", "__pycache__",
    ".venv", "venv", "env", ".tox", ".mypy_cache", ".pytest_cache", ".next", "coverage", ".idea",
}  # fmt: skip
# Lock files are huge and machine-generated: useless for answering questions.
SKIPPED_FILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "uv.lock"}


class RepoError(Exception):
    """The repository URL is invalid, the repo is unavailable, or cloning failed."""


@dataclass(frozen=True)
class RepoRef:
    owner: str
    name: str

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.name}"

    @property
    def url(self) -> str:
        return f"https://github.com/{self.slug}.git"


@dataclass(frozen=True)
class RepoFile:
    path: Path  # where the file is on disk (inside the temporary clone)
    source: str  # citation name, e.g. "pallets/itsdangerous/src/itsdangerous/signer.py"


def parse_repo_url(url: str) -> RepoRef:
    """Accept only https://github.com/<owner>/<repo>[.git] (no other hosts or protocols)."""
    match = _REPO_URL.match(url.strip())
    if match is None:
        raise RepoError("only public GitHub repository URLs like https://github.com/owner/repo")
    return RepoRef(match["owner"], match["name"])


def check_repo_size(ref: RepoRef, settings: Settings, client: httpx.Client) -> None:
    """Ask the GitHub API for the repo's size, so oversized repos are refused before cloning."""
    headers = {"Accept": "application/vnd.github+json"}
    if settings.github_token is not None:
        headers["Authorization"] = f"Bearer {settings.github_token.get_secret_value()}"
    response = client.get(f"https://api.github.com/repos/{ref.slug}", headers=headers)
    if response.status_code == 404:
        raise RepoError(f"{ref.slug}: repository not found (or it is private)")
    response.raise_for_status()
    size_mb = response.json().get("size", 0) / 1024  # the API reports kilobytes
    if size_mb > settings.github_max_repo_mb:
        raise RepoError(
            f"{ref.slug}: {size_mb:.0f} MB exceeds the {settings.github_max_repo_mb} MB limit"
        )


def clone_repo(ref: RepoRef, destination: Path, settings: Settings) -> None:
    """Shallow-clone the default branch into `destination`, with a hard timeout.

    Runs `git` directly via subprocess (arguments as a list, no shell, so nothing in the URL
    can be interpreted as a command). GitPython's clone timeout doesn't work on Windows.
    """
    git_exe = shutil.which("git")
    if git_exe is None:
        raise RepoError("git is not installed or not on PATH")
    env = {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",  # never hang waiting for a password prompt
        "GIT_LFS_SKIP_SMUDGE": "1",  # don't download large binary (LFS) files
        "GIT_ALLOW_PROTOCOL": "https",  # refuse every other transport (ssh, file, ext, ...)
        # core.symlinks=false checks symlinks out as plain text files.
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "core.symlinks",
        "GIT_CONFIG_VALUE_0": "false",
    }
    url = ref.url
    if settings.github_token is not None:  # optional: private repos / higher rate limits
        token = settings.github_token.get_secret_value()
        url = f"https://x-access-token:{token}@github.com/{ref.slug}.git"
    command = [git_exe, "clone", "--depth=1", "--single-branch", "--no-tags", "--quiet", url]
    try:
        subprocess.run(  # noqa: S603 - fixed argument list, URL validated by parse_repo_url
            [*command, str(destination)],
            env=env,
            capture_output=True,
            timeout=settings.github_clone_timeout_s,
            check=True,
        )
    except subprocess.TimeoutExpired:
        raise RepoError(
            f"{ref.slug}: clone timed out after {settings.github_clone_timeout_s:g}s"
        ) from None
    except subprocess.CalledProcessError as exc:
        # Never echo the command or git's output: the URL may contain the token.
        raise RepoError(f"{ref.slug}: clone failed (git exit code {exc.returncode})") from None


def select_repo_files(root: Path, ref: RepoRef, settings: Settings) -> tuple[list[RepoFile], int]:
    """Return the files worth indexing (sorted), and how many were skipped."""
    wanted_types = set(settings.allowed_file_types) | set(CODE_LANGUAGES)
    max_bytes = settings.github_max_file_kb * 1024
    selected: list[RepoFile] = []
    skipped = 0
    for directory, subdirs, files in os.walk(root):
        subdirs[:] = sorted(d for d in subdirs if d not in SKIPPED_DIRS and not d.startswith("."))
        for name in sorted(files):
            path = Path(directory) / name
            if not _is_wanted(path, wanted_types, max_bytes):
                skipped += 1
                continue
            relative = path.relative_to(root).as_posix()
            selected.append(RepoFile(path=path, source=f"{ref.slug}/{relative}"))
    if len(selected) > settings.github_max_files:
        skipped += len(selected) - settings.github_max_files
        selected = selected[: settings.github_max_files]
    return selected, skipped


def remove_tree(path: Path) -> None:
    """Delete a clone. Git marks some files read-only, which Windows refuses to delete, so
    clear that flag and retry."""

    def make_writable_and_retry(func: Callable[..., Any], target: str, _exc: BaseException) -> None:
        os.chmod(target, stat.S_IWRITE)
        func(target)

    shutil.rmtree(path, onexc=make_writable_and_retry)


def _is_wanted(path: Path, wanted_types: set[str], max_bytes: int) -> bool:
    if path.is_symlink() or path.name in SKIPPED_FILES or path.name.startswith("."):
        return False
    if path.suffix.lower() not in wanted_types:
        return False
    size = path.stat().st_size
    if size == 0 or size > max_bytes:
        return False
    with path.open("rb") as handle:
        return b"\x00" not in handle.read(8192)  # a NUL byte early on means binary data
