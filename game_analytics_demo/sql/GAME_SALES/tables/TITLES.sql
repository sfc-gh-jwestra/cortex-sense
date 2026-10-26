create or replace TABLE CORTEX_SENSE_DEMO.GAME_SALES.TITLES (
	TITLE_ID NUMBER(38,0) NOT NULL,
	TITLE_NAME VARCHAR(16777216),
	STUDIO VARCHAR(16777216) COMMENT 'Development studio',
	PUBLISHER_LABEL VARCHAR(16777216) COMMENT 'Publishing label',
	CATALOG_GAME_ID NUMBER(38,0) COMMENT 'Game id in the catalog system, when known',
	RELEASE_DATE VARCHAR(8),
	primary key (TITLE_ID)
)COMMENT='Sales system copy of the games it sells: ID, official title and release date only. Game descriptive data (developer, POV, narrative, franchise) lives in GAME_CATALOG. Kept in sync by the add-game-data-ontology skill.'
;
