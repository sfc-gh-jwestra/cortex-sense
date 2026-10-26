create or replace TABLE CORTEX_SENSE_DEMO.GAME_SALES.MONETIZATION_TYPES (
	MONETIZATION_ID NUMBER(38,0) NOT NULL,
	MONETIZATION_NAME VARCHAR(16777216) NOT NULL,
	unique (MONETIZATION_NAME),
	primary key (MONETIZATION_ID)
)COMMENT='Sales system copy of monetization model names (premium, dlc, microtransactions, ...) used to pick each game''s synthetic sales profile. Kept in sync by the add-game-data-ontology skill.'
;
