"""Tests for the background JobRunner, run synchronously with fakes."""

import uuid
from pathlib import Path

from app.ingestion.github import RepoError
from app.ingestion.jobs import JobRunner
from app.ingestion.pipeline import FileResult, Outcome


class FakeJobStore:
    def __init__(self) -> None:
        self.events: list[tuple[str, object]] = []

    def mark_running(self, job_id: uuid.UUID) -> None:
        self.events.append(("running", None))

    def update_progress(self, job_id: uuid.UUID, done: int, total: int) -> None:
        self.events.append(("progress", (done, total)))

    def finish(self, job_id: uuid.UUID, summary: dict, results: list) -> None:
        self.events.append(("finish", (summary, results)))

    def fail(self, job_id: uuid.UUID, error: str) -> None:
        self.events.append(("fail", error))


def _runner(store: FakeJobStore) -> JobRunner:
    return JobRunner(store, pipeline=lambda: object())  # type: ignore[arg-type]


def test_successful_job_records_progress_summary_and_results() -> None:
    store = FakeJobStore()

    def work(pipeline, progress):  # noqa: ANN001, ANN202
        progress(1, 2)
        progress(2, 2)
        return [FileResult(Path("a.md"), Outcome.INDEXED, 3),
                FileResult(Path("b.md"), Outcome.FAILED, detail="empty")]  # fmt: skip

    _runner(store)._run(uuid.uuid4(), work)
    assert store.events[:3] == [("running", None), ("progress", (1, 2)), ("progress", (2, 2))]
    kind, (summary, results) = store.events[3]
    assert kind == "finish"
    assert summary == {"indexed": 1, "failed": 1}
    assert results[1] == {"file": "b.md", "outcome": "failed", "chunks": 0, "detail": "empty"}


def test_repo_errors_fail_the_job_with_their_message() -> None:
    store = FakeJobStore()

    def work(pipeline, progress):  # noqa: ANN001, ANN202
        raise RepoError("o/r: repository not found (or it is private)")

    _runner(store)._run(uuid.uuid4(), work)
    assert store.events[-1] == ("fail", "o/r: repository not found (or it is private)")


def test_unexpected_crashes_are_recorded_and_temp_folder_removed(tmp_path: Path) -> None:
    store = FakeJobStore()
    upload_dir = tmp_path / "upload"
    upload_dir.mkdir()

    def work(pipeline, progress):  # noqa: ANN001, ANN202
        raise ConnectionError("qdrant down")

    _runner(store)._run(uuid.uuid4(), work, cleanup=upload_dir)
    assert store.events[-1] == ("fail", "ConnectionError: qdrant down")
    assert not upload_dir.exists()
