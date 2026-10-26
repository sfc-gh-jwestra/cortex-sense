"""
Generate app/web/lib/demo_data.json for the demo UI.

Inputs:
  - evaluations/demo/demo_questions.yaml   questions, tier, concept, knowledge_doc, tables, ground truth, gt_sql
  - eval runs, one per agent (AGENTS below), read with SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA:
      answer text, answer_correctness score, duration, judge explanation
  - each record's trace (SNOWFLAKE.LOCAL.GET_AI_RECORD_TRACE): ordered tool steps with SQL and result preview
  - gt_sql, run once per question: the expected rows
  - scripts/rule_checks.py: pass/fail flags for each answer's SQL against the feedback rules
  - scripts/record_feedback.py RECORDS: the feedback rules list

Also refreshes CORTEX_SENSE_DEMO.EVALS.DEMO_AGENT_RESULTS (one row per agent and question) from
whichever runs exist. A run that hasn't happened yet (e.g. the Sense run before the context build
finishes) is skipped and its answers show as not recorded.

Reads need SNOWFLAKE.CORTEX_USER, so every statement runs under ACCOUNTADMIN.
Re-run after re-running the demo evals:
  python3 scripts/build_web_data.py --runs finance=finance_run2,analyst=analyst_run2,sense=sense_run2
Without --runs, the run names come from .install_state (written by install.sh), then the defaults below.
"""
import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from rule_checks import check_steps  # noqa: E402

BANK = ROOT / "evaluations" / "demo" / "demo_questions.yaml"
OUT = ROOT / "app" / "web" / "lib" / "demo_data.json"
SOURCE_TABLE = "CORTEX_SENSE_DEMO.EVALS.EVAL_SOURCE_DEMO_FINANCE_VS_SENSE"
RESULTS_TABLE = "CORTEX_SENSE_DEMO.EVALS.DEMO_AGENT_RESULTS"
CONNECTION = os.environ.get("SNOWFLAKE_CONNECTION_NAME", "CORTEX_SENSE_DEMO_CONN")
STATE = ROOT / ".install_state"
PASS = 0.67
PREVIEW_ROWS = 5

# Ordered agent registry; mirrored in app/web/lib/questions.ts and app/web/api_server.py.
# "run" is the default eval run name; --runs or .install_state override it.
AGENTS = [
    {"key": "finance", "agent": "GAME_AGENT_FINANCE", "run": "finance_v4",
     "label": "Without Cortex Sense", "sublabel": "GAME_AGENT_FINANCE: Cortex Analyst over SV_GAME_SALES"},
    {"key": "analyst", "agent": "GAME_AGENT_ANALYST", "run": "analyst_v4",
     "label": "Capable analyst", "sublabel": "GAME_AGENT_ANALYST: Cortex Analyst + catalog search + own SQL"},
    {"key": "sense", "agent": "GAME_AGENT_SENSE", "run": "sense_v5",
     "label": "With Cortex Sense", "sublabel": "GAME_AGENT_SENSE: GAME_ANALYTICS_CTX_V2"},
]
AGENT_DB, AGENT_SCHEMA = "CORTEX_SENSE_DEMO", "AGENTS"


def snow(sql, check=True):
    """Run one statement under ACCOUNTADMIN; return result rows (list of dicts) or None on error."""
    r = subprocess.run(
        ["snow", "sql", "-c", CONNECTION, "--format", "json", "--enable-templating", "NONE",
         "-q", f"USE ROLE ACCOUNTADMIN; {sql}"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        if check:
            raise RuntimeError((r.stderr or r.stdout)[:600])
        return None
    data = json.loads(r.stdout)
    return data[-1] if data and isinstance(data[0], list) else data


def q(s):
    return "'" + str(s).replace("'", "''") + "'"


# ----------------------------------------------------------------------------- eval results
def load_results(a):
    sql = f"""SELECT RECORD_ID, INPUT, EVAL_AGG_SCORE AS SCORE, DURATION_MS, OUTPUT,
                     METRIC_CALLS[0]:explanation::STRING AS JUDGE_EXPLANATION
              FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA({q(AGENT_DB)}, {q(AGENT_SCHEMA)},
                   {q(a['agent'])}, 'CORTEX AGENT', {q(a['run'])}))
              WHERE METRIC_NAME = 'answer_correctness'"""
    rows = snow(sql, check=False)
    if rows is None:
        print(f"  {a['key']}: run {a['run']} not found, skipped")
        return {}
    print(f"  {a['key']}: {len(rows)} records from {a['run']}")
    return {r["INPUT"]: r for r in rows}


def refresh_results_table(present):
    parts = [
        f"""SELECT {q(a['key'])} AS AGENT_KEY, {q(a['agent'])} AS AGENT, {q(a['run'])} AS RUN, s.DEMO_ID,
                   e.RECORD_ID, e.EVAL_AGG_SCORE AS SCORE, e.DURATION_MS, e.OUTPUT,
                   e.METRIC_CALLS[0]:explanation::STRING AS JUDGE_EXPLANATION
            FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA({q(AGENT_DB)}, {q(AGENT_SCHEMA)},
                 {q(a['agent'])}, 'CORTEX AGENT', {q(a['run'])})) e
            JOIN {SOURCE_TABLE} s ON s.INPUT_QUERY = e.INPUT
            WHERE e.METRIC_NAME = 'answer_correctness'"""
        for a in present
    ]
    if parts:
        snow(f"CREATE OR REPLACE TABLE {RESULTS_TABLE} AS " + " UNION ALL ".join(parts))
        print(f"  refreshed {RESULTS_TABLE} ({', '.join(a['key'] for a in present)})")


# ----------------------------------------------------------------------------- traces
TOOL_SPAN = re.compile(r"^(\w+?)Tool(?:Impl)?[_-](.+)$")
TABLE_REF = re.compile(r"\bCORTEX_SENSE_DEMO\.(GAME_CATALOG|GAME_SALES|EVALS|CONTEXTS)\.(\w+)", re.IGNORECASE)


def _attr(attrs, *suffixes):
    for k, v in attrs.items():
        if any(k.endswith(s) for s in suffixes) and v not in (None, ""):
            return v
    return None


def _preview(raw):
    """Turn a tool result into {columns, rows, total} (first PREVIEW_ROWS rows) or a short text."""
    if raw is None:
        return None
    try:
        obj = json.loads(raw) if isinstance(raw, str) else raw
    except ValueError:
        return {"text": str(raw)[:400]}
    if isinstance(obj, dict) and isinstance(obj.get("data"), list):
        meta = obj.get("resultSetMetaData") or {}
        cols = [c.get("name") for c in meta.get("rowType", [])] or obj.get("columns") or []
        data = obj["data"]
        return {"columns": cols, "rows": data[:PREVIEW_ROWS], "total": meta.get("numRows", len(data))}
    return {"text": json.dumps(obj)[:400]}


def load_steps(a, record_id):
    rows = snow(
        f"""SELECT SPAN_TYPE, SPAN_NAME, STATUS, DURATION_MS, TOOL, ATTRIBUTES
            FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_RECORD_TRACE({q(AGENT_DB)}, {q(AGENT_SCHEMA)},
                 {q(a['agent'])}, 'CORTEX AGENT', {q(record_id)}))
            ORDER BY START_TIMESTAMP""",
        check=False,
    ) or []
    steps = []
    for r in rows:
        name, stype = r["SPAN_NAME"] or "", r["SPAN_TYPE"] or ""
        attrs = json.loads(r["ATTRIBUTES"] or "{}")
        m = TOOL_SPAN.match(name)
        if stype == "chart_generation":
            steps.append({"tool": "data_to_chart", "kind": "Chart", "input": None, "sql": None,
                          "status": r["STATUS"], "ms": int(r["DURATION_MS"] or 0), "result": None})
            continue
        if not m or stype == "sql_execution":
            continue  # planning/response/eval spans; sql_execution duplicates its parent tool span
        kind, tool = m.group(1), m.group(2)
        if tool == "chart_instructions":
            continue  # internal skill load before charting
        sql = _attr(attrs, ".sql_execution.final_sql", ".sql_execution.query")
        steps.append({
            "tool": tool,
            "kind": kind,
            "input": _attr(attrs, ".user_question", ".query_text", ".search_query", ".input") if not sql else None,
            "sql": sql,
            "status": _attr(attrs, ".status.description", ".status") or r["STATUS"],
            "ms": int(r["DURATION_MS"] or 0),
            "result": _preview(_attr(attrs, ".sql_execution.result", ".result", ".response")),
        })
    return steps


def tables_used(steps):
    seen = []
    for s in steps:
        for schema, table in TABLE_REF.findall(s.get("sql") or ""):
            t = f"{schema.upper()}.{table.upper()}"
            if t not in seen:
                seen.append(t)
    return seen


# ----------------------------------------------------------------------------- expected rows
def expected_rows(question):
    sql = question.get("gt_sql")
    if not sql:
        return None
    rows = snow(sql, check=False)
    if rows is None:
        print(f"  gt_sql failed for {question['id']}")
        return None
    cols = list(rows[0].keys()) if rows else []
    total = len(rows)
    if total > 16:  # long lists (e.g. T02 franchises): top 10 plus any Unmapped row
        keep = rows[:10] + [r for r in rows[10:] if "Unmapped" in [str(v) for v in r.values()]]
        rows = keep
    return {"columns": cols, "rows": [[r[c] for c in cols] for r in rows], "total": total, "sql": sql}


# ----------------------------------------------------------------------------- existing helpers
def load_rules():
    spec = importlib.util.spec_from_file_location("record_feedback", ROOT / "scripts" / "record_feedback.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rules = []
    for r in mod.RECORDS:
        label = r["raw_feedback"].split(":", 1)[0].strip() if ":" in r["raw_feedback"][:60] else r["concepts"][0]
        label = " ".join(w if w in ("EU", "AAA", "M&A", "YoY") else w.capitalize() for w in label.split())
        rules.append({"label": label, "type": r["type"], "rule": r["feedback_rule"], "concepts": r.get("concepts", [])})
    return rules


TABLE_BLOCK = re.compile(r"\[table\]\s*```json\s*(\{.*?\})\s*```\s*\[/table\]", re.DOTALL)


def _cell(v):
    try:
        f = float(v)
        return f"{f:,.0f}" if abs(f) >= 1000 else f"{f:.4g}"
    except (TypeError, ValueError):
        return str(v).replace("|", "\\|")


def tables_to_markdown(text):
    """Eval OUTPUT embeds result sets as [table]```json {columns, data}```[/table]; render them as markdown tables."""
    def repl(m):
        try:
            t = json.loads(m.group(1))
            cols, rows = t["columns"], t["data"]
        except (ValueError, KeyError):
            return m.group(0)
        lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
        lines += ["| " + " | ".join(_cell(v) for v in r) + " |" for r in rows[:25]]
        if len(rows) > 25:
            lines.append(f"\n_{len(rows) - 25} more rows not shown_")
        return "\n" + "\n".join(lines) + "\n"
    return TABLE_BLOCK.sub(repl, text or "")


def matching_rules(q_, rules):
    hay = (q_["question"] + " " + q_.get("concept", "")).lower()
    return [r["label"] for r in rules if any(c.lower() in hay for c in r["concepts"])]


def verdict(score):
    if score is None:
        return None
    return "correct" if score >= PASS else ("partial" if score > 0 else "wrong")


# ----------------------------------------------------------------------------- main
def apply_run_names():
    """Override AGENTS run names from --runs key=name,... or from .install_state RUN_<KEY>= lines."""
    runs = {}
    if STATE.exists():
        for line in STATE.read_text().splitlines():
            k, _, v = line.partition("=")
            if k.startswith("RUN_") and v:
                runs[k[4:].lower()] = v.strip()
    if "--runs" in sys.argv:
        for pair in sys.argv[sys.argv.index("--runs") + 1].split(","):
            k, _, v = pair.partition("=")
            runs[k.strip()] = v.strip()
    for a in AGENTS:
        a["run"] = runs.get(a["key"], a["run"])


def main():
    apply_run_names()
    questions = yaml.safe_load(BANK.read_text())["questions"]
    rules = load_rules()

    print("Eval runs:")
    results = {a["key"]: load_results(a) for a in AGENTS}
    present = [a for a in AGENTS if results[a["key"]]]
    refresh_results_table(present)

    items = []
    for qn in questions:
        print(f"{qn['id']}: expected rows + traces")
        recorded, verdicts = {}, {}
        for a in AGENTS:
            r = results[a["key"]].get(qn["question"])
            if not r:
                recorded[a["key"]] = {"text": "", "score": None, "elapsed": 0, "run": None, "steps": [],
                                      "ruleFlags": [], "judgeExplanation": None, "tablesUsed": []}
                verdicts[a["key"]] = None
                continue
            steps = load_steps(a, r["RECORD_ID"])
            score = float(r["SCORE"]) if r["SCORE"] is not None else None
            recorded[a["key"]] = {
                "text": tables_to_markdown(r["OUTPUT"]),
                "score": score,
                "elapsed": round((r["DURATION_MS"] or 0) / 1000, 1),
                "run": a["run"],
                "steps": steps,
                "ruleFlags": check_steps(steps),
                "judgeExplanation": r["JUDGE_EXPLANATION"],
                "tablesUsed": tables_used(steps),
            }
            verdicts[a["key"]] = verdict(score)
        tables = qn.get("tables", [])
        if qn["bucket"] == "tie":
            source = "Semantic view: SV_GAME_SALES"
        elif qn.get("knowledge_doc"):
            source = f"Cortex Sense -> knowledge base: {qn['knowledge_doc']} + {', '.join(tables)}"
        else:
            source = f"Cortex Sense -> {', '.join(tables)}"
        items.append({
            "id": qn["id"],
            "tier": qn["bucket"],
            "concept": qn.get("concept", ""),
            "q": qn["question"],
            "expected": (qn.get("ground_truth") or "").strip(),
            "expectedRows": expected_rows(qn),
            "source": source,
            "tables": tables,
            "knowledgeDoc": qn.get("knowledge_doc"),
            "rules": matching_rules(qn, rules),
            "verdicts": verdicts,
            "recorded": recorded,
        })

    def avg(tier, key):
        xs = [i["recorded"][key]["score"] for i in items if i["tier"] == tier and i["recorded"][key]["score"] is not None]
        return round(sum(xs) / len(xs), 2) if xs else None

    summary = {"questions": len(items)}
    for a in AGENTS:
        k = a["key"]
        summary[k] = {"tie": avg("tie", k), "sense_only": avg("sense_only", k),
                      "correct": sum(1 for i in items if (i["recorded"][k]["score"] or 0) >= PASS),
                      "recorded": bool(results[k])}
    agents = [{"key": a["key"], "agent": f"{AGENT_DB}.{AGENT_SCHEMA}.{a['agent']}", "run": a["run"],
               "label": a["label"], "sublabel": a["sublabel"]} for a in AGENTS]
    OUT.write_text(json.dumps({"agents": agents, "summary": summary, "questions": items, "rules": rules},
                              indent=2, default=str))
    print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB): {len(items)} questions, {len(rules)} rules")
    print("Summary:", json.dumps(summary))


if __name__ == "__main__":
    main()
