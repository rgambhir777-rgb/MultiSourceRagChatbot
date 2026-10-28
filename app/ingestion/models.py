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


SECTION_SEPARATOR = " > "


def with_context(source: str, section: str, text: str) -> str:
    """Prefix text with where it comes from, e.g. "handbook.md > Installation\n\n<text>".

    Used both when embedding chunks (ingestion) and when reranking them (retrieval), so the
    models always see a chunk together with its document and section.
    """
    header = SECTION_SEPARATOR.join(part for part in (source, section) if part)
    return f"{header}\n\n{text}"


# Source-code and plain-config file types accepted from GitHub repos (never from uploads).
# The value is the splitter language used for code-aware chunking (None = generic splitting).
# Code is split at language boundaries (classes, functions) and never parsed for Markdown
# headings: in Python or shell, "# comment" lines are comments, not headings.
CODE_LANGUAGES: dict[str, str | None] = {
    ".py": "python", ".js": "js", ".jsx": "js", ".mjs": "js", ".ts": "ts", ".tsx": "ts",
    ".java": "java", ".kt": "kotlin", ".scala": "scala", ".go": "go", ".rs": "rust",
    ".rb": "ruby", ".php": "php", ".c": "c", ".h": "c", ".cpp": "cpp", ".hpp": "cpp",
    ".cs": "csharp", ".swift": "swift", ".lua": "lua", ".html": "html", ".rst": "rst",
    ".sh": None, ".sql": None, ".css": None, ".toml": None, ".yaml": None, ".yml": None,
    ".ini": None, ".cfg": None, ".json": None,
}  # fmt: skip
