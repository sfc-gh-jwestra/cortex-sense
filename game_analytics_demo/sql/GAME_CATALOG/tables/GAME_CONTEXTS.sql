create or replace TABLE CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_CONTEXTS (
	GAME_CONTEXT_ID NUMBER(38,0) NOT NULL autoincrement start 1 increment 1 noorder,
	GAME_ID NUMBER(38,0),
	CONTEXT_ID NUMBER(38,0),
	primary key (GAME_CONTEXT_ID)
)COMMENT='The table contains records of game contexts, specifically settings or scenarios within games. Each record represents a unique context and includes details about the associated game.'
;
