create or replace TABLE CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_ENGINES (
	GAME_ID NUMBER(38,0),
	ENGINE_ID NUMBER(38,0),
	ENGINE_VERSION VARCHAR(16777216),
	CUSTOM_FORK BOOLEAN
)COMMENT='The table contains records of game engines, specifically their versions and custom forks. Each record represents a single game engine and includes details about its version and custom modifications.'
;
