create or replace TABLE CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_PLATFORMS (
	GAME_PLATFORM_ID NUMBER(38,0) NOT NULL autoincrement start 1 increment 1 noorder,
	GAME_ID NUMBER(38,0),
	PLATFORM_ID NUMBER(38,0),
	IS_EXCLUSIVE BOOLEAN DEFAULT FALSE,
	EXCLUSIVITY_TYPE VARCHAR(16777216),
	EXCLUSIVE_START DATE,
	EXCLUSIVE_END DATE,
	EXCLUSIVITY_NOTE VARCHAR(16777216),
	primary key (GAME_PLATFORM_ID)
)COMMENT='The table contains records of game platforms, specifically the platforms on which games are available. Each record represents a single platform and includes details about the games and platform types.'
;
