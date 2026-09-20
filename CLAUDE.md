# CLAUDE.md — Jev Inbox Lab

Read `PRD.md` in this directory before making changes. It is the spec.

## What this is

A local web app for exploring TypeSafe's Jev model on a frozen corpus of 50
personal Gmail messages. It classifies and scores emails and exposes the run's
latency, token and cost behaviour in real time.

This is a **learning instrument**, not an inbox tool. It classifies. It never
acts on mail — no archive, no label, no send, no reply.

## Hard rules

1. **Never commit real email.** `corpus.jsonl`, `*.db`, `*.sqlite` and `.env`
   are gitignored. Do not add them, do not `git add -f` them, do not paste
   their contents into a commit message, a comment or a test fixture. If you
   need sample data, use `fixtures/corpus.sample.jsonl` (synthetic).
2. **The API key stays server-side.** `TYPESAFE_API_KEY` is read from `.env` by
   the backend only. It is never sent to the browser, never embedded in a
   frontend build, never logged.
3. **No caching of Jev responses.** Every run calls the API fresh. Caching would
   hide the thing this app exists to study. Cost is about a tenth of a cent per
   run over 50 emails — it does not need optimising.
4. **Store raw answers unmodified.** Persist the full `answers` object as JSON.
   Derive display values at read time. Never store only the derived value.
5. **Record `question_set_json` and `model_version` on every run row.** Without
   these, a diff between two runs cannot be interpreted. `jev-latest` moves.

## Stack

- Backend: Python 3.11+, FastAPI, `httpx.AsyncClient`, SQLite (stdlib `sqlite3`)
- Frontend: React + Vite + Tailwind
- No ORM. No Redis. No Docker. No auth. Keep the dependency list short.

Do **not** use the `typesafe-sdk` package. Call the HTTP endpoint directly —
the SDK's own docs disagree on the response accessor (`response.answers[...]`
vs `response.choices[...]`), and the wire shape below is verified.

## The Jev contract (verified against a live call)

```
POST https://api.typesafe.ai/v1/systemone
Authorization: Bearer $TYPESAFE_API_KEY
Content-Type: application/json
```

Request body:

```json
{
  "model": "jev-latest",
  "state": { "from": "...", "subject": "...", "date": "...", "body": "..." },
  "questions": { "<question_id>": { "type": "...", "instructions": "...", "criteria": ... } }
}
```

Response body:

```json
{
  "model": "jev-1.13.0",
  "answers": {
    "category":    { "type": "choice", "choice": "admin", "confidence": 1.0,
                     "probabilities": { "admin": 1.0, "marketing": 0.0 } },
    "needs_reply": { "type": "noul", "noul": 0.06 },
    "importance":  { "type": "score", "score": 1.97, "confidence": 0.96,
                     "legend": { "0": "...", "1": "...", "2": "..." },
                     "probabilities": { "0": 0.0, "1": 0.02, "2": 0.98 } }
  },
  "usage": { "input_tokens": 453, "output_tokens": 76 }
}
```

Notes that follow from the shape:

- `answers` is keyed by **your** question id. Question ids are not sent to the
  model — the full question goes in `instructions`.
- Noul returns only `noul`. There is no `confidence` field on a Noul.
- Score returns a **fractional** `score` (1.97, not 2). Map to the nearest
  legend entry for display; keep the float for sorting and diffing.
- Choice `probabilities` are keyed by option label; Score `probabilities` are
  keyed by level index as a string.

## Cost

`input_tokens * 0.042 / 1_000_000`. Output tokens are billed at zero. Show the
output token count anyway, with its cost rendered as `$0.00` — that is the
point of the demo.

## Directory ownership

```
backend/    run engine, Jev client, SSE, SQLite
frontend/   React app
tools/      corpus pull, loader, fixture generator
fixtures/   synthetic sample data (committed)
```

Keep changes inside one directory per task where possible.

## Commands

```
backend:   uvicorn backend.app:app --reload --port 8000
frontend:  cd frontend && npm run dev
```

## How I want you to work in this repo

- **Give me actual files** to download and `mv` into place. Do not hand me
  heredocs or `cat > file << EOF` commands that generate files.
- **Label every command block outside the code fence** as `-- on MAC --`.
  ASCII-clean: no apostrophes or parentheses inside command blocks. A label
  inside the fence errors as `zsh: command not found: --`.
- **Put a language tag on every fence** (bash, python, json) so it highlights.
- **One command block at a time when debugging.**
- **Never use silent git commands.** No `git push -q`, no `git commit -q`. I
  need to see what was committed and what was missed.
- **Say when you are inferring rather than knowing.** This applies to asides and
  summaries, not just headline claims. If you assert something about this repo
  and you have not read that file in this session, mark it as inference.
- **Never claim something is verified without naming the artifact** that proves
  it. I will hold you to "name the artifact" on any sentence.
- **Use `mv`, not `cp`**, unless the file genuinely needs to persist in the
  source folder.
- **Lead with the answer.** Short and plain. When I ask what a command does,
  explain it literally, part by part, with no framing before the explanation.

## Out of scope

Live Gmail sync. Acting on mail. Thresholds and automation rules. Auth.
Deployment. Multi-user. Hand-labelling and agreement scoring.
