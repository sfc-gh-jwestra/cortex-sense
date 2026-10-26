create or replace TABLE CORTEX_SENSE_DEMO.GAME_CATALOG.GENRE_RULES (
	GENRE_RULE_ID NUMBER(38,0) NOT NULL autoincrement start 1 increment 1 noorder,
	GENRE VARCHAR(16777216),
	RULE_DEFINITION VARCHAR(16777216),
	DISJOINT_WITH VARCHAR(16777216),
	PARENT_GENRE VARCHAR(16777216) COMMENT 'Single parent genre (subClassOf), aligned to VIDEOWL.ONT_CLASS. NULL only for the root Genre.',
	primary key (GENRE_RULE_ID)
)COMMENT='The table contains rules governing game genres, specifically categorizations and relationships between them. Each record represents a single genre rule, including its definition and relationships to other genres.'
;
