create or replace TABLE CORTEX_SENSE_DEMO.GAME_SALES.SUBSCRIPTION_CHARGES (
	CHARGE_ID NUMBER(38,0) NOT NULL autoincrement start 1 increment 1 noorder,
	PLAN_ID NUMBER(38,0) NOT NULL,
	SUBSCRIBER_ID NUMBER(38,0) NOT NULL,
	CHARGE_TIMESTAMP TIMESTAMP_NTZ(9) NOT NULL,
	BILLING_PERIOD_START DATE,
	BILLING_PERIOD_END DATE,
	GROSS_REVENUE FLOAT,
	primary key (CHARGE_ID),
	foreign key (PLAN_ID) references CORTEX_SENSE_DEMO.GAME_SALES.SUBSCRIPTION_PLANS(PLAN_ID)
)COMMENT='One row per recurring subscription billing event. Charges on game-specific plans roll into per-game MONTHLY_REVENUE; platform-wide plan charges roll only into VW_PLATFORM_REVENUE_SUMMARY.'
;
