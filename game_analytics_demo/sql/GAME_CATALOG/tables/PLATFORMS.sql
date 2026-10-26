create or replace TABLE CORTEX_SENSE_DEMO.GAME_CATALOG.PLATFORMS (
	PLATFORM_ID NUMBER(38,0) NOT NULL autoincrement start 1 increment 1 noorder,
	PLATFORM_NAME VARCHAR(16777216),
	primary key (PLATFORM_ID)
)COMMENT='The table contains records of gaming platforms. Each record represents a single platform and includes details about its name.'
;
