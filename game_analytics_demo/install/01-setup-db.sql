-- 01-setup-db
-- Database, schemas, stages and file format for the demo. Safe to re-run (IF NOT EXISTS).
-- Run from the repo root: snow sql -c <connection> --enable-templating NONE -f install/01-setup-db.sql

USE ROLE ACCOUNTADMIN;

CREATE DATABASE IF NOT EXISTS CORTEX_SENSE_DEMO;

-- Two data domains
CREATE SCHEMA IF NOT EXISTS CORTEX_SENSE_DEMO.GAME_CATALOG;   -- game attributes (genres, engines, awards, ...)
CREATE SCHEMA IF NOT EXISTS CORTEX_SENSE_DEMO.GAME_SALES;     -- titles, transactions, revenue, dashboard
-- Demo objects
CREATE SCHEMA IF NOT EXISTS CORTEX_SENSE_DEMO.CONTEXTS;       -- Cortex Sense context + knowledge base
CREATE SCHEMA IF NOT EXISTS CORTEX_SENSE_DEMO.AGENTS;         -- the three Cortex Agents
CREATE SCHEMA IF NOT EXISTS CORTEX_SENSE_DEMO.EVALS;          -- eval dataset, configs, results

-- Parquet upload stage and format used by 02-load-data
CREATE STAGE IF NOT EXISTS CORTEX_SENSE_DEMO.PUBLIC.DATA_STAGE;
CREATE FILE FORMAT IF NOT EXISTS CORTEX_SENSE_DEMO.PUBLIC.PARQUET_FF
  TYPE = PARQUET
  USE_VECTORIZED_SCANNER = TRUE
  USE_LOGICAL_TYPE = TRUE;

-- Dashboard source files (04-deploy-streamlit)
CREATE STAGE IF NOT EXISTS CORTEX_SENSE_DEMO.PUBLIC.STREAMLIT_STAGE;

-- Knowledge base documents indexed by the context (06-upload-knowledge-base). The context
-- reads stage files through the directory table, so it must be enabled.
CREATE STAGE IF NOT EXISTS CORTEX_SENSE_DEMO.CONTEXTS.KNOWLEDGE_BASE
  DIRECTORY = (ENABLE = TRUE);

-- Eval configs read by EXECUTE_AI_EVALUATION (10-load-eval-dataset, 12-run-evals)
CREATE STAGE IF NOT EXISTS CORTEX_SENSE_DEMO.EVALS.EVAL_CONFIG;
