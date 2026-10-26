#!/usr/bin/env bash
# Install the Cortex Sense gaming demo end to end: database, data, semantic view, dashboard,
# query history, knowledge base, Cortex Sense context, feedback rules, agents, evals, demo UI.
#
# Each step is a numbered file in install/ (or a command for 00, 13, 14) and runs in order:
#   00 generate the SQL files from their sources   07 create the context and queue its build
#   01 database, schemas, stages, file format       08 record the feedback rules
#   02 load data (tables, COPY INTO, views, DTs)   09 deploy the three agents
#   03 semantic view SV_GAME_SALES                  10 eval dataset and configs
#   04 Streamlit dashboard                          11 wait for the context build (often hours)
#   05 prime query history                          12 run the three evals and wait for them
#   06 upload the knowledge base                    13 build the UI data   14 start the UI
#
# Usage: ./install.sh [--from NN] [--only NN] [--no-wait] [--list]
#   --from NN   resume at step NN        --no-wait  stop at step 11 if the build isn't done
#   --only NN   run just step NN         --list     show steps and what has completed
# Connection: SNOWFLAKE_CONNECTION_NAME (default CORTEX_SENSE_DEMO_CONN in ~/.snowflake/connections.toml).
# Progress and eval run names are kept in .install_state; delete it to start over.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
CONN="${SNOWFLAKE_CONNECTION_NAME:-CORTEX_SENSE_DEMO_CONN}"
STATE="$ROOT/.install_state"
POLL_SECONDS=300

STEPS=(00 01 02 03 04 05 06 07 08 09 10 11 12 13 14)
title() {  # bash 3.2 (macOS default) has no associative arrays
  case "$1" in
    00) echo "Generate install SQL from sources" ;;  01) echo "Database, schemas, stages" ;;
    02) echo "Load data" ;;                          03) echo "Semantic view SV_GAME_SALES" ;;
    04) echo "Streamlit dashboard" ;;                05) echo "Prime query history" ;;
    06) echo "Upload knowledge base" ;;              07) echo "Create Cortex Sense context" ;;
    08) echo "Record feedback rules" ;;              09) echo "Deploy agents" ;;
    10) echo "Eval dataset and configs" ;;           11) echo "Wait for context build" ;;
    12) echo "Run evals" ;;                          13) echo "Build UI data" ;;
    14) echo "Start demo UI" ;;
  esac
}

FROM=00; ONLY=""; WAIT=1
while (($#)); do
  case "$1" in
    --from) FROM="$2"; shift 2 ;;
    --only) ONLY="$2"; shift 2 ;;
    --no-wait) WAIT=0; shift ;;
    --list)
      for s in "${STEPS[@]}"; do
        mark=" "; grep -qx "DONE_$s=1" "$STATE" 2>/dev/null && mark="x"
        printf "[%s] %s  %s\n" "$mark" "$s" "$(title "$s")"
      done
      grep '^RUN_' "$STATE" 2>/dev/null || true
      exit 0 ;;
    *) echo "Unknown option: $1 (see the header of install.sh)" >&2; exit 1 ;;
  esac
done

state_set() {  # state_set KEY VALUE
  touch "$STATE"
  grep -v "^$1=" "$STATE" > "$STATE.tmp" || true
  echo "$1=$2" >> "$STATE.tmp"
  mv "$STATE.tmp" "$STATE"
}
state_get() { grep "^$1=" "$STATE" 2>/dev/null | tail -1 | cut -d= -f2-; }

sql_file() {  # sql_file install/NN-name.sql
  snow sql -c "$CONN" --enable-templating NONE -f "$1"
}

# Reads the last result set of a `snow sql --format json` call and prints one column.
json_col() {
  python3 -c '
import json, sys
data = json.load(sys.stdin)
rows = data[-1] if data and isinstance(data[0], list) else data
print(rows[0].get(sys.argv[1], "") if rows else "")' "$1"
}

step_file() { ls install/"$1"-*.sql 2>/dev/null | head -1; }

run_step() {
  local s="$1" out
  echo; echo "==> $s $(title "$s")"
  case "$s" in
    00) python3 scripts/generate_install_sql.py ;;
    10)
      # A dataset can't be overwritten. On a re-run, keep the existing one and still upload configs.
      if ! out="$(sql_file "$(step_file 10)" 2>&1)"; then
        if grep -qi "already exists" <<<"$out"; then
          echo "  dataset already exists; keeping it (bump dataset_name in the eval configs to replace it)"
          snow sql -c "$CONN" --enable-templating NONE -q "$(grep '^PUT ' "$(step_file 10)")"
        else
          echo "$out" >&2; return 1
        fi
      fi ;;
    11)
      while :; do
        local ready ts
        out="$(snow sql -c "$CONN" --enable-templating NONE --format json -f "$(step_file 11)")"
        ready="$(json_col CONTEXT_READY <<<"$out")"; ts="$(json_col LAST_PROCESSED_AT <<<"$out")"
        if [[ "$ready" == "True" || "$ready" == "true" ]]; then
          echo "  context build finished (last processed $ts)"; break
        fi
        if ((WAIT == 0)); then
          echo "  context is still building. Re-run later with: ./install.sh --from 11"; exit 0
        fi
        echo "  still building ($(date +%H:%M)); checking again in $((POLL_SECONDS / 60)) min. Ctrl-C is safe: resume with ./install.sh --from 11"
        sleep "$POLL_SECONDS"
      done ;;
    12)
      local suffix; suffix="$(date +%Y%m%d_%H%M)"
      snow sql -c "$CONN" --enable-templating STANDARD -D "run_suffix=$suffix" -f "$(step_file 12)"
      for a in finance analyst sense; do state_set "RUN_$(tr a-z A-Z <<<"$a")" "${a}_${suffix}"; done
      for a in finance analyst sense; do
        local run="${a}_${suffix}" status=""
        while :; do
          status="$(snow sql -c "$CONN" --enable-templating NONE --format json -q \
            "USE ROLE ACCOUNTADMIN; USE SCHEMA CORTEX_SENSE_DEMO.EVALS;
             CALL EXECUTE_AI_EVALUATION('STATUS', OBJECT_CONSTRUCT('run_name', '$run'),
                  '@CORTEX_SENSE_DEMO.EVALS.EVAL_CONFIG/${a}_demo_eval.yaml');" | json_col STATUS)"
          echo "  $run: $status"
          [[ "$status" == COMPLETED ]] && break
          [[ "$status" == *FAIL* ]] && { echo "  $run failed; check it in Snowsight, then ./install.sh --from 12" >&2; return 1; }
          sleep 60
        done
      done ;;
    13) python3 scripts/build_web_data.py ;;
    14)
      (cd app/web
       [[ -d node_modules ]] || npm install
       [[ -x .venv/bin/python ]] || { python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt; }
       npm run build
       SNOWFLAKE_CONNECTION_NAME="$CONN" nohup .venv/bin/python api_server.py > api_server.log 2>&1 &
       nohup npx next start -p 3000 > next.log 2>&1 &)
      sleep 5
      echo "  Demo UI: http://localhost:3000 (live mode API on :5001; logs in app/web/*.log)" ;;
    *) sql_file "$(step_file "$s")" ;;
  esac
  state_set "DONE_$s" 1
}

echo "Connection: $CONN"
snow connection test -c "$CONN" > /dev/null || {
  echo "Connection '$CONN' failed. Add it to ~/.snowflake/connections.toml (see README) or set SNOWFLAKE_CONNECTION_NAME." >&2
  exit 1; }

for s in "${STEPS[@]}"; do
  if [[ -n "$ONLY" ]]; then [[ "$s" == "$ONLY" ]] && run_step "$s"; continue; fi
  [[ "$s" < "$FROM" ]] && continue
  run_step "$s"
done
echo; echo "Done."
