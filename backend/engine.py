"""Run engine: semaphore-bounded worker pool over one Jev call per email.

Lifecycle of a run:

  1. `start_run` inserts the `runs` row (with question_set_json) and returns
     the id immediately. The pool runs as a background asyncio task.
  2. Each worker takes the semaphore, POSTs to Jev, writes one `answers` row,
     and publishes `email_done` or `error` followed by `progress`.
  3. When every email has been tried, totals are computed, the run row is
     finished, and `run_done` is published.

SSE clients may connect at any point, including after the run finished or
after a backend restart. `stream` therefore replays: the in-memory event
buffer for a live run, or the `answers` rows from SQLite for a finished one.

Nothing here caches Jev responses. Every run is a fresh set of calls.
"""

from __future__ import annotations

import asyncio
import json
import logging
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from backend import db
from backend.config import COST_PER_INPUT_TOKEN
from backend.jev import JevError, classify, make_client

log = logging.getLogger("jev_inbox_lab.engine")

TOTAL_KEYS = (
    "model_version", "total_input_tokens", "total_output_tokens",
    "total_cost_usd", "avg_ms", "p95_ms", "per_second", "failed_count",
)


def sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def compute_totals(
    results: list[dict],
    model_version: str | None,
    wall_seconds: float,
) -> dict[str, Any]:
    """Aggregate a run's per-email results into the run row's totals."""
    ok = [r for r in results if r.get("error") is None and r.get("answers") is not None]
    latencies = sorted(int(r["latency_ms"]) for r in ok if r.get("latency_ms") is not None)
    in_tok = sum(int(r.get("input_tokens") or 0) for r in ok)
    out_tok = sum(int(r.get("output_tokens") or 0) for r in ok)
    p95 = None
    if latencies:
        # nearest-rank p95: small n, no interpolation needed
        idx = max(0, min(len(latencies) - 1, round(0.95 * len(latencies)) - 1))
        p95 = float(latencies[idx])
    return {
        "model_version": model_version,
        "total_input_tokens": in_tok,
        "total_output_tokens": out_tok,
        "total_cost_usd": round(in_tok * COST_PER_INPUT_TOKEN, 8),
        "avg_ms": round(statistics.fmean(latencies), 1) if latencies else None,
        "p95_ms": p95,
        "per_second": round(len(ok) / wall_seconds, 2) if wall_seconds > 0 else None,
        "failed_count": len(results) - len(ok),
    }


@dataclass
class LiveRun:
    run_id: int
    email_ids: list[str]
    worker_count: int
    questions: dict[str, dict[str, Any]]
    events: list[str] = field(default_factory=list)
    subscribers: set[asyncio.Queue[str | None]] = field(default_factory=set)
    done: int = 0
    failed: int = 0
    retries: int = 0
    in_flight: int = 0
    model_version: str | None = None
    results: list[dict] = field(default_factory=list)
    finished: bool = False
    task: asyncio.Task | None = None

    def publish(self, frame: str) -> None:
        self.events.append(frame)
        for q in list(self.subscribers):
            q.put_nowait(frame)

    def progress_frame(self) -> str:
        return sse("progress", {
            "done": self.done,
            "total": len(self.email_ids),
            "in_flight": self.in_flight,
            "failed": self.failed,
            "retries": self.retries,
        })


class RunManager:
    def __init__(self) -> None:
        self.live: dict[int, LiveRun] = {}

    # -- starting ---------------------------------------------------------

    def start_run(
        self,
        *,
        api_key: str,
        email_ids: list[str],
        worker_count: int,
        questions: dict[str, dict[str, Any]],
    ) -> int:
        run_id = db.insert_run(_now(), worker_count, len(email_ids), questions)
        live = LiveRun(run_id=run_id, email_ids=email_ids, worker_count=worker_count, questions=questions)
        self.live[run_id] = live
        live.task = asyncio.create_task(self._run(live, api_key), name=f"run-{run_id}")
        return run_id

    async def _run(self, live: LiveRun, api_key: str) -> None:
        sem = asyncio.Semaphore(live.worker_count)
        started = time.perf_counter()
        try:
            async with make_client(api_key) as client:
                await asyncio.gather(*(self._one(live, client, sem, eid) for eid in live.email_ids))
        except Exception:  # pragma: no cover - defensive; per-email errors are caught below
            log.exception("run %s crashed", live.run_id)
        wall = time.perf_counter() - started
        totals = compute_totals(live.results, live.model_version, wall)
        db.finish_run(live.run_id, _now(), totals)
        live.finished = True
        live.publish(sse("run_done", {"run_id": live.run_id, "totals": totals}))
        for q in list(live.subscribers):
            q.put_nowait(None)
        log.info("run %s done: %s", live.run_id, totals)

    async def _one(self, live: LiveRun, client, sem: asyncio.Semaphore, email_id: str) -> None:
        state = db.get_email_state(email_id)
        async with sem:
            live.in_flight += 1
            try:
                if state is None:
                    raise JevError(None, f"email {email_id} not in corpus")
                result = await classify(client, state, live.questions)
            except Exception as exc:
                # Per-email failure: recorded as a row with `error`, run continues.
                msg = exc.message if isinstance(exc, JevError) else f"{type(exc).__name__}: {exc}"
                live.in_flight -= 1
                live.done += 1
                live.failed += 1
                db.insert_answer(live.run_id, email_id, None, None, None, None, msg)
                live.results.append({"email_id": email_id, "answers": None, "error": msg})
                live.publish(sse("error", {"email_id": email_id, "message": msg}))
                live.publish(live.progress_frame())
                return
            live.in_flight -= 1

        live.done += 1
        live.retries += result.retries
        if live.model_version is None:
            live.model_version = result.model
            db.set_model_version(live.run_id, result.model)
        db.insert_answer(
            live.run_id, email_id, result.answers, result.latency_ms,
            result.input_tokens, result.output_tokens, None,
        )
        row = {
            "email_id": email_id,
            "answers": result.answers,
            "latency_ms": result.latency_ms,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "error": None,
        }
        live.results.append(row)
        live.publish(sse("email_done", {k: row[k] for k in (
            "email_id", "answers", "latency_ms", "input_tokens", "output_tokens",
        )}))
        live.publish(live.progress_frame())

    # -- streaming --------------------------------------------------------

    async def stream(self, run_id: int) -> AsyncIterator[str]:
        live = self.live.get(run_id)
        if live is not None:
            queue: asyncio.Queue[str | None] = asyncio.Queue()
            # Subscribe and snapshot in one synchronous step: everything up to
            # `snapshot` is replayed from the buffer, everything after arrives
            # on the queue, so no frame is lost or duplicated.
            live.subscribers.add(queue)
            snapshot = len(live.events)
            already_finished = live.finished
            try:
                for frame in live.events[:snapshot]:
                    yield frame
                if already_finished:
                    return
                while True:
                    frame = await queue.get()
                    if frame is None:
                        return
                    yield frame
            finally:
                live.subscribers.discard(queue)
            return

        # Not in memory: finished before this process started. Replay from SQLite.
        run = db.get_run(run_id)
        if run is None:
            raise KeyError(run_id)
        rows = db.get_run_results(run_id)
        total = run["email_count"]
        done = failed = 0
        for row in rows:
            done += 1
            if row["error"] is not None:
                failed += 1
                yield sse("error", {"email_id": row["email_id"], "message": row["error"]})
            else:
                yield sse("email_done", {k: row[k] for k in (
                    "email_id", "answers", "latency_ms", "input_tokens", "output_tokens",
                )})
            yield sse("progress", {"done": done, "total": total, "in_flight": 0,
                                   "failed": failed, "retries": 0})
        yield sse("run_done", {"run_id": run_id, "totals": {k: run[k] for k in TOTAL_KEYS}})


manager = RunManager()
