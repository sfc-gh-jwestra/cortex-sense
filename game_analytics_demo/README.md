# Gaming Analytics with Cortex Sense

> **Disclaimer.** This demo uses game data publicly sourced from the web, so it may contain inaccuracies when compared with real data. All revenue and sales data is fictional and synthetically generated, based on how games have historically earned revenue. Sony was chosen because of the popularity of its platform. Microsoft (Xbox), Nintendo, or a completely fictional game and console provider would serve the demonstration equally well.

## What this demonstrates

A game publisher has two data domains, built like two separate systems. The **catalog** describes each game (genres, engines, awards, accessibility, age ratings, audience similarity). The **sales** system records titles, transactions and revenue. Each is accurate on its own, but they use different keys and spell the same names differently. See [Database](#database).

The demo asks the same ten questions of three Cortex Agents:

- **The finance agent** (`GAME_AGENT_FINANCE`) is what most teams build today: an accurate, curated revenue model (the `SV_GAME_SALES` semantic view) behind Cortex Analyst. It answers finance questions correctly, but it can't answer anything outside its view, and it can't cross into the catalog.
- **The analyst agent** (`GAME_AGENT_ANALYST`) is the quick first pass an organization makes when the sales dashboard starts showing genre and other cross-domain charts and people want to ask questions across domains. It keeps the semantic view and adds catalog search and its own SQL, so it can reach every long-tail table. But it has no business context, so its cross-domain answers are often wrong: it joins on the wrong key, double-counts multi-platform titles, or mixes partial and full genre matches.
- **The Cortex Sense agent** (`GAME_AGENT_SENSE`) gets its tables, business rules, query patterns and knowledge-base documents from a Cortex Sense context. It answers questions about revenue by genre, award winners, monetization models, engines, accessibility and audience overlap correctly, because the long-tail tables and the rules for using them are in its context.

It shows three things:

1. **Cross-domain answers.** Only the Cortex Sense agent reliably joins sales revenue to catalog attributes, and follows company documents such as the FY2027 portfolio strategy memo and the EU loot box regulatory brief.
2. **Uplift in Accuracy** On the current eval runs, the finance agent answers 3 of 10 questions correctly, the analyst agent 6, and the Cortex Sense agent 10.
3. **Tool and Token Usage Uplift** The Cortex Sense agent utilizes less tool calls and less tokens to answer the same questions correctly. Its context steers the Sense agent to the correct answer right away whereas other agents try different tools and probe for context to answer.

## Project structure

```
game_analytics_demo/
├── install.sh              One-command installer (steps 00-14, resumable)
├── install/                Numbered install SQL: 01-12 (02, 03, 05, 07-10 generated)
├── agents/                 Agent specs (CORTEX_SENSE_DEMO.AGENTS)
├── semantic_views/         SV_GAME_SALES.yaml
├── cortex_project/         Semantic view YAML to object mapping
├── context/scope.yaml      Cortex Sense context scope
├── stage_files/            Knowledge-base documents
├── streamlits/             Game sales dashboard
├── scripts/                generate_install_sql, record_feedback, prime_query_history,
│                           build_web_data, rule_checks
├── evaluations/demo/       Question bank and eval configs (finance, analyst, sense)
├── documentation/          Database design, join paths, revenue types, query history priming
├── sql/, data/             DDL and parquet data for GAME_CATALOG and GAME_SALES
└── app/web/                Three-agent demo UI (Next.js + api_server.py)
```

## Architecture

The project has 3 agents defined and used to understand the uplift Cortex Sense offers. 

```
GAME_AGENT_FINANCE (baseline)
  └── Cortex Analyst → CORTEX_SENSE_DEMO.GAME_SALES.SV_GAME_SALES
```

The Finance Agent was built for the CFO, and finance department to ask questions about revenue and sales. It uses a semantic view that is curated to answer these questions accurately, but it not capable of stepping outside the bounds of its finance/commerce domain. We call this the baseline. It is what many customers build to start.

```
GAME_AGENT_ANALYST (capable analyst, no Cortex Sense)
  ├── Cortex Analyst → CORTEX_SENSE_DEMO.GAME_SALES.SV_GAME_SALES
  └── own SQL + catalog search (AgenticAnalystAllowArbitrarySQL, EnableStandaloneExecuteSqlTool)
```

This agent represents a highly capable analyst that can search across schemas to discover tables, views, and more then build reasonable SQL to answer questions. While the analyst can probe and discover data and helpful joins, it does not have the full breadth of rules for how the business operates.

```
GAME_AGENT_SENSE (EnableCortexSense)
  └── cortex_sense → CORTEX_SENSE_DEMO.CONTEXTS.GAME_ANALYTICS_CTX_V2
        ├── feedback rules        business definitions and procedures (served as corrections)
        ├── catalog_objects       table documents for GAME_CATALOG and GAME_SALES
        ├── query_history         query patterns primed by install/05-prime-query-history.sql
        ├── streamlit_apps        GAME_SALES_DASHBOARD
        ├── semantic_views        SV_GAME_SALES (revenue model + verified queries)
        └── stage_files           FY2027 portfolio strategy memo, EU loot box regulatory brief
```

The project's Cortex Sense scope.yaml references numerous data sources to build its context and help it learn the business.

| Component | Snowflake object | Source in this repo |
|---|---|---|
| Data | `CORTEX_SENSE_DEMO.GAME_CATALOG`, `CORTEX_SENSE_DEMO.GAME_SALES` | [`sql/`](sql/) (DDL), [`data/`](data/) (parquet) |
| Semantic view | `CORTEX_SENSE_DEMO.GAME_SALES.SV_GAME_SALES` | [`semantic_views/SV_GAME_SALES.yaml`](semantic_views/SV_GAME_SALES.yaml) |
| Dashboard | `CORTEX_SENSE_DEMO.GAME_SALES.GAME_SALES_DASHBOARD` | [`streamlits/`](streamlits/) |
| Context | `CORTEX_SENSE_DEMO.CONTEXTS.GAME_ANALYTICS_CTX_V2` | [`context/scope.yaml`](context/scope.yaml), rules in [`scripts/record_feedback.py`](scripts/record_feedback.py) |
| Knowledge base | `@CORTEX_SENSE_DEMO.CONTEXTS.KNOWLEDGE_BASE` | [`stage_files/`](stage_files/) |
| Agents | `CORTEX_SENSE_DEMO.AGENTS.GAME_AGENT_FINANCE`, `GAME_AGENT_ANALYST`, `GAME_AGENT_SENSE` | [`agents/`](agents/) |
| Evals | `CORTEX_SENSE_DEMO.EVALS` (dataset, `EVAL_CONFIG` stage, `DEMO_AGENT_RESULTS`) | [`evaluations/demo/`](evaluations/demo/) |
| Demo UI | Next.js app plus a Flask API, run locally | [`app/web/`](app/web/) |

## Prerequisites

**Tools on your machine:** the [Snowflake CLI](https://docs.snowflake.com/en/developer-guide/snowflake-cli/index) (`snow`), Python 3.11 with `pyyaml`, Node.js 18 or later, and Cortex Code (CoCo) if you want the one-prompt install.

**Snowflake account:** Cortex Agents, Cortex Sense and AI evaluations must be available in your account and region.

### Connection

Every script uses one named connection, `CORTEX_SENSE_DEMO_CONN`. Add it to `~/.snowflake/connections.toml` (and restrict the file with `chmod 0600`):

```toml
[CORTEX_SENSE_DEMO_CONN]
account       = "<orgname>-<account_name>"
user          = "<your_user>"
authenticator = "externalbrowser"     # or SNOWFLAKE_JWT with private_key_file, or a PAT
role          = "ACCOUNTADMIN"
warehouse     = "COMPUTE_WH"
database      = "CORTEX_SENSE_DEMO"
```

Check it with `snow connection test -c CORTEX_SENSE_DEMO_CONN`. To use a connection with a different name, set `SNOWFLAKE_CONNECTION_NAME=<name>`; every script and the installer honor it.

- **Role.** The install needs `ACCOUNTADMIN`. The eval functions (`EXECUTE_AI_EVALUATION`, `GET_AI_EVALUATION_DATA`, `GET_AI_RECORD_TRACE`) need it, and several steps run `USE ROLE ACCOUNTADMIN` explicitly, so a user without that role can't complete the install even if the connection's role is lower.
- **Database and schema.** All SQL uses fully qualified names and sets `USE SCHEMA` where it matters (for example `CORTEX_SENSE_DEMO.EVALS` for the evals), so nothing depends on the connection's schema. The `database` line is a convenience; on a new account the database doesn't exist until step 01 creates it.
- **Warehouse.** `COMPUTE_WH` is only an example; any warehouse the role can use works. The name is also set in `context/scope.yaml`, `streamlits/snowflake.yml` and `install/04-deploy-streamlit.sql`, the dynamic tables under `sql/`, and the analyst agent's `FallbackWarehouse` in `agents/GAME_AGENT_ANALYST.yaml`. If you use another warehouse, change those too.
- **Authentication.** `externalbrowser` (SSO) is the easiest to set up. For the long, unattended parts of the install (waiting for the context build, running evals), key-pair or PAT authentication is more reliable, because browser sign-in can time out mid-run.

## Database

The demo creates one database, `CORTEX_SENSE_DEMO`:

| Schema | Holds |
|---|---|
| `AGENTS` | The three agents |
| `CONTEXTS` | The Cortex Sense context and the knowledge-base stage |
| `EVALS` | Eval dataset, configs and recorded results |
| `GAME_CATALOG` | Game attributes: 90 games with genres, engines, awards, accessibility, ratings, modes, similarity and genre whitespace |
| `GAME_SALES` | Sales titles, digital, hardware and subscription transactions, revenue tables, `SV_GAME_SALES`, the dashboard |
| `PUBLIC` | Stages and file format used by the install |



## Install, step by step

> **Note:** For a one-step install, go to [Easy button: install with CoCo](#easy-button-install-with-coco). For a manual install, continue below.

Each step is a numbered file in [`install/`](install/), run in order from the repo root. Steps 00, 13 and 14 are commands rather than SQL, because they generate files or start the UI.

The files marked *generated* embed a source file from this repo (YAML, or a list defined in Python). [`scripts/generate_install_sql.py`](scripts/generate_install_sql.py) writes them, so the source is always the one place to edit: change the YAML or Python source, then re-run step 00.

Run a SQL step with:

```bash
snow sql -c CORTEX_SENSE_DEMO_CONN --enable-templating NONE -f install/<file>.sql
```

| Step | File | What it does |
|---|---|---|
| 00 | `python3 scripts/generate_install_sql.py` | Writes the generated files below from their sources. |
| 01 | `01-setup-db.sql` | Creates the `CORTEX_SENSE_DEMO` database; the `GAME_CATALOG`, `GAME_SALES`, `CONTEXTS`, `AGENTS` and `EVALS` schemas; the data, dashboard, knowledge-base and eval-config stages; and the parquet file format. Safe to re-run. |
| 02 | `02-load-data.sql` (generated) | Loads the data, in this order: uploads `data/<SCHEMA>/*.parquet` to the data stage, creates every base table from `sql/<SCHEMA>/tables/`, runs a `COPY INTO` for each table, and finally creates the functions, procedures, views and dynamic tables in dependency order. Table DDL is `CREATE OR REPLACE`. |
| 03 | `03-deploy-semantic-view.sql` (generated) | Creates `SV_GAME_SALES` from `semantic_views/SV_GAME_SALES.yaml` with `SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML`. |
| 04 | `04-deploy-streamlit.sql` | Uploads `streamlits/` and creates the `GAME_SALES_DASHBOARD` app on the container runtime. |
| 05 | `05-prime-query-history.sql` (generated) | Runs 73 rule-compliant queries, so Cortex Sense learns correct join patterns from query history. See [documentation/how-query-history-is-primed.md](documentation/how-query-history-is-primed.md). |
| 06 | `06-upload-knowledge-base.sql` | Uploads the strategy memo and EU brief from `stage_files/` to the knowledge-base stage. |
| 07 | `07-create-context.sql` (generated) | Registers the Cortex Sense context, writes its scope from `context/scope.yaml`, and queues a build. |
| 08 | `08-record-feedback.sql` (generated) | Records the business rules from `scripts/record_feedback.py`. They apply as soon as they're recorded. |
| 09 | `09-deploy-agents.sql` (generated) | Creates the three agents from `agents/*.yaml`. |
| 10 | `10-load-eval-dataset.sql` (generated) | Loads the questions and ground truth from `evaluations/demo/demo_questions.yaml` into an eval dataset, and uploads the three eval configs. |
| 11 | `11-check-context-build.sql` | Reports whether the context build has finished (`CONTEXT_READY`). |
| 12 | `12-run-evals.sql` | Starts one eval run per agent. It's templated with a run-name suffix: `snow sql -c CORTEX_SENSE_DEMO_CONN --enable-templating STANDARD -D run_suffix=run1 -f install/12-run-evals.sql` |
| 13 | `python3 scripts/build_web_data.py --runs finance=finance_run1,analyst=analyst_run1,sense=sense_run1` | Reads each run's answers, scores and traces, refreshes `EVALS.DEMO_AGENT_RESULTS`, and writes `app/web/lib/demo_data.json` for the UI. |
| 14 | See [Demo UI](#demo-ui) | Installs the UI dependencies and starts the app. |

**The context build takes a while.** Step 07 queues the Cortex Sense build, which runs in the background and often takes a few hours. Until it finishes, the Sense agent can't retrieve its table documents or the knowledge-base files. So wait for step 11 to report `CONTEXT_READY = TRUE` before running the evals in step 12. Steps 08 to 10 don't depend on the build, so you can run them while it's in progress.

**Steps after the build may need restarting.** The build, the evals and long sign-in sessions can outlast a terminal session. Each step can be re-run on its own. The installer below records what has finished, so you can resume where you left off. If you use CoCo, ask it to keep track of where the install is: its project memory carries progress and the eval run names across sessions.

## Install everything with one command

[`install.sh`](install.sh) runs steps 00 to 14 in order. It waits for the context build at step 11 (checking every 5 minutes), starts the evals and waits for all three, then builds the UI data and starts the app at http://localhost:3000.

```bash
bash install.sh              # everything, waiting for the build and the evals
bash install.sh --no-wait    # stop at step 11 if the build hasn't finished
bash install.sh --from 11    # resume (e.g. after the build finishes)
bash install.sh --only 09    # run a single step, e.g. redeploy the agents
bash install.sh --list       # show which steps have completed, and the eval run names
```

Progress and the eval run names are saved in `.install_state` in the repo root; delete that file to start over. Re-running step 08 records the feedback rules a second time, so resume past it rather than re-running it.

## Easy button: install with CoCo

Open this folder in Cortex Code and paste:

```
Install the Cortex Sense gaming demo in this repo into my Snowflake account, using the
connection CORTEX_SENSE_DEMO_CONN.

First, create a plan; don't run anything yet. Read README.md, install.sh and install/,
check that the connection works and uses a role that can do this install, then plan each
install step (00 to 14) with what it will create. Stop and let me review the plan.

When I build the plan, run the install with install.sh one step at a time, and tell me
after each step what was created. Record progress, and the eval run names, in project
memory. The context build in step 07 takes a while: if it hasn't finished, tell me, stop at
step 11, and pick up from step 11 when I ask you to resume. Finish with the demo UI running
at http://localhost:3000.
```

CoCo creates the plan first, so you can see every object it will create before anything runs. Clicking **Build** on the plan starts the install. Because CoCo records progress in its project memory, you can come back after the context build finishes and say "resume the demo install".

## Running the evals again

The demo compares how each of the three agents answers a set of golden questions using Snowflake Agentic Evals. It displays the comparison and an analysis in a Next.js app UI. The ten questions in [`evaluations/demo/demo_questions.yaml`](evaluations/demo/demo_questions.yaml) are of two kinds. Two are ties that every agent can answer from `SV_GAME_SALES`. The other eight need catalog tables, business rules or knowledge-base documents; S07 depends on the strategy memo and S08 on the EU brief. Each question's ground truth was computed on `CORTEX_SENSE_DEMO` with SQL (`gt_sql`) that follows the feedback rules. The eval judge sees only the ground-truth text; the UI also shows the rows `gt_sql` returns.

The evals are already run in batch and ready for the UI to show. However, if the agents are changed, you will want to re-run the evals in batch again and record them for the UI to display.

Easy button: to re-run evals simply ask CoCo to run batch evals on all three agents and then update the UI's recorded results. To manually re-run the evals, run step 12 with a new suffix (run names must be unique), and then step 13 with the new run names:

```bash
bash install.sh --from 12
```

- **A new feedback rule** takes effect as soon as it's recorded; no rebuild is needed. Add it to `RECORDS` in `scripts/record_feedback.py`, record just that rule with `python3 scripts/record_feedback.py --only "<first concept>"`, and re-run the evals.
- **A scope change** (`context/scope.yaml`), new tables or new knowledge-base files need a rebuild. Run steps 00, 06 (if documents changed) and 07, then wait for step 11.
- **Changed questions or ground truth** need a new dataset, because a dataset can't be overwritten. Bump the `dataset_name` suffix in all three `evaluations/demo/*_demo_eval.yaml` files, then run steps 00 and 10.

## Demo UI

The UI is a Next.js app with a small Flask API that calls the agents for live questions:

Easy button: 
Ask CoCo to launch the UI app. It will launch it and provide you with the URL to open in your own external browser of choice.

```bash
cd app/web
npm install
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python api_server.py &          # live mode and agent definitions, port 5001
npm run build && npx next start -p 3000   # http://localhost:3000
```


The UI has three tabs:

- **Setup.** This tab explains the demo before any question is asked. It shows the architecture, the data each of the three agents can reach, the deployed definition of each agent, and the sources that make up the Cortex Sense context.
- **Comparison.** This tab puts the three agents side by side for one question at a time. Each panel shows the agent's answer and its score, and badges for the business rules its SQL followed or broke. Below that is a numbered trace of what the agent did: the question it sent to Cortex Analyst, each SQL statement it ran with a preview of the first rows returned, and the chart it drew. The judge's explanation of the score follows. Under the three panels are the expected answer, the rows its ground-truth SQL returns, and a verdict for each agent. In live mode, you can ask your own question. It goes to all three agents and comes back with the same traces and rule checks, but no score.
- **Analysis.** This tab summarizes all ten questions. It shows each agent's overall score, then a behavior table that gives, for each question, every agent's score, how many steps it took, which tables it touched, and its rule checks. All three answers follow, with their traces.

The rule checks are deterministic regex checks of an agent's SQL against six of the feedback rules: sales-to-catalog mapping, monthly rather than cumulative income, lifecycle phases from release date, fully matched genres, income counted once per title, and a digital title taken from its product. A check skips exploratory queries such as `SELECT * ... LIMIT 3`, which only look at a table. `python3 scripts/rule_checks.py` confirms that all 73 primed queries pass every check.

## Agents

- **GAME_AGENT_SENSE** ([spec](agents/GAME_AGENT_SENSE.yaml)) sets `experimental.EnableCortexSense: true` and declares one tool, `data_to_chart`. Its orchestration instructions tell it to call `cortex_sense` with the context before writing any SQL, to read the corrections first, and to use fully qualified `CORTEX_SENSE_DEMO` names. Business definitions don't go in the spec; they go in feedback rules or the semantic view.
- **GAME_AGENT_FINANCE** ([spec](agents/GAME_AGENT_FINANCE.yaml)) has one Cortex Analyst tool over `SV_GAME_SALES`, plus `data_to_chart`.
- **GAME_AGENT_ANALYST** ([spec](agents/GAME_AGENT_ANALYST.yaml)) has the same Cortex Analyst tool and `data_to_chart`, plus the experimental flags `AgenticAnalystAllowArbitrarySQL` (its own SQL on any readable table), `EnableStandaloneExecuteSqlTool` (catalog and tool search) and `FallbackWarehouse: COMPUTE_WH`. Its instructions are an analyst's habits (explore schemas, check cardinality, state assumptions) without business rules. It shows what a strong agent gets right by exploring, and which rules it still breaks without Cortex Sense. Agent tools run with the caller's role, so an analyst agent run as `ACCOUNTADMIN` can also find and read the knowledge-base stage.

All titles in the data are Sony's, so no agent filters by publisher.

## The Cortex Sense context

- **Feedback rules.** `RECORDS` in [`scripts/record_feedback.py`](scripts/record_feedback.py) is the source of truth for the business rules: definitions, procedures and retrieval steers. They're served to the agent as corrections at query time.
- **Semantic view as context.** `SV_GAME_SALES` is a scope source, so its definitions, custom instructions and verified queries are documents the Sense agent reads. For the finance and analyst agents, it's their Cortex Analyst tool.
- **Query history.** The primed queries teach correct join patterns; see [documentation/how-query-history-is-primed.md](documentation/how-query-history-is-primed.md).
- **Knowledge base.** The strategy memo and EU brief in `stage_files/` are indexed through the `stage_files` source.
