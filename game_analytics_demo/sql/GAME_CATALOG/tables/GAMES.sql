create or replace TABLE CORTEX_SENSE_DEMO.GAME_CATALOG.GAMES (
	GAME_ID NUMBER(38,0) NOT NULL autoincrement start 1 increment 1 noorder,
	GAME_NAME VARCHAR(16777216),
	DEVELOPER_ID NUMBER(38,0),
	POV VARCHAR(16777216),
	RELEASE_DATE DATE,
	NARRATIVE_STRUCTURE_ID NUMBER(38,0),
	DEVELOPER_NAME VARCHAR(16777216) COMMENT 'Studio that built the game',
	DEVELOPER_IS_INDIE BOOLEAN,
	PUBLISHER_ID NUMBER(38,0),
	PUBLISHER_NAME VARCHAR(16777216),
	PUBLISHER_HQ VARCHAR(16777216),
	FRANCHISE_NAME VARCHAR(16777216),
	STATUS VARCHAR(16777216),
	primary key (GAME_ID)
)COMMENT='The table contains records of video games, specifically games that have been developed and released. Each record represents a single game and includes details about the game''s narrative, gameplay perspective, and financial performance.'
;
