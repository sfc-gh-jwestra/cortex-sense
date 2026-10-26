create or replace view CORTEX_SENSE_DEMO.GAME_CATALOG.DISJOINT_GENRE_PAIRS(
	GENRE_A,
	GENRE_B,
	REASON
) COMMENT='The table contains records of relationships between different genres. Each record represents a pair of genres and includes the reason for their connection.'
 as
SELECT GENRE AS GENRE_A, TRIM(VALUE::STRING) AS GENRE_B,
       'Declared disjoint in GENRE_RULES' AS REASON
FROM CORTEX_SENSE_DEMO.GAME_CATALOG.GENRE_RULES, LATERAL FLATTEN(INPUT => SPLIT(DISJOINT_WITH, ','))
WHERE DISJOINT_WITH IS NOT NULL AND DISJOINT_WITH != '' AND DISJOINT_WITH != 'None';
