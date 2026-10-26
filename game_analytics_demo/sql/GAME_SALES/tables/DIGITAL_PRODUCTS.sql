create or replace TABLE CORTEX_SENSE_DEMO.GAME_SALES.DIGITAL_PRODUCTS (
	DIGITAL_PRODUCT_ID NUMBER(38,0) NOT NULL autoincrement start 1 increment 1 noorder,
	TITLE_ID NUMBER(38,0),
	CATEGORY_ID NUMBER(38,0) NOT NULL,
	PRODUCT_NAME VARCHAR(16777216) NOT NULL,
	LIST_PRICE FLOAT,
	CURRENCY_CODE VARCHAR(3) DEFAULT 'USD',
	IS_CONSUMABLE BOOLEAN DEFAULT FALSE,
	RELEASE_DATE DATE,
	SKU_CODE VARCHAR(16777216),
	STATUS VARCHAR(16777216),
	primary key (DIGITAL_PRODUCT_ID)
)COMMENT='Unified SKU catalog for every digital good: base games, DLC, expansions, season and battle passes, cosmetics, consumables, loot boxes, and virtual currency bundles. GAME_ID is null for platform-wide items.'
;
