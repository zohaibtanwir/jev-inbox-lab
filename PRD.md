# PRD — Jev Inbox Lab

**Owner:** Zohaib Tanwir
**Status:** ready to build
**Last updated:** 20 Sep 2026

---

## 1. Purpose

A local web app to explore TypeSafe's Jev model on a frozen corpus of 50
personal Gmail messages. The app classifies and scores each email and exposes
the run's latency, token and cost characteristics in real time.

This is a learning instrument. The goal is to understand how System One models
behave — how question wording changes answers, where confidence collapses, what
throughput looks like at different concurrency — not to manage an inbox.

**Non-goals:** live Gmail sync; acting on mail (archive, label, send, reply);
thresholds or automation rules; auth; deployment; multi-user; hand-labelling and
agreement scoring against ground truth.

## 2. Success criteria

- A run over 50 emails completes and streams results into the table live.
- Latency, token and cost figures are visible and believable.
- Changing a question's wording and re-running shows exactly which rows moved.
- After using it, the three primitives can be explained to a client from
  experience rather than from the docs.

## 3. Architecture

```
React + Vite + Tailwind  ──HTTP + SSE──▶  FastAPI  ──HTTPS──▶  api.typesafe.ai/v1/systemone
                                             │
                                          SQLite
```

- API key stays server-side. The browser never sees it.
- Jev called via direct HTTP (`httpx.AsyncClient`), not the SDK.
- Concurrency via `asyncio.Semaphore(worker_count)`.
- One Jev call per email, with all questions batched into that call.
- No caching. Every run is fresh.

**Cost per run:** 50 emails at roughly 600 input tokens each is about 30K
tokens, which at $0.042/MTok is approximately **$0.0013** — a tenth of a cent.
Re-run freely.

## 4. Corpus

`corpus.jsonl`, 50 messages, pulled once via Gmail MCP. Fields: `id`, `from`,
`subject`, `date`, `body` (plain text, quoted reply chains stripped, truncated
to 1500 characters).

The file is the source of truth. The app is read-only over it. It is loaded
into SQLite on first boot.

A synthetic `fixtures/corpus.sample.jsonl` with the same field shape is
committed for development and tests. The real corpus is never committed.

State sent to Jev is a JSON object, not a flat string:

```json
{ "from": "...", "subject": "...", "date": "...", "body": "..." }
```

This lets questions target parts of the state by path — for example
"Does `subject` name a deadline?" — which is the documented way to point a
judgment at one part of a structured state.

## 5. Data model (SQLite)

**runs**
`id`, `started_at`, `finished_at`, `worker_count`, `email_count`,
`model_version`, `question_set_json`, `total_input_tokens`,
`total_output_tokens`, `total_cost_usd`, `avg_ms`, `p95_ms`, `per_second`,
`failed_count`

**answers**
`id`, `run_id`, `email_id`, `answers_json` (raw, unmodified), `latency_ms`,
`input_tokens`, `output_tokens`, `error`

**emails**
`id`, `from_addr`, `subject`, `date`, `body`

Storing `question_set_json` and `model_version` on the run row is mandatory.
Without them a diff between two runs cannot be interpreted.

## 6. Question set v1

Eight questions, sent in a single call per email. Two are deliberately
speculative — they only matter for some emails — which exercises the
speculative fan-out pattern at near-zero marginal cost.

| id | type | asks |
|---|---|---|
| `category` | Choice | which of 11 buckets |
| `importance` | Score | 4 levels, ignorable to act today |
| `needs_reply` | Noul | does this need a written reply |
| `is_spam` | Noul | unsolicited or deceptive, not merely promotional |
| `is_automated` | Noul | sent by a system vs typed by a person |
| `money_involved` | Noul | concerns a payment, charge or amount |
| `has_deadline` | Noul | names a date by which the recipient must act |
| `deadline_pressure` | Score | speculative: only read when `has_deadline` > 0.5 |

**Category options (11):**
`personal`, `professional`, `finance`, `shopping_order`, `travel`, `marketing`,
`newsletter`, `account_admin`, `learning_cert`, `social_notification`, `other`

Two deliberate stress tests in this taxonomy:

- `newsletter` vs `marketing` turns on whether the recipient subscribed, which
  is often not present in the text. Expect low confidence here. That is the
  interesting part, not a defect.
- `learning_cert` is a personal bucket a general model has no prior for. Watch
  what a vague description does to it versus a specific one.

Questions live in `backend/questions.py` and are loaded at startup. Phase 2
makes them editable from the UI.

## 7. UI

Two-pane layout.

### Left — inbox table

| Column | Source |
|---|---|
| From | corpus |
| Subject | corpus |
| Category | `category.choice` |
| Importance | `importance.score` mapped to nearest legend label, as a pill |
| Spam | `is_spam.noul` as a percentage with an inline bar |
| Reply | `needs_reply.noul` as a percentage with an inline bar |
| Confidence | minimum of the Choice and Score confidences |
| Time | per-email latency in ms |

Every column is sortable. **Sorting ascending by Confidence is the primary
debugging view** — it surfaces exactly the emails where category definitions
overlap.

Rows expand to show the full probability distribution for every question, the
two speculative answers, and the raw JSON.

Rows stream in as answers arrive. Pending rows show a spinner in the answer
columns.

### Right — run panel

- **Controls:** Emails selector (All / First 25 / Random 50), Workers selector
  (8 / 16 / 32 / 64), Start, Reset results
- **Progress:** `n of 50`, percentage, remaining, failed
- **Stats:** Run (wall clock), Average, Per second, p95
- **Live:** in flight, API retries, failed
- **Tokens:** In, Out, Estimated cost. Out renders as its count with `$0.00`
  beside it.

### Run history

A strip of chips along the top, one per past run, showing timestamp and model
version. Selecting two opens the diff view.

## 8. Run diffing

Select run A and run B. Show only what changed:

- Category flips, rendered as `marketing -> newsletter`
- Confidence deltas beyond ±0.10
- Noul deltas beyond ±0.10
- A side-by-side of the two question sets with changed `criteria` text
  highlighted

This is where the learning happens. Everything else in the app is
instrumentation for this view.

## 9. API

| Endpoint | Does |
|---|---|
| `GET /api/emails` | corpus list |
| `GET /api/questions` | current question set |
| `POST /api/runs` | start a run, body `{worker_count, email_limit, sample, seed}` (`sample` = `first` or `random`; `seed` optional, makes a random pick reproducible), returns `{run_id, email_ids}` |
| `GET /api/runs/{id}/stream` | SSE channel for a run |
| `GET /api/runs` | run history |
| `GET /api/runs/{id}` | full results for one run |
| `GET /api/runs/diff?a=&b=` | diff payload |
| `PUT /api/questions` | phase 2 |

### SSE events

- `email_done` — `{ email_id, answers, latency_ms, input_tokens, output_tokens }`
- `progress` — `{ done, total, in_flight, failed, retries }`
- `run_done` — `{ run_id, totals }`
- `error` — `{ email_id, message }`

The frontend aggregates its own running statistics from `email_done` events so
the numbers tick smoothly rather than jumping on each `progress` frame.

## 10. Phases

1. **Core.** Corpus load, run engine, SSE, table, run panel, SQLite. This is
   the working app.
2. **Question editor.** Edit instructions and criteria in the UI, versioned per
   run. Turns a demo into a lab.
3. **Diffing.** Run A vs run B.

Phases 1 and 3 are the minimum that teaches anything. Phase 2 makes the loop
pleasant enough that the experiments actually happen.

## 11. Experiments to run once it works

These are the reason the app exists. Each is a pair of runs and a diff.

1. **Vague vs specific criteria.** Give `learning_cert` a one-word description,
   then a two-sentence one. Diff.
2. **Body truncation.** 500 vs 1500 vs 3000 characters, same questions. Where
   does accuracy stop improving, and where does it start degrading from
   irrelevant context?
3. **Concurrency curve.** 8 / 16 / 32 / 64 workers. Plot p95 against workers.
4. **Subject-only vs full state.** Does the body earn its tokens?
5. **Option count.** Collapse the 11 categories to 5. What happens to
   confidence?
6. **Splitting a judgment.** Replace `importance` with three separate Scores
   and weight them in code. Compare against the single question.

## 12. Risks

- **`jev-latest` moves.** Mitigated by recording `model_version` per run and
  surfacing it in the diff view.
- **Rate limits unknown.** Early access; limits are not publicly documented.
  Back off on 429, surface the retry count in the panel, and start at 16
  workers rather than 64.
- **32K token budget** is per request and shared between state and questions.
  Comfortable at 1500-character bodies, but the truncation is a real design
  choice — see experiment 2.
- **Personal email on disk.** `corpus.jsonl` and the SQLite file both hold real
  mail in plain text. Both gitignored from the first commit.
- **Confidence is not correctness.** A calibrated 0.9 means the model is right
  about 90% of the time across a group of such answers, not that this answer is
  right. With no ground-truth labels in scope, the app measures behaviour and
  consistency, not accuracy.
