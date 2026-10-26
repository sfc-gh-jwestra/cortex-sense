create or replace TABLE CORTEX_SENSE_DEMO.GAME_SALES.SUBSCRIPTION_PLANS (
	PLAN_ID NUMBER(38,0) NOT NULL autoincrement start 1 increment 1 noorder,
	PLAN_NAME VARCHAR(16777216) NOT NULL,
	PLAN_TIER VARCHAR(16777216),
	GAME_ID NUMBER(38,0),
	BILLING_CYCLE VARCHAR(16777216),
	LIST_PRICE FLOAT,
	CURRENCY_CODE VARCHAR(3) DEFAULT 'USD',
	primary key (PLAN_ID)
)COMMENT='Subscription plan catalog. GAME_ID null means a platform-wide plan (e.g. PS Plus Essential/Extra/Premium); non-null means a single game subscription. BILLING_CYCLE is MONTHLY, QUARTERLY, or ANNUAL.'
;
