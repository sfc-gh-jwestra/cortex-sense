create or replace TABLE CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_MODES (
	GAME_ID NUMBER(38,0),
	MODE_NAME VARCHAR(16777216),
	MIN_PLAYERS NUMBER(38,0),
	MAX_PLAYERS NUMBER(38,0),
	ONLINE_REQUIRED BOOLEAN
)COMMENT='The table contains records of game modes, specifically types of gameplay experiences. Each record represents a single game mode and includes details about the minimum and maximum number of players required, as well as online requirements.'
;
