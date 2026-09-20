// Left pane (PRD section 7): sortable inbox table, rows expand to the full
// probability distributions, the speculative answers and the raw JSON.

import { useMemo, useState, type ReactNode } from "react";
import {
  displayName,
  isGateOpen,
  minConfidence,
  scoreLabel,
  SPECULATIVE,
  type Answer,
  type Answers,
  type Email,
  type RunResult,
} from "../api";

type SortKey = "from" | "subject" | "category" | "importance" | "spam" | "reply" | "confidence" | "time";

interface Row {
  email: Email;
  result: RunResult | null; // null = pending (in the run, no answer yet)
  inRun: boolean;
}

interface Props {
  emails: Email[];
  emailIds: string[]; // the run's selection; empty = no run
  results: Record<string, RunResult>;
}

const noul = (a: Answers | null | undefined, qid: string) => {
  const x = a?.[qid];
  return x?.type === "noul" ? x.noul : null;
};

function sortValue(row: Row, key: SortKey): string | number | null {
  const a = row.result?.answers ?? null;
  switch (key) {
    case "from": return displayName(row.email.from).toLowerCase();
    case "subject": return row.email.subject.toLowerCase();
    case "category": return a?.category?.type === "choice" ? a.category.choice : null;
    case "importance": return a?.importance?.type === "score" ? a.importance.score : null;
    case "spam": return noul(a, "is_spam");
    case "reply": return noul(a, "needs_reply");
    case "confidence": return a ? minConfidence(a) : null;
    case "time": return row.result?.latency_ms ?? null;
  }
}

const IMPORTANCE_STYLE = [
  "bg-neutral-200 text-neutral-600",
  "bg-sky-100 text-sky-800",
  "bg-amber-100 text-amber-700",
  "bg-red-100 text-red-700",
];

function Pill({ level, label }: { level: number; label: string }) {
  const cls = IMPORTANCE_STYLE[Math.max(0, Math.min(IMPORTANCE_STYLE.length - 1, level))];
  return (
    <span className={`inline-block max-w-[11rem] truncate rounded px-1.5 py-0.5 text-xs ${cls}`} title={label}>
      {label.split(":")[0]}
    </span>
  );
}

function Bar({ value, tone }: { value: number | null; tone: string }) {
  if (value === null) return <span className="text-neutral-400">–</span>;
  const pct = Math.round(value * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded bg-neutral-200">
        <div className={`h-full ${tone}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-8 text-right tabular-nums text-neutral-700">{pct}%</span>
    </div>
  );
}

function Spinner() {
  return <span className="inline-block h-3 w-3 animate-spin rounded-full border border-neutral-400 border-t-neutral-800" />;
}

function ProbList({ probs, pick }: { probs: Record<string, number>; pick?: string }) {
  const entries = Object.entries(probs).sort((a, b) => b[1] - a[1]);
  return (
    <ul className="space-y-0.5">
      {entries.map(([k, v]) => (
        <li key={k} className="flex items-center gap-2 text-xs">
          <div className="h-1 w-24 overflow-hidden rounded bg-neutral-200">
            <div className={`h-full ${k === pick ? "bg-emerald-500" : "bg-neutral-400"}`} style={{ width: `${Math.round(v * 100)}%` }} />
          </div>
          <span className={`w-10 text-right tabular-nums ${k === pick ? "text-emerald-700" : "text-neutral-600"}`}>
            {(v * 100).toFixed(1)}%
          </span>
          <span className={k === pick ? "text-neutral-900" : "text-neutral-600"}>{k}</span>
        </li>
      ))}
    </ul>
  );
}

function AnswerCard({ qid, answer, answers }: { qid: string; answer: Answer; answers: Answers }) {
  const spec = SPECULATIVE[qid];
  const open = isGateOpen(answers, qid);
  let body: ReactNode;
  if (answer.type === "choice") {
    body = (
      <>
        <div className="mb-1 text-sm text-neutral-900">
          {answer.choice} <span className="text-xs text-neutral-500">conf {answer.confidence.toFixed(2)}</span>
        </div>
        <ProbList probs={answer.probabilities} pick={answer.choice} />
      </>
    );
  } else if (answer.type === "score") {
    const probs: Record<string, number> = {};
    for (const [k, v] of Object.entries(answer.probabilities)) probs[`${k} · ${answer.legend[k] ?? ""}`] = v;
    body = (
      <>
        <div className="mb-1 text-sm text-neutral-900">
          {answer.score.toFixed(2)} → {scoreLabel(answer)}{" "}
          <span className="text-xs text-neutral-500">conf {answer.confidence.toFixed(2)}</span>
        </div>
        <ProbList probs={probs} pick={`${Math.round(answer.score)} · ${answer.legend[String(Math.round(answer.score))] ?? ""}`} />
      </>
    );
  } else {
    body = (
      <div className="text-sm text-neutral-900">
        {(answer.noul * 100).toFixed(1)}% <span className="text-xs text-neutral-500">noul · no confidence field</span>
        <div className="mt-1 h-1 w-40 overflow-hidden rounded bg-neutral-200">
          <div className="h-full bg-violet-500" style={{ width: `${Math.round(answer.noul * 100)}%` }} />
        </div>
      </div>
    );
  }
  return (
    <div className={`rounded border p-2 ${spec && !open ? "border-neutral-100 opacity-50" : "border-neutral-200"}`}>
      <div className="mb-1 flex items-center gap-2 text-xs uppercase tracking-wide text-neutral-500">
        {qid}
        <span className="rounded bg-neutral-100 px-1 normal-case tracking-normal">{answer.type}</span>
        {spec && (
          <span className="normal-case tracking-normal text-neutral-400">
            speculative · gate {spec.gated_by} {open ? "open" : `closed (≤ ${spec.threshold})`}
          </span>
        )}
      </div>
      {body}
    </div>
  );
}

function Expanded({ row }: { row: Row }) {
  const r = row.result;
  if (!r) return <div className="p-3 text-sm text-neutral-500">Pending…</div>;
  if (r.error || !r.answers) {
    return <div className="p-3 text-sm text-red-700">Error: {r.error ?? "no answers"}</div>;
  }
  const answers = r.answers;
  return (
    <div className="grid grid-cols-[1fr_minmax(20rem,32rem)] gap-4 p-3">
      <div className="space-y-3">
        <div className="text-xs text-neutral-500">
          {row.email.from} · {row.email.date}
        </div>
        <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded bg-neutral-100/60 p-2 text-xs text-neutral-700">
          {row.email.body}
        </pre>
        <div className="grid grid-cols-2 gap-2">
          {Object.entries(answers).map(([qid, a]) => (
            <AnswerCard key={qid} qid={qid} answer={a} answers={answers} />
          ))}
        </div>
        <div className="text-xs text-neutral-500">
          {r.latency_ms} ms · in {r.input_tokens} · out {r.output_tokens} tokens
        </div>
      </div>
      <div>
        <div className="mb-1 text-xs uppercase tracking-wide text-neutral-500">raw answers</div>
        <pre className="max-h-[32rem] overflow-auto rounded bg-neutral-100/60 p-2 text-[11px] leading-tight text-neutral-700">
          {JSON.stringify(answers, null, 2)}
        </pre>
      </div>
    </div>
  );
}

const COLS: { key: SortKey; label: string; cls?: string }[] = [
  { key: "from", label: "From", cls: "w-36" },
  { key: "subject", label: "Subject" },
  { key: "category", label: "Category", cls: "w-36" },
  { key: "importance", label: "Importance", cls: "w-40" },
  { key: "spam", label: "Spam", cls: "w-28" },
  { key: "reply", label: "Reply", cls: "w-28" },
  { key: "confidence", label: "Conf", cls: "w-16" },
  { key: "time", label: "ms", cls: "w-16" },
];

export default function InboxTable({ emails, emailIds, results }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("from");
  const [asc, setAsc] = useState(true);
  const [openId, setOpenId] = useState<string | null>(null);

  const rows = useMemo<Row[]>(() => {
    const byId = new Map(emails.map((e) => [e.id, e]));
    const inRun = new Set(emailIds);
    const hasRun = emailIds.length > 0;
    // With a run, show that run's emails only; otherwise the whole corpus.
    const ids = hasRun ? emailIds : emails.map((e) => e.id);
    return ids
      .map((id) => byId.get(id))
      .filter((e): e is Email => !!e)
      .map((email) => ({ email, result: results[email.id] ?? null, inRun: inRun.has(email.id) }));
  }, [emails, emailIds, results]);

  const sorted = useMemo(() => {
    const out = [...rows];
    out.sort((a, b) => {
      const va = sortValue(a, sortKey);
      const vb = sortValue(b, sortKey);
      if (va === null && vb === null) return 0;
      if (va === null) return 1; // nulls (pending) always last
      if (vb === null) return -1;
      const c = typeof va === "number" && typeof vb === "number" ? va - vb : String(va).localeCompare(String(vb));
      return asc ? c : -c;
    });
    return out;
  }, [rows, sortKey, asc]);

  const onSort = (k: SortKey) => {
    if (k === sortKey) setAsc(!asc);
    else {
      setSortKey(k);
      setAsc(true); // ascending by Confidence is the primary debugging view (PRD 7)
    }
  };

  return (
    <table className="w-full min-w-[68rem] table-fixed text-sm">
      <thead className="sticky top-0 bg-white text-left text-xs uppercase tracking-wide text-neutral-500">
        <tr>
          {COLS.map((c) => (
            <th
              key={c.key}
              className={`cursor-pointer select-none px-3 py-2 font-medium hover:text-neutral-700 ${c.cls ?? ""}`}
              onClick={() => onSort(c.key)}
            >
              {c.label}
              {sortKey === c.key && <span className="ml-1 text-neutral-600">{asc ? "▲" : "▼"}</span>}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {sorted.map((row) => {
          const a = row.result?.answers ?? null;
          const pending = row.inRun && !row.result;
          const failed = !!row.result?.error;
          const cat = a?.category?.type === "choice" ? a.category : null;
          const imp = a?.importance?.type === "score" ? a.importance : null;
          const conf = a ? minConfidence(a) : null;
          const open = openId === row.email.id;
          const cell = (content: ReactNode) =>
            pending ? <Spinner /> : failed ? <span className="text-red-600">error</span> : content;
          return [
            <tr
              key={row.email.id}
              className={`cursor-pointer border-t border-neutral-100 hover:bg-neutral-100/60 ${open ? "bg-neutral-100/40" : ""}`}
              onClick={() => setOpenId(open ? null : row.email.id)}
            >
              <td className="truncate px-3 py-1.5 text-neutral-700" title={row.email.from}>
                {displayName(row.email.from)}
              </td>
              <td className="truncate px-3 py-1.5 text-neutral-900" title={row.email.subject}>
                {row.email.subject}
              </td>
              <td className="px-3 py-1.5 text-neutral-800">
                {cell(cat ? <span title={`conf ${cat.confidence.toFixed(2)}`}>{cat.choice}</span> : "–")}
              </td>
              <td className="px-3 py-1.5">
                {cell(imp ? <Pill level={Math.round(imp.score)} label={scoreLabel(imp)} /> : "–")}
              </td>
              <td className="px-3 py-1.5">{cell(<Bar value={noul(a, "is_spam")} tone="bg-red-500" />)}</td>
              <td className="px-3 py-1.5">{cell(<Bar value={noul(a, "needs_reply")} tone="bg-emerald-500" />)}</td>
              <td className="px-3 py-1.5 tabular-nums">
                {cell(
                  conf === null ? "–" : (
                    <span className={conf < 0.6 ? "text-amber-700" : conf < 0.8 ? "text-neutral-800" : "text-neutral-600"}>
                      {conf.toFixed(2)}
                    </span>
                  ),
                )}
              </td>
              <td className="px-3 py-1.5 tabular-nums text-neutral-600">
                {cell(row.result?.latency_ms != null ? `${row.result.latency_ms}` : "–")}
              </td>
            </tr>,
            open ? (
              <tr key={`${row.email.id}-x`} className="border-t border-neutral-100 bg-white">
                <td colSpan={COLS.length}>
                  <Expanded row={row} />
                </td>
              </tr>
            ) : null,
          ];
        })}
        {sorted.length === 0 && (
          <tr>
            <td colSpan={COLS.length} className="px-3 py-8 text-center text-neutral-400">
              No emails loaded.
            </td>
          </tr>
        )}
      </tbody>
    </table>
  );
}
