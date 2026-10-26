create or replace view CORTEX_SENSE_DEMO.GAME_CATALOG.VW_GENRE_HIERARCHY(
	GENRE,
	PARENT_GENRE,
	DEPTH,
	PATH,
	IS_LEAF,
	HAS_RULE
) COMMENT='The table contains a hierarchical structure of genres, with each record representing a specific genre and its relationships to other genres. Each record includes details about the genre''s position in the hierarchy, including its parent genre and depth level, as well as whether it is a leaf node and if it has any associated rules.'
 as
WITH RECURSIVE tree AS (
    SELECT GENRE, PARENT_GENRE, 0 AS DEPTH, GENRE::VARCHAR AS PATH, RULE_DEFINITION
    FROM CORTEX_SENSE_DEMO.GAME_CATALOG.GENRE_RULES
    WHERE PARENT_GENRE IS NULL
    UNION ALL
    SELECT c.GENRE, c.PARENT_GENRE, t.DEPTH + 1, t.PATH || ' > ' || c.GENRE, c.RULE_DEFINITION
    FROM CORTEX_SENSE_DEMO.GAME_CATALOG.GENRE_RULES c
    JOIN tree t ON c.PARENT_GENRE = t.GENRE
)
SELECT t.GENRE, t.PARENT_GENRE, t.DEPTH, t.PATH,
       NOT EXISTS (SELECT 1 FROM CORTEX_SENSE_DEMO.GAME_CATALOG.GENRE_RULES c WHERE c.PARENT_GENRE = t.GENRE) AS IS_LEAF,
       t.RULE_DEFINITION IS NOT NULL AS HAS_RULE
FROM tree t;
