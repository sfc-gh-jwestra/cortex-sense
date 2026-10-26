create or replace TABLE CORTEX_SENSE_DEMO.GAME_CATALOG.ACCESSIBILITY_FEATURES (
	FEATURE_ID NUMBER(38,0),
	FEATURE_NAME VARCHAR(16777216),
	FEATURE_CATEGORY VARCHAR(16777216)
)COMMENT='The table contains records of accessibility features in games. Each record represents a specific feature, categorized by type, with details about its characteristics.'
;
