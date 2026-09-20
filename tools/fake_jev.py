"""A stand-in for api.typesafe.ai for UI development. NOT the model.

Answers are random but in the verified wire shape (CLAUDE.md), with a
plausible latency and the occasional 429 so the retry path gets exercised.

Usage:
    uvicorn tools.fake_jev:app --port 8099
    JEV_URL=http://localhost:8099/v1/systemone uvicorn backend.app:app --reload --port 8000

Never point this at anything that matters. It exists so the table, panel,
diff and editor can be built without spending real calls.
"""

from __future__ import annotations

import asyncio
import random

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="fake jev")

MODEL = "jev-0.0.0-fake"
RATE_LIMIT_PROBABILITY = 0.05


def _dist(keys: list[str], rng: random.Random) -> tuple[str, float, dict[str, float]]:
    weights = [rng.random() ** 3 for _ in keys]
    top = rng.randrange(len(keys))
    weights[top] += rng.uniform(0.5, 4.0)
    total = sum(weights)
    probs = {k: round(w / total, 4) for k, w in zip(keys, weights)}
    pick = max(probs, key=probs.get)
    return pick, probs[pick], probs


@app.post("/v1/systemone")
async def systemone(req: Request) -> JSONResponse:
    body = await req.json()
    rng = random.Random()  # fresh per call: two runs differ, which is what the diff view is for
    if rng.random() < RATE_LIMIT_PROBABILITY:
        await asyncio.sleep(0.05)
        return JSONResponse({"detail": "rate limited (fake)"}, status_code=429)
    await asyncio.sleep(rng.uniform(0.15, 1.2))
    answers: dict = {}
    for qid, q in body["questions"].items():
        if q["type"] == "choice":
            pick, conf, probs = _dist(list(q["criteria"]), rng)
            answers[qid] = {"type": "choice", "choice": pick, "confidence": conf, "probabilities": probs}
        elif q["type"] == "noul":
            answers[qid] = {"type": "noul", "noul": round(rng.random(), 4)}
        else:
            levels = list(q["criteria"])
            keys = [str(i) for i in range(len(levels))]
            _, conf, probs = _dist(keys, rng)
            score = sum(i * p for i, p in enumerate(probs.values()))
            answers[qid] = {
                "type": "score", "score": round(score, 2), "confidence": conf,
                "legend": dict(zip(keys, levels)), "probabilities": probs,
            }
    body_chars = len(body["state"].get("body", ""))
    return JSONResponse({
        "model": MODEL,
        "answers": answers,
        "usage": {"input_tokens": 300 + body_chars // 4, "output_tokens": 8 * len(answers)},
    })

