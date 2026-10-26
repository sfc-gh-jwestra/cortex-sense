"use client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AGENTS, DEMO_DATA, EVAL_QUESTIONS, PASS, TIER_COLORS, TIER_LABELS } from "@/lib/questions";
import { EvalQuestion, RecordedAnswer } from "@/lib/types";
import AgentTrace, { RuleFlags } from "@/components/common/AgentTrace";

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

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        {AGENTS.map((a) => (
          <div key={a.key} className="rounded-lg border border-[var(--border)] p-3 text-center">
            <div className="text-2xl font-bold" style={{ color: a.color }}>
              {s[a.key].recorded ? `${s[a.key].correct}/${s.questions}` : "not run"}
            </div>
            <div className="text-xs text-[var(--text-muted)]">{a.label}</div>
            <div className="text-[10px] text-[var(--text-muted)]">tie {pct(s[a.key].tie)} | sense-only {pct(s[a.key].sense_only)}</div>
          </div>
        ))}
        <div className="rounded-lg border border-[var(--border)] p-3 text-center">
          <div className="text-2xl font-bold" style={{ color: "var(--sense)" }}>
            {EVAL_QUESTIONS.filter((q) => q.tier === "sense_only").length}
          </div>
          <div className="text-xs text-[var(--text-muted)]">Concepts outside the semantic view</div>
        </div>
      </div>

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
