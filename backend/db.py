"""SQLite access. Stdlib sqlite3, no ORM.

The DB file path comes from JEV_DB_PATH (default ./jev_inbox_lab.db). Both
the default name and the `*.db` glob are gitignored — the file holds real
mail in plain text once the real corpus is loaded.
"""

from __future__ import annotations

import json
import os
import random
import sqlite3
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = Path(__file__).with_name("schema.sql")

DB_PATH = Path(os.environ.get("JEV_DB_PATH", REPO_ROOT / "jev_inbox_lab.db"))
CORPUS_PATH = Path(os.environ.get("CORPUS_PATH", REPO_ROOT / "corpus.jsonl"))
FIXTURE_CORPUS_PATH = REPO_ROOT / "fixtures" / "corpus.sample.jsonl"

EMAIL_FIELDS = ("id", "from", "subject", "date", "body")


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: Path = DB_PATH) -> None:
    """Create tables if missing. Safe to call on every boot."""
    with connect(path) as conn:
        conn.executescript(SCHEMA_PATH.read_text())


def read_corpus(path: Path) -> list[dict]:
    """Parse a corpus JSONL file. Each line: {id, from, subject, date, body}."""
    rows: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            missing = [f for f in EMAIL_FIELDS if f not in row]
            if missing:
                raise ValueError(f"{path}:{lineno} missing fields {missing}")
            rows.append(row)
    return rows


def load_emails(rows: Iterable[dict], path: Path = DB_PATH) -> int:
    """Insert emails, ignoring ids already present. Returns rows inserted."""
    with connect(path) as conn:
        before = conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
        conn.executemany(
            "INSERT OR IGNORE INTO emails (id, from_addr, subject, date, body) "
            "VALUES (:id, :from, :subject, :date, :body)",
            list(rows),
        )
        after = conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
    return after - before


def resolve_corpus_path() -> tuple[Path, bool]:
    """Real corpus if present, else the synthetic fixture.

    Returns (path, is_fixture).
    """
    if CORPUS_PATH.exists():
        return CORPUS_PATH, False
    return FIXTURE_CORPUS_PATH, True


def bootstrap(path: Path = DB_PATH) -> dict:
    """First-boot load (PRD section 4). Idempotent."""
    init_db(path)
    corpus_path, is_fixture = resolve_corpus_path()
    inserted = load_emails(read_corpus(corpus_path), path)
    with connect(path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
    return {
        "db_path": str(path),
        "corpus_path": str(corpus_path),
        "is_fixture": is_fixture,
        "inserted": inserted,
        "email_count": total,
    }


def list_emails(path: Path = DB_PATH) -> list[dict]:
    with connect(path) as conn:
        cur = conn.execute(
            "SELECT id, from_addr, subject, date, body FROM emails ORDER BY date"
        )
        return [
            {
                "id": r["id"],
                "from": r["from_addr"],
                "subject": r["subject"],
                "date": r["date"],
                "body": r["body"],
            }
            for r in cur.fetchall()
        ]


SAMPLE_MODES = ("first", "random")


def select_email_ids(
    limit: int | None,
    sample: str = "first",
    seed: int | None = None,
    path: Path = DB_PATH,
) -> list[str]:
    """Pick the emails a run will send to Jev.

    "first"  -> the first `limit` by date (None = all).
    "random" -> `limit` drawn uniformly from the whole corpus with
                random.Random(seed), so a seed makes the pick reproducible.
    The chosen ids are what the engine iterates; each run's `answers` rows
    record them, so a run's selection is always recoverable from the DB.
    """
    if sample not in SAMPLE_MODES:
        raise ValueError(f"sample must be one of {SAMPLE_MODES}")
    with connect(path) as conn:
        ids = [r["id"] for r in conn.execute("SELECT id FROM emails ORDER BY date, id")]
    if limit is None or limit >= len(ids):
        return ids if sample == "first" else random.Random(seed).sample(ids, len(ids))
    if sample == "first":
        return ids[:limit]
    return random.Random(seed).sample(ids, limit)


# ---------------------------------------------------------------------------
# Runs and answers (written by the engine, read by the API)
# ---------------------------------------------------------------------------

RUN_COLUMNS = (
    "id", "started_at", "finished_at", "worker_count", "email_count",
    "model_version", "question_set_json", "total_input_tokens",
    "total_output_tokens", "total_cost_usd", "avg_ms", "p95_ms",
    "per_second", "failed_count",
)


def _row_to_run(r: sqlite3.Row) -> dict:
    return {k: r[k] for k in RUN_COLUMNS}


def get_email_state(email_id: str, path: Path = DB_PATH) -> dict | None:
    """The state object sent to Jev for one email (PRD section 4)."""
    with connect(path) as conn:
        r = conn.execute(
            "SELECT from_addr, subject, date, body FROM emails WHERE id = ?", (email_id,)
        ).fetchone()
    if r is None:
        return None
    return {"from": r["from_addr"], "subject": r["subject"], "date": r["date"], "body": r["body"]}


def insert_run(
    started_at: str,
    worker_count: int,
    email_count: int,
    question_set: dict,
    path: Path = DB_PATH,
) -> int:
    """Create the run row before the first Jev call, with question_set_json."""
    with connect(path) as conn:
        cur = conn.execute(
            "INSERT INTO runs (started_at, worker_count, email_count, question_set_json) "
            "VALUES (?, ?, ?, ?)",
            (started_at, worker_count, email_count,
             json.dumps(question_set, ensure_ascii=False, separators=(",", ":"))),
        )
        return int(cur.lastrowid)


def set_model_version(run_id: int, model_version: str, path: Path = DB_PATH) -> None:
    """Fill from the first response. Never overwrites a value already set."""
    with connect(path) as conn:
        conn.execute(
            "UPDATE runs SET model_version = ? WHERE id = ? AND model_version IS NULL",
            (model_version, run_id),
        )


def insert_answer(
    run_id: int,
    email_id: str,
    answers: dict | None,
    latency_ms: int | None,
    input_tokens: int | None,
    output_tokens: int | None,
    error: str | None,
    path: Path = DB_PATH,
) -> None:
    """One row per (run, email). `answers` is stored verbatim as JSON."""
    with connect(path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO answers "
            "(run_id, email_id, answers_json, latency_ms, input_tokens, output_tokens, error) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                run_id, email_id,
                None if answers is None else json.dumps(answers, ensure_ascii=False, separators=(",", ":")),
                latency_ms, input_tokens, output_tokens, error,
            ),
        )


def finish_run(run_id: int, finished_at: str, totals: dict, path: Path = DB_PATH) -> None:
    with connect(path) as conn:
        conn.execute(
            "UPDATE runs SET finished_at = ?, total_input_tokens = ?, total_output_tokens = ?, "
            "total_cost_usd = ?, avg_ms = ?, p95_ms = ?, per_second = ?, failed_count = ? "
            "WHERE id = ?",
            (
                finished_at,
                totals["total_input_tokens"], totals["total_output_tokens"],
                totals["total_cost_usd"], totals["avg_ms"], totals["p95_ms"],
                totals["per_second"], totals["failed_count"], run_id,
            ),
        )


def list_runs(path: Path = DB_PATH) -> list[dict]:
    with connect(path) as conn:
        cur = conn.execute("SELECT * FROM runs ORDER BY started_at DESC, id DESC")
        return [_row_to_run(r) for r in cur.fetchall()]


def get_run(run_id: int, path: Path = DB_PATH) -> dict | None:
    with connect(path) as conn:
        r = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    return None if r is None else _row_to_run(r)


def get_run_results(run_id: int, path: Path = DB_PATH) -> list[dict]:
    """One entry per email in the run, raw answers parsed back to an object."""
    with connect(path) as conn:
        cur = conn.execute(
            "SELECT email_id, answers_json, latency_ms, input_tokens, output_tokens, error "
            "FROM answers WHERE run_id = ? ORDER BY id",
            (run_id,),
        )
        return [
            {
                "email_id": r["email_id"],
                "answers": None if r["answers_json"] is None else json.loads(r["answers_json"]),
                "latency_ms": r["latency_ms"],
                "input_tokens": r["input_tokens"],
                "output_tokens": r["output_tokens"],
                "error": r["error"],
            }
            for r in cur.fetchall()
        ]


# ---------------------------------------------------------------------------
# Diff (PRD section 8). Same rules as tools/gen_fixture.py diff_runs.
# ---------------------------------------------------------------------------

DELTA_THRESHOLD = 0.10


def diff_runs(run_a: dict, rows_a: list[dict], run_b: dict, rows_b: list[dict]) -> dict:
    by_a = {r["email_id"]: r["answers"] for r in rows_a if r["answers"]}
    by_b = {r["email_id"]: r["answers"] for r in rows_b if r["answers"]}
    flips, conf_deltas, noul_deltas = [], [], []
    for eid in sorted(set(by_a) & set(by_b)):
        a, b = by_a[eid], by_b[eid]
        for qid in sorted(set(a) & set(b)):
            qa, qb = a[qid], b[qid]
            if qa.get("type") != qb.get("type"):
                continue
            if qa["type"] == "choice" and qa["choice"] != qb["choice"]:
                flips.append({"email_id": eid, "question_id": qid,
                              "a": qa["choice"], "b": qb["choice"]})
            if "confidence" in qa and "confidence" in qb:
                d = round(qb["confidence"] - qa["confidence"], 2)
                if abs(d) > DELTA_THRESHOLD:
                    conf_deltas.append({"email_id": eid, "question_id": qid,
                                        "a": qa["confidence"], "b": qb["confidence"], "delta": d})
            if qa["type"] == "noul":
                d = round(qb["noul"] - qa["noul"], 2)
                if abs(d) > DELTA_THRESHOLD:
                    noul_deltas.append({"email_id": eid, "question_id": qid,
                                        "a": qa["noul"], "b": qb["noul"], "delta": d})
    qs_a = json.loads(run_a["question_set_json"])
    qs_b = json.loads(run_b["question_set_json"])
    question_changes = []
    for qid in sorted(set(qs_a) | set(qs_b)):
        for field in ("type", "instructions", "criteria"):
            va, vb = qs_a.get(qid, {}).get(field), qs_b.get(qid, {}).get(field)
            if va != vb:
                question_changes.append({"question_id": qid, "field": field, "a": va, "b": vb})
    keys = ("id", "started_at", "model_version", "worker_count", "email_count")
    return {
        "a": {k: run_a[k] for k in keys},
        "b": {k: run_b[k] for k in keys},
        "delta_threshold": DELTA_THRESHOLD,
        "common_email_count": len(set(by_a) & set(by_b)),
        "category_flips": flips,
        "confidence_deltas": conf_deltas,
        "noul_deltas": noul_deltas,
        "question_changes": question_changes,
    }


# ---------------------------------------------------------------------------
# Settings (phase 2: the editable current question set)
# ---------------------------------------------------------------------------

def get_setting(key: str, path: Path = DB_PATH) -> str | None:
    with connect(path) as conn:
        r = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return None if r is None else r["value"]


def set_setting(key: str, value: str | None, path: Path = DB_PATH) -> None:
    with connect(path) as conn:
        if value is None:
            conn.execute("DELETE FROM settings WHERE key = ?", (key,))
        else:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
