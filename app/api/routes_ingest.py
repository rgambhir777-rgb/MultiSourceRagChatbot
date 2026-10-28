"""Ingestion endpoints: upload files, add a GitHub repo, follow jobs, list documents.

Ingestion is slow, so the POST endpoints only validate the request and queue a background job,
answering `202 Accepted` with the job. Clients then poll `GET /api/jobs/{id}`.

Database work here is synchronous, so each call runs in a worker thread
(`run_in_threadpool`) and never blocks the server's event loop.
"""

import shutil
import tempfile
import uuid
from dataclasses import asdict
from pathlib import Path, PurePosixPath
from typing import Annotated

import structlog
from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, status
from starlette.concurrency import run_in_threadpool

from app.api.schemas import DocumentResponse, GithubIngestRequest, JobResponse
from app.db.jobs import JobRecord
from app.ingestion.github import RepoError, parse_repo_url
from app.services import Services

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api", tags=["ingestion"])

_UPLOAD_CHUNK_BYTES = 1024 * 1024  # stream uploads to disk 1 MB at a time


def _services(request: Request) -> Services:
    return request.app.state.services


@router.post("/ingest/files", status_code=status.HTTP_202_ACCEPTED, response_model=JobResponse)
async def ingest_files(request: Request, files: Annotated[list[UploadFile], File()]) -> JobResponse:
    """Upload PDF / Markdown / text / Word files and queue them for indexing."""
    services = _services(request)
    settings = services.settings
    if len(files) > settings.max_upload_files:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"at most {settings.max_upload_files} files per upload"
        )
    upload_dir = Path(tempfile.mkdtemp(prefix="ragbot-upload-"))
    try:
        names = [
            await _save_upload(
                upload, upload_dir, settings.allowed_file_types, settings.max_upload_mb
            )
            for upload in files
        ]
        job = await run_in_threadpool(services.job_runner().submit_files, upload_dir, names)
    except BaseException:
        shutil.rmtree(upload_dir, ignore_errors=True)  # the job owns the folder only on success
        raise
    log.info("upload_queued", job_id=str(job.id), files=len(names))
    return _job_response(job)


@router.post("/ingest/github", status_code=status.HTTP_202_ACCEPTED, response_model=JobResponse)
async def ingest_github(request: Request, body: GithubIngestRequest) -> JobResponse:
    """Queue indexing of a public GitHub repository."""
    try:
        parse_repo_url(body.url)  # validate now, so a typo fails immediately with 422
    except RepoError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    job = await run_in_threadpool(_services(request).job_runner().submit_repo, body.url.strip())
    return _job_response(job)


@router.get("/jobs", response_model=list[JobResponse])
async def list_jobs(request: Request, limit: int = Query(20, ge=1, le=100)) -> list[JobResponse]:
    """Most recent ingestion jobs first."""
    jobs = await run_in_threadpool(_services(request).jobs().list_recent, limit)
    return [_job_response(job) for job in jobs]


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(request: Request, job_id: uuid.UUID) -> JobResponse:
    job = await run_in_threadpool(_services(request).jobs().get, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
    return _job_response(job)


@router.get("/documents", response_model=list[DocumentResponse])
async def list_documents(request: Request) -> list[DocumentResponse]:
    """Every indexed document, alphabetically."""
    documents = await run_in_threadpool(_services(request).registry().list_all)
    return [DocumentResponse(**asdict(doc)) for doc in documents]


async def _save_upload(
    upload: UploadFile, folder: Path, allowed_types: list[str], max_mb: int
) -> str:
    """Validate one upload's name and type, then stream it to disk within the size limit."""
    # Keep only the final name component: "../../etc/passwd" or "C:\\x\\y.pdf" become safe.
    name = PurePosixPath((upload.filename or "").replace("\\", "/")).name.strip()
    if not name or name.startswith("."):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "every file needs a normal file name")
    if Path(name).suffix.lower() not in allowed_types:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"{name}: only {', '.join(allowed_types)} files are supported",
        )
    limit, written = max_mb * 1024 * 1024, 0
    with (folder / name).open("wb") as target:
        while chunk := await upload.read(_UPLOAD_CHUNK_BYTES):
            written += len(chunk)
            if written > limit:
                raise HTTPException(
                    status.HTTP_413_CONTENT_TOO_LARGE, f"{name}: larger than {max_mb} MB"
                )
            target.write(chunk)
    return name


def _job_response(job: JobRecord) -> JobResponse:
    return JobResponse.model_validate(asdict(job))
