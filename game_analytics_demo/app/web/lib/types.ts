export type AgentKey = "finance" | "analyst" | "sense";

export interface ResultPreview {
  columns?: string[];
  rows?: unknown[][];
  total?: number;
  text?: string;
}

export interface ToolStep {
  tool: string;
  kind: string;
  sql: string | null;
  input: string | null;
  status: string | null;
  ms: number;
  result: ResultPreview | null;
}

export interface RuleFlag {
  rule: string;
  status: "pass" | "fail";
  reason: string;
}

export interface AgentResponse {
  text: string;
  htmlArtifacts: string[];
  elapsed: number;
  score?: number | null;
  steps?: ToolStep[];
  ruleFlags?: RuleFlag[];
  judgeExplanation?: string | null;
}

export interface RecordedAnswer {
  text: string;
  score: number | null;
  elapsed: number;
  run: string | null;
  steps: ToolStep[];
  ruleFlags: RuleFlag[];
  judgeExplanation: string | null;
  tablesUsed: string[];
}

export interface ExpectedRows {
  columns: string[];
  rows: unknown[][];
  total: number;
  sql: string;
}

export type Verdict = "correct" | "partial" | "wrong" | null;

export interface EvalQuestion {
  id: string;
  tier: string;
  concept: string;
  q: string;
  expected: string;
  expectedRows?: ExpectedRows | null;
  source: string;
  tables: string[];
  knowledgeDoc?: string | null;
  rules: string[];
  verdicts: Record<AgentKey, Verdict>;
  recorded: Record<AgentKey, RecordedAnswer>;
}

export interface FeedbackRule {
  label: string;
  type: string;
  rule: string;
  concepts: string[];
}

export interface AgentSummary {
  tie: number | null;
  sense_only: number | null;
  correct: number;
  recorded: boolean;
}

export interface AgentInfo {
  key: AgentKey;
  agent: string;
  run: string;
  label: string;
  sublabel: string;
}

export interface DemoData {
  agents: AgentInfo[];
  summary: { questions: number } & Record<AgentKey, AgentSummary>;
  questions: EvalQuestion[];
  rules: FeedbackRule[];
}

export interface TableInfo {
  schema: string;
  name: string;
  rows: number | null;
  type: string;
}

export interface ConfigData {
  ddl: Record<AgentKey, string>;
  svTables: { name: string; base: string; schema?: string; comment: string }[];
  allTables: TableInfo[];
  longTailTables: TableInfo[];
  streamlitUrl: string;
}
