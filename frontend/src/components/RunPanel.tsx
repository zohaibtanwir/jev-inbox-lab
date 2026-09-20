// Right pane (PRD section 7): controls, progress, stats, live, tokens.

import { useState } from "react";
import type { SampleMode } from "../api";
import type { RunState } from "../useRun";

export type EmailChoice = "all" | "first25" | "random50";

interface Props {
  run: RunState;
  corpusSize: number;
  questionVersion: string;
  apiKeyPresent: boolean | null;
  onStart: (workers: number, limit: number | null, sample: SampleMode) => void;
  onReset: () => void;
}

const WORKERS = [8, 16, 32, 64];

const EMAIL_CHOICES: { key: EmailChoice; label: string; limit: number | null; sample: SampleMode }[] = [
  { key: "all", label: "All", limit: null, sample: "first" },
  { key: "first25", label: "First 25", limit: 25, sample: "first" },
  { key: "random50", label: "Random 50", limit: 50, sample: "random" },
];

const ms = (v: number | null) => (v === null ? "–" : `${Math.round(v)} ms`);
const secs = (v: number) => `${(v / 1000).toFixed(1)} s`;
const usd = (v: number) => `$${v.toFixed(5)}`;

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <span className="text-neutral-500">{label}</span>
      <span className="tabular-nums text-neutral-100">
        {value}
        {hint && <span className="ml-1 text-xs text-neutral-500">{hint}</span>}
      </span>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1 border-t border-neutral-800 pt-3">
      <h3 className="mb-1 text-xs uppercase tracking-wide text-neutral-500">{title}</h3>
      {children}
    </div>
  );
}

function Segmented<T extends string | number>({
  options, value, onChange, disabled,
}: { options: { value: T; label: string }[]; value: T; onChange: (v: T) => void; disabled?: boolean }) {
  return (
    <div className="flex overflow-hidden rounded border border-neutral-800 text-xs">
      {options.map((o) => (
        <button
          key={String(o.value)}
          type="button"
          disabled={disabled}
          onClick={() => onChange(o.value)}
          className={`flex-1 px-2 py-1 transition-colors disabled:cursor-not-allowed ${
            o.value === value ? "bg-neutral-200 text-neutral-900" : "bg-neutral-950 text-neutral-400 hover:bg-neutral-900"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export default function RunPanel({ run, corpusSize, questionVersion, apiKeyPresent, onStart, onReset }: Props) {
  const [emailChoice, setEmailChoice] = useState<EmailChoice>("random50");
  const [workers, setWorkers] = useState(16);
  const busy = run.phase === "starting" || run.phase === "running";
  const s = run.stats;
  const pct = s.total ? Math.round((s.done / s.total) * 100) : 0;
  const choice = EMAIL_CHOICES.find((c) => c.key === emailChoice)!;

  return (
    <div className="space-y-3 text-sm">
      <div className="space-y-2">
        <div>
          <div className="mb-1 text-xs text-neutral-500">Emails ({corpusSize} in corpus)</div>
          <Segmented options={EMAIL_CHOICES.map((c) => ({ value: c.key, label: c.label }))} value={emailChoice} onChange={setEmailChoice} disabled={busy} />
        </div>
        <div>
          <div className="mb-1 text-xs text-neutral-500">Workers</div>
          <Segmented options={WORKERS.map((w) => ({ value: w, label: String(w) }))} value={workers} onChange={setWorkers} disabled={busy} />
        </div>
        <div className="flex gap-2 pt-1">
          <button
            type="button"
            disabled={busy || apiKeyPresent === false}
            onClick={() => onStart(workers, choice.limit, choice.sample)}
            className="flex-1 rounded bg-emerald-600 px-3 py-1.5 font-medium text-white hover:bg-emerald-500 disabled:cursor-not-allowed disabled:bg-neutral-800 disabled:text-neutral-500"
          >
            {run.phase === "starting" ? "Starting…" : run.phase === "running" ? "Running…" : "Start"}
          </button>
          <button
            type="button"
            disabled={busy || run.phase === "idle"}
            onClick={onReset}
            className="rounded border border-neutral-700 px-3 py-1.5 text-neutral-300 hover:bg-neutral-900 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Reset
          </button>
        </div>
        <div className="text-xs text-neutral-600">
          question set <span className="text-neutral-400">{questionVersion}</span>
          {run.runId !== null && (
            <>
              {" "}· run <span className="text-neutral-400">#{run.runId}</span>
              {run.modelVersion && <> · <span className="text-neutral-400">{run.modelVersion}</span></>}
              {run.phase === "viewing" && <span className="text-neutral-500"> (history)</span>}
            </>
          )}
        </div>
        {apiKeyPresent === false && (
          <div className="rounded border border-amber-900 bg-amber-950/40 p-2 text-xs text-amber-300">
            TYPESAFE_API_KEY is not set in .env — the backend will refuse to start a run.
          </div>
        )}
        {run.error && (
          <div className="rounded border border-red-900 bg-red-950/40 p-2 text-xs text-red-300">{run.error}</div>
        )}
      </div>

      <Section title="Progress">
        <div className="h-1.5 w-full overflow-hidden rounded bg-neutral-800">
          <div className="h-full bg-emerald-500 transition-[width] duration-150" style={{ width: `${pct}%` }} />
        </div>
        <Stat label="Done" value={`${s.done} of ${s.total}`} hint={`${pct}%`} />
        <Stat label="Remaining" value={String(Math.max(0, s.total - s.done))} />
        <Stat label="Failed" value={String(s.failed)} />
      </Section>

      <Section title="Stats">
        <Stat label="Run" value={secs(run.wallMs)} hint="wall clock" />
        <Stat label="Average" value={ms(s.avgMs)} />
        <Stat label="Per second" value={s.perSecond === null ? "–" : s.perSecond.toFixed(1)} />
        <Stat label="p95" value={ms(s.p95Ms)} />
      </Section>

      <Section title="Live">
        <Stat label="In flight" value={String(s.inFlight)} />
        <Stat label="API retries" value={String(s.retries)} />
        <Stat label="Failed" value={String(s.failed)} />
      </Section>

      <Section title="Tokens">
        <Stat label="In" value={s.inputTokens.toLocaleString()} hint={usd(s.costUsd)} />
        <Stat label="Out" value={s.outputTokens.toLocaleString()} hint="$0.00" />
        <Stat label="Estimated cost" value={usd(s.costUsd)} />
        <div className="pt-1 text-[11px] text-neutral-600">$0.042 per million input tokens. Output is free.</div>
      </Section>
    </div>
  );
}
