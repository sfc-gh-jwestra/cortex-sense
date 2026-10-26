"use client";
import { useState } from "react";
import { RuleFlag, ToolStep, ResultPreview } from "@/lib/types";

const TOOL_LABEL: Record<string, string> = {
  system_execute_sql: "SQL",
  finance_analyst: "Cortex Analyst",
  cortex_sense: "Cortex Sense",
  data_to_chart: "Chart",
  table_details: "Table details",
  snowscope_search: "Catalog search",
};

function fmt(v: unknown): string {
  if (v === null || v === undefined) return "";
  const n = Number(v);
  if (typeof v !== "boolean" && v !== "" && !Number.isNaN(n)) {
    return Math.abs(n) >= 1000 ? n.toLocaleString(undefined, { maximumFractionDigits: 0 }) : String(Math.round(n * 1000) / 1000);
  }
  return String(v);
}

export function MiniTable({ columns, rows, total }: { columns?: string[]; rows?: unknown[][]; total?: number }) {
  if (!rows || rows.length === 0) return null;
  return (
    <div className="overflow-x-auto">
      <table className="text-[11px] border-collapse">
        {columns && columns.length > 0 && (
          <thead>
            <tr>{columns.map((c) => <th key={c} className="text-left font-semibold px-2 py-1 border-b border-[var(--border)]">{c}</th>)}</tr>
          </thead>
        )}
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>{r.map((v, j) => <td key={j} className="px-2 py-0.5 border-b border-[var(--border)] font-mono">{fmt(v)}</td>)}</tr>
          ))}
        </tbody>
      </table>
      {total !== undefined && total > rows.length && (
        <div className="text-[10px] text-[var(--text-muted)] mt-1">{rows.length} of {total} rows shown</div>
      )}
    </div>
  );
}

function Result({ result }: { result: ResultPreview | null }) {
  if (!result) return null;
  if (result.rows) return <MiniTable columns={result.columns} rows={result.rows} total={result.total} />;
  if (result.text) return <pre className="text-[11px] whitespace-pre-wrap text-[var(--text-muted)]">{result.text}</pre>;
  return null;
}

export function RuleFlags({ flags }: { flags?: RuleFlag[] }) {
  if (!flags || flags.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {flags.map((f) => (
        <span key={f.rule} title={f.reason}
              className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${f.status === "pass"
                ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                : "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300"}`}>
          {f.status === "pass" ? "Follows" : "Breaks"} rule: {f.rule}
        </span>
      ))}
    </div>
  );
}

function Step({ step, n }: { step: ToolStep; n: number }) {
  const [open, setOpen] = useState(false);
  const label = TOOL_LABEL[step.tool] || step.tool;
  const summary = (step.sql || step.input || "").replace(/\s+/g, " ").slice(0, 110);
  const failed = step.status && !/success|ok|200/i.test(step.status);
  return (
    <li className="border-b border-[var(--border)] last:border-b-0">
      <button onClick={() => setOpen(!open)} className="w-full text-left flex items-start gap-2 py-1.5">
        <span className="text-[10px] font-bold w-5 shrink-0 text-[var(--text-muted)]">{n}.</span>
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--border)] shrink-0 font-semibold">{label}</span>
        <span className="text-[11px] font-mono text-[var(--text-muted)] flex-1 truncate">{summary}</span>
        {failed && <span className="text-[10px] text-red-600 shrink-0">{step.status}</span>}
        {step.ms > 0 && <span className="text-[10px] text-[var(--text-muted)] shrink-0">{(step.ms / 1000).toFixed(1)}s</span>}
        <span className="text-[10px] text-[var(--text-muted)] shrink-0">{open ? "−" : "+"}</span>
      </button>
      {open && (
        <div className="pl-7 pb-2 space-y-2">
          {step.sql && <pre className="text-[11px] leading-snug whitespace-pre-wrap bg-[var(--bg)] border border-[var(--border)] rounded p-2 font-mono">{step.sql}</pre>}
          {!step.sql && step.input && <pre className="text-[11px] whitespace-pre-wrap text-[var(--text-muted)]">{step.input}</pre>}
          <Result result={step.result} />
        </div>
      )}
    </li>
  );
}

export default function AgentTrace({ steps, flags, judge }: { steps?: ToolStep[]; flags?: RuleFlag[]; judge?: string | null }) {
  const [open, setOpen] = useState(false);
  if ((!steps || steps.length === 0) && !judge) return null;
  const tools = Array.from(new Set((steps || []).map((s) => TOOL_LABEL[s.tool] || s.tool)));
  return (
    <div className="mt-4 border-t border-[var(--border)] pt-3 space-y-2">
      <RuleFlags flags={flags} />
      {steps && steps.length > 0 && (
        <div>
          <button onClick={() => setOpen(!open)} className="text-xs font-semibold flex items-center gap-2">
            <span>{open ? "▾" : "▸"} How it answered: {steps.length} tool {steps.length === 1 ? "step" : "steps"}</span>
            <span className="font-normal text-[var(--text-muted)]">({tools.join(", ")})</span>
          </button>
          {open && <ol className="mt-1">{steps.map((s, i) => <Step key={i} step={s} n={i + 1} />)}</ol>}
        </div>
      )}
      {judge && (
        <details className="text-xs">
          <summary className="cursor-pointer font-semibold">Why this score (judge)</summary>
          <p className="mt-1 text-[var(--text-muted)] whitespace-pre-wrap">{judge}</p>
        </details>
      )}
    </div>
  );
}
