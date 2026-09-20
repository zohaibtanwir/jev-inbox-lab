// Run A vs run B (PRD section 8). Shows only what changed.

import { useEffect, useState } from "react";
import { api, displayName, type DiffPayload, type Email, type Question } from "../api";

interface Props {
  a: number;
  b: number;
  emails: Email[];
  onClose: () => void;
}

const sign = (d: number) => (d > 0 ? `+${d.toFixed(2)}` : d.toFixed(2));

function RunHead({ label, r }: { label: string; r: DiffPayload["a"] }) {
  return (
    <div className="rounded border border-neutral-200 p-2 text-xs">
      <span className="mr-2 rounded bg-emerald-100 px-1 text-emerald-800">{label}</span>
      <span className="text-neutral-800">run #{r.id}</span>
      <span className="ml-2 text-neutral-500">{new Date(r.started_at).toLocaleString()}</span>
      <span className="ml-2 text-neutral-600">{r.model_version ?? "no model"}</span>
      <span className="ml-2 text-neutral-400">{r.email_count} emails · {r.worker_count} workers</span>
    </div>
  );
}

function criteriaText(c: Question["criteria"] | unknown): string {
  if (Array.isArray(c)) return c.map((v, i) => `${i}: ${v}`).join("\n");
  if (c && typeof c === "object") return Object.entries(c as Record<string, string>).map(([k, v]) => `${k}: ${v}`).join("\n");
  return String(c ?? "");
}

function QuestionSideBySide({ change }: { change: DiffPayload["question_changes"][number] }) {
  const isCriteria = change.field === "criteria";
  const aText = isCriteria ? criteriaText(change.a) : String(change.a ?? "");
  const bText = isCriteria ? criteriaText(change.b) : String(change.b ?? "");
  // Line-level highlight for criteria: a line that differs from the other side is marked.
  const aLines = aText.split("\n");
  const bLines = bText.split("\n");
  const aSet = new Set(aLines);
  const bSet = new Set(bLines);
  const render = (lines: string[], other: Set<string>) =>
    lines.map((l, i) => (
      <div key={i} className={other.has(l) ? "text-neutral-600" : "rounded bg-amber-100 px-1 text-amber-900"}>
        {l || " "}
      </div>
    ));
  return (
    <div className="rounded border border-neutral-200">
      <div className="border-b border-neutral-200 px-2 py-1 text-xs">
        <span className="text-neutral-900">{change.question_id}</span>
        <span className="ml-2 text-neutral-500">{change.field}</span>
      </div>
      <div className="grid grid-cols-2 gap-px bg-neutral-200 text-xs">
        <div className="whitespace-pre-wrap bg-white p-2 font-mono">{render(aLines, bSet)}</div>
        <div className="whitespace-pre-wrap bg-white p-2 font-mono">{render(bLines, aSet)}</div>
      </div>
    </div>
  );
}

export default function DiffView({ a, b, emails, onClose }: Props) {
  const [diff, setDiff] = useState<DiffPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const byId = new Map(emails.map((e) => [e.id, e]));
  const who = (id: string) => {
    const e = byId.get(id);
    return e ? (
      <span>
        <span className="text-neutral-700">{displayName(e.from)}</span>
        <span className="ml-1 text-neutral-500">{e.subject}</span>
      </span>
    ) : (
      <span className="text-neutral-500">{id}</span>
    );
  };

  useEffect(() => {
    setDiff(null);
    setError(null);
    api.diff(a, b).then(setDiff).catch((e: Error) => setError(e.message));
  }, [a, b]);

  return (
    <div className="space-y-4 p-4 text-sm">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold">Diff: run #{a} → run #{b}</h2>
        <button type="button" onClick={onClose} className="rounded border border-neutral-300 px-2 py-1 text-xs text-neutral-700 hover:bg-neutral-100">
          Back to inbox
        </button>
      </div>
      {error && <div className="text-red-700">{error}</div>}
      {!diff && !error && <div className="text-neutral-500">Loading…</div>}
      {diff && (
        <>
          <div className="grid grid-cols-2 gap-2">
            <RunHead label="A" r={diff.a} />
            <RunHead label="B" r={diff.b} />
          </div>
          <div className="text-xs text-neutral-500">
            {diff.common_email_count} emails in both runs · thresholds ±{diff.delta_threshold.toFixed(2)}
            {diff.a.model_version !== diff.b.model_version && (
              <span className="ml-2 text-amber-700">model version differs — answer changes may be the model, not your edit</span>
            )}
          </div>

          <section>
            <h3 className="mb-1 text-xs uppercase tracking-wide text-neutral-500">
              Question changes <span className="text-neutral-400">({diff.question_changes.length})</span>
            </h3>
            {diff.question_changes.length === 0 ? (
              <div className="text-neutral-400">Identical question sets.</div>
            ) : (
              <div className="space-y-2">
                {diff.question_changes.map((c, i) => <QuestionSideBySide key={i} change={c} />)}
              </div>
            )}
          </section>

          <section>
            <h3 className="mb-1 text-xs uppercase tracking-wide text-neutral-500">
              Category flips <span className="text-neutral-400">({diff.category_flips.length})</span>
            </h3>
            {diff.category_flips.length === 0 ? (
              <div className="text-neutral-400">None.</div>
            ) : (
              <table className="w-full text-xs">
                <tbody>
                  {diff.category_flips.map((f, i) => (
                    <tr key={i} className="border-t border-neutral-100">
                      <td className="py-1 pr-3">{who(f.email_id)}</td>
                      <td className="py-1 pr-3 text-neutral-500">{f.question_id}</td>
                      <td className="py-1 font-mono">
                        <span className="text-neutral-600">{f.a}</span>
                        <span className="mx-2 text-neutral-400">→</span>
                        <span className="text-neutral-900">{f.b}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <div className="grid grid-cols-2 gap-4">
            {(["confidence_deltas", "noul_deltas"] as const).map((key) => (
              <section key={key}>
                <h3 className="mb-1 text-xs uppercase tracking-wide text-neutral-500">
                  {key === "confidence_deltas" ? "Confidence deltas" : "Noul deltas"}{" "}
                  <span className="text-neutral-400">({diff[key].length})</span>
                </h3>
                {diff[key].length === 0 ? (
                  <div className="text-neutral-400">None beyond ±{diff.delta_threshold.toFixed(2)}.</div>
                ) : (
                  <table className="w-full text-xs">
                    <tbody>
                      {[...diff[key]].sort((x, y) => Math.abs(y.delta) - Math.abs(x.delta)).map((d, i) => (
                        <tr key={i} className="border-t border-neutral-100">
                          <td className="py-1 pr-3">{who(d.email_id)}</td>
                          <td className="py-1 pr-3 text-neutral-500">{d.question_id}</td>
                          <td className="py-1 font-mono tabular-nums">
                            <span className="text-neutral-600">{d.a.toFixed(2)}</span>
                            <span className="mx-1 text-neutral-400">→</span>
                            <span className="text-neutral-900">{d.b.toFixed(2)}</span>
                            <span className={`ml-2 ${d.delta > 0 ? "text-emerald-700" : "text-red-700"}`}>{sign(d.delta)}</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </section>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
