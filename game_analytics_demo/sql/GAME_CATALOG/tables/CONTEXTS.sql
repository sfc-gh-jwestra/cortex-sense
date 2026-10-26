create or replace TABLE CORTEX_SENSE_DEMO.GAME_CATALOG.CONTEXTS (
	CONTEXT_ID NUMBER(38,0) NOT NULL autoincrement start 1 increment 1 noorder,
	CONTEXT_NAME VARCHAR(16777216),
	primary key (CONTEXT_ID)
)COMMENT='The table contains records of gaming contexts. Each record represents a single context and includes details about its name.'
;
