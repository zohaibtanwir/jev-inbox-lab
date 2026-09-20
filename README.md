# Jev Inbox Lab

A local web app for exploring [TypeSafe's Jev model](https://docs.typesafe.ai)
on a frozen corpus of personal Gmail messages. It classifies and scores each
email with one Jev call and shows the run's latency, token and cost behaviour
as it happens.

It is a learning instrument, not an inbox tool. It classifies. It never acts
on mail.

## What it does

- **Run**: pick All / First 25 / Random 50 emails and 8–64 workers, hit Start.
  Rows fill in live over SSE; the panel tracks progress, average, p95,
  throughput, retries, tokens and cost.
- **Inspect**: every column sorts. Ascending by Confidence surfaces the emails
  where category definitions overlap. Rows expand to the full probability
  distribution for each question and the raw Jev answer.
- **Edit questions**: change instructions and criteria in the UI. Every run
  stores the exact question set it sent, so runs stay comparable.
- **Diff**: pick two runs. See category flips, confidence and Noul deltas
  beyond ±0.10, and the two question sets side by side with changed criteria
  highlighted. This view is the point of the app.

Eight questions go in each call: one Choice (11 categories), two Scores
(importance, deadline pressure) and five Nouls (needs reply, spam, automated,
money involved, has deadline). See [`backend/questions.py`](backend/questions.py).

## Stack

- Backend: Python 3.11+, FastAPI, `httpx`, stdlib `sqlite3`. Jev is called
  over plain HTTP — no SDK.
- Frontend: React 19, Vite, Tailwind 4.
- No ORM, no Redis, no Docker, no auth.

## Run it

```bash
pip install -r requirements.txt
cd frontend && npm install && cd ..
cp .env.example .env        # then put your key after TYPESAFE_API_KEY=
```

Two terminals:

```bash
uvicorn backend.app:app --reload --port 8000
```

```bash
cd frontend && npm run dev
```

Open http://localhost:5173.

Without a `corpus.jsonl` the app loads
[`fixtures/corpus.sample.jsonl`](fixtures/corpus.sample.jsonl), 50 synthetic
emails, so everything works out of the box. To use your own mail, produce a
`corpus.jsonl` with one `{id, from, subject, date, body}` object per line
(`tools/pull_corpus.py` normalises a raw dump). It is loaded into SQLite on
first boot.

To work on the UI without spending real calls, `tools/fake_jev.py` stands in
for the API:

```bash
uvicorn tools.fake_jev:app --port 8099
```

```bash
JEV_URL=http://localhost:8099/v1/systemone TYPESAFE_API_KEY=fake CORPUS_PATH=fixtures/corpus.sample.jsonl uvicorn backend.app:app --port 8000
```

## Cost

Input tokens cost $0.042 per million; output tokens are free. A run over 50
emails is roughly a tenth of a cent. Nothing is cached — every run is a fresh
set of calls, by design.

## Privacy

`corpus.jsonl`, `corpus.raw.json`, the SQLite database and `.env` are
gitignored. The API key is read by the backend only and never reaches the
browser. Only the synthetic fixture is committed.

## Layout

```
backend/    FastAPI app, Jev client, run engine, SQLite
frontend/   React app
tools/      corpus pull and normalise, fixture generator, fake Jev server
fixtures/   synthetic sample data
PRD.md      the spec
CLAUDE.md   working rules for the repo
```

## API

| Endpoint | Does |
|---|---|
| `GET /api/emails` | corpus list |
| `GET /api/questions` · `PUT /api/questions` | current question set; `null` resets to v1 |
| `POST /api/runs` | start a run: `{worker_count, email_limit, sample, seed}` |
| `GET /api/runs/{id}/stream` | SSE: `email_done`, `error`, `progress`, `run_done` |
| `GET /api/runs` · `GET /api/runs/{id}` | history, full results |
| `GET /api/runs/diff?a=&b=` | diff payload |
