// Typed client for the PRD section 9 endpoints, plus the Jev answer shapes
// from CLAUDE.md. Display values (importance label, min confidence) are
// derived here at read time — never stored.

export interface Email {
  id: string;
  from: string;
  subject: string;
  date: string;
  body: string;
}

export interface ChoiceAnswer {
  type: "choice";
  choice: string;
  confidence: number;
  probabilities: Record<string, number>;
}

export interface NoulAnswer {
  type: "noul";
  noul: number; // no confidence field on a Noul
}

export interface ScoreAnswer {
  type: "score";
  score: number; // fractional, e.g. 1.97
  confidence: number;
  legend: Record<string, string>; // keyed by level index as a string
  probabilities: Record<string, number>;
}

export type Answer = ChoiceAnswer | NoulAnswer | ScoreAnswer;
export type Answers = Record<string, Answer>;

export interface Question {
  type: "choice" | "noul" | "score";
  instructions: string;
  criteria: Record<string, string> | string[];
}

export interface QuestionSet {
  version: string; // "v1" or "custom"
  default_version: string;
  questions: Record<string, Question>;
}

export interface Health {
  ok: boolean;
  question_set_version: string;
  question_count: number;
  api_key_present: boolean;
  email_count: number;
}

export interface Run {
  id: number;
  started_at: string;
  finished_at: string | null;
  worker_count: number;
  email_count: number;
  model_version: string | null;
  question_set_json: string;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_usd: number;
  avg_ms: number | null;
  p95_ms: number | null;
  per_second: number | null;
  failed_count: number;
}

export interface RunResult {
  email_id: string;
  answers: Answers | null;
  latency_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  error: string | null;
}

export interface RunDetail {
  run: Run;
  results: RunResult[];
}

// SSE payloads
export interface EmailDoneEvent {
  email_id: string;
  answers: Answers;
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
}
export interface ProgressEvent {
  done: number;
  total: number;
  in_flight: number;
  failed: number;
  retries: number;
}
export interface RunDoneEvent {
  run_id: number;
  totals: Pick<
    Run,
    | "model_version"
    | "total_input_tokens"
    | "total_output_tokens"
    | "total_cost_usd"
    | "avg_ms"
    | "p95_ms"
    | "per_second"
    | "failed_count"
  >;
}
export interface ErrorEvent {
  email_id: string;
  message: string;
}

export interface DiffPayload {
  a: Pick<Run, "id" | "started_at" | "model_version" | "worker_count" | "email_count">;
  b: Pick<Run, "id" | "started_at" | "model_version" | "worker_count" | "email_count">;
  delta_threshold: number;
  common_email_count: number;
  category_flips: { email_id: string; question_id: string; a: string; b: string }[];
  confidence_deltas: { email_id: string; question_id: string; a: number; b: number; delta: number }[];
  noul_deltas: { email_id: string; question_id: string; a: number; b: number; delta: number }[];
  question_changes: { question_id: string; field: string; a: unknown; b: unknown }[];
}

export type SampleMode = "first" | "random";

export const COST_PER_INPUT_TOKEN = 0.042 / 1_000_000;

async function get<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${url}`);
  return res.json() as Promise<T>;
}

export const api = {
  health: () => get<Health>("/api/health"),
  emails: () => get<Email[]>("/api/emails"),
  questions: () => get<QuestionSet>("/api/questions"),
  /** Replace the current question set for future runs; null resets to v1. */
  putQuestions: async (questions: Record<string, Question> | null) => {
    const res = await fetch("/api/questions", {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ questions }),
    });
    if (!res.ok) {
      let detail = `${res.status} PUT /api/questions`;
      try {
        const body = (await res.json()) as { detail?: string };
        if (body.detail) detail = body.detail;
      } catch {
        /* keep status text */
      }
      throw new Error(detail);
    }
    return res.json() as Promise<QuestionSet>;
  },
  runs: () => get<Run[]>("/api/runs"),
  run: (id: number) => get<RunDetail>(`/api/runs/${id}`),
  diff: (a: number, b: number) => get<DiffPayload>(`/api/runs/diff?a=${a}&b=${b}`),
  startRun: async (
    worker_count: number,
    email_limit: number | null,
    sample: SampleMode = "first",
    seed: number | null = null,
  ) => {
    const res = await fetch("/api/runs", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ worker_count, email_limit, sample, seed }),
    });
    if (!res.ok) {
      let detail = `${res.status} POST /api/runs`;
      try {
        const body = (await res.json()) as { detail?: string };
        if (body.detail) detail = body.detail;
      } catch {
        /* keep status text */
      }
      throw new Error(detail);
    }
    return res.json() as Promise<{ run_id: number; email_ids: string[] }>;
  },
  streamUrl: (id: number) => `/api/runs/${id}/stream`,
};

// ---- derived display values ------------------------------------------------

/** Nearest legend entry for a fractional score. Keeps the float elsewhere. */
export function scoreLabel(a: ScoreAnswer): string {
  const idx = Math.round(a.score);
  return a.legend[String(idx)] ?? String(a.score);
}

/** Minimum of the Choice and Score confidences. Nouls have none. */
export function minConfidence(answers: Answers): number | null {
  let min: number | null = null;
  for (const a of Object.values(answers)) {
    if (a.type === "noul") continue;
    if (min === null || a.confidence < min) min = a.confidence;
  }
  return min;
}

export function costUsd(inputTokens: number): number {
  return inputTokens * COST_PER_INPUT_TOKEN;
}

/** Speculative answers are only meaningful when their gate is on (PRD 6). */
export const SPECULATIVE: Record<string, { gated_by: string; threshold: number }> = {
  deadline_pressure: { gated_by: "has_deadline", threshold: 0.5 },
};

export function isGateOpen(answers: Answers, qid: string): boolean {
  const gate = SPECULATIVE[qid];
  if (!gate) return true;
  const g = answers[gate.gated_by];
  return g?.type === "noul" && g.noul > gate.threshold;
}

export function displayName(from: string): string {
  return from.replace(/\s*<.*>$/, "").replace(/^"|"$/g, "");
}
