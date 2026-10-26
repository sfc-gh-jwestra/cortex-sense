-- 06-upload-knowledge-base
-- The FY2027 portfolio strategy memo and the EU loot box brief, indexed by the context's
-- stage_files source. Only the Sense agent can read them, through Cortex Sense.
-- Run from the repo root: snow sql -c <connection> --enable-templating NONE -f install/06-upload-knowledge-base.sql

PUT 'file://stage_files/*.md' @CORTEX_SENSE_DEMO.CONTEXTS.KNOWLEDGE_BASE AUTO_COMPRESS = FALSE OVERWRITE = TRUE;

-- Refresh the directory table so the new files are visible to the context build
ALTER STAGE CORTEX_SENSE_DEMO.CONTEXTS.KNOWLEDGE_BASE REFRESH;
