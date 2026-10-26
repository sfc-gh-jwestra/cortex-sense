-- 12-run-evals
-- Starts one evaluation run per agent. Runs are asynchronous; check them with
--   CALL EXECUTE_AI_EVALUATION('STATUS', OBJECT_CONSTRUCT('run_name', '<name>'), '<config>');
-- Run names must be new each time, so this file is templated: pass a suffix, e.g.
--   snow sql -c <connection> --enable-templating STANDARD -D run_suffix=run1 -f install/12-run-evals.sql
-- install.sh picks the suffix and records the run names in .install_state.
-- Run only after 11-check-context-build reports CONTEXT_READY = TRUE.

USE ROLE ACCOUNTADMIN;
USE SCHEMA CORTEX_SENSE_DEMO.EVALS;

CALL EXECUTE_AI_EVALUATION('START', OBJECT_CONSTRUCT('run_name', 'finance_<% run_suffix %>'),
     '@CORTEX_SENSE_DEMO.EVALS.EVAL_CONFIG/finance_demo_eval.yaml');
CALL EXECUTE_AI_EVALUATION('START', OBJECT_CONSTRUCT('run_name', 'analyst_<% run_suffix %>'),
     '@CORTEX_SENSE_DEMO.EVALS.EVAL_CONFIG/analyst_demo_eval.yaml');
CALL EXECUTE_AI_EVALUATION('START', OBJECT_CONSTRUCT('run_name', 'sense_<% run_suffix %>'),
     '@CORTEX_SENSE_DEMO.EVALS.EVAL_CONFIG/sense_demo_eval.yaml');
