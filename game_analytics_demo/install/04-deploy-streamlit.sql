-- 04-deploy-streamlit
-- GAME_SALES_DASHBOARD from streamlits/ (settings mirror streamlits/snowflake.yml).
-- The context indexes this app (streamlit_apps source), so deploy it before 07.
-- Run from the repo root: snow sql -c <connection> --enable-templating NONE -f install/04-deploy-streamlit.sql

-- Upload app files, keeping their folder layout (PUT doesn't recurse)
PUT 'file://streamlits/streamlit_app.py' @CORTEX_SENSE_DEMO.PUBLIC.STREAMLIT_STAGE/game_sales_dashboard/ AUTO_COMPRESS = FALSE OVERWRITE = TRUE;
PUT 'file://streamlits/.streamlit/config.toml' @CORTEX_SENSE_DEMO.PUBLIC.STREAMLIT_STAGE/game_sales_dashboard/.streamlit/ AUTO_COMPRESS = FALSE OVERWRITE = TRUE;
PUT 'file://streamlits/static/*.ttf' @CORTEX_SENSE_DEMO.PUBLIC.STREAMLIT_STAGE/game_sales_dashboard/static/ AUTO_COMPRESS = FALSE OVERWRITE = TRUE;

-- Container runtime on the account's system CPU pool. COMPUTE_WH is the example warehouse
-- used throughout the project; change it here and in streamlits/snowflake.yml to use another.
CREATE OR REPLACE STREAMLIT CORTEX_SENSE_DEMO.GAME_SALES.GAME_SALES_DASHBOARD
  FROM '@CORTEX_SENSE_DEMO.PUBLIC.STREAMLIT_STAGE/game_sales_dashboard'
  MAIN_FILE = 'streamlit_app.py'
  QUERY_WAREHOUSE = COMPUTE_WH
  RUNTIME_NAME = 'SYSTEM$ST_CONTAINER_RUNTIME_PY3_11'
  COMPUTE_POOL = SYSTEM_COMPUTE_POOL_CPU
  TITLE = 'Game Sales Dashboard';

-- A new app isn't live until it has a live version
ALTER STREAMLIT CORTEX_SENSE_DEMO.GAME_SALES.GAME_SALES_DASHBOARD ADD LIVE VERSION FROM LAST;
