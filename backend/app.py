"""FastAPI app — PRD section 9 endpoints.

Run:
    uvicorn backend.app:app --reload --port 8000

Every endpoint is real. Runs are executed by backend/engine.py, which calls
Jev directly over HTTP (backend/jev.py) and writes SQLite (backend/db.py).
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend import config, db
from backend.engine import manager
from backend.questions import QUESTION_SET_VERSION, get_question_set

log = logging.getLogger("jev_inbox_lab")

WORKER_OPTIONS = (8, 16, 32, 64)
QUESTION_TYPES = ("choice", "noul", "score")
CURRENT_QUESTIONS_KEY = "current_questions"


# ---------------------------------------------------------------------------
# Current question set (phase 2). v1 from questions.py unless edited.
# ---------------------------------------------------------------------------

def current_questions() -> tuple[str, dict[str, dict[str, Any]]]:
    """(version label, questions). Edited sets are labelled "custom"."""
    raw = db.get_setting(CURRENT_QUESTIONS_KEY)
    if raw is None:
        return QUESTION_SET_VERSION, get_question_set()
    return "custom", json.loads(raw)


def validate_questions(questions: Any) -> dict[str, dict[str, Any]]:
    """Shape check against the verified wire contract (backend/questions.py)."""
    if not isinstance(questions, dict) or not questions:
        raise HTTPException(422, "questions must be a non-empty object keyed by question id")
    for qid, q in questions.items():
        if not isinstance(qid, str) or not qid.strip():
            raise HTTPException(422, "question ids must be non-empty strings")
        if not isinstance(q, dict):
            raise HTTPException(422, f"{qid}: question must be an object")
        qtype = q.get("type")
        if qtype not in QUESTION_TYPES:
            raise HTTPException(422, f"{qid}: type must be one of {QUESTION_TYPES}")
        if not isinstance(q.get("instructions"), str) or not q["instructions"].strip():
            raise HTTPException(422, f"{qid}: instructions must be a non-empty string")
        crit = q.get("criteria")
        if qtype == "choice":
            if not isinstance(crit, dict) or len(crit) < 2 or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in crit.items()
            ):
                raise HTTPException(422, f"{qid}: choice criteria must map >= 2 option labels to descriptions")
        elif qtype == "noul":
            if not isinstance(crit, dict) or set(crit) != {"true", "false"} or not all(
                isinstance(v, str) for v in crit.values()
            ):
                raise HTTPException(422, f'{qid}: noul criteria must be {{"true": "...", "false": "..."}}')
        else:
            if not isinstance(crit, list) or len(crit) < 2 or not all(isinstance(v, str) for v in crit):
                raise HTTPException(422, f"{qid}: score criteria must be an ordered list of >= 2 level descriptions")
        extra = set(q) - {"type", "instructions", "criteria"}
        if extra:
            raise HTTPException(422, f"{qid}: unexpected fields {sorted(extra)}")
    return {qid: {"type": q["type"], "instructions": q["instructions"], "criteria": q["criteria"]}
            for qid, q in questions.items()}


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    info = db.bootstrap()
    if info["is_fixture"]:
        log.warning("corpus.jsonl not found; loaded synthetic fixture %s", info["corpus_path"])
    log.info("db ready: %s", info)
    if config.api_key() is None:
        log.warning("TYPESAFE_API_KEY is not set; POST /api/runs will refuse until it is")
    yield


app = FastAPI(title="Jev Inbox Lab", version="0.2.0", lifespan=lifespan)


class StartRunRequest(BaseModel):
    worker_count: int = Field(default=16)
    email_limit: int | None = Field(default=None, description="None = all")
    sample: str = Field(default="first", description='"first" by date, or "random"')
    seed: int | None = Field(default=None, description="random sample seed; omit for fresh draw")


class StartRunResponse(BaseModel):
    run_id: int
    email_ids: list[str]


class PutQuestionsRequest(BaseModel):
    questions: dict[str, Any] | None = Field(
        default=None, description="Full question set to use for future runs; null resets to v1"
    )


@app.get("/api/health")
async def health() -> dict:
    version, questions = current_questions()
    return {
        "ok": True,
        "question_set_version": version,
        "question_count": len(questions),
        "api_key_present": config.api_key() is not None,
        "email_count": len(db.list_emails()),
    }


@app.get("/api/emails")
async def get_emails() -> list[dict]:
    return db.list_emails()


@app.get("/api/questions")
async def get_questions() -> dict:
    version, questions = current_questions()
    return {"version": version, "questions": questions, "default_version": QUESTION_SET_VERSION}


@app.put("/api/questions")
async def put_questions(req: PutQuestionsRequest) -> dict:
    """Phase 2. Replace the current question set, or reset to v1 with null.

    Only future runs are affected; every past run keeps the exact set it
    sent in runs.question_set_json.
    """
    if req.questions is None:
        db.set_setting(CURRENT_QUESTIONS_KEY, None)
    else:
        cleaned = validate_questions(req.questions)
        if cleaned == get_question_set():
            db.set_setting(CURRENT_QUESTIONS_KEY, None)
        else:
            db.set_setting(CURRENT_QUESTIONS_KEY, json.dumps(cleaned, ensure_ascii=False))
    version, questions = current_questions()
    return {"version": version, "questions": questions, "default_version": QUESTION_SET_VERSION}


@app.post("/api/runs", response_model=StartRunResponse, status_code=202)
async def start_run(req: StartRunRequest) -> StartRunResponse:
    if req.worker_count not in WORKER_OPTIONS:
        raise HTTPException(status_code=422, detail=f"worker_count must be one of {WORKER_OPTIONS}")
    if req.email_limit is not None and req.email_limit < 1:
        raise HTTPException(status_code=422, detail="email_limit must be >= 1 or null")
    if req.sample not in db.SAMPLE_MODES:
        raise HTTPException(status_code=422, detail=f"sample must be one of {db.SAMPLE_MODES}")
    key = config.api_key()
    if key is None:
        raise HTTPException(status_code=503, detail="TYPESAFE_API_KEY is not set in .env")
    email_ids = db.select_email_ids(req.email_limit, req.sample, req.seed)
    if not email_ids:
        raise HTTPException(status_code=409, detail="corpus is empty")
    _, questions = current_questions()
    run_id = manager.start_run(
        api_key=key, email_ids=email_ids, worker_count=req.worker_count, questions=questions,
    )
    return StartRunResponse(run_id=run_id, email_ids=email_ids)


@app.get("/api/runs")
async def list_runs() -> list[dict]:
    """Run history, newest first."""
    return db.list_runs()


@app.get("/api/runs/diff")
async def diff_runs(a: int = Query(...), b: int = Query(...)) -> dict:
    """Diff payload for runs a and b (PRD section 8).

    Declared before /api/runs/{run_id} so "diff" is never parsed as an id.
    """
    run_a, run_b = db.get_run(a), db.get_run(b)
    if run_a is None or run_b is None:
        raise HTTPException(status_code=404, detail="run not found")
    return db.diff_runs(run_a, db.get_run_results(a), run_b, db.get_run_results(b))


@app.get("/api/runs/{run_id}")
async def get_run(run_id: int) -> dict:
    """Full results for one run. `answers` is the raw Jev object, unmodified."""
    run = db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    return {"run": run, "results": db.get_run_results(run_id)}


@app.get("/api/runs/{run_id}/stream")
async def stream_run(run_id: int) -> StreamingResponse:
    """SSE channel for a run: email_done / error / progress / run_done.

    Connecting late replays what was already emitted, then continues live.
    """
    if db.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    return StreamingResponse(
        manager.stream(run_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
