create or replace TABLE CORTEX_SENSE_DEMO.GAME_CATALOG.AGE_RATINGS (
	RATING_ID NUMBER(38,0),
	RATING_SYSTEM VARCHAR(16777216),
	RATING_VALUE VARCHAR(16777216),
	MIN_AGE NUMBER(38,0),
	DESCRIPTION VARCHAR(16777216)
)COMMENT='The table contains age ratings for various media content. Each record represents a specific rating system and includes details about the minimum age requirement and a brief description.'
;
