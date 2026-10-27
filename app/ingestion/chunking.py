"""Split a loaded document into chunks: `chunk_document(doc, settings)`.

Two steps:
1. **Sections.** Walk the text line by line and track Markdown headings (`#`, `##`, ...), so each
   piece of text knows its heading path, e.g. "Installation > Before you start". PDF page breaks
   (`\\f`) are tracked too, so each piece knows its page.
2. **Size.** Cut each section into pieces of at most `chunk_size_tokens`, with
   `chunk_overlap_tokens` repeated between neighbours, so an idea cut at a boundary still
   appears whole in one of the two chunks. The cutter prefers paragraph breaks, then line
   breaks, then spaces, so chunks rarely end mid-sentence.

Sections are never merged, so a chunk never mixes two topics.
"""

import hashlib
import re
from dataclasses import dataclass
from functools import lru_cache

import structlog
import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import Settings
from app.ingestion.loaders import PAGE_BREAK
from app.ingestion.models import SECTION_SEPARATOR, Chunk, LoadedDocument

log = structlog.get_logger(__name__)

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")  # "## Title" -> level 2, "Title"
_CODE_FENCE = re.compile(r"^\s*(```|~~~)")  # a "# comment" inside a code block is not a heading


@dataclass(frozen=True)
class Section:
    """A run of text under one heading path, on one page."""

    heading_path: str
    text: str
    page: int | None


def chunk_document(doc: LoadedDocument, settings: Settings) -> list[Chunk]:
    """Turn one document into ordered, fingerprinted chunks."""
    encoding = _encoding(settings.tokenizer_encoding)
    splitter = _splitter(
        settings.tokenizer_encoding, settings.chunk_size_tokens, settings.chunk_overlap_tokens
    )
    chunks: list[Chunk] = []
    for section in split_into_sections(doc.text, paged=doc.page_count is not None):
        for piece in splitter.split_text(section.text):
            text = piece.strip()
            if not text:
                continue
            chunks.append(
                Chunk(
                    text=text,
                    source=doc.source,
                    file_type=doc.file_type,
                    section=section.heading_path,
                    chunk_index=len(chunks),
                    token_count=len(encoding.encode(text, disallowed_special=())),
                    content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    doc_hash=doc.content_hash,
                    page=section.page,
                )
            )
    log.info("document_chunked", source=doc.source, chunks=len(chunks))
    return chunks


def split_into_sections(text: str, paged: bool = False) -> list[Section]:
    """Split text into sections at Markdown headings (and at page breaks when `paged`).

    The heading line stays in the section text (it helps search later), and its title goes
    into the heading path. A heading with no text of its own (e.g. "## Setup" followed directly
    by "### Wi-Fi") is carried into the next section's text, so no words are ever lost.
    """
    sections: list[Section] = []
    headings: list[
        tuple[int, str]
    ] = []  # stack of (level, title), e.g. [(1, "Guide"), (2, "Setup")]
    lines: list[str] = []
    in_code_block = False

    def flush(page: int | None) -> None:
        body = "\n".join(lines).strip()
        if not _has_body(body):
            return  # only headings so far: keep them and prepend them to the next section
        path = SECTION_SEPARATOR.join(title for _, title in headings)
        sections.append(Section(heading_path=path, text=body, page=page))
        lines.clear()

    for page_number, page_text in enumerate(text.split(PAGE_BREAK), start=1):
        page = page_number if paged else None
        for line in page_text.split("\n"):
            if _CODE_FENCE.match(line):
                in_code_block = not in_code_block
            heading = None if in_code_block else _HEADING.match(line)
            if heading:
                flush(page)
                level, title = len(heading.group(1)), heading.group(2)
                # A new heading closes every heading at the same or a deeper level.
                headings[:] = [(lvl, t) for lvl, t in headings if lvl < level] + [(level, title)]
            lines.append(line)
        flush(page)  # a section never spans two pages, so page numbers stay exact
    return sections


def _has_body(text: str) -> bool:
    """True if the text has at least one non-blank line that is not a heading."""
    return any(line.strip() and not _HEADING.match(line) for line in text.split("\n"))


@lru_cache(maxsize=4)
def _encoding(name: str) -> tiktoken.Encoding:
    return tiktoken.get_encoding(name)


@lru_cache(maxsize=8)
def _splitter(encoding_name: str, chunk_size: int, overlap: int) -> RecursiveCharacterTextSplitter:
    """Build (once per setting combination) a splitter that measures length in tokens."""
    return RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name=encoding_name,
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        disallowed_special=(),  # text like "<|endoftext|>" in a document is just text
    )
