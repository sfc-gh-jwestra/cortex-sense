"use client";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { EVAL_QUESTIONS, TIER_LABELS, TIER_COLORS, TIER_SHORT, API_URL, AGENTS, PASS } from "@/lib/questions";
import { AgentKey, AgentResponse, EvalQuestion, Verdict } from "@/lib/types";
import AgentTrace, { MiniTable } from "@/components/common/AgentTrace";
import TokenCount from "@/components/common/TokenCount";

type Responses = Partial<Record<AgentKey, AgentResponse>>;

function ScoreBadge({ score }: { score?: number | null }) {
  if (score === undefined || score === null) return null;
  const ok = score >= PASS;
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${ok ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}`}>
      AC {score.toFixed(2)}
    </span>
  );
}

function AgentPanel({ label, sublabel, response, color }: { label: string; sublabel: string; response: AgentResponse | null; color: string }) {
  if (!response) {
    return (
      <div className="rounded-xl border-l-4 border-[var(--border)] bg-[var(--bg-card)] p-5 animate-pulse"
           style={{ borderLeftColor: color }}>
        <div className="h-4 bg-[var(--border)] rounded w-1/3 mb-3" />
        <div className="h-3 bg-[var(--border)] rounded w-full mb-2" />
        <div className="h-3 bg-[var(--border)] rounded w-2/3" />
      </div>
    );
  }
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-card)] overflow-hidden"
         style={{ borderLeftWidth: "4px", borderLeftColor: color }}>
      <div className="flex items-center justify-between px-5 py-3 border-b border-[var(--border)] bg-[var(--bg)]">
        <div>
          <span className="font-semibold text-sm">{label}</span>
          <div className="text-[10px] text-[var(--text-muted)]">{sublabel}</div>
        </div>
        <div className="flex items-center gap-2">
          <ScoreBadge score={response.score} />
          {response.tokens && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--border)] text-[var(--text-muted)]">
              <TokenCount t={response.tokens} suffix=" tokens" />
            </span>
          )}
          <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--border)] text-[var(--text-muted)]">
            {response.elapsed}s
          </span>
        </div>
      </div>
      <div className="p-5">
        {response.text ? (
          <div className="text-sm leading-relaxed prose prose-sm dark:prose-invert max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{response.text}</ReactMarkdown>
          </div>
        ) : (
          <p className="text-sm text-[var(--text-muted)] italic">No text response</p>
        )}
        {response.htmlArtifacts.map((html, i) => (
          <div key={i} className="mt-4 border border-[var(--border)] rounded-lg overflow-hidden">
            <div className="text-xs px-3 py-1.5 bg-[var(--bg)] text-[var(--text-muted)] border-b border-[var(--border)]">
              Chart
            </div>
            <iframe srcDoc={html} className="w-full border-0" style={{ height: "400px" }} sandbox="allow-scripts" />
          </div>
        ))}
        <AgentTrace steps={response.steps} flags={response.ruleFlags} judge={response.judgeExplanation} />
      </div>
    </div>
  );
}

const VERDICT_STYLE: Record<string, { label: string; cls: string }> = {
  correct: { label: "answers correctly", cls: "text-emerald-600" },
  partial: { label: "partly correct", cls: "text-amber-600" },
  wrong: { label: "wrong or can't answer", cls: "text-red-600" },
};

// Same thresholds as scripts/build_web_data.py verdict().
const toVerdict = (score?: number | null): Verdict =>
  score === undefined || score === null ? null : score >= PASS ? "correct" : score > 0 ? "partial" : "wrong";

function firstSentence(text?: string | null) {
  if (!text) return "";
  // Drop judge preambles ("Comparing the actual response to the expected answer:") and list markers.
  const s = text.replace(/^[^:\n]{0,80}expected answer:\s*/i, "").replace(/(^|\s)\d+\.\s+/g, " ").replace(/\s+/g, " ").trim();
  const m = s.match(/^.{20,280}?[a-z)%\]][.!?](\s|$)/i);
  return m ? m[0].trim() : s.slice(0, 280);
}

const blank = { text: "", score: null, elapsed: 0, run: null, steps: [], ruleFlags: [], judgeExplanation: null, tablesUsed: [] };
const CUSTOM: EvalQuestion = {
  id: "Custom", tier: "", concept: "", q: "", expected: "", source: "Live question", tables: [], rules: [],
  verdicts: { finance: null, analyst: null, sense: null },
  recorded: { finance: blank, analyst: blank, sense: blank },
};

export default function ComparisonView() {
  const [selectedIdx, setSelectedIdx] = useState<number>(0);
  const [customQ, setCustomQ] = useState("");
  const [mode, setMode] = useState<"recorded" | "live">("recorded");
  const [loading, setLoading] = useState(false);
  const [responses, setResponses] = useState<Responses>({});
  const [currentQ, setCurrentQ] = useState<EvalQuestion | null>(null);

  const showRecorded = (q: EvalQuestion) => {
    setCurrentQ(q);
    const out: Responses = {};
    for (const a of AGENTS) {
      const r = q.recorded[a.key];
      out[a.key] = {
        text: r.text || "No recorded answer yet. Re-run this agent's demo eval.", htmlArtifacts: [],
        elapsed: r.elapsed, score: r.score, steps: r.steps, ruleFlags: r.ruleFlags, judgeExplanation: r.judgeExplanation,
        tokens: r.tokens,
      };
    }
    setResponses(out);
  };

  const runLive = async (q: EvalQuestion) => {
    setLoading(true);
    setResponses({});
    setCurrentQ(q);
    try {
      const res = await fetch(`${API_URL}/api/agent`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(q.id === "Custom" ? { question: q.q } : { question: q.q, id: q.id }),
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      setResponses(data);
    } catch (err: any) {
      const e: AgentResponse = { text: `Error: ${err.message}. Is api_server.py running?`, htmlArtifacts: [], elapsed: 0 };
      setResponses({ finance: e, analyst: e, sense: e });
    }
    setLoading(false);
  };

  const ask = (q: EvalQuestion) => (mode === "recorded" && q.id !== "Custom" ? showRecorded(q) : runLive(q));
  const askCustom = () => {
    if (!customQ.trim()) return;
    runLive({ ...CUSTOM, q: customQ.trim() });
    setCustomQ("");
  };

  const grouped = Object.entries(TIER_LABELS).map(([tier, label]) => ({
    tier, label, questions: EVAL_QUESTIONS.filter((q) => q.tier === tier),
  }));

  return (
    <div>
      {/* Question selector */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-5 mb-6">
        <div className="flex flex-col lg:flex-row gap-4">
          <div className="flex-1">
            <label className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2 block">
              Select a question
            </label>
            <select
              value={selectedIdx}
              onChange={(e) => setSelectedIdx(parseInt(e.target.value))}
              className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--bg)] text-sm"
            >
              {grouped.map((g) => (
                <optgroup key={g.tier} label={g.label}>
                  {g.questions.map((q) => (
                    <option key={q.id} value={EVAL_QUESTIONS.indexOf(q)}>
                      {q.id} [{q.concept}]: {q.q.slice(0, 80)}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </div>
          <div className="flex items-end gap-3">
            <div className="flex rounded-lg border border-[var(--border)] overflow-hidden text-xs">
              {(["recorded", "live"] as const).map((m) => (
                <button key={m} onClick={() => setMode(m)}
                        className={`px-3 py-2 font-medium ${mode === m ? "bg-[var(--sense)] text-white" : "bg-[var(--bg)]"}`}>
                  {m === "recorded" ? "Recorded" : "Live"}
                </button>
              ))}
            </div>
            <button
              onClick={() => ask(EVAL_QUESTIONS[selectedIdx])}
              disabled={loading}
              className="px-6 py-2 rounded-lg bg-[var(--sense)] text-white font-medium text-sm hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {loading ? "Running..." : "Ask All Agents"}
            </button>
          </div>
        </div>
        <p className="text-[11px] text-[var(--text-muted)] mt-2">
          Recorded replays the scored answers and tool steps from the latest demo eval runs instantly. Live calls all three agents now (about 10 to 90 seconds) and scores each answer against the expected answer with a live judge.
        </p>

        <div className="mt-4 pt-4 border-t border-[var(--border)]">
          <label className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2 block">
            Or type a custom question (always live)
          </label>
          <div className="flex gap-3">
            <input
              type="text"
              value={customQ}
              onChange={(e) => setCustomQ(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") askCustom(); }}
              placeholder="Ask any gaming portfolio question..."
              className="flex-1 px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--bg)] text-sm"
            />
            <button
              onClick={askCustom}
              disabled={loading || !customQ.trim()}
              className="px-5 py-2 rounded-lg border border-[var(--border)] text-sm font-medium hover:bg-[var(--bg)] disabled:opacity-50"
            >
              Ask
            </button>
          </div>
        </div>
      </div>

      {/* Current question */}
      {currentQ && (
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className="text-xs font-bold px-2 py-0.5 rounded-full text-white"
                  style={{ backgroundColor: TIER_COLORS[currentQ.tier] || "#666" }}>
              {currentQ.id}
            </span>
            {currentQ.concept && <span className="text-xs font-medium">{currentQ.concept}</span>}
            <span className="text-xs text-[var(--text-muted)]">{currentQ.source}</span>
          </div>
          <p className="text-lg font-medium">{currentQ.q}</p>
        </div>
      )}

      {loading && (
        <div className="text-center py-6 text-[var(--text-muted)]">
          <div className="inline-block w-8 h-8 border-2 border-[var(--sense)] border-t-transparent rounded-full animate-spin mb-3" />
          <p className="text-sm">Running all three agents in parallel...</p>
        </div>
      )}

      {/* Side-by-side results */}
      {(Object.keys(responses).length > 0 || loading) && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
          {AGENTS.map((a) => (
            <AgentPanel key={a.key} label={a.label} sublabel={a.sublabel} response={responses[a.key] ?? null} color={a.color} />
          ))}
        </div>
      )}

      {/* Expected answer and verdicts */}
      {currentQ?.expected && !loading && Object.keys(responses).length > 0 && (
        <div className="mt-5 grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="rounded-xl px-5 py-4 bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800">
            <div className="text-xs font-semibold uppercase tracking-wider text-blue-600 mb-1">Expected answer</div>
            <p className="text-xs mb-3">{currentQ.expected}</p>
            {currentQ.expectedRows && (
              <>
                <MiniTable columns={currentQ.expectedRows.columns} rows={currentQ.expectedRows.rows} total={currentQ.expectedRows.total} />
                <details className="mt-2 text-xs">
                  <summary className="cursor-pointer font-semibold">Ground-truth SQL (follows the feedback rules)</summary>
                  <pre className="text-[11px] whitespace-pre-wrap font-mono mt-1">{currentQ.expectedRows.sql}</pre>
                </details>
              </>
            )}
          </div>
          <div className="rounded-xl px-5 py-4 bg-[var(--bg-card)] border border-[var(--border)] space-y-3">
            {mode === "recorded" && currentQ.id !== "Custom" ? (
              AGENTS.map((a) => {
                const v: Verdict = currentQ.verdicts[a.key];
                const style = v ? VERDICT_STYLE[v] : null;
                return (
                  <div key={a.key}>
                    <div className={`text-xs font-semibold uppercase tracking-wider ${style?.cls ?? "text-[var(--text-muted)]"}`}>
                      <span style={{ color: a.color }}>{a.label}</span>: {style?.label ?? "not run yet"}
                    </div>
                    <p className="text-xs text-[var(--text-muted)]">{firstSentence(currentQ.recorded[a.key].judgeExplanation)}</p>
                  </div>
                );
              })
            ) : currentQ.id !== "Custom" ? (
              AGENTS.map((a) => {
                const r = responses[a.key];
                const style = r ? VERDICT_STYLE[toVerdict(r.score) ?? ""] : null;
                return (
                  <div key={a.key}>
                    <div className={`text-xs font-semibold uppercase tracking-wider ${style?.cls ?? "text-[var(--text-muted)]"}`}>
                      <span style={{ color: a.color }}>{a.label}</span>: {!r ? "waiting for answer" : style ? `${style.label} (live judge)` : "not scored"}
                    </div>
                    <p className="text-xs text-[var(--text-muted)]">{firstSentence(r?.judgeExplanation)}</p>
                  </div>
                );
              })
            ) : (
              <p className="text-xs text-[var(--text-muted)]">Custom questions have no expected answer, so they aren&apos;t scored; compare them using the rule flags.</p>
            )}
            <div className="pt-2 border-t border-[var(--border)]">
              <div className="text-xs font-semibold" style={{ color: "var(--sense)" }}>Context Cortex Sense brings</div>
              <p className="text-xs text-[var(--text-muted)]">{currentQ.source}</p>
              {currentQ.rules.length > 0 && <p className="text-xs text-[var(--text-muted)] mt-1">Feedback rules: {currentQ.rules.join(", ")}</p>}
            </div>
          </div>
        </div>
      )}

      {/* Scorecard */}
      <div className="mt-8 rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-5">
        <h3 className="font-semibold text-sm mb-4">Scorecard (recorded answer correctness, pass at 0.67 or higher)</h3>
        <div className="grid grid-cols-2 gap-3">
          {Object.keys(TIER_LABELS).map((tier) => {
            const qs = EVAL_QUESTIONS.filter((q) => q.tier === tier);
            const pass = (k: AgentKey) => qs.filter((q) => (q.recorded[k].score ?? 0) >= PASS).length;
            return (
              <div key={tier} className="text-center p-3 rounded-lg border border-[var(--border)]">
                <div className="text-xs font-bold mb-2" style={{ color: TIER_COLORS[tier] }}>{TIER_SHORT[tier]}</div>
                {AGENTS.map((a) => (
                  <div key={a.key} className="text-xs" style={{ color: a.color }}>
                    {a.label}: {qs.some((q) => q.recorded[a.key].run) ? `${pass(a.key)}/${qs.length}` : "not run yet"}
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
