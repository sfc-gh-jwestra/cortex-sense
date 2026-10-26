create or replace TABLE CORTEX_SENSE_DEMO.GAME_CATALOG.ENGINES (
	ENGINE_ID NUMBER(38,0),
	ENGINE_NAME VARCHAR(16777216),
	DEVELOPER_COMPANY VARCHAR(16777216),
	SUPPORTS_RAY_TRACING BOOLEAN
)COMMENT='The table contains records of game engine components. Each record represents a specific engine and includes details about its capabilities and development.'
;
