"""Tests for the ingestion endpoints with fake services (no Docker, no models, no network)."""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db.jobs import JobRecord
from app.db.repositories import DocumentRecord
from app.main import create_app


def _job(kind: str, target: str, status: str = "queued") -> JobRecord:
    return JobRecord(
        id=uuid.uuid4(), kind=kind, target=target, status=status, progress_done=0,
        progress_total=0, summary={}, results=[], error=None,
        created_at=datetime.now(UTC), started_at=None, finished_at=None,
    )  # fmt: skip


class FakeRunner:
    def __init__(self) -> None:
        self.files: list[tuple[list[str], list[bytes]]] = []
        self.repos: list[str] = []

    def submit_files(self, upload_dir: Path, names: list[str]) -> JobRecord:
        self.files.append((names, [(upload_dir / n).read_bytes() for n in names]))
        return _job("files", ", ".join(names))

    def submit_repo(self, url: str) -> JobRecord:
        self.repos.append(url)
        return _job("github", url)


class FakeJobs:
    def __init__(self) -> None:
        self.known = _job("github", "https://github.com/a/b", "succeeded")

    def get(self, job_id: uuid.UUID) -> JobRecord | None:
        return self.known if job_id == self.known.id else None

    def list_recent(self, limit: int) -> list[JobRecord]:
        return [self.known]


class FakeRegistry:
    def list_all(self) -> list[DocumentRecord]:
        now = datetime.now(UTC)
        return [DocumentRecord(uuid.uuid4(), "a.md", ".md", "h" * 64, 10, None, 2, now, now)]


class FakeServices:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.runner, self.jobs_store, self.registry_store = FakeRunner(), FakeJobs(), FakeRegistry()

    def job_runner(self) -> FakeRunner:
        return self.runner

    def jobs(self) -> FakeJobs:
        return self.jobs_store

    def registry(self) -> FakeRegistry:
        return self.registry_store

    def close(self) -> None:
        pass


@pytest.fixture
def api(settings: Settings) -> Iterator[tuple[TestClient, FakeServices]]:
    small = settings.model_copy(update={"max_upload_mb": 1, "max_upload_files": 3})
    with TestClient(create_app(small)) as client:
        fake = FakeServices(small)
        client.app.state.services = fake
        yield client, fake


def test_github_ingest_queues_a_job(api) -> None:
    client, fake = api
    response = client.post("/api/ingest/github", json={"url": "https://github.com/pallets/x"})
    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert fake.runner.repos == ["https://github.com/pallets/x"]


def test_github_ingest_rejects_non_github_urls(api) -> None:
    client, fake = api
    response = client.post("/api/ingest/github", json={"url": "https://evil.example/a/b"})
    assert response.status_code == 422
    assert fake.runner.repos == []


def test_upload_saves_files_and_queues_a_job(api) -> None:
    client, fake = api
    files = [("files", ("notes.md", b"# Notes\nhello", "text/markdown")),
             ("files", ("faq.txt", b"Q: A?", "text/plain"))]  # fmt: skip
    response = client.post("/api/ingest/files", files=files)
    assert response.status_code == 202
    assert fake.runner.files == [(["notes.md", "faq.txt"], [b"# Notes\nhello", b"Q: A?"])]


def test_upload_strips_directories_from_file_names(api) -> None:
    client, fake = api
    response = client.post("/api/ingest/files", files=[("files", ("../../evil.md", b"x"))])
    assert response.status_code == 202
    assert fake.runner.files[0][0] == ["evil.md"]


@pytest.mark.parametrize(
    ("files", "code"),
    [
        ([("files", ("data.csv", b"a,b"))], 415),
        ([("files", (".env", b"SECRET=1"))], 400),
        ([("files", ("big.txt", b"x" * (1024 * 1024 + 1)))], 413),
        ([("files", (f"f{i}.md", b"x")) for i in range(4)], 400),
    ],
)
def test_upload_rejects_bad_files(api, files: list, code: int) -> None:
    client, fake = api
    assert client.post("/api/ingest/files", files=files).status_code == code
    assert fake.runner.files == []


def test_get_job_and_404(api) -> None:
    client, fake = api
    assert client.get(f"/api/jobs/{fake.jobs_store.known.id}").json()["status"] == "succeeded"
    assert client.get(f"/api/jobs/{uuid.uuid4()}").status_code == 404
    assert client.get("/api/jobs/not-a-uuid").status_code == 422


def test_list_jobs_and_documents(api) -> None:
    client, _ = api
    assert len(client.get("/api/jobs").json()) == 1
    assert client.get("/api/documents").json()[0]["source"] == "a.md"
