create or replace TABLE CORTEX_SENSE_DEMO.GAME_SALES.GAME_PLATFORMS (
	GAME_PLATFORM_ID NUMBER(38,0) NOT NULL,
	TITLE_ID NUMBER(38,0),
	PLATFORM_ID NUMBER(38,0),
	EXCLUSIVITY_TYPE VARCHAR(16777216),
	EXCLUSIVE_START DATE,
	EXCLUSIVE_END DATE,
	EXCLUSIVITY_NOTE VARCHAR(16777216),
	IS_EXCLUSIVE VARCHAR(1),
	primary key (GAME_PLATFORM_ID)
)COMMENT='Sales system copy: which platforms each game is sold on, with exclusivity windows (drives store availability dates and VW_PLATFORM_EXCLUSIVITY). Same GAME_PLATFORM_IDs as GAME_CATALOG. Kept in sync by the add-game-data-ontology skill.'
;
