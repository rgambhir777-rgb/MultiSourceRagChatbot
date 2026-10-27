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

-- Background ingestion jobs (file uploads, GitHub repos), so the API can answer immediately
-- and the UI can poll for progress.
CREATE TABLE IF NOT EXISTS ingest_jobs (
    id              UUID        PRIMARY KEY,
    kind            TEXT        NOT NULL CHECK (kind IN ('files', 'github')),
    target          TEXT        NOT NULL,                        -- file names or repo URL
    status          TEXT        NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
    progress_done   INTEGER     NOT NULL DEFAULT 0,
    progress_total  INTEGER     NOT NULL DEFAULT 0,
    summary         JSONB       NOT NULL DEFAULT '{}'::jsonb,    -- e.g. {"indexed": 3, "failed": 1}
    results         JSONB       NOT NULL DEFAULT '[]'::jsonb,    -- one entry per file
    error           TEXT,                                        -- set when the whole job failed
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ingest_jobs_created_at_idx ON ingest_jobs (created_at DESC);

-- Chat sessions (conversations). The messages themselves are stored by LangGraph's
-- checkpointer (its own tables, keyed by thread_id = this id); this table holds the list
-- shown in the UI's sidebar.
CREATE TABLE IF NOT EXISTS chat_sessions (
    id          UUID        PRIMARY KEY,
    title       TEXT        NOT NULL DEFAULT 'New chat',
    turn_count  INTEGER     NOT NULL DEFAULT 0 CHECK (turn_count >= 0),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS chat_sessions_updated_at_idx ON chat_sessions (updated_at DESC);
