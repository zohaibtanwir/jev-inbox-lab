import { useCallback, useEffect, useState } from "react";
import { api, type Email, type Health, type QuestionSet, type Run, type SampleMode } from "./api";
import DiffView from "./components/DiffView";
import InboxTable from "./components/InboxTable";
import QuestionEditor from "./components/QuestionEditor";
import RunChips from "./components/RunChips";
import RunPanel from "./components/RunPanel";
import { useRun } from "./useRun";

type View = { kind: "inbox" } | { kind: "diff"; a: number; b: number } | { kind: "questions" };

export default function App() {
  const [emails, setEmails] = useState<Email[]>([]);
  const [questions, setQuestions] = useState<QuestionSet | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<View>({ kind: "inbox" });
  const [picked, setPicked] = useState<number[]>([]);
  const { state: run, start, view: openRun, reset } = useRun();

  const refreshRuns = useCallback(() => api.runs().then(setRuns).catch(() => undefined), []);

  useEffect(() => {
    Promise.all([api.emails(), api.questions(), api.runs(), api.health()])
      .then(([e, q, r, h]) => {
        setEmails(e);
        setQuestions(q);
        setRuns(r);
        setHealth(h);
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  // Refresh the history strip when a run starts and when it finishes, so the
  // chip picks up model_version and totals.
  useEffect(() => {
    if (run.phase === "running" || run.phase === "done") void refreshRuns();
  }, [run.phase, refreshRuns]);

  const onStart = async (workers: number, limit: number | null, sample: SampleMode) => {
    setView({ kind: "inbox" });
    await start(workers, limit, sample);
  };

  const onPick = (id: number) =>
    setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : p.length >= 2 ? [p[1], id] : [...p, id]));

  return (
    <div className="flex h-screen flex-col bg-white text-neutral-900">
      <header className="flex items-center gap-4 border-b border-neutral-200 px-4 py-2">
        <h1 className="text-base font-semibold tracking-tight">Jev Inbox Lab</h1>
        <span className="text-xs text-neutral-500">
          {emails.length} emails · question set {questions?.version ?? "…"} · {runs.length} runs
        </span>
        <div className="ml-auto flex items-center gap-2 text-xs">
          <button
            type="button"
            onClick={() => setView(view.kind === "questions" ? { kind: "inbox" } : { kind: "questions" })}
            className={`rounded border px-2 py-1 ${view.kind === "questions" ? "border-neutral-600 text-neutral-900" : "border-neutral-300 text-neutral-700 hover:bg-neutral-100"}`}
          >
            Questions
          </button>
          {view.kind !== "inbox" && (
            <button type="button" onClick={() => setView({ kind: "inbox" })} className="rounded border border-neutral-300 px-2 py-1 text-neutral-700 hover:bg-neutral-100">
              Inbox
            </button>
          )}
        </div>
      </header>

      <div className="border-b border-neutral-200 px-4 py-1.5">
        <RunChips
          runs={runs}
          activeId={run.runId}
          picked={picked}
          onOpen={(id) => {
            setView({ kind: "inbox" });
            void openRun(id);
          }}
          onPick={onPick}
          onDiff={() => picked.length === 2 && setView({ kind: "diff", a: picked[0], b: picked[1] })}
        />
      </div>

      {error && (
        <div className="m-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
          Backend unreachable: {error}. Is uvicorn running on :8000?
        </div>
      )}

      <main className="grid min-h-0 flex-1 grid-cols-[1fr_300px]">
        <section className="min-h-0 overflow-auto border-r border-neutral-200">
          {view.kind === "inbox" && <InboxTable emails={emails} emailIds={run.emailIds} results={run.results} />}
          {view.kind === "diff" && <DiffView a={view.a} b={view.b} emails={emails} onClose={() => setView({ kind: "inbox" })} />}
          {view.kind === "questions" && questions && (
            <QuestionEditor
              key={questions.version + JSON.stringify(questions.questions).length}
              initial={questions}
              onSaved={(qs) => setQuestions(qs)}
              onClose={() => setView({ kind: "inbox" })}
            />
          )}
        </section>
        <aside className="min-h-0 overflow-auto p-3">
          <RunPanel
            run={run}
            corpusSize={emails.length}
            questionVersion={questions?.version ?? "…"}
            apiKeyPresent={health ? health.api_key_present : null}
            onStart={onStart}
            onReset={reset}
          />
        </aside>
      </main>
    </div>
  );
}
