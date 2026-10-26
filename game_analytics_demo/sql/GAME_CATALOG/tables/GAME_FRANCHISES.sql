create or replace TABLE CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_FRANCHISES (
	GAME_ID NUMBER(38,0),
	FRANCHISE_ID NUMBER(38,0),
	SEQUENCE_ORDER NUMBER(38,0),
	FRANCHISE_NAME VARCHAR(16777216),
	FIRST_RELEASE_YEAR NUMBER(38,0),
	PUBLISHER_ID NUMBER(38,0),
	RELATED_GAME_ID NUMBER(38,0) COMMENT 'Game this one derives from; may be in another franchise',
	RELATIONSHIP_TYPE VARCHAR(16777216) DEFAULT 'original' COMMENT 'original, sequel, prequel, spinoff, remake, spiritual_successor'
)COMMENT='The table contains records of game franchises. Each record represents a single franchise and includes details about its sequence order and relationship to a specific game.'
;
