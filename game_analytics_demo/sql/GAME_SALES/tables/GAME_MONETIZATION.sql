create or replace TABLE CORTEX_SENSE_DEMO.GAME_SALES.GAME_MONETIZATION (
	TITLE_ID NUMBER(38,0) NOT NULL,
	MONETIZATION_ID NUMBER(38,0) NOT NULL,
	primary key (TITLE_ID, MONETIZATION_ID),
	foreign key (MONETIZATION_ID) references CORTEX_SENSE_DEMO.GAME_SALES.MONETIZATION_TYPES(MONETIZATION_ID)
)COMMENT='Sales system copy: monetization models each game uses. Drives the synthetic sales profile (SP_GEN_CATALOG). Kept in sync by the add-game-data-ontology skill.'
;
