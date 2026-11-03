"""
Backend API server for the gaming Cortex Sense demo UI.
Adapted from sfc-gh-tjia/cortex_sense Demo/web/api_server.py.

Agents (CORTEX_SENSE_DEMO.AGENTS): GAME_AGENT_FINANCE (Cortex Analyst over SV_GAME_SALES),
GAME_AGENT_ANALYST (plus catalog search and its own SQL) and GAME_AGENT_SENSE (Cortex Sense).

Run:  .venv/bin/python api_server.py   (port 5001; needs snowflake-connector-python >= 3.15)
Then: npm run build && npx next start -p 3000
Uses the CORTEX_SENSE_DEMO_CONN connection from ~/.snowflake/connections.toml;
set SNOWFLAKE_CONNECTION_NAME to use another.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import snowflake.connector
import json
import re
import sys
import time
import os
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
CORS(app, origins=["http://localhost:3000", "http://127.0.0.1:3000"])

REPO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO_DIR, "scripts"))
from rule_checks import check_steps  # noqa: E402  (same flags as the recorded answers)
import yaml  # noqa: E402

CONNECTION_NAME = os.environ.get("SNOWFLAKE_CONNECTION_NAME", "CORTEX_SENSE_DEMO_CONN")

# Live answers to bank questions are scored against their ground_truth by an LLM judge that mirrors
# the eval's answer_correctness scale (0, 0.33, 0.67, 1.00). Loaded server-side so the client can't
# supply its own golden answer.
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "claude-sonnet-4-5")
with open(os.path.join(REPO_DIR, "evaluations", "demo", "demo_questions.yaml")) as _f:
    GOLDEN = {q["id"]: q for q in yaml.safe_load(_f)["questions"]}

# Allowed files for the file viewer (relative to the repo root)
ALLOWED_FILES = {
    "strategy_memo": "stage_files/sony_portfolio_strategy_fy2027.md",
    "eu_brief": "stage_files/eu_regulatory_brief_loot_boxes.md",
    "scope": "context/scope.yaml",
    "finance_sv": "semantic_views/SV_GAME_SALES.yaml",
    "finance_agent": "agents/GAME_AGENT_FINANCE.yaml",
    "analyst_agent": "agents/GAME_AGENT_ANALYST.yaml",
    "sense_agent": "agents/GAME_AGENT_SENSE.yaml",
    "questions": "evaluations/demo/demo_questions.yaml",
    "feedback_rules": "scripts/record_feedback.py",
}

# Ordered agent registry; mirrored in app/web/lib/questions.ts and scripts/build_web_data.py.
AGENTS = {
    "finance": "CORTEX_SENSE_DEMO.AGENTS.GAME_AGENT_FINANCE",
    "analyst": "CORTEX_SENSE_DEMO.AGENTS.GAME_AGENT_ANALYST",
    "sense": "CORTEX_SENSE_DEMO.AGENTS.GAME_AGENT_SENSE",
}
AGENT_ALIAS = os.environ.get("AGENT_ALIAS", "")  # empty = the agent's default version
BASELINE_SV = "CORTEX_SENSE_DEMO.GAME_SALES.SV_GAME_SALES"
SCOPE_SCHEMAS = ("GAME_CATALOG", "GAME_SALES")
STREAMLIT_APP = "CORTEX_SENSE_DEMO.GAME_SALES.GAME_SALES_DASHBOARD"


def get_connection():
    return snowflake.connector.connect(
        connection_name=CONNECTION_NAME,
        database="CORTEX_SENSE_DEMO",
        schema="AGENTS",
    )


def _preview(obj, limit=5):
    """Small result preview: {columns, rows, total} for result sets, else a short text."""
    if obj is None:
        return None
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except ValueError:
            return {"text": obj[:400]}
    if isinstance(obj, dict):
        rs = obj.get("result_set") or obj
        if isinstance(rs, dict) and isinstance(rs.get("data"), list):
            meta = rs.get("resultSetMetaData") or {}
            cols = [c.get("name") for c in meta.get("rowType", [])]
            return {"columns": cols, "rows": rs["data"][:limit], "total": meta.get("numRows", len(rs["data"]))}
    return {"text": json.dumps(obj)[:400]}


def parse_tokens(resp):
    """Sum metadata.usage.tokens_consumed across models into {total, input, output, cacheRead}."""
    usage = ((resp.get("metadata") or {}).get("usage") or {}).get("tokens_consumed") or []
    totals = {"input": 0, "output": 0, "cacheRead": 0}
    for u in usage:
        if not isinstance(u, dict):
            continue
        inp, out = u.get("input_tokens") or {}, u.get("output_tokens") or {}
        totals["input"] += int(inp.get("total") or 0)
        totals["cacheRead"] += int(inp.get("cache_read") or 0)
        totals["output"] += int(out.get("total") or 0)
    if not (totals["input"] or totals["output"]):
        return None
    return {"total": totals["input"] + totals["output"], **totals}


def parse_agent_response(raw):
    html_artifacts = []
    text_parts = []
    steps = []
    tokens = None
    raw_str = str(raw) if raw else ""

    try:
        resp = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(resp, dict):
            tokens = parse_tokens(resp)
            for item in resp.get("content", []):
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "text" and item.get("text", "").strip():
                    text_parts.append(item["text"].strip())
                elif item.get("type") == "tool_use":
                    tu = item.get("tool_use", {})
                    inp = tu.get("input") or {}
                    sql = inp.get("sql") if isinstance(inp, dict) else None
                    steps.append({
                        "tool": tu.get("name"), "kind": tu.get("type") or "", "sql": sql,
                        "input": None if sql else (json.dumps(inp)[:600] if inp else None),
                        "status": None, "ms": 0, "result": None, "_id": tu.get("tool_use_id"),
                    })
                elif item.get("type") == "tool_result":
                    tr = item.get("tool_result", {})
                    step = next((s for s in reversed(steps) if s["_id"] == tr.get("tool_use_id")), None)
                    for tc in tr.get("content", []):
                        if isinstance(tc, dict) and tc.get("type") == "json":
                            js = tc.get("json", {})
                            result_str = js.get("result", "")
                            if isinstance(result_str, str) and "<!DOCTYPE html>" in result_str:
                                html_artifacts.append(result_str)
                            elif step is not None:
                                step["sql"] = step["sql"] or js.get("sql")
                                step["result"] = _preview(js)
                    if step is not None:
                        step["status"] = tr.get("status")
    except (json.JSONDecodeError, TypeError):
        pass

    if not html_artifacts and "<!DOCTYPE html>" in raw_str:
        match = re.search(r'"result"\s*:\s*"(<!DOCTYPE html>.*?</html>)"', raw_str, re.DOTALL)
        if match:
            html = match.group(1).replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t')
            html_artifacts.append(html)

    for s in steps:
        s.pop("_id", None)
    # server_skill chart_instructions is an internal load before charting; recorded traces omit it too
    steps = [s for s in steps if not (s["tool"] == "server_skill" and "chart_instructions" in (s["input"] or ""))]
    return {"text": "\n".join(text_parts), "htmlArtifacts": html_artifacts,
            "steps": steps, "ruleFlags": check_steps(steps), "tokens": tokens}


def call_single_agent(question, agent_fqn):
    req = json.dumps({"messages": [{"role": "user", "content": [{"type": "text", "text": question}]}]})
    # Agent names are constants; the question travels as a bound parameter, never interpolated.
    target = f"{agent_fqn}!{AGENT_ALIAS}" if AGENT_ALIAS else agent_fqn
    sql = f"SELECT SNOWFLAKE.CORTEX.DATA_AGENT_RUN('{target}', %s) AS response"
    start = time.time()
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(sql, (req,))
        row = cur.fetchone()
        elapsed = round(time.time() - start, 1)
        cur.close()
        conn.close()
        if row:
            parsed = parse_agent_response(row[0])
            parsed["elapsed"] = elapsed
            return parsed
    except Exception as e:
        elapsed = round(time.time() - start, 1)
        return {"text": f"Error: {str(e)}", "htmlArtifacts": [], "elapsed": elapsed, "steps": [], "ruleFlags": []}
    return {"text": "No response.", "htmlArtifacts": [], "elapsed": 0, "steps": [], "ruleFlags": []}


JUDGE_PROMPT = """You are grading an analytics agent's answer for correctness against an expected answer.

Question:
{question}

Expected answer (the ground truth, including any stated tolerances):
{expected}

Agent's answer:
{answer}

Rate how correct the agent's answer is compared with the expected answer:
3 = fully correct: the key facts, figures and conclusions match, within any stated tolerance
2 = mostly correct: minor omissions or small errors
1 = partly correct: some key facts right, but significant errors or omissions
0 = wrong, unrelated, or the agent declined to answer

Reply with only JSON: {{"rating": <0-3>, "explanation": "<one or two sentences>"}}"""


def judge_answer(question, expected, answer):
    """Score one answer against its golden answer; returns {score, judgeExplanation}."""
    if not (answer or "").strip():
        return {"score": 0.0, "judgeExplanation": "No answer was returned."}
    prompt = JUDGE_PROMPT.format(question=question, expected=expected.strip(), answer=answer[:12000])
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT AI_COMPLETE(%s, %s)", (JUDGE_MODEL, prompt))
        raw = cur.fetchone()[0] or ""
        cur.close()
        conn.close()
        try:  # AI_COMPLETE returns the model text as a JSON string, often wrapped in a ```json fence
            raw = json.loads(raw) if raw.startswith('"') else raw
        except ValueError:
            pass
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        verdict = json.loads(m.group(0) if m else raw)
        rating = max(0, min(3, int(verdict["rating"])))
        return {"score": round(rating / 3, 2), "judgeExplanation": str(verdict.get("explanation", "")).strip()}
    except Exception as e:
        return {"score": None, "judgeExplanation": f"Live judge failed: {str(e)[:200]}"}


@app.route("/api/agent", methods=["POST"])
def agent_endpoint():
    data = request.json or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "Missing question"}), 400
    if len(question) > 2000:
        return jsonify({"error": "Question too long"}), 400
    # Score only bank questions asked verbatim; custom questions have no golden answer.
    bank = GOLDEN.get(data.get("id") or "")
    expected = bank.get("ground_truth") if bank and bank["question"].strip() == question else None

    def run(fqn):
        r = call_single_agent(question, fqn)
        if expected and not r["text"].startswith("Error:"):
            r.update(judge_answer(question, expected, r["text"]))
        return r

    with ThreadPoolExecutor(max_workers=len(AGENTS)) as executor:
        futures = {key: executor.submit(run, fqn) for key, fqn in AGENTS.items()}
        return jsonify({key: f.result() for key, f in futures.items()})


@app.route("/api/config", methods=["GET"])
def config_endpoint():
    try:
        conn = get_connection()
        cur = conn.cursor()

        ddl = {}
        for key, fqn in AGENTS.items():
            cur.execute(f"SELECT GET_DDL('CORTEX_AGENT', '{fqn}')")
            ddl[key] = cur.fetchone()[0]

        # Baseline semantic view: logical tables and their base tables
        cur.execute(f"DESCRIBE SEMANTIC VIEW {BASELINE_SV}")
        sv_tables = {}
        for kind, name, parent, prop, val in [r[:5] for r in cur.fetchall()]:
            if kind == "TABLE":
                t = sv_tables.setdefault(name, {"name": name, "base": "", "comment": ""})
                if prop == "BASE_TABLE_NAME":
                    t["base"] = val
                elif prop == "BASE_TABLE_SCHEMA_NAME":
                    t["schema"] = val
                elif prop == "COMMENT":
                    t["comment"] = val

        placeholders = ",".join(["%s"] * len(SCOPE_SCHEMAS))
        cur.execute(f"""
            SELECT TABLE_SCHEMA, TABLE_NAME, ROW_COUNT, TABLE_TYPE
            FROM CORTEX_SENSE_DEMO.INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA IN ({placeholders})
            AND TABLE_TYPE IN ('BASE TABLE', 'VIEW')
            ORDER BY TABLE_SCHEMA, TABLE_NAME
        """, SCOPE_SCHEMAS)
        all_tables = [{"schema": r[0], "name": r[1], "rows": r[2], "type": r[3]} for r in cur.fetchall()]

        cur.execute("SELECT CURRENT_ORGANIZATION_NAME(), CURRENT_ACCOUNT_NAME()")
        org, account = cur.fetchone()
        cur.close()
        conn.close()

        sv_base_names = {(t.get("schema"), t["base"]) for t in sv_tables.values() if t["base"]}
        long_tail = [t for t in all_tables if (t["schema"], t["name"]) not in sv_base_names]

        return jsonify({
            "ddl": ddl,
            "svTables": list(sv_tables.values()),
            "allTables": all_tables,
            "longTailTables": long_tail,
            "streamlitUrl": f"https://app.snowflake.com/{org.lower()}/{account.lower()}/#/streamlit-apps/{STREAMLIT_APP}",
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/files", methods=["GET"])
def list_files():
    result = {}
    for key, rel_path in ALLOWED_FILES.items():
        full = os.path.join(REPO_DIR, rel_path)
        result[key] = {
            "name": os.path.basename(rel_path),
            "path": rel_path,
            "exists": os.path.isfile(full),
            "size": os.path.getsize(full) if os.path.isfile(full) else 0,
        }
    return jsonify(result)


@app.route("/api/file/<key>", methods=["GET"])
def get_file(key):
    if key not in ALLOWED_FILES:
        return jsonify({"error": f"Unknown file key: {key}"}), 404
    full = os.path.join(REPO_DIR, ALLOWED_FILES[key])
    if not os.path.isfile(full):
        return jsonify({"error": f"File not found: {ALLOWED_FILES[key]}"}), 404
    with open(full, "r") as f:
        content = f.read()
    return jsonify({"key": key, "name": os.path.basename(ALLOWED_FILES[key]), "content": content})


if __name__ == "__main__":
    print(f"Starting gaming Cortex Sense demo API on http://127.0.0.1:5001 (connection {CONNECTION_NAME})")
    app.run(host="127.0.0.1", port=5001, debug=False)
