"""Jev HTTP client. Direct call to api.typesafe.ai — no SDK (CLAUDE.md).

One call per email, every question batched into it. Retries 429 and 529
with exponential backoff (docs.typesafe.ai/api.md, "Handling rate limits").
Everything else fails fast so a bad key or a malformed question shows up
on the first email, not after a retry storm.

No caching anywhere in this module, by design (CLAUDE.md rule 3).
"""

from __future__ import annotations

import asyncio
import json
import random
import time
from dataclasses import dataclass
from typing import Any

import httpx

from backend.config import JEV_MODEL, JEV_URL

RETRY_STATUSES = (429, 529)
MAX_ATTEMPTS = 6
BASE_DELAY_S = 0.5
MAX_DELAY_S = 8.0
REQUEST_TIMEOUT_S = 60.0


class JevError(Exception):
    """A call that will not succeed by retrying."""

    def __init__(self, status: int | None, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass
class JevResult:
    answers: dict[str, Any]   # raw `answers` object, stored unmodified
    model: str                # e.g. "jev-1.13.0"
    input_tokens: int
    output_tokens: int
    latency_ms: int           # wall clock for this email, including retries
    retries: int              # how many 429/529 backoffs it took


def make_client(api_key: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=httpx.Timeout(REQUEST_TIMEOUT_S, connect=10.0),
    )


def _error_message(resp: httpx.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:300]
    if isinstance(body, dict):
        for key in ("detail", "error", "message"):
            if key in body:
                val = body[key]
                return val if isinstance(val, str) else json.dumps(val)[:300]
    return json.dumps(body)[:300]


async def classify(
    client: httpx.AsyncClient,
    state: dict[str, Any],
    questions: dict[str, dict[str, Any]],
    *,
    model: str = JEV_MODEL,
) -> JevResult:
    """POST one state + all questions. Raises JevError when it gives up."""
    payload = {"model": model, "state": state, "questions": questions}
    started = time.perf_counter()
    retries = 0
    last_status: int | None = None
    last_message = "unknown error"

    for attempt in range(MAX_ATTEMPTS):
        try:
            resp = await client.post(JEV_URL, json=payload)
        except httpx.HTTPError as exc:
            # Network-level failure: treat like an overload and back off.
            last_status, last_message = None, f"{type(exc).__name__}: {exc}"
        else:
            last_status = resp.status_code
            if resp.status_code == 200:
                body = resp.json()
                usage = body.get("usage") or {}
                return JevResult(
                    answers=body["answers"],
                    model=str(body.get("model", model)),
                    input_tokens=int(usage.get("input_tokens", 0)),
                    output_tokens=int(usage.get("output_tokens", 0)),
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    retries=retries,
                )
            last_message = _error_message(resp)
            if resp.status_code not in RETRY_STATUSES:
                raise JevError(resp.status_code, f"HTTP {resp.status_code}: {last_message}")

        if attempt == MAX_ATTEMPTS - 1:
            break
        retries += 1
        delay = min(MAX_DELAY_S, BASE_DELAY_S * (2 ** attempt)) * (0.5 + random.random())
        await asyncio.sleep(delay)

    raise JevError(last_status, f"gave up after {MAX_ATTEMPTS} attempts: HTTP {last_status}: {last_message}")
