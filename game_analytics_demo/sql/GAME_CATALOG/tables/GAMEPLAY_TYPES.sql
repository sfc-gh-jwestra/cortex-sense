create or replace TABLE CORTEX_SENSE_DEMO.GAME_CATALOG.GAMEPLAY_TYPES (
	GAMEPLAY_TYPE_ID NUMBER(38,0) NOT NULL autoincrement start 1 increment 1 noorder,
	GAMEPLAY_TYPE_NAME VARCHAR(16777216),
	primary key (GAMEPLAY_TYPE_ID)
)COMMENT='The table contains records of gameplay types. Each record represents a specific type of gameplay and includes a unique identifier and a descriptive name.'
;
