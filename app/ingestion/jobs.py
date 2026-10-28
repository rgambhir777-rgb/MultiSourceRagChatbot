"""Run ingestion in the background, one job at a time.

The API must answer within milliseconds, but ingesting a repo can take a minute. So a request
only *creates* a job (status "queued") and returns its id; this runner does the work on a
background thread and records progress in Postgres, where the UI polls it.

A single worker thread means jobs run one after another: two big ingests never fight over
the CPU, and two jobs never index the same file at the same moment.
"""

import uuid
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import structlog

from app.db.jobs import JobRecord, JobStore
from app.ingestion.github import RepoError, remove_tree
from app.ingestion.pipeline import FileResult, IngestionPipeline, ProgressCallback

log = structlog.get_logger(__name__)

# What a job does, given the pipeline and a progress callback.
JobWork = Callable[[IngestionPipeline, ProgressCallback], list[FileResult]]


class JobRunner:
    def __init__(self, jobs: JobStore, pipeline: Callable[[], IngestionPipeline]) -> None:
        self._jobs = jobs
        self._pipeline = pipeline  # a factory: models load on first use, in the worker
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ingest")

    def submit_files(self, upload_dir: Path, names: list[str]) -> JobRecord:
        """Queue ingestion of uploaded files; the upload folder is deleted afterwards."""
        job = self._jobs.create("files", ", ".join(names))
        self._executor.submit(
            self._run,
            job.id,
            lambda p, progress: p.ingest_paths([upload_dir], progress),
            upload_dir,
        )
        return job

    def submit_repo(self, url: str) -> JobRecord:
        """Queue ingestion of a GitHub repository."""
        job = self._jobs.create("github", url)
        self._executor.submit(self._run, job.id, lambda p, progress: p.ingest_repo(url, progress))
        return job

    def shutdown(self) -> None:
        """Stop accepting work. Queued jobs are cancelled (and marked failed at next start)."""
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _run(self, job_id: uuid.UUID, work: JobWork, cleanup: Path | None = None) -> None:
        log.info("job_started", job_id=str(job_id))
        try:
            self._jobs.mark_running(job_id)
            results = work(self._pipeline(), lambda d, t: self._jobs.update_progress(job_id, d, t))
            summary = dict(Counter(r.outcome.value for r in results))
            self._jobs.finish(job_id, summary, [_result_json(r) for r in results])
            log.info("job_succeeded", job_id=str(job_id), **summary)
        except RepoError as exc:
            self._jobs.fail(job_id, str(exc))
            log.warning("job_failed", job_id=str(job_id), error=str(exc))
        except Exception as exc:  # anything unexpected: record it on the job, never lose it
            log.exception("job_crashed", job_id=str(job_id))
            self._jobs.fail(job_id, f"{type(exc).__name__}: {exc}")
        finally:
            if cleanup is not None:
                remove_tree(cleanup)


def _result_json(result: FileResult) -> dict[str, object]:
    return {
        "file": result.name,
        "outcome": result.outcome.value,
        "chunks": result.chunks,
        "detail": result.detail,
    }
