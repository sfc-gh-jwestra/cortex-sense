"use client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AGENTS, DEMO_DATA, EVAL_QUESTIONS, PASS, TIER_COLORS, TIER_LABELS } from "@/lib/questions";
import { EvalQuestion, RecordedAnswer } from "@/lib/types";
import AgentTrace, { RuleFlags } from "@/components/common/AgentTrace";
import TokenCount from "@/components/common/TokenCount";

const pct = (x: number | null) => (x === null ? "n/a" : x.toFixed(2));

function Score({ score }: { score: number | null }) {
  if (score === null) return <span className="text-xs font-semibold uppercase text-[var(--text-muted)]">not run</span>;
  const label = score >= PASS ? "CORRECT" : score > 0 ? "PARTIAL" : "WRONG / DECLINED";
  const cls = score >= PASS ? "text-emerald-600" : score > 0 ? "text-amber-600" : "text-red-600";
  return <span className={`text-xs font-semibold uppercase ${cls}`}>{label} (AC {score.toFixed(2)})</span>;
}

function AnswerBlock({ title, color, r }: { title: string; color: string; r: RecordedAnswer }) {
  return (
    <div className="p-5" style={{ borderLeft: `4px solid ${color}` }}>
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        <span className="text-xs font-semibold">{title}</span>
        <Score score={r.score} />
      </div>
      <div className="text-xs leading-relaxed prose prose-xs dark:prose-invert max-w-none max-h-72 overflow-auto">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{r.text || "_No recorded answer._"}</ReactMarkdown>
      </div>
      <AgentTrace steps={r.steps} flags={r.ruleFlags} judge={r.judgeExplanation} />
    </div>
  );
}

function BehaviorRow({ q }: { q: EvalQuestion }) {
  return (
    <div className="overflow-x-auto">
      <table className="text-xs w-full">
        <thead>
          <tr className="text-left text-[var(--text-muted)]">
            <th className="font-semibold py-1 pr-3">Agent</th>
            <th className="font-semibold py-1 pr-3">Score</th>
            <th className="font-semibold py-1 pr-3">Tool steps</th>
            <th className="font-semibold py-1 pr-3">Tokens</th>
            <th className="font-semibold py-1 pr-3">Time</th>
            <th className="font-semibold py-1 pr-3">Tables touched</th>
            <th className="font-semibold py-1">Rule checks</th>
          </tr>
        </thead>
        <tbody>
          {AGENTS.map((a) => {
            const r = q.recorded[a.key];
            return (
              <tr key={a.key} className="border-t border-[var(--border)] align-top">
                <td className="py-1.5 pr-3 font-semibold" style={{ color: a.color }}>{a.label}</td>
                <td className="py-1.5 pr-3">{r.score === null ? "not run" : r.score.toFixed(2)}</td>
                <td className="py-1.5 pr-3">{r.run ? r.steps.length : ""}</td>
                <td className="py-1.5 pr-3"><TokenCount t={r.tokens} /></td>
                <td className="py-1.5 pr-3">{r.run ? `${r.elapsed}s` : ""}</td>
                <td className="py-1.5 pr-3 font-mono text-[11px]">{r.tablesUsed.join(", ")}</td>
                <td className="py-1.5"><RuleFlags flags={r.ruleFlags} /></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** Tokens spent on answers below the pass mark, for the capable analyst and Cortex Sense. */
function WastedTokenCards() {
  const cards = AGENTS.filter((a) => a.key === "analyst" || a.key === "sense").map((a) => {
    const rs = EVAL_QUESTIONS.map((q) => q.recorded[a.key]).filter((r) => r.run);
    const all = rs.reduce((t, r) => t + (r.tokens?.total ?? 0), 0);
    const wrong = rs.filter((r) => (r.score ?? 0) < PASS);
    const wasted = wrong.reduce((t, r) => t + (r.tokens?.total ?? 0), 0);
    return { a, ran: rs.length > 0, hasTokens: rs.some((r) => r.tokens), wrong: wrong.length, wasted, share: all ? Math.round((wasted / all) * 100) : 0 };
  }).filter((c) => c.ran && c.hasTokens);
  if (!cards.length) return null;
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
      {cards.map(({ a, wrong, wasted, share }) => (
        <div key={a.key} className="rounded-lg border border-[var(--border)] p-3 text-center">
          <div className="text-2xl font-bold" style={{ color: a.color }}>{wasted.toLocaleString("en-US")}</div>
          <div className="text-xs text-[var(--text-muted)]">Wasted tokens: {a.label}</div>
          <div className="text-[10px] text-[var(--text-muted)]">
            {wrong ? `${wrong} wrong ${wrong === 1 ? "answer" : "answers"} | ${share}% of its tokens` : "no wrong answers"}
          </div>
        </div>
      ))}
    </div>
  );
}

/** Capable analyst vs. Cortex Sense on the questions both answered correctly. Rows show only where Sense is better. */
function EfficiencyTable() {
  const both = EVAL_QUESTIONS.filter((q) => (q.recorded.analyst.score ?? 0) >= PASS && (q.recorded.sense.score ?? 0) >= PASS);
  if (!both.length) return null;
  const sum = (k: "analyst" | "sense", f: (r: RecordedAnswer) => number) => both.reduce((t, q) => t + f(q.recorded[k]), 0);
  const tok = (r: RecordedAnswer) => r.tokens?.total ?? 0;
  const n = (x: number) => x.toLocaleString("en-US");
  const less = (a: number, s: number) => Math.round(((a - s) / a) * 100);
  const rows: { metric: string; a: string; s: string; diff: string; better: boolean }[] = [];
  if (both.every((q) => q.recorded.analyst.tokens && q.recorded.sense.tokens)) {
    const a = sum("analyst", tok), s = sum("sense", tok);
    rows.push({ metric: "Token count", a: n(a), s: n(s), diff: `${((a - s) / a * 100).toFixed(1)}% fewer tokens`, better: s < a });
  }
  const ac = sum("analyst", (r) => r.steps.length), sc = sum("sense", (r) => r.steps.length);
  rows.push({ metric: "Tool calls", a: n(ac), s: n(sc), diff: `${ac - sc} fewer tool calls (-${less(ac, sc)}%)`, better: sc < ac });
  const at = sum("analyst", (r) => r.elapsed) / both.length, st = sum("sense", (r) => r.elapsed) / both.length;
  rows.push({ metric: "Avg. time", a: `${at.toFixed(1)}s`, s: `${st.toFixed(1)}s`, diff: `${(at - st).toFixed(1)}s faster (-${less(at, st)}%)`, better: st < at });
  const shown = rows.filter((r) => r.better);
  if (!shown.length) return null;
  const sense = AGENTS.find((a) => a.key === "sense")!, analyst = AGENTS.find((a) => a.key === "analyst")!;
  return (
    <div className="rounded-lg border border-[var(--border)] p-4 mb-6">
      <h3 className="text-sm font-bold mb-1">Cortex Sense vs. capable analyst, on questions both answered correctly</h3>
      <p className="text-xs text-[var(--text-muted)] mb-3">{both.length} questions: {both.map((q) => q.id).join(", ")}</p>
      <table className="text-sm w-full">
        <thead>
          <tr className="text-left text-xs text-[var(--text-muted)]">
            <th className="font-semibold py-1 pr-3">Metric</th>
            <th className="font-semibold py-1 pr-3" style={{ color: analyst.color }}>{analyst.label}</th>
            <th className="font-semibold py-1 pr-3" style={{ color: sense.color }}>{sense.label}</th>
            <th className="font-semibold py-1">Cortex Sense vs. analyst</th>
          </tr>
        </thead>
        <tbody>
          {shown.map((r) => (
            <tr key={r.metric} className="border-t border-[var(--border)]">
              <td className="py-1.5 pr-3 font-medium">{r.metric}</td>
              <td className="py-1.5 pr-3">{r.a}</td>
              <td className="py-1.5 pr-3">{r.s}</td>
              <td className="py-1.5 font-semibold text-emerald-600">{r.diff}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function notes(q: EvalQuestion): string[] {
  const out: string[] = [];
  if (q.tier === "tie") {
    out.push("All three agents can answer from SV_GAME_SALES; Sense also gets its verified queries as context documents.");
  } else {
    out.push(`Tables outside SV_GAME_SALES that Cortex Sense points to: ${q.tables.join(", ")}`);
    if (q.knowledgeDoc) out.push(`Business definitions from the knowledge base stage file ${q.knowledgeDoc}`);
    if (q.rules.length) out.push(`Feedback rules that apply: ${q.rules.join(", ")}`);
  }
  const broken = q.recorded.analyst.ruleFlags.filter((f) => f.status === "fail");
  if (broken.length) {
    out.push(`The capable analyst found the tables on its own but broke ${broken.map((f) => `"${f.rule}"`).join(" and ")}: ${broken[0].reason} Cortex Sense serves this rule as a correction.`);
  }
  return out;
}

export default function AnalysisView() {
  const s = DEMO_DATA.summary;
  const runs = AGENTS.filter((a) => s[a.key].recorded)
    .map((a) => DEMO_DATA.agents.find((x) => x.key === a.key)?.run).filter(Boolean).join(", ");
  return (
    <div>
      <p className="text-sm text-[var(--text-muted)] mb-2">
        {s.questions} questions scored with answer correctness. Answers, tool steps and judge notes below are from the
        recorded eval runs ({runs}). Rule checks compare each agent&apos;s SQL with the Cortex Sense feedback rules.
      </p>

      <h2 className="text-lg font-bold mb-3 mt-4">Uplift</h2>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        {AGENTS.map((a) => (
          <div key={a.key} className="rounded-lg border border-[var(--border)] p-3 text-center">
            <div className="text-2xl font-bold" style={{ color: a.color }}>
              {s[a.key].recorded ? `${s[a.key].correct}/${s.questions}` : "not run"}
            </div>
            <div className="text-xs text-[var(--text-muted)]">{a.label}</div>
            <div className="text-[10px] text-[var(--text-muted)]">tie {pct(s[a.key].tie)} | long-tail {pct(s[a.key].sense_only)}</div>
          </div>
        ))}
        <div className="rounded-lg border border-[var(--border)] p-3 text-center">
          <div className="text-2xl font-bold" style={{ color: "var(--sense)" }}>
            {EVAL_QUESTIONS.filter((q) => q.tier === "sense_only").length}
          </div>
          <div className="text-xs text-[var(--text-muted)]">Concepts outside the semantic view</div>
        </div>
      </div>

      <WastedTokenCards />
      <EfficiencyTable />

      <h2 className="text-lg font-bold mb-3">Questions</h2>

      {Object.entries(TIER_LABELS).map(([tier, label]) => {
        const items = EVAL_QUESTIONS.filter((q) => q.tier === tier);
        return (
          <div key={tier} className="mb-6">
            <h3 className="text-sm font-bold mb-3 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: TIER_COLORS[tier] }} />
              {label}
              <span className="text-xs font-normal text-[var(--text-muted)]">({items.length} questions)</span>
            </h3>
            <div className="space-y-4">
              {items.map((q) => (
                <div key={q.id} className="rounded-xl border border-[var(--border)] bg-[var(--bg-card)] overflow-hidden">
                  <div className="flex items-center gap-3 px-5 py-3 border-b border-[var(--border)] bg-[var(--bg)]">
                    <span className="text-xs font-bold px-2 py-0.5 rounded-full text-white" style={{ backgroundColor: TIER_COLORS[q.tier] }}>
                      {q.id}
                    </span>
                    <span className="text-xs font-medium text-[var(--text-muted)]">{q.concept}</span>
                    <span className="font-medium text-sm flex-1">{q.q}</span>
                  </div>
                  <div className="px-5 py-3 border-b border-[var(--border)]">
                    <BehaviorRow q={q} />
                  </div>
                  <div className="grid grid-cols-1 xl:grid-cols-3 divide-y xl:divide-y-0 xl:divide-x divide-[var(--border)]">
                    {AGENTS.map((a) => <AnswerBlock key={a.key} title={a.label} color={a.color} r={q.recorded[a.key]} />)}
                  </div>
                  <div className="px-5 py-3 border-t border-[var(--border)] bg-[var(--bg)] space-y-1">
                    {notes(q).map((line, i) => (
                      <p key={i} className="text-xs"><span className="text-emerald-500">+</span> {line}</p>
                    ))}
                    <p className="text-xs text-[var(--text-muted)]"><span className="font-semibold">Expected:</span> {q.expected}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
