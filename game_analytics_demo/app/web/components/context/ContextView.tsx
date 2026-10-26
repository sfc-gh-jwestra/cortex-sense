"use client";
import { useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AGENTS, API_URL, DEMO_DATA } from "@/lib/questions";
import { ConfigData } from "@/lib/types";

const CODE_EXT = [".py", ".yaml", ".yml", ".sql"];

const SOURCES: { key: string; title: string; detail: string }[] = [
  { key: "strategy_memo", title: "Stage file: FY2027 portfolio strategy memo", detail: "sony_portfolio_strategy_fy2027.md: Core, Growth and Harvest franchise tiers, strategic priorities" },
  { key: "eu_brief", title: "Stage file: EU loot box regulatory brief", detail: "eu_regulatory_brief_loot_boxes.md: EU risk rubric (HIGH, ELEVATED, WATCH, LOW) and mitigations" },
  { key: "scope", title: "Cortex Sense scope", detail: "scope.yaml: catalog objects and query history for GAME_CATALOG and GAME_SALES, Streamlit app, SV_GAME_SALES, knowledge base stage" },
  { key: "finance_sv", title: "Semantic view: SV_GAME_SALES", detail: "Cortex Analyst tool for the finance and analyst agents (digital, hardware and subscription revenue); a context document for Cortex Sense" },
  { key: "feedback_rules", title: `Feedback rules (${DEMO_DATA.rules.length})`, detail: "record_feedback.py: business definitions, procedures and retrieval steers" },
  { key: "finance_agent", title: "Agent spec: GAME_AGENT_FINANCE", detail: "Without Cortex Sense: Cortex Analyst tool over SV_GAME_SALES only" },
  { key: "analyst_agent", title: "Agent spec: GAME_AGENT_ANALYST", detail: "Capable analyst without Cortex Sense: Cortex Analyst plus catalog search and its own SQL on any table" },
  { key: "sense_agent", title: "Agent spec: GAME_AGENT_SENSE", detail: "With Cortex Sense: EnableCortexSense on GAME_ANALYTICS_CTX_V2" },
  { key: "questions", title: "Demo question bank", detail: "demo_questions.yaml: 2 ties and 8 Sense-only questions" },
];

function FileViewer({ fileKey, onClose }: { fileKey: string; onClose: () => void }) {
  const [content, setContent] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_URL}/api/file/${fileKey}`)
      .then((r) => r.json())
      .then((data) => {
        setContent(data.content || data.error || "Empty");
        setName(data.name || fileKey);
        setLoading(false);
      })
      .catch((e) => {
        setContent(`Error loading file: ${e.message}. Is api_server.py running?`);
        setLoading(false);
      });
  }, [fileKey]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-xl w-[90vw] max-w-4xl max-h-[85vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-3 border-b border-[var(--border)]">
          <span className="font-semibold text-sm font-mono">{name}</span>
          <button onClick={onClose} className="text-[var(--text-muted)] hover:text-[var(--text)] text-lg px-2">✕</button>
        </div>
        <div className="flex-1 overflow-auto p-5">
          {loading ? (
            <div className="text-[var(--text-muted)]">Loading...</div>
          ) : CODE_EXT.some((e) => name.endsWith(e)) ? (
            <pre className="text-xs leading-relaxed whitespace-pre-wrap">{content}</pre>
          ) : (
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{content || ""}</ReactMarkdown>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ContextView() {
  const [viewingFile, setViewingFile] = useState<string | null>(null);
  const [config, setConfig] = useState<ConfigData | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/api/config`)
      .then((r) => r.json())
      .then((d) => (d.error ? setConfigError(d.error) : setConfig(d)))
      .catch((e) => setConfigError(`${e.message}. Is api_server.py running?`));
  }, []);

  return (
    <div className="space-y-6">
      {viewingFile && <FileViewer fileKey={viewingFile} onClose={() => setViewingFile(null)} />}

      <section>
        <iframe src="/architecture.html" className="w-full border border-[var(--border)] rounded-xl" style={{ height: "620px" }} sandbox="" />
      </section>

      <section>
        <h2 className="text-lg font-bold mb-3">Data each agent can reach</h2>
        {configError && <p className="text-xs text-red-600 mb-2">Could not load live config: {configError}</p>}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-card)] p-4">
            <div className="font-semibold text-sm mb-1" style={{ color: "var(--baseline)" }}>
              Without Cortex Sense: {config ? config.svTables.length : "..."} tables
            </div>
            <div className="text-xs text-[var(--text-muted)] mb-2">Logical tables in SV_GAME_SALES, through Cortex Analyst only</div>
            <ul className="text-xs font-mono space-y-0.5">
              {config?.svTables.map((t) => <li key={t.name}>{t.schema ? `${t.schema}.${t.base}` : t.name}</li>)}
            </ul>
          </div>
          <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-card)] p-4">
            <div className="font-semibold text-sm mb-1" style={{ color: "var(--analyst)" }}>
              Capable analyst: {config ? config.allTables.length : "..."} tables and views
            </div>
            <div className="text-xs text-[var(--text-muted)] mb-2">
              SV_GAME_SALES through Cortex Analyst, plus catalog search, INFORMATION_SCHEMA and its own SQL on every
              readable table. No business rules, query history or knowledge base documents.
            </div>
            <div className="text-xs font-mono max-h-48 overflow-auto columns-2">
              {config?.allTables.map((t) => <div key={`${t.schema}.${t.name}`}>{t.schema}.{t.name}</div>)}
            </div>
          </div>
          <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-card)] p-4">
            <div className="font-semibold text-sm mb-1" style={{ color: "var(--sense)" }}>
              With Cortex Sense: {config ? config.allTables.length : "..."} tables and views,
              {" "}{config ? config.longTailTables.length : "..."} outside the semantic view
            </div>
            <div className="text-xs text-[var(--text-muted)] mb-2">
              The same tables, plus {DEMO_DATA.rules.length} feedback rules, query patterns, the semantic view and the
              knowledge base documents
            </div>
            <div className="text-xs font-mono max-h-48 overflow-auto columns-2">
              {config?.longTailTables.map((t) => <div key={`${t.schema}.${t.name}`}>{t.schema}.{t.name}</div>)}
            </div>
          </div>
        </div>
      </section>

      {config?.ddl && (
        <section>
          <h2 className="text-lg font-bold mb-3">Deployed agent definitions</h2>
          <div className="space-y-2">
            {AGENTS.map((a) => (
              <details key={a.key} className="rounded-lg border border-[var(--border)] bg-[var(--bg-card)] p-3">
                <summary className="cursor-pointer text-sm font-semibold" style={{ color: a.color }}>{a.label}: {a.sublabel}</summary>
                <pre className="text-[11px] leading-snug whitespace-pre-wrap font-mono mt-2 max-h-96 overflow-auto">{config.ddl[a.key]}</pre>
              </details>
            ))}
          </div>
        </section>
      )}

      <section>
        <h2 className="text-lg font-bold mb-3">Indexed sources (click to view)</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {SOURCES.map((s) => (
            <button key={s.key} onClick={() => setViewingFile(s.key)}
                    className="rounded-lg border border-[var(--border)] bg-[var(--bg-card)] p-4 text-left hover:border-[var(--sense)] transition-colors">
              <div className="font-semibold text-sm mb-1">{s.title}</div>
              <div className="text-xs text-[var(--text-muted)]">{s.detail}</div>
            </button>
          ))}
        </div>
        {config?.streamlitUrl && (
          <div className="mt-3">
            <a href={config.streamlitUrl} target="_blank" rel="noopener noreferrer"
               className="text-xs font-medium hover:underline inline-flex items-center gap-1" style={{ color: "var(--sense)" }}>
              Open the GAME_SALES_DASHBOARD Streamlit app in Snowsight ↗
            </a>
          </div>
        )}
      </section>
    </div>
  );
}
