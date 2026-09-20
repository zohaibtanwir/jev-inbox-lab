// Phase 2: edit instructions and criteria. Saving PUTs the whole set; the
// backend validates the wire shape and every future run snapshots exactly
// what it sent into runs.question_set_json.

import { useEffect, useState } from "react";
import { api, type Question, type QuestionSet } from "../api";

interface Props {
  initial: QuestionSet;
  onSaved: (qs: QuestionSet) => void;
  onClose: () => void;
}

type Draft = Record<string, Question>;

const clone = (q: Record<string, Question>): Draft => JSON.parse(JSON.stringify(q)) as Draft;

function TextArea({ value, onChange, rows = 3, mono = false }: { value: string; onChange: (v: string) => void; rows?: number; mono?: boolean }) {
  return (
    <textarea
      value={value}
      rows={rows}
      onChange={(e) => onChange(e.target.value)}
      className={`w-full resize-y rounded border border-neutral-800 bg-neutral-950 p-1.5 text-xs text-neutral-200 focus:border-neutral-500 focus:outline-none ${mono ? "font-mono" : ""}`}
    />
  );
}

function CriteriaEditor({ q, onChange }: { q: Question; onChange: (c: Question["criteria"]) => void }) {
  if (q.type === "score") {
    const levels = Array.isArray(q.criteria) ? q.criteria : [];
    return (
      <div className="space-y-1">
        {levels.map((l, i) => (
          <div key={i} className="flex items-start gap-2">
            <span className="w-5 pt-1.5 text-right font-mono text-xs text-neutral-500">{i}</span>
            <TextArea value={l} rows={1} onChange={(v) => onChange(levels.map((x, j) => (j === i ? v : x)))} />
            <button type="button" className="pt-1 text-xs text-neutral-600 hover:text-red-400" onClick={() => onChange(levels.filter((_, j) => j !== i))} title="Remove level">
              ×
            </button>
          </div>
        ))}
        <button type="button" className="text-xs text-neutral-500 hover:text-neutral-200" onClick={() => onChange([...levels, ""])}>
          + add level (highest)
        </button>
      </div>
    );
  }
  const entries = Array.isArray(q.criteria) ? [] : Object.entries(q.criteria);
  const fixedKeys = q.type === "noul";
  const set = (next: [string, string][]) => onChange(Object.fromEntries(next));
  return (
    <div className="space-y-1">
      {entries.map(([k, v], i) => (
        <div key={i} className="flex items-start gap-2">
          {fixedKeys ? (
            <span className="w-24 shrink-0 pt-1.5 font-mono text-xs text-neutral-400">{k}</span>
          ) : (
            <input
              value={k}
              onChange={(e) => set(entries.map((x, j) => (j === i ? [e.target.value, x[1]] : x)))}
              className="w-32 shrink-0 rounded border border-neutral-800 bg-neutral-950 p-1.5 font-mono text-xs text-neutral-200 focus:border-neutral-500 focus:outline-none"
            />
          )}
          <TextArea value={v} rows={2} onChange={(nv) => set(entries.map((x, j) => (j === i ? [x[0], nv] : x)))} />
          {!fixedKeys && (
            <button type="button" className="pt-1 text-xs text-neutral-600 hover:text-red-400" onClick={() => set(entries.filter((_, j) => j !== i))} title="Remove option">
              ×
            </button>
          )}
        </div>
      ))}
      {!fixedKeys && (
        <button type="button" className="text-xs text-neutral-500 hover:text-neutral-200" onClick={() => set([...entries, ["new_option", ""]])}>
          + add option
        </button>
      )}
    </div>
  );
}

export default function QuestionEditor({ initial, onSaved, onClose }: Props) {
  const [draft, setDraft] = useState<Draft>(() => clone(initial.questions));
  const [raw, setRaw] = useState(false);
  const [rawText, setRawText] = useState("");
  const [rawError, setRawError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dirty = JSON.stringify(draft) !== JSON.stringify(initial.questions);

  useEffect(() => {
    if (raw) setRawText(JSON.stringify(draft, null, 2));
  }, [raw]); // eslint-disable-line react-hooks/exhaustive-deps

  const update = (qid: string, patch: Partial<Question>) =>
    setDraft((d) => ({ ...d, [qid]: { ...d[qid], ...patch } }));

  const applyRaw = (): Draft | null => {
    try {
      const parsed = JSON.parse(rawText) as Draft;
      setRawError(null);
      setDraft(parsed);
      return parsed;
    } catch (e) {
      setRawError((e as Error).message);
      return null;
    }
  };

  const save = async (questions: Draft | null) => {
    setSaving(true);
    setError(null);
    try {
      const qs = await api.putQuestions(questions);
      onSaved(qs);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4 p-4 text-sm">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold">Question set</h2>
          <div className="text-xs text-neutral-500">
            current: <span className="text-neutral-300">{initial.version}</span>
            {initial.version !== initial.default_version && <span className="ml-1 text-neutral-600">(edited from {initial.default_version})</span>}
            {" · "}saved edits apply to future runs only; every run keeps the exact set it sent.
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" onClick={() => setRaw(!raw)} className="rounded border border-neutral-700 px-2 py-1 text-xs text-neutral-300 hover:bg-neutral-900">
            {raw ? "Form" : "Raw JSON"}
          </button>
          <button
            type="button"
            disabled={saving || initial.version === initial.default_version}
            onClick={() => save(null)}
            className="rounded border border-neutral-700 px-2 py-1 text-xs text-neutral-300 hover:bg-neutral-900 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Reset to {initial.default_version}
          </button>
          <button
            type="button"
            disabled={saving || (!dirty && !raw)}
            onClick={() => {
              const q = raw ? applyRaw() : draft;
              if (q) void save(q);
            }}
            className="rounded bg-emerald-600 px-3 py-1 text-xs font-medium text-white hover:bg-emerald-500 disabled:cursor-not-allowed disabled:bg-neutral-800 disabled:text-neutral-500"
          >
            {saving ? "Saving…" : "Save"}
          </button>
          <button type="button" onClick={onClose} className="rounded border border-neutral-700 px-2 py-1 text-xs text-neutral-300 hover:bg-neutral-900">
            Close
          </button>
        </div>
      </div>
      {error && <div className="rounded border border-red-900 bg-red-950/40 p-2 text-xs text-red-300">{error}</div>}

      {raw ? (
        <div>
          <textarea
            value={rawText}
            onChange={(e) => setRawText(e.target.value)}
            rows={30}
            spellCheck={false}
            className="w-full rounded border border-neutral-800 bg-neutral-950 p-2 font-mono text-xs text-neutral-200 focus:border-neutral-500 focus:outline-none"
          />
          {rawError && <div className="mt-1 text-xs text-red-300">{rawError}</div>}
          <div className="mt-1 text-xs text-neutral-600">Add or remove whole questions here. Ids are for your code only — the model never sees them.</div>
        </div>
      ) : (
        <div className="space-y-3">
          {Object.entries(draft).map(([qid, q]) => (
            <div key={qid} className="rounded border border-neutral-800 p-3">
              <div className="mb-2 flex items-center gap-2 text-xs">
                <span className="font-mono text-neutral-100">{qid}</span>
                <span className="rounded bg-neutral-900 px-1 text-neutral-400">{q.type}</span>
                <button
                  type="button"
                  className="ml-auto text-neutral-600 hover:text-red-400"
                  onClick={() => setDraft((d) => Object.fromEntries(Object.entries(d).filter(([k]) => k !== qid)))}
                >
                  remove question
                </button>
              </div>
              <div className="mb-2">
                <div className="mb-1 text-xs text-neutral-500">instructions</div>
                <TextArea value={q.instructions} onChange={(v) => update(qid, { instructions: v })} />
              </div>
              <div>
                <div className="mb-1 text-xs text-neutral-500">
                  criteria{" "}
                  <span className="text-neutral-600">
                    {q.type === "choice" ? "(option → description)" : q.type === "noul" ? "(true / false)" : "(ordered levels, low → high)"}
                  </span>
                </div>
                <CriteriaEditor q={q} onChange={(c) => update(qid, { criteria: c })} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
