create or replace TABLE CORTEX_SENSE_DEMO.GAME_CATALOG.MECHANICS (
	MECHANIC_ID NUMBER(38,0) NOT NULL autoincrement start 1 increment 1 noorder,
	MECHANIC_NAME VARCHAR(16777216),
	primary key (MECHANIC_ID)
)COMMENT='The table contains records of mechanics, specifically those involved in gaming. Each record represents a single mechanic and includes details about the mechanic''s name.'
;
