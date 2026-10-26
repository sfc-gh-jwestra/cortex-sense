create or replace TABLE CORTEX_SENSE_DEMO.GAME_CATALOG.STUDIO_ACQUISITIONS (
	PUBLISHER_ID NUMBER(38,0),
	DEVELOPER_ID NUMBER(38,0),
	ACQUISITION_DATE DATE,
	RETAINED_AUTONOMY BOOLEAN,
	STUDIO_NAME VARCHAR(16777216)
)COMMENT='The table contains records of game studio acquisitions. Each record represents a single acquisition event and includes details about the publisher and developer involved, as well as the date of acquisition and the level of autonomy retained.'
;
