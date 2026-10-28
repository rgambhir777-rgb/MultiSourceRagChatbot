"""GitHub ingestion and the jobs table against real services (needs Docker + internet).

Uses a throwaway Qdrant collection and Postgres schema, removed afterwards.
Run with:  pytest -m integration
"""

import uuid
from collections.abc import Iterator

import pytest
from psycopg import sql

from app.config import Settings
from app.ingestion.github import RepoError
from app.ingestion.pipeline import Outcome
from app.services import Services

pytestmark = pytest.mark.integration

TINY_REPO = "https://github.com/octocat/Spoon-Knife"  # GitHub's tiny demo repo (3 files)


@pytest.fixture
def services() -> Iterator[Services]:
    name = f"test_{uuid.uuid4().hex[:10]}"
    services = Services(Settings(qdrant_collection=name, postgres_schema=name))
    try:
        yield services
    finally:
        services.store().drop_collection()
        with services.pool().connection() as conn:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(name)))
        services.close()


def test_ingest_a_public_repo(services: Services) -> None:
    progress: list[tuple[int, int]] = []
    results = services.pipeline().ingest_repo(TINY_REPO, lambda d, t: progress.append((d, t)))
    indexed = sorted(r.name for r in results if r.outcome is Outcome.INDEXED)
    assert indexed == [
        "octocat/Spoon-Knife/README.md",
        "octocat/Spoon-Knife/index.html",
        "octocat/Spoon-Knife/styles.css",
    ]
    assert progress and progress[-1][0] == progress[-1][1]
    again = services.pipeline().ingest_repo(TINY_REPO)
    assert all(r.outcome is Outcome.SKIPPED for r in again)


def test_missing_repo_is_a_clear_error(services: Services) -> None:
    with pytest.raises(RepoError, match="not found"):
        services.pipeline().ingest_repo("https://github.com/octocat/this-repo-does-not-exist-42")


def test_job_lifecycle_in_postgres(services: Services) -> None:
    jobs = services.jobs()
    job = jobs.create("github", TINY_REPO)
    assert job.status == "queued"
    jobs.mark_running(job.id)
    jobs.update_progress(job.id, 1, 2)
    running = jobs.get(job.id)
    assert running is not None and running.status == "running" and running.progress_total == 2
    jobs.finish(job.id, {"indexed": 1}, [{"file": "a", "outcome": "indexed", "chunks": 1}])
    done = jobs.get(job.id)
    assert done is not None and done.status == "succeeded" and done.summary == {"indexed": 1}

    stuck = jobs.create("files", "x.md")
    assert jobs.fail_interrupted() == 1  # e.g. after a crash/restart
    failed = jobs.get(stuck.id)
    assert failed is not None and failed.status == "failed" and "restarted" in (failed.error or "")
