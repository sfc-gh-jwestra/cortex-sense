create or replace TABLE CORTEX_SENSE_DEMO.GAME_CATALOG.BACKUP_GAME_GENRE_CLASSIFICATION_20261009 (
	GAME_ID NUMBER(38,0) NOT NULL,
	GAME_NAME VARCHAR(16777216),
	GENRE VARCHAR(16777216) NOT NULL,
	MATCH_STATUS VARCHAR(16777216) NOT NULL,
	MATCH_SCORE FLOAT,
	TOTAL_CONDITIONS NUMBER(38,0),
	MET_CONDITIONS NUMBER(38,0),
	MATCHED_CONDITIONS VARIANT,
	MISSING_CONDITIONS VARIANT,
	UNKNOWN_CONDITIONS VARIANT,
	CLASSIFIED_AT TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP(),
	primary key (GAME_ID, GENRE)
)COMMENT='The table contains records of game classification, specifically categorizing games by genre. Each record represents a single game and includes details about its classification status, score, and condition matching information.\nGAME_GENRE_CLASSIFICATION is used by GENRE_WHITESPACE_ANALYSIS (to count games per genre pair) and VW_GAME_OVERLAP_MATRIX (to compute genre overlap between games via Jaccard similarity), which feeds GAME_SIMILARITY_SCORES, which feeds VW_CANNIBALIZATION_CANDIDATES.'
;
