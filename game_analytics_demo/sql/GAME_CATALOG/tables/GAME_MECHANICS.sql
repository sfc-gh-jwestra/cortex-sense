create or replace TABLE CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_MECHANICS (
	GAME_MECHANIC_ID NUMBER(38,0) NOT NULL autoincrement start 1 increment 1 noorder,
	GAME_ID NUMBER(38,0),
	MECHANIC_ID NUMBER(38,0),
	primary key (GAME_MECHANIC_ID)
)COMMENT='The table contains records of game mechanics. Each record represents a single game mechanic and includes details about the game and the mechanic itself.'
;
