create or replace TABLE CORTEX_SENSE_DEMO.GAME_CATALOG.SIMILARITY_WEIGHTS (
	DIMENSION_NAME VARCHAR(16777216) NOT NULL,
	WEIGHT FLOAT NOT NULL,
	primary key (DIMENSION_NAME)
)COMMENT='The table contains similarity weights for game attributes. Each record represents a specific attribute and its corresponding weight value, categorizing the importance of each attribute in the game catalog.'
;
