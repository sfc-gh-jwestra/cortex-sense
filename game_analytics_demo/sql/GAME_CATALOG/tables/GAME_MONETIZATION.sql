create or replace TABLE CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_MONETIZATION (
	GAME_ID NUMBER(38,0) NOT NULL,
	MONETIZATION_ID NUMBER(38,0) NOT NULL,
	primary key (GAME_ID, MONETIZATION_ID)
)COMMENT='The table contains records of game monetization strategies. Each record represents a single game and includes details about its monetization plan and associated ID.'
;
