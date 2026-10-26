-- 11-check-context-build
-- Read-only. CONTEXT_READY is TRUE once the build queued by 07 has finished: LAST_PROCESSED_AT
-- stays at the epoch (or NULL) until then. The build often takes hours; run the Sense eval (12)
-- only after this reports TRUE, or the agent can't retrieve the knowledge-base documents.
-- Run from the repo root: snow sql -c <connection> --enable-templating NONE -f install/11-check-context-build.sql

SELECT ctx:last_processed_at::STRING AS last_processed_at,
       COALESCE(TRY_TO_TIMESTAMP_TZ(ctx:last_processed_at::STRING) > '1971-01-01'::TIMESTAMP_TZ, FALSE) AS context_ready
FROM (
  SELECT TRY_PARSE_JSON(SYSTEM$CORTEX_AGENT_CORTEX_CONTEXT_BUILDER(
    '{"action":"get-context","parameters":{"name":"GAME_ANALYTICS_CTX_V2","database_name":"CORTEX_SENSE_DEMO","schema_name":"CONTEXTS"}}'
  )):response_structured:cortex_context AS ctx
);
