create or replace TABLE CORTEX_SENSE_DEMO.GAME_CATALOG.AWARDS (
	AWARD_ID NUMBER(38,0),
	AWARD_NAME VARCHAR(16777216),
	AWARDING_BODY VARCHAR(16777216)
)COMMENT='The table contains records of awards, specifically those given to individuals or entities. Each record represents a single award and includes details about the awarding body.'
;
