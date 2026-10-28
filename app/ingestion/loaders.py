"""Load a file from disk and turn it into clean text: `load_document(path, settings)`.

- `.md` / `.txt` are read directly (they are already text).
- `.docx` is converted to Markdown by MarkItDown, so Word headings become `#` headings that the
  chunker uses as section labels.
- `.pdf` is read page by page with pdfplumber. Pages are joined with a form-feed character
  (`\\f`), so every chunk can remember its page number, and near-empty pages (usually scanned
  images) can be reported.

Every failure raises a specific `IngestionError` subclass with a clear message, so callers (the
CLI now, the ingestion API later) can tell the user exactly what went wrong.
"""

import hashlib
import io
import re
import zipfile
from pathlib import Path

import dotenv
import pdfplumber
import structlog

from app.config import Settings
from app.ingestion.models import CODE_LANGUAGES, LoadedDocument

log = structlog.get_logger(__name__)


def _import_markitdown_without_dotenv() -> tuple[type, type]:
    """Import MarkItDown's DOCX converter WITHOUT its side effect on secrets.

    MarkItDown depends on `magika`, which calls `dotenv.load_dotenv()` when imported. That
    copies every value in our `.env` (the OpenAI key, the database password) into `os.environ`,
    where every child process (e.g. `git clone` of an untrusted repo) would inherit it. Our
    settings are read only through app/config.py, so we disable load_dotenv during the import.
    """
    real_load_dotenv = dotenv.load_dotenv
    dotenv.load_dotenv = lambda *args, **kwargs: False  # type: ignore[assignment]
    try:
        from markitdown import StreamInfo
        from markitdown.converters import DocxConverter
    finally:
        dotenv.load_dotenv = real_load_dotenv
    return StreamInfo, DocxConverter


StreamInfo, DocxConverter = _import_markitdown_without_dotenv()

PAGE_BREAK = "\f"
TEXT_TYPES = {".md", ".txt"}
# "Magic bytes": every real PDF starts with %PDF- and every DOCX (a zip archive) with PK\x03\x04.
# Checking them catches files whose extension lies.
MAGIC_BYTES = {".pdf": b"%PDF-", ".docx": b"PK\x03\x04"}
# Control characters other than tab (\t), newline (\n) and form feed (\f) are junk from bad
# conversions and can break JSON or databases later.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0d-\x1f\x7f]")
_MANY_BLANK_LINES = re.compile(r"\n{3,}")


class IngestionError(Exception):
    """Base class for every "this file cannot be ingested" problem."""


class UnsupportedFileTypeError(IngestionError):
    pass


class FileTooLargeError(IngestionError):
    pass


class DocumentParseError(IngestionError):
    """The file is corrupt or not really the type its extension claims."""


class EmptyDocumentError(IngestionError):
    """The file contains no usable text."""


class ScannedDocumentError(EmptyDocumentError):
    """A PDF whose pages are images: there is no text to extract without OCR."""


def load_document(
    path: Path, settings: Settings, *, source: str | None = None, allow_code: bool = False
) -> LoadedDocument:
    """Read, convert and clean one file. Raises an IngestionError subclass on any problem.

    `source` overrides the name used in citations (default: the file name); GitHub ingestion
    passes "owner/repo/path/file.py". `allow_code` also accepts source-code types, which only
    repo ingestion enables.
    """
    file_type = path.suffix.lower()
    raw = _read_checked(path, file_type, settings, allow_code)

    warnings: list[str] = []
    page_count = None
    if file_type in TEXT_TYPES or file_type in CODE_LANGUAGES:
        text = _decode_text(raw, warnings)
    elif file_type == ".pdf":
        pages = _extract_pdf_pages(path.name, raw)
        page_count = len(pages)
        _check_pdf_pages(path.name, pages, settings.min_chars_per_pdf_page, warnings)
        text = PAGE_BREAK.join(pages)
    else:
        text = _convert_docx(path.name, raw)

    text = normalize_text(text)
    if not text.replace(PAGE_BREAK, "").strip():
        raise EmptyDocumentError(f"{path.name}: the file contains no text")

    document = LoadedDocument(
        source=source or path.name,
        file_type=file_type,
        text=text,
        content_hash=hashlib.sha256(raw).hexdigest(),
        size_bytes=len(raw),
        page_count=page_count,
        warnings=tuple(warnings),
    )
    log.info(
        "document_loaded",
        source=document.source,
        chars=len(text),
        pages=page_count,
        warnings=len(warnings),
    )
    return document


def normalize_text(text: str) -> str:
    """Clean text without changing its meaning: unify line endings, drop control characters,
    trim trailing spaces and collapse runs of blank lines. Page breaks (\\f) are kept, so page
    numbers stay correct even when a page is empty."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL_CHARS.sub("", text)
    pages = []
    for page in text.split(PAGE_BREAK):
        lines = [line.rstrip() for line in page.split("\n")]
        pages.append(_MANY_BLANK_LINES.sub("\n\n", "\n".join(lines)).strip("\n"))
    return PAGE_BREAK.join(pages)


def _read_checked(path: Path, file_type: str, settings: Settings, allow_code: bool) -> bytes:
    """Validate type, size and file signature, and return the file's bytes."""
    code_ok = allow_code and file_type in CODE_LANGUAGES
    if file_type not in settings.allowed_file_types and not code_ok:
        allowed = ", ".join(settings.allowed_file_types)
        raise UnsupportedFileTypeError(f"{path.name}: '{file_type}' is not supported ({allowed})")

    size_bytes = path.stat().st_size  # check size BEFORE reading the whole file into memory
    if size_bytes > settings.max_upload_mb * 1024 * 1024:
        raise FileTooLargeError(
            f"{path.name}: {size_bytes:,} bytes exceeds the {settings.max_upload_mb} MB limit"
        )

    raw = path.read_bytes()
    magic = MAGIC_BYTES.get(file_type)
    if magic is not None and not raw.startswith(magic):
        raise DocumentParseError(f"{path.name}: not a real {file_type} file (wrong file signature)")
    return raw


def _decode_text(raw: bytes, warnings: list[str]) -> str:
    """Decode text files as UTF-8 (the modern default), falling back to Windows-1252."""
    try:
        return raw.decode("utf-8-sig")  # utf-8-sig also strips a BOM if an editor added one
    except UnicodeDecodeError:
        warnings.append("not valid UTF-8; decoded as Windows-1252, some characters may differ")
        return raw.decode("cp1252", errors="replace")


def _extract_pdf_pages(name: str, raw: bytes) -> list[str]:
    """Return the text of every page, in order (an empty string for a page with no text)."""
    try:
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            pages = []
            for page in pdf.pages:
                pages.append(page.extract_text() or "")
                page.close()  # free the page's cached layout data right away
            return pages
    except Exception as exc:  # pdfplumber/pdfminer raise many types for broken or locked PDFs
        raise DocumentParseError(
            f"{name}: could not be read as a PDF ({type(exc).__name__})"
        ) from exc


def _check_pdf_pages(name: str, pages: list[str], min_chars: int, warnings: list[str]) -> None:
    """Warn about pages with almost no text; fail if every page is like that (scanned PDF)."""
    sparse = [number for number, page in enumerate(pages, start=1) if len(page.strip()) < min_chars]
    if not pages or len(sparse) == len(pages):
        raise ScannedDocumentError(
            f"{name}: no extractable text on any page; it looks scanned (OCR is not supported)"
        )
    for number in sparse:
        warnings.append(f"page {number} has almost no text (scanned image or blank page?)")


def _convert_docx(name: str, raw: bytes) -> str:
    """Convert a Word file with MarkItDown's DOCX converter only. Calling the specific converter
    (not MarkItDown's auto-detect) means a broken file fails loudly instead of silently being
    read as plain text."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if "word/document.xml" not in archive.namelist():
                raise DocumentParseError(f"{name}: zip file is not a Word document")
        result = DocxConverter().convert(io.BytesIO(raw), StreamInfo(extension=".docx"))
    except zipfile.BadZipFile as exc:
        raise DocumentParseError(f"{name}: damaged .docx file (not a valid zip)") from exc
    except DocumentParseError:
        raise
    except Exception as exc:  # the converter raises many types for malformed XML
        raise DocumentParseError(
            f"{name}: could not be read as a DOCX ({type(exc).__name__})"
        ) from exc
    return result.text_content or ""
