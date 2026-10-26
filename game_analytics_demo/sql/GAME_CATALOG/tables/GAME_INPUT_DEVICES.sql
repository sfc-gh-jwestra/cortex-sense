create or replace TABLE CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_INPUT_DEVICES (
	GAME_INPUT_DEVICE_ID NUMBER(38,0) NOT NULL autoincrement start 1 increment 1 noorder,
	GAME_ID NUMBER(38,0) NOT NULL,
	DEVICE_ID NUMBER(38,0) NOT NULL,
	IS_PRIMARY BOOLEAN DEFAULT FALSE,
	primary key (GAME_INPUT_DEVICE_ID)
)COMMENT='Bridge table linking games to supported input devices. IS_PRIMARY indicates the recommended input method.'
;
