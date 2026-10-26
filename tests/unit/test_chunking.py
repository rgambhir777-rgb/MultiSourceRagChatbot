"""Tests for app.ingestion.chunking: sections, sizes, overlap, fingerprints, and no lost text."""

import re
from pathlib import Path

import pytest

from app.config import Settings
from app.ingestion.chunking import chunk_document, split_into_sections
from app.ingestion.loaders import PAGE_BREAK, load_document
from app.ingestion.models import LoadedDocument

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "sample_docs"
SAMPLE_FILES = sorted(p.name for p in SAMPLES.iterdir())


def _doc(text: str, page_count: int | None = None) -> LoadedDocument:
    return LoadedDocument(
        source="t.md",
        file_type=".md",
        text=text,
        content_hash="doc-hash",
        size_bytes=len(text),
        page_count=page_count,
    )


# ------------------------------------------------------------------- sections


def test_sections_follow_the_heading_hierarchy() -> None:
    text = "# Guide\nIntro.\n## Setup\nSetup text.\n### Wi-Fi\nWi-Fi text.\n## Usage\nUse it."
    paths = [s.heading_path for s in split_into_sections(text)]
    assert paths == ["Guide", "Guide > Setup", "Guide > Setup > Wi-Fi", "Guide > Usage"]


def test_text_before_the_first_heading_has_an_empty_path() -> None:
    sections = split_into_sections("Preface text.\n# Chapter\nBody.")
    assert [(s.heading_path, s.text) for s in sections] == [
        ("", "Preface text."),
        ("Chapter", "# Chapter\nBody."),
    ]


def test_heading_only_sections_merge_into_the_next_section() -> None:
    sections = split_into_sections("# Guide\n## Setup\n### Wi-Fi\nOnly this has text.")
    assert len(sections) == 1
    assert sections[0].heading_path == "Guide > Setup > Wi-Fi"
    assert sections[0].text == "# Guide\n## Setup\n### Wi-Fi\nOnly this has text."


def test_hash_lines_inside_code_blocks_are_not_headings() -> None:
    text = "# Script\n```bash\n# install deps\npip install x\n```\nDone."
    sections = split_into_sections(text)
    assert [s.heading_path for s in sections] == ["Script"]
    assert "# install deps" in sections[0].text


def test_pages_are_tracked_and_headings_carry_across_pages() -> None:
    text = f"# Report\nPage one text.{PAGE_BREAK}Page two text."
    sections = split_into_sections(text, paged=True)
    assert [(s.heading_path, s.page) for s in sections] == [("Report", 1), ("Report", 2)]


def test_unpaged_documents_have_no_page_numbers() -> None:
    assert split_into_sections("Just text.")[0].page is None


# --------------------------------------------------------------- real samples


@pytest.mark.parametrize("file_name", SAMPLE_FILES)
def test_sample_chunks_respect_the_size_limit(settings: Settings, file_name: str) -> None:
    chunks = chunk_document(load_document(SAMPLES / file_name, settings), settings)
    assert chunks, "every sample should produce at least one chunk"
    assert all(0 < c.token_count <= settings.chunk_size_tokens for c in chunks)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


@pytest.mark.parametrize("file_name", SAMPLE_FILES)
def test_chunking_is_deterministic(settings: Settings, file_name: str) -> None:
    document = load_document(SAMPLES / file_name, settings)
    first = chunk_document(document, settings)
    second = chunk_document(document, settings)
    assert first == second
    assert all(c.doc_hash == document.content_hash for c in first)
    assert len({c.content_hash for c in first}) == len(first), "chunk fingerprints are unique"


@pytest.mark.parametrize("file_name", SAMPLE_FILES)
def test_no_words_are_lost(settings: Settings, file_name: str) -> None:
    document = load_document(SAMPLES / file_name, settings)
    chunks = chunk_document(
        document, settings.model_copy(update={"chunk_size_tokens": 60, "chunk_overlap_tokens": 10})
    )
    chunk_words = set(re.findall(r"\w+", " ".join(c.text for c in chunks)))
    assert set(re.findall(r"\w+", document.text)) <= chunk_words


def test_handbook_chunks_carry_section_paths(settings: Settings) -> None:
    chunks = chunk_document(load_document(SAMPLES / "orbit_handbook.md", settings), settings)
    wifi = next(c for c in chunks if "E-207" in c.text)
    assert wifi.section.endswith("Connecting to Wi-Fi")
    assert any(c.section.endswith("Installation > Before you start") for c in chunks)


def test_pdf_chunks_carry_page_numbers(settings: Settings) -> None:
    chunks = chunk_document(
        load_document(SAMPLES / "orbit_troubleshooting.pdf", settings), settings
    )
    assert next(c for c in chunks if "E-207" in c.text).page == 1
    assert next(c for c in chunks if "Contacting support" in c.text).page == 2


# ------------------------------------------------------------- size & overlap


def test_small_chunk_size_creates_more_chunks_with_overlap(settings: Settings) -> None:
    sentences = " ".join(f"Sentence number {i} talks about thermostats." for i in range(60))
    small = settings.model_copy(update={"chunk_size_tokens": 50, "chunk_overlap_tokens": 15})
    chunks = chunk_document(_doc(sentences), small)
    assert len(chunks) > 5
    assert all(c.token_count <= 50 for c in chunks)
    # Overlap: the start of each chunk repeats words from the end of the previous one.
    for previous, current in zip(chunks, chunks[1:], strict=False):
        first_words = " ".join(current.text.split()[:3])
        assert first_words in previous.text


def test_special_token_text_is_treated_as_plain_text(settings: Settings) -> None:
    chunks = chunk_document(_doc("A document that mentions <|endoftext|> literally."), settings)
    assert "<|endoftext|>" in chunks[0].text
