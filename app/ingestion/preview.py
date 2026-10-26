"""Print how a file is chunked, to see (and experiment with) chunking. Nothing is stored.

python -m app.ingestion.preview data/sample_docs/orbit_handbook.md
python -m app.ingestion.preview data/sample_docs/orbit_faq.txt --chunk-size 100 --overlap 20
python -m app.ingestion.preview data/sample_docs/orbit_handbook.md --full
"""

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from app.config import get_settings
from app.ingestion.chunking import chunk_document
from app.ingestion.loaders import IngestionError, load_document
from app.logging_setup import configure_logging

PREVIEW_CHARS = 160  # characters of each chunk shown without --full


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show how a document is split into chunks.")
    parser.add_argument("path", type=Path, help="file to load (.pdf, .md, .txt, .docx)")
    parser.add_argument("--chunk-size", type=int, help="tokens per chunk (default from .env)")
    parser.add_argument("--overlap", type=int, help="overlap tokens (default from .env)")
    parser.add_argument("--full", action="store_true", help="print each chunk's full text")
    args = parser.parse_args(argv)

    sys.stdout.reconfigure(encoding="utf-8")  # the Windows console defaults to a legacy encoding
    configure_logging("WARNING")
    settings = get_settings()
    overrides = {"chunk_size_tokens": args.chunk_size, "chunk_overlap_tokens": args.overlap}
    # model_validate re-runs validation, so e.g. an overlap >= chunk size is still rejected.
    try:
        settings = type(settings).model_validate(
            settings.model_dump() | {k: v for k, v in overrides.items() if v is not None}
        )
    except ValidationError as exc:
        parser.error("; ".join(error["msg"] for error in exc.errors()))

    try:
        document = load_document(args.path, settings)
    except (IngestionError, FileNotFoundError) as exc:
        print(f"Cannot ingest: {exc}")
        return 1
    chunks = chunk_document(document, settings)

    print(
        f"{document.source}  type={document.file_type}  pages={document.page_count}  "
        f"chars={len(document.text):,}  hash={document.content_hash[:12]}"
    )
    for warning in document.warnings:
        print(f"  warning: {warning}")
    print(
        f"{len(chunks)} chunks  (size={settings.chunk_size_tokens} tokens, "
        f"overlap={settings.chunk_overlap_tokens})\n"
    )
    for chunk in chunks:
        page = f"  page={chunk.page}" if chunk.page else ""
        section = chunk.section or "-"
        print(f"[{chunk.chunk_index}] {chunk.token_count} tokens{page}  section: {section}")
        text = chunk.text if args.full else chunk.text[:PREVIEW_CHARS].replace("\n", " ")
        suffix = "" if args.full or len(chunk.text) <= PREVIEW_CHARS else " ..."
        print(f"    {text}{suffix}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
