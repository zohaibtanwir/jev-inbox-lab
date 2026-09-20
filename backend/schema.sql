-- Jev Inbox Lab — SQLite schema (PRD section 5)
--
-- Three tables. `emails` is the frozen corpus. `runs` is one row per run.
-- `answers` is one row per (run, email), holding the raw Jev `answers`
-- object unmodified as JSON. Display values are derived at read time.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS emails (
    id        TEXT PRIMARY KEY,   -- Gmail message id, or fixture id
    from_addr TEXT NOT NULL,
    subject   TEXT NOT NULL,
    date      TEXT NOT NULL,      -- ISO 8601 as pulled; not parsed
    body      TEXT NOT NULL       -- plain text, quotes stripped, <= 1500 chars
);

CREATE TABLE IF NOT EXISTS runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at          TEXT    NOT NULL,   -- ISO 8601 UTC
    finished_at         TEXT,               -- NULL while running
    worker_count        INTEGER NOT NULL,
    email_count         INTEGER NOT NULL,
    -- Mandatory for diffs (CLAUDE.md rule 5). model_version is NULL only
    -- between run creation and the first Jev response; the engine fills it
    -- from the first response's `model` field and it never changes after.
    model_version       TEXT,
    question_set_json   TEXT    NOT NULL,   -- exact `questions` object sent
    total_input_tokens  INTEGER NOT NULL DEFAULT 0,
    total_output_tokens INTEGER NOT NULL DEFAULT 0,
    total_cost_usd      REAL    NOT NULL DEFAULT 0.0,
    avg_ms              REAL,
    p95_ms              REAL,
    per_second          REAL,
    failed_count        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS answers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        INTEGER NOT NULL REFERENCES runs(id)   ON DELETE CASCADE,
    email_id      TEXT    NOT NULL REFERENCES emails(id) ON DELETE CASCADE,
    answers_json  TEXT,               -- raw `answers` object from Jev; NULL on error
    latency_ms    INTEGER,
    input_tokens  INTEGER,
    output_tokens INTEGER,
    error         TEXT,               -- NULL on success
    UNIQUE (run_id, email_id)
);

CREATE INDEX IF NOT EXISTS idx_answers_run_id  ON answers(run_id);
CREATE INDEX IF NOT EXISTS idx_answers_email   ON answers(email_id);
CREATE INDEX IF NOT EXISTS idx_runs_started_at ON runs(started_at);

-- Small key/value store. Holds the editable "current" question set (phase 2)
-- so an edit survives a backend restart. Each run still snapshots the exact
-- questions it sent into runs.question_set_json.
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
