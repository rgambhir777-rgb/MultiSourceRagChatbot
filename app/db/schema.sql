-- Application tables. Safe to run any number of times ("IF NOT EXISTS" everywhere), so the
-- app applies it on startup. A row in `documents` means the document is fully indexed in Qdrant
-- (the row is written only after its chunks were stored).

CREATE TABLE IF NOT EXISTS documents (
    id            UUID        PRIMARY KEY,               -- also the doc_id stored with each chunk in Qdrant
    source        TEXT        NOT NULL UNIQUE,           -- file name shown in citations
    file_type     TEXT        NOT NULL,                  -- ".pdf", ".md", ...
    content_hash  CHAR(64)    NOT NULL,                  -- SHA-256 of the file bytes
    size_bytes    BIGINT      NOT NULL CHECK (size_bytes >= 0),
    page_count    INTEGER     CHECK (page_count IS NULL OR page_count > 0),
    chunk_count   INTEGER     NOT NULL CHECK (chunk_count >= 0),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Finding a document by its fingerprint (duplicate detection) should not scan the whole table.
CREATE INDEX IF NOT EXISTS documents_content_hash_idx ON documents (content_hash);
