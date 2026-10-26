create or replace TABLE CORTEX_SENSE_DEMO.GAME_SALES.CUSTOMER_ACCOUNTS (
	CUSTOMER_ID NUMBER(38,0) NOT NULL autoincrement start 1 increment 1 noorder,
	PLATFORM_ID NUMBER(38,0),
	REGION VARCHAR(16777216),
	ACCOUNT_CREATED_DATE DATE,
	STATUS VARCHAR(1),
	primary key (CUSTOMER_ID)
)COMMENT='Platform network accounts (PSN-style) that buy hardware, buy digital products, and hold subscriptions. PLATFORM_ID is the account home network.'
;
