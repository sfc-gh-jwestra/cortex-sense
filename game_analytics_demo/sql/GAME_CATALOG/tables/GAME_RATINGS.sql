create or replace TABLE CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_RATINGS (
	GAME_ID NUMBER(38,0),
	RATING_ID NUMBER(38,0),
	EFFECTIVE_DATE DATE
)COMMENT='The table contains ratings for games, specifically their quality and performance. Each record represents a single rating and includes details about the game and the rating itself.'
;
