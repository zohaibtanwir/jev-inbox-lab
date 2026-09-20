// Owns one run's live state: which emails are in it, per-email results as
// they stream in over SSE, and the running statistics aggregated client-side
// from `email_done` events (PRD section 9) so the panel ticks smoothly.

import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  costUsd,
  type EmailDoneEvent,
  type ErrorEvent,
  type ProgressEvent,
  type RunDoneEvent,
  type RunResult,
  type SampleMode,
} from "./api";

export type RunPhase = "idle" | "starting" | "running" | "done" | "viewing";

export interface RunStats {
  done: number;
  total: number;
  failed: number;
  inFlight: number;
  retries: number;
  avgMs: number | null;
  p95Ms: number | null;
  perSecond: number | null;
  inputTokens: number;
  outputTokens: number;
  costUsd: number;
}

export interface RunState {
  phase: RunPhase;
  runId: number | null;
  emailIds: string[]; // the run's selection, in the order the engine iterates
  results: Record<string, RunResult>;
  stats: RunStats;
  wallMs: number;
  modelVersion: string | null;
  error: string | null;
}

const EMPTY_STATS: RunStats = {
  done: 0, total: 0, failed: 0, inFlight: 0, retries: 0,
  avgMs: null, p95Ms: null, perSecond: null,
  inputTokens: 0, outputTokens: 0, costUsd: 0,
};

const IDLE: RunState = {
  phase: "idle", runId: null, emailIds: [], results: {},
  stats: EMPTY_STATS, wallMs: 0, modelVersion: null, error: null,
};

function p95(sorted: number[]): number | null {
  if (!sorted.length) return null;
  const idx = Math.max(0, Math.min(sorted.length - 1, Math.round(0.95 * sorted.length) - 1));
  return sorted[idx];
}

function aggregate(results: Record<string, RunResult>, total: number, wallMs: number): Omit<RunStats, "inFlight" | "retries"> {
  const rows = Object.values(results);
  const ok = rows.filter((r) => r.error === null && r.answers);
  const lat = ok.map((r) => r.latency_ms ?? 0).sort((a, b) => a - b);
  const inTok = ok.reduce((s, r) => s + (r.input_tokens ?? 0), 0);
  const outTok = ok.reduce((s, r) => s + (r.output_tokens ?? 0), 0);
  return {
    done: rows.length,
    total,
    failed: rows.length - ok.length,
    avgMs: lat.length ? lat.reduce((a, b) => a + b, 0) / lat.length : null,
    p95Ms: p95(lat),
    perSecond: wallMs > 0 && ok.length ? ok.length / (wallMs / 1000) : null,
    inputTokens: inTok,
    outputTokens: outTok,
    costUsd: costUsd(inTok),
  };
}

export function useRun() {
  const [state, setState] = useState<RunState>(IDLE);
  const esRef = useRef<EventSource | null>(null);
  const startedAtRef = useRef<number | null>(null);
  const finishedAtRef = useRef<number | null>(null);
  const tickRef = useRef<number | null>(null);

  const closeStream = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
    if (tickRef.current !== null) {
      window.clearInterval(tickRef.current);
      tickRef.current = null;
    }
  }, []);

  useEffect(() => closeStream, [closeStream]);

  const wallNow = () => {
    const s = startedAtRef.current;
    if (s === null) return 0;
    return (finishedAtRef.current ?? performance.now()) - s;
  };

  const attach = useCallback((runId: number, emailIds: string[], live: boolean) => {
    closeStream();
    startedAtRef.current = live ? performance.now() : null;
    finishedAtRef.current = null;
    const es = new EventSource(api.streamUrl(runId));
    esRef.current = es;

    const upsert = (row: RunResult) =>
      setState((prev) => {
        const results = { ...prev.results, [row.email_id]: row };
        const wall = wallNow();
        return {
          ...prev,
          results,
          wallMs: wall,
          stats: { ...prev.stats, ...aggregate(results, prev.emailIds.length || prev.stats.total, wall) },
        };
      });

    es.addEventListener("email_done", (ev) => {
      const d = JSON.parse((ev as MessageEvent).data) as EmailDoneEvent;
      upsert({ ...d, error: null });
    });
    es.addEventListener("error", (ev) => {
      // Note: a network-level EventSource error has no `data`.
      const raw = (ev as MessageEvent).data as string | undefined;
      if (!raw) {
        if (es.readyState === EventSource.CLOSED) {
          setState((prev) => (prev.phase === "running" ? { ...prev, error: "stream closed" } : prev));
        }
        return;
      }
      const d = JSON.parse(raw) as ErrorEvent;
      upsert({ email_id: d.email_id, answers: null, latency_ms: null, input_tokens: null, output_tokens: null, error: d.message });
    });
    es.addEventListener("progress", (ev) => {
      const d = JSON.parse((ev as MessageEvent).data) as ProgressEvent;
      setState((prev) => ({
        ...prev,
        stats: { ...prev.stats, total: d.total, inFlight: d.in_flight, retries: d.retries },
      }));
    });
    es.addEventListener("run_done", (ev) => {
      const d = JSON.parse((ev as MessageEvent).data) as RunDoneEvent;
      finishedAtRef.current = performance.now();
      closeStream();
      setState((prev) => ({
        ...prev,
        phase: live ? "done" : "viewing",
        modelVersion: d.totals.model_version,
        wallMs: wallNow(),
        stats: {
          ...prev.stats,
          inFlight: 0,
          // Server totals are authoritative once the run is finished.
          avgMs: d.totals.avg_ms,
          p95Ms: d.totals.p95_ms,
          perSecond: d.totals.per_second,
          failed: d.totals.failed_count,
          inputTokens: d.totals.total_input_tokens,
          outputTokens: d.totals.total_output_tokens,
          costUsd: d.totals.total_cost_usd,
        },
      }));
    });

    if (live) {
      tickRef.current = window.setInterval(() => {
        setState((prev) => (prev.phase === "running" ? { ...prev, wallMs: wallNow() } : prev));
      }, 100);
    }

    setState({
      ...IDLE,
      phase: live ? "running" : "viewing",
      runId,
      emailIds,
      stats: { ...EMPTY_STATS, total: emailIds.length },
    });
  }, [closeStream]);

  const start = useCallback(async (workerCount: number, emailLimit: number | null, sample: SampleMode) => {
    setState({ ...IDLE, phase: "starting" });
    try {
      const { run_id, email_ids } = await api.startRun(workerCount, emailLimit, sample);
      attach(run_id, email_ids, true);
      return run_id;
    } catch (e) {
      setState({ ...IDLE, error: (e as Error).message });
      return null;
    }
  }, [attach]);

  /** Load a past run: fetch its rows, then replay its stream (no Jev calls). */
  const view = useCallback(async (runId: number) => {
    closeStream();
    const detail = await api.run(runId);
    const emailIds = detail.results.map((r) => r.email_id);
    const results: Record<string, RunResult> = {};
    for (const r of detail.results) results[r.email_id] = r;
    setState({
      ...IDLE,
      phase: detail.run.finished_at ? "viewing" : "running",
      runId,
      emailIds,
      results,
      modelVersion: detail.run.model_version,
      stats: {
        ...aggregate(results, detail.run.email_count, 0),
        inFlight: 0,
        retries: 0,
        avgMs: detail.run.avg_ms,
        p95Ms: detail.run.p95_ms,
        perSecond: detail.run.per_second,
        failed: detail.run.failed_count,
        inputTokens: detail.run.total_input_tokens,
        outputTokens: detail.run.total_output_tokens,
        costUsd: detail.run.total_cost_usd,
      },
    });
    if (!detail.run.finished_at) attach(runId, emailIds, true);
  }, [attach, closeStream]);

  const reset = useCallback(() => {
    closeStream();
    startedAtRef.current = finishedAtRef.current = null;
    setState(IDLE);
  }, [closeStream]);

  return { state, start, view, reset };
}
