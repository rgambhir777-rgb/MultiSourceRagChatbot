"""Tests for app.ingestion.github: URL validation, file selection and clean-up (no network)."""

import os
import stat
from pathlib import Path

import pytest

from app.config import Settings
from app.ingestion.github import RepoError, RepoRef, parse_repo_url, remove_tree, select_repo_files


@pytest.mark.parametrize(
    ("url", "slug"),
    [
        ("https://github.com/pallets/itsdangerous", "pallets/itsdangerous"),
        ("https://github.com/pallets/itsdangerous.git", "pallets/itsdangerous"),
        ("  https://github.com/a-b/c.d_e/  ", "a-b/c.d_e"),
    ],
)
def test_valid_github_urls(url: str, slug: str) -> None:
    assert parse_repo_url(url).slug == slug


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/a/b",  # not https
        "https://evil.example/a/b",  # other host
        "https://github.com.evil.example/a/b",  # look-alike host
        "https://github.com/a",  # no repo
        "https://github.com/a/b/tree/main",  # not a repo root
        "https://github.com/a/b/../c",
        "file:///etc/passwd",
        "git@github.com:a/b.git",  # ssh
        "",
    ],
)
def test_everything_else_is_rejected(url: str) -> None:
    with pytest.raises(RepoError):
        parse_repo_url(url)


def _make(root: Path, relative: str, content: bytes = b"print('hi')\n") -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def test_select_keeps_code_and_docs_and_skips_junk(settings: Settings, tmp_path: Path) -> None:
    for keep in ("README.md", "src/app.py", "docs/guide.rst", "web/ui.tsx", "pyproject.toml"):
        _make(tmp_path, keep)
    for skip in ("node_modules/x/index.js", ".git/config", "dist/bundle.js", ".env",
                 "package-lock.json", "logo.png", "notes.xyz", "empty.py"):  # fmt: skip
        _make(tmp_path, skip, b"" if skip == "empty.py" else b"data")
    _make(tmp_path, "data.py", b"\x00\x01binary")  # binary despite the .py name
    _make(tmp_path, "huge.md", b"x" * (settings.github_max_file_kb * 1024 + 1))

    files, skipped = select_repo_files(tmp_path, RepoRef("o", "r"), settings)
    sources = [f.source for f in files]
    assert sources == [
        "o/r/README.md", "o/r/pyproject.toml", "o/r/docs/guide.rst", "o/r/src/app.py",
        "o/r/web/ui.tsx",
    ]  # fmt: skip
    assert (
        skipped == 7
    )  # .env, lockfile, png, .xyz, empty, binary, huge (skipped dirs: not counted)


def test_select_caps_the_number_of_files(settings: Settings, tmp_path: Path) -> None:
    for i in range(5):
        _make(tmp_path, f"f{i}.md")
    files, skipped = select_repo_files(
        tmp_path, RepoRef("o", "r"), settings.model_copy(update={"github_max_files": 3})
    )
    assert len(files) == 3 and skipped == 2


def test_remove_tree_deletes_read_only_files(tmp_path: Path) -> None:
    target = tmp_path / "clone"
    _make(target, ".git/objects/pack/file.pack", b"x")
    os.chmod(target / ".git/objects/pack/file.pack", stat.S_IREAD)  # git does this on Windows
    remove_tree(target)
    assert not target.exists()
