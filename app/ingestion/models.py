"""Data shapes that flow through ingestion: a whole loaded document, then its chunks.

They are frozen dataclasses (read-only once created), because a chunk should never be changed
after it has been fingerprinted: its hash would no longer match its text.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LoadedDocument:
    """One file converted to clean Markdown-ish text, ready for chunking."""

    source: str  # file name shown in citations, e.g. "handbook.md"
    file_type: str  # lowercase extension, e.g. ".pdf"
    text: str  # normalised text; Markdown headings (#, ##) mark sections
    content_hash: str  # SHA-256 of the original file bytes: same file => same hash
    size_bytes: int
    page_count: int | None = None  # PDFs only
    warnings: tuple[str, ...] = field(default=())  # e.g. "page 3 has almost no text"


@dataclass(frozen=True)
class Chunk:
    """One passage of a document: the unit we embed, search and cite."""

    text: str
    source: str
    file_type: str
    section: str  # heading path like "Setup > Wi-Fi", or "" when the document has no headings
    chunk_index: int  # 0, 1, 2... position within the document
    token_count: int
    content_hash: str  # SHA-256 of `text`: identical text => identical hash
    doc_hash: str  # content_hash of the parent LoadedDocument
    page: int | None = None  # PDFs only: page the chunk starts on
