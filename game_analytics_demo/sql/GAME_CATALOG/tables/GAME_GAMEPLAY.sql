create or replace TABLE CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_GAMEPLAY (
	GAME_GAMEPLAY_ID NUMBER(38,0) NOT NULL autoincrement start 1 increment 1 noorder,
	GAME_ID NUMBER(38,0),
	GAMEPLAY_TYPE_ID NUMBER(38,0),
	primary key (GAME_GAMEPLAY_ID)
)COMMENT='The table contains records of gameplay types for games. Each record represents a single gameplay type and includes details about the game it belongs to.'
;
