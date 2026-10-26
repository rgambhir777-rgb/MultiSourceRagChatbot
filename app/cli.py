"""Command-line interface for the backend.

    python -m app.cli ingest data/sample_docs            # ingest a folder (recursively)
    python -m app.cli ingest notes.md manual.pdf         # ingest specific files
    python -m app.cli documents                          # list what is indexed

Exit code is 1 if any file failed, so scripts and automations can detect problems.
"""

import argparse
import sys
from pathlib import Path

from app.config import get_settings
from app.db.pool import apply_schema, create_pool
from app.db.repositories import DocumentRegistry
from app.ingestion.pipeline import FileResult, Outcome, open_pipeline
from app.logging_setup import configure_logging


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest", help="index files or folders into the knowledge base")
    ingest.add_argument("paths", nargs="+", type=Path)
    commands.add_parser("documents", help="list indexed documents")
    args = parser.parse_args(argv)

    sys.stdout.reconfigure(encoding="utf-8")  # the Windows console defaults to a legacy encoding
    configure_logging("WARNING")  # keep the CLI output readable; results are printed below

    if args.command == "ingest":
        return _ingest(args.paths)
    return _list_documents()


def _ingest(paths: list[Path]) -> int:
    with open_pipeline(get_settings()) as pipeline:
        results = pipeline.ingest_paths(paths)
    for result in results:
        print(_format_result(result))
    counts = {outcome: sum(r.outcome is outcome for r in results) for outcome in Outcome}
    summary = ", ".join(f"{n} {outcome}" for outcome, n in counts.items() if n)
    print(f"\n{len(results)} file(s): {summary or 'nothing to do'}")
    return 1 if counts[Outcome.FAILED] else 0


def _format_result(result: FileResult) -> str:
    chunks = f"{result.chunks} chunks" if result.chunks else ""
    parts = [f"{result.outcome.value:<10}", f"{result.path.name:<32}", chunks, result.detail]
    return "  ".join(part for part in parts if part).rstrip()


def _list_documents() -> int:
    pool = create_pool(get_settings())
    try:
        apply_schema(pool)
        documents = DocumentRegistry(pool).list_all()
    finally:
        pool.close()
    if not documents:
        print("No documents indexed yet. Try: python -m app.cli ingest data/sample_docs")
        return 0
    print(f"{'source':<32} {'type':<6} {'chunks':>6} {'pages':>5}  {'updated (UTC)':<19}  hash")
    for doc in documents:
        pages = doc.page_count if doc.page_count is not None else "-"
        updated = doc.updated_at.strftime("%Y-%m-%d %H:%M:%S")
        print(
            f"{doc.source:<32} {doc.file_type:<6} {doc.chunk_count:>6} {pages:>5}  "
            f"{updated:<19}  {doc.content_hash[:12]}"
        )
    print(f"\n{len(documents)} document(s), {sum(d.chunk_count for d in documents)} chunks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
