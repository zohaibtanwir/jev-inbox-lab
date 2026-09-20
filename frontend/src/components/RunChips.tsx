// Run history strip (PRD section 7). Click a chip to load that run into the
// table. Tick two chips to open the diff view (PRD section 8).

import type { Run } from "../api";

interface Props {
  runs: Run[];
  activeId: number | null;
  picked: number[]; // up to two run ids chosen for diffing
  onOpen: (id: number) => void;
  onPick: (id: number) => void;
  onDiff: () => void;
}

function when(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export default function RunChips({ runs, activeId, picked, onOpen, onPick, onDiff }: Props) {
  if (runs.length === 0) {
    return <div className="text-xs text-neutral-400">No runs yet. Start one on the right.</div>;
  }
  return (
    <div className="flex items-center gap-2">
      <span className="shrink-0 text-xs uppercase tracking-wide text-neutral-500">Runs</span>
      <div className="flex min-w-0 flex-1 items-center gap-2 overflow-x-auto py-0.5 [scrollbar-width:none]">
      {runs.map((r) => {
        const active = r.id === activeId;
        const pickedIdx = picked.indexOf(r.id);
        const qs = (() => {
          try {
            return Object.keys(JSON.parse(r.question_set_json) as object).length;
          } catch {
            return "?";
          }
        })();
        return (
          <div
            key={r.id}
            className={`flex shrink-0 items-center gap-1 rounded border px-1.5 py-0.5 text-xs ${
              active ? "border-neutral-600 bg-neutral-100 text-neutral-900" : "border-neutral-200 text-neutral-600 hover:border-neutral-400"
            }`}
          >
            <input
              type="checkbox"
              className="accent-emerald-500"
              checked={pickedIdx >= 0}
              onChange={() => onPick(r.id)}
              title="Pick for diff"
            />
            <button type="button" onClick={() => onOpen(r.id)} className="flex items-center gap-1.5" title={`${qs} questions · ${r.worker_count} workers`}>
              <span className="text-neutral-500">#{r.id}</span>
              <span>{when(r.started_at)}</span>
              <span className={r.model_version ? "text-neutral-500" : "text-amber-600"}>{r.model_version ?? (r.finished_at ? "no model" : "running")}</span>
              <span className="text-neutral-400">{r.email_count}e · {r.worker_count}w</span>
              {r.failed_count > 0 && <span className="text-red-600">{r.failed_count} failed</span>}
              {pickedIdx >= 0 && <span className="rounded bg-emerald-100 px-1 text-emerald-800">{pickedIdx === 0 ? "A" : "B"}</span>}
            </button>
          </div>
        );
      })}
      </div>
      <button
        type="button"
        disabled={picked.length !== 2}
        onClick={onDiff}
        className="shrink-0 rounded bg-neutral-800 px-2 py-0.5 text-xs font-medium text-neutral-100 disabled:cursor-not-allowed disabled:bg-neutral-200 disabled:text-neutral-500"
      >
        Diff A → B
      </button>
    </div>
  );
}
