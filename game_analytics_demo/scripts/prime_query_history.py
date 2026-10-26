"""
Prime QUERY_HISTORY and ACCESS_HISTORY for Cortex Sense discovery.

Four groups of queries, all of which follow the rules in scripts/record_feedback.py
(never add a query here that breaks one -- Cortex Sense learns join patterns from history):

  1. SEMANTIC_VIEW(...) queries against CORTEX_SENSE_DEMO.GAME_SALES.SV_GAME_SALES
  2. Cross-domain queries (GAME_SALES revenue x GAME_CATALOG attributes), one or more per rule
  3. Catalog-only queries backing the catalog rules
  4. SQL used by the Streamlit dashboard (streamlits/streamlit_app.py), with fixed parameters
     and with the dashboard's rule-breaking joins corrected (see notes inline)

Rules applied throughout:
  - sales -> catalog only via SELECT DISTINCT TITLE_ID, CATALOG_GAME_ID FROM TITLE_CODE_XREF
    (never TITLES.CATALOG_GAME_ID); unmapped titles reported as 'Unmapped'
  - a digital transaction's title comes from DIGITAL_PRODUCTS.TITLE_ID, not the transaction
  - MONTHLY_REVENUE: sum MONTHLY_INCOME (never CUMULATIVE_INCOME); REVENUE_SOURCE is the
    monetization type; launch/early/tail phases derive from months since TITLES.RELEASE_DATE
    (YYYYMMDD string); never added to digital transaction revenue
  - genres: MATCH_STATUS = 'FULL', or VW_GAME_GENRE_ROLLUP for top-level; overlapping totals
  - publisher filters use each schema's own spelling ('SIE' vs 'Sony Interactive Entertainment')
  - total company revenue = hardware + subscriptions + digital gross, each summed separately
  - exclusivity income counted once per title

Rerunnable -- executing multiple times just adds more history entries.

QUERIES is the source of truth. A full install runs them through install/05-prime-query-history.sql
(generated from QUERIES by scripts/generate_install_sql.py); this script runs them directly.

Usage:
    python3 scripts/prime_query_history.py
"""

import json
import os
import subprocess
import sys

DB = "CORTEX_SENSE_DEMO"
S = f"{DB}.GAME_SALES"
C = f"{DB}.GAME_CATALOG"
SV = f"{S}.SV_GAME_SALES"
CONNECTION = os.environ.get("SNOWFLAKE_CONNECTION_NAME", "CORTEX_SENSE_DEMO_CONN")

# Sales titles -> catalog games. One xref row per title code, so dedupe first.
TITLE_MAP = f"SELECT DISTINCT TITLE_ID, CATALOG_GAME_ID FROM {S}.TITLE_CODE_XREF"
# Fixed stand-ins for the dashboard's default filters (3 years ending 2026-10-08, monthly grain).
START, END = "2023-10-09", "2026-10-09"
TITLE_START, TITLE_END = "2023-10-01", "2026-10-08"

QUERIES = [
    # ═══════════════════════════════════════════════════════════════
    # 1. SEMANTIC_VIEW queries against SV_GAME_SALES
    # ═══════════════════════════════════════════════════════════════
    ("SV: digital revenue by title", f"""
SELECT * FROM SEMANTIC_VIEW({SV}
    DIMENSIONS titles.title_name
    METRICS digital_transactions.total_gross_revenue, digital_transactions.total_net_developer_revenue)
ORDER BY total_gross_revenue DESC LIMIT 20"""),

    ("SV: digital revenue by monetization type", f"""
SELECT * FROM SEMANTIC_VIEW({SV}
    DIMENSIONS revenue_types.category_group, revenue_types.monetization_type
    METRICS digital_transactions.total_gross_revenue, digital_transactions.transaction_count)
ORDER BY total_gross_revenue DESC"""),

    ("SV: gross vs net digital revenue by platform", f"""
SELECT * FROM SEMANTIC_VIEW({SV}
    DIMENSIONS sales_platforms.platform_name
    METRICS digital_transactions.total_gross_revenue, digital_transactions.total_net_developer_revenue)
ORDER BY total_gross_revenue DESC"""),

    ("SV: total company revenue by stream (each summed separately)", f"""
SELECT * FROM SEMANTIC_VIEW({SV}
    METRICS hardware_sales.hardware_gross_revenue,
            subscription_charges.subscription_gross_revenue,
            digital_transactions.total_gross_revenue)"""),

    ("SV: hardware revenue by product type", f"""
SELECT * FROM SEMANTIC_VIEW({SV}
    DIMENSIONS hardware_products.product_type
    METRICS hardware_sales.hardware_gross_revenue)
ORDER BY hardware_gross_revenue DESC"""),

    ("SV: hardware revenue by region", f"""
SELECT * FROM SEMANTIC_VIEW({SV}
    DIMENSIONS hardware_sales.region
    METRICS hardware_sales.hardware_gross_revenue)
ORDER BY hardware_gross_revenue DESC"""),

    ("SV: subscription revenue by plan tier", f"""
SELECT * FROM SEMANTIC_VIEW({SV}
    DIMENSIONS subscription_plans.plan_tier, subscription_plans.plan_name
    METRICS subscription_charges.subscription_gross_revenue)
ORDER BY subscription_gross_revenue DESC"""),

    ("SV: monthly digital revenue trend", f"""
SELECT * FROM SEMANTIC_VIEW({SV}
    DIMENSIONS monthly_revenue.revenue_month
    METRICS monthly_revenue.total_monthly_income)
ORDER BY revenue_month"""),

    ("SV: monthly revenue by monetization type (REVENUE_SOURCE)", f"""
SELECT * FROM SEMANTIC_VIEW({SV}
    DIMENSIONS monthly_revenue.revenue_source
    METRICS monthly_revenue.total_monthly_income)
ORDER BY total_monthly_income DESC"""),

    ("SV: Sony (PUBLISHER_LABEL = 'SIE') digital revenue by studio", f"""
SELECT * FROM SEMANTIC_VIEW({SV}
    DIMENSIONS titles.studio
    METRICS digital_transactions.total_gross_revenue
    WHERE titles.publisher_label = 'SIE')
ORDER BY total_gross_revenue DESC"""),

    ("SV: customers by region and status", f"""
SELECT * FROM SEMANTIC_VIEW({SV}
    DIMENSIONS customers.region, customers.status
    METRICS customers.customer_count)
ORDER BY customer_count DESC"""),

    ("SV: titles by exclusivity type", f"""
SELECT * FROM SEMANTIC_VIEW({SV}
    DIMENSIONS sales_game_platforms.exclusivity_type
    METRICS sales_game_platforms.game_platform_count)
ORDER BY game_platform_count DESC"""),

    # ═══════════════════════════════════════════════════════════════
    # 2. Cross-domain queries: GAME_SALES revenue x GAME_CATALOG attributes
    # ═══════════════════════════════════════════════════════════════
    ("Revenue: top 5 revenue earners (title level, no percentile cutoff)", f"""
SELECT t.TITLE_NAME, r.INCOME
FROM {S}.GAME_REVENUE r
JOIN {S}.TITLES t ON t.TITLE_ID = r.TITLE_ID
ORDER BY r.INCOME DESC LIMIT 5"""),

    ("Revenue: lifetime revenue by franchise", f"""
WITH title_map AS ({TITLE_MAP})
SELECT COALESCE(g.FRANCHISE_NAME, 'Unmapped') AS franchise,
       SUM(r.INCOME) AS income, COUNT(DISTINCT r.TITLE_ID) AS titles
FROM {S}.GAME_REVENUE r
LEFT JOIN title_map x ON x.TITLE_ID = r.TITLE_ID
LEFT JOIN {C}.GAMES g ON g.GAME_ID = x.CATALOG_GAME_ID
GROUP BY 1 ORDER BY income DESC"""),

    ("Revenue: by developer (display names without underscores)", f"""
WITH title_map AS ({TITLE_MAP})
SELECT COALESCE(REPLACE(g.DEVELOPER_NAME, '_', ' '), 'Unmapped') AS developer,
       SUM(r.INCOME) AS income, COUNT(DISTINCT r.TITLE_ID) AS titles
FROM {S}.GAME_REVENUE r
LEFT JOIN title_map x ON x.TITLE_ID = r.TITLE_ID
LEFT JOIN {C}.GAMES g ON g.GAME_ID = x.CATALOG_GAME_ID
GROUP BY 1 ORDER BY income DESC"""),

    ("Revenue: indie vs studio", f"""
WITH title_map AS ({TITLE_MAP})
SELECT CASE WHEN g.GAME_ID IS NULL THEN 'Unmapped'
            WHEN g.DEVELOPER_IS_INDIE THEN 'Indie' ELSE 'Studio' END AS developer_type,
       SUM(r.INCOME) AS income, COUNT(DISTINCT r.TITLE_ID) AS titles
FROM {S}.GAME_REVENUE r
LEFT JOIN title_map x ON x.TITLE_ID = r.TITLE_ID
LEFT JOIN {C}.GAMES g ON g.GAME_ID = x.CATALOG_GAME_ID
GROUP BY 1 ORDER BY income DESC"""),

    ("Revenue: Sony revenue by publisher, filtered in each schema's own spelling", f"""
WITH title_map AS ({TITLE_MAP})
SELECT COALESCE(g.PUBLISHER_NAME, 'Unmapped') AS publisher,
       SUM(r.INCOME) AS income, COUNT(DISTINCT r.TITLE_ID) AS titles
FROM {S}.GAME_REVENUE r
JOIN {S}.TITLES t ON t.TITLE_ID = r.TITLE_ID AND t.PUBLISHER_LABEL = 'SIE'
LEFT JOIN title_map x ON x.TITLE_ID = r.TITLE_ID
LEFT JOIN {C}.GAMES g ON g.GAME_ID = x.CATALOG_GAME_ID
    AND g.PUBLISHER_NAME = 'Sony Interactive Entertainment'
GROUP BY 1"""),

    ("Genre revenue: fully matched genres (overlapping totals), unmatched reported", f"""
WITH title_map AS ({TITLE_MAP})
SELECT COALESCE(gg.GENRE, IFF(x.TITLE_ID IS NULL, 'Unmapped', 'No full genre match')) AS genre,
       SUM(r.INCOME) AS income, COUNT(DISTINCT x.CATALOG_GAME_ID) AS games
FROM {S}.GAME_REVENUE r
LEFT JOIN title_map x ON x.TITLE_ID = r.TITLE_ID
LEFT JOIN {C}.GAME_GENRE_CLASSIFICATION gg
    ON gg.GAME_ID = x.CATALOG_GAME_ID AND gg.MATCH_STATUS = 'FULL'
GROUP BY 1 ORDER BY income DESC"""),

    ("Genre revenue: top-level genres via VW_GAME_GENRE_ROLLUP", f"""
WITH title_map AS ({TITLE_MAP})
SELECT gr.ROLLUP_GENRE AS genre, SUM(r.INCOME) AS income, COUNT(DISTINCT gr.GAME_ID) AS games
FROM {S}.GAME_REVENUE r
JOIN title_map x ON x.TITLE_ID = r.TITLE_ID
JOIN {C}.VW_GAME_GENRE_ROLLUP gr ON gr.GAME_ID = x.CATALOG_GAME_ID AND gr.ROLLUP_DEPTH = 1
GROUP BY 1 ORDER BY income DESC"""),

    ("Revenue: by game engine", f"""
WITH title_map AS ({TITLE_MAP})
SELECT e.ENGINE_NAME, SUM(r.INCOME) AS income, COUNT(DISTINCT ge.GAME_ID) AS games
FROM {S}.GAME_REVENUE r
JOIN title_map x ON x.TITLE_ID = r.TITLE_ID
JOIN {C}.GAME_ENGINES ge ON ge.GAME_ID = x.CATALOG_GAME_ID
JOIN {C}.ENGINES e ON e.ENGINE_ID = ge.ENGINE_ID
GROUP BY 1 ORDER BY income DESC"""),

    ("Revenue: currently exclusive titles (income counted once per title)", f"""
SELECT COUNT(*) AS exclusive_titles, SUM(INCOME) AS exclusive_income
FROM (SELECT DISTINCT TITLE_ID, INCOME FROM {S}.VW_PLATFORM_EXCLUSIVITY
      WHERE IS_CURRENTLY_EXCLUSIVE = TRUE)"""),

    ("Monetization risk: income by monetization type x exclusivity", f"""
WITH excl AS (
  SELECT TITLE_ID, MAX(INCOME) AS INCOME, BOOLOR_AGG(IS_CURRENTLY_EXCLUSIVE) AS is_exclusive
  FROM {S}.VW_PLATFORM_EXCLUSIVITY GROUP BY 1)
SELECT mt.MONETIZATION_NAME,
       IFF(e.is_exclusive, 'Currently exclusive', 'Not exclusive') AS exclusivity,
       COUNT(DISTINCT e.TITLE_ID) AS titles, SUM(e.INCOME) AS income
FROM excl e
JOIN {S}.GAME_MONETIZATION gm ON gm.TITLE_ID = e.TITLE_ID
JOIN {S}.MONETIZATION_TYPES mt ON mt.MONETIZATION_ID = gm.MONETIZATION_ID
GROUP BY 1, 2 ORDER BY income DESC"""),

    ("Lifecycle: launch month, early life, tail (derived from release date)", f"""
SELECT CASE WHEN DATEDIFF(MONTH, DATE_TRUNC('MONTH', TO_DATE(t.RELEASE_DATE, 'YYYYMMDD')), m.REVENUE_MONTH) = 0
            THEN 'Launch month'
            WHEN DATEDIFF(MONTH, DATE_TRUNC('MONTH', TO_DATE(t.RELEASE_DATE, 'YYYYMMDD')), m.REVENUE_MONTH) BETWEEN 1 AND 5
            THEN 'Early life (months 1-5)'
            ELSE 'Tail (month 6+)' END AS lifecycle_phase,
       SUM(m.MONTHLY_INCOME) AS revenue, COUNT(DISTINCT m.TITLE_ID) AS titles
FROM {S}.MONTHLY_REVENUE m
JOIN {S}.TITLES t ON t.TITLE_ID = m.TITLE_ID
GROUP BY 1 ORDER BY MIN(DATEDIFF(MONTH, DATE_TRUNC('MONTH', TO_DATE(t.RELEASE_DATE, 'YYYYMMDD')), m.REVENUE_MONTH))"""),

    ("Lifecycle: award winners vs others, average launch-month revenue", f"""
WITH title_map AS ({TITLE_MAP}),
winners AS (SELECT DISTINCT GAME_ID FROM {C}.GAME_AWARDS WHERE WON_OR_NOMINATED = 'won'),
launch AS (
  SELECT m.TITLE_ID, SUM(m.MONTHLY_INCOME) AS launch_income
  FROM {S}.MONTHLY_REVENUE m
  JOIN {S}.TITLES t ON t.TITLE_ID = m.TITLE_ID
  WHERE DATE_TRUNC('MONTH', m.REVENUE_MONTH) = DATE_TRUNC('MONTH', TO_DATE(t.RELEASE_DATE, 'YYYYMMDD'))
  GROUP BY 1)
SELECT CASE WHEN x.TITLE_ID IS NULL THEN 'Unmapped'
            WHEN w.GAME_ID IS NOT NULL THEN 'Award winner' ELSE 'No awards' END AS award_status,
       AVG(l.launch_income) AS avg_launch_income, COUNT(*) AS titles
FROM launch l
LEFT JOIN title_map x ON x.TITLE_ID = l.TITLE_ID
LEFT JOIN winners w ON w.GAME_ID = x.CATALOG_GAME_ID
GROUP BY 1"""),

    ("Quarterly: Sony quarterly revenue (sales spelling 'SIE')", f"""
SELECT q.REVENUE_YEAR, q.REVENUE_QUARTER, SUM(q.QUARTERLY_INCOME) AS quarterly_income
FROM {S}.QUARTERLY_REVENUE q
JOIN {S}.TITLES t ON t.TITLE_ID = q.TITLE_ID
WHERE t.PUBLISHER_LABEL = 'SIE'
GROUP BY 1, 2 ORDER BY 1, 2"""),

    ("Quarterly: Q1 year-over-year", f"""
SELECT REVENUE_YEAR, SUM(QUARTERLY_INCOME) AS q1_income,
       SUM(QUARTERLY_INCOME) - LAG(SUM(QUARTERLY_INCOME)) OVER (ORDER BY REVENUE_YEAR) AS yoy_change
FROM {S}.QUARTERLY_REVENUE
WHERE REVENUE_QUARTER = 1
GROUP BY 1 ORDER BY 1"""),

    ("Quarterly: franchise revenue by year", f"""
WITH title_map AS ({TITLE_MAP})
SELECT COALESCE(g.FRANCHISE_NAME, 'Unmapped') AS franchise, q.REVENUE_YEAR,
       SUM(q.QUARTERLY_INCOME) AS annual_income
FROM {S}.QUARTERLY_REVENUE q
LEFT JOIN title_map x ON x.TITLE_ID = q.TITLE_ID
LEFT JOIN {C}.GAMES g ON g.GAME_ID = x.CATALOG_GAME_ID
GROUP BY 1, 2 ORDER BY 1, 2"""),

    ("Accessibility: missing features in the top 5 revenue earners", f"""
WITH title_map AS ({TITLE_MAP}),
top5 AS (SELECT TITLE_ID, INCOME FROM {S}.GAME_REVENUE ORDER BY INCOME DESC LIMIT 5)
SELECT t.TITLE_NAME, top5.INCOME,
       COUNT_IF(NOT ag.IS_SUPPORTED) AS missing_features
FROM top5
JOIN {S}.TITLES t ON t.TITLE_ID = top5.TITLE_ID
LEFT JOIN title_map x ON x.TITLE_ID = top5.TITLE_ID
LEFT JOIN {C}.VW_ACCESSIBILITY_GAPS ag ON ag.GAME_ID = x.CATALOG_GAME_ID
GROUP BY 1, 2 ORDER BY top5.INCOME DESC"""),

    ("Accessibility investment: priority score (ranking proxy, not dollars)", f"""
WITH title_map AS ({TITLE_MAP}),
game_income AS (
  SELECT x.CATALOG_GAME_ID AS GAME_ID, SUM(r.INCOME) AS INCOME
  FROM {S}.GAME_REVENUE r JOIN title_map x ON x.TITLE_ID = r.TITLE_ID GROUP BY 1),
family AS (
  SELECT DISTINCT gr.GAME_ID FROM {C}.GAME_RATINGS gr
  JOIN {C}.AGE_RATINGS ar ON ar.RATING_ID = gr.RATING_ID WHERE ar.MIN_AGE <= 10)
SELECT ag.FEATURE_CATEGORY, ag.FEATURE_NAME,
       COUNT(DISTINCT ag.GAME_ID) AS games_missing,
       COUNT(DISTINCT f.GAME_ID) AS family_games_missing,
       COUNT(DISTINCT ag.GAME_ID) * AVG(gi.INCOME) AS priority_score
FROM {C}.VW_ACCESSIBILITY_GAPS ag
JOIN game_income gi ON gi.GAME_ID = ag.GAME_ID
LEFT JOIN family f ON f.GAME_ID = ag.GAME_ID
WHERE NOT ag.IS_SUPPORTED
GROUP BY 1, 2 ORDER BY priority_score DESC"""),

    ("Proven capability proxy: award wins, top-quartile income, 3+ full genres", f"""
WITH title_map AS ({TITLE_MAP}),
game_income AS (
  SELECT x.CATALOG_GAME_ID AS GAME_ID, SUM(r.INCOME) AS INCOME
  FROM {S}.GAME_REVENUE r JOIN title_map x ON x.TITLE_ID = r.TITLE_ID GROUP BY 1),
ranked AS (SELECT GAME_ID, INCOME, NTILE(4) OVER (ORDER BY INCOME DESC) AS income_quartile FROM game_income),
genres AS (SELECT GAME_ID, COUNT(*) AS full_genres FROM {C}.GAME_GENRE_CLASSIFICATION
           WHERE MATCH_STATUS = 'FULL' GROUP BY 1),
wins AS (SELECT GAME_ID, COUNT(*) AS award_wins FROM {C}.GAME_AWARDS
         WHERE WON_OR_NOMINATED = 'won' GROUP BY 1)
SELECT REPLACE(g.DEVELOPER_NAME, '_', ' ') AS studio,
       SUM(COALESCE(w.award_wins, 0)) AS award_wins,
       COUNT_IF(r.income_quartile = 1) AS top_quartile_games,
       COUNT_IF(ge.full_genres >= 3) AS games_with_3plus_genres
FROM {C}.GAMES g
LEFT JOIN ranked r ON r.GAME_ID = g.GAME_ID
LEFT JOIN genres ge ON ge.GAME_ID = g.GAME_ID
LEFT JOIN wins w ON w.GAME_ID = g.GAME_ID
GROUP BY 1 ORDER BY award_wins DESC, top_quartile_games DESC"""),

    ("Breakout hits: top-quartile income or Game of the Year win", f"""
WITH title_map AS ({TITLE_MAP}),
game_income AS (
  SELECT x.CATALOG_GAME_ID AS GAME_ID, SUM(r.INCOME) AS INCOME
  FROM {S}.GAME_REVENUE r JOIN title_map x ON x.TITLE_ID = r.TITLE_ID GROUP BY 1),
ranked AS (SELECT GAME_ID, INCOME, NTILE(4) OVER (ORDER BY INCOME DESC) AS income_quartile FROM game_income),
goty AS (
  SELECT DISTINCT ga.GAME_ID FROM {C}.GAME_AWARDS ga
  JOIN {C}.AWARDS a ON a.AWARD_ID = ga.AWARD_ID
  WHERE ga.WON_OR_NOMINATED = 'won' AND a.AWARD_NAME = 'Game_of_the_Year')
SELECT g.GAME_NAME, g.DEVELOPER_IS_INDIE, r.INCOME,
       r.income_quartile = 1 AS top_quartile_income, gt.GAME_ID IS NOT NULL AS goty_winner
FROM {C}.GAMES g
LEFT JOIN ranked r ON r.GAME_ID = g.GAME_ID
LEFT JOIN goty gt ON gt.GAME_ID = g.GAME_ID
WHERE r.income_quartile = 1 OR gt.GAME_ID IS NOT NULL
ORDER BY r.INCOME DESC NULLS LAST"""),

    ("Release calendar: same-quarter releases with overlapping audiences", f"""
WITH rel AS (
  SELECT GAME_ID, GAME_NAME, YEAR(RELEASE_DATE) AS yr, QUARTER(RELEASE_DATE) AS qtr
  FROM {C}.GAMES WHERE RELEASE_DATE IS NOT NULL)
SELECT a.yr, a.qtr, a.GAME_NAME AS game_a, b.GAME_NAME AS game_b, s.WEIGHTED_OVERLAP, s.OVERLAP_TIER
FROM {C}.GAME_SIMILARITY_SCORES s
JOIN rel a ON a.GAME_ID = s.GAME_A_ID
JOIN rel b ON b.GAME_ID = s.GAME_B_ID
WHERE a.yr = b.yr AND a.qtr = b.qtr AND s.WEIGHTED_OVERLAP >= 0.3
ORDER BY s.WEIGHTED_OVERLAP DESC"""),

    ("Release calendar: catalog releases by year and quarter", f"""
SELECT YEAR(RELEASE_DATE) AS release_year, QUARTER(RELEASE_DATE) AS release_quarter,
       COUNT(*) AS releases
FROM {C}.GAMES WHERE RELEASE_DATE IS NOT NULL
GROUP BY 1, 2 ORDER BY 1, 2"""),

    ("Fiscal year: this fiscal year's digital revenue (fiscal = calendar year)", f"""
SELECT YEAR(REVENUE_MONTH) AS fiscal_year, SUM(MONTHLY_INCOME) AS income
FROM {S}.MONTHLY_REVENUE
WHERE YEAR(REVENUE_MONTH) IN (YEAR(CURRENT_DATE()) - 1, YEAR(CURRENT_DATE()))
GROUP BY 1 ORDER BY 1"""),

    # ═══════════════════════════════════════════════════════════════
    # 3. Catalog-only queries backing the catalog rules
    # ═══════════════════════════════════════════════════════════════
    ("Content rating risk: which of the three criteria each game meets", f"""
WITH mature AS (
  SELECT DISTINCT gr.GAME_ID FROM {C}.GAME_RATINGS gr
  JOIN {C}.AGE_RATINGS ar ON ar.RATING_ID = gr.RATING_ID WHERE ar.MIN_AGE >= 16),
violent_genre AS (
  SELECT DISTINCT GAME_ID FROM {C}.GAME_GENRE_CLASSIFICATION
  WHERE MATCH_STATUS = 'FULL' AND GENRE IN ('Gore', 'Shooter', 'FPS', 'TPS', 'Fighting', 'Horror', 'SurvivalHorror')),
grotesque AS (
  SELECT DISTINCT gc.GAME_ID FROM {C}.GAME_CONTEXTS gc
  JOIN {C}.CONTEXTS c ON c.CONTEXT_ID = gc.CONTEXT_ID
  WHERE c.CONTEXT_NAME IN ('monster_invasion', 'zombies_invasion')),
combat AS (
  SELECT DISTINCT gg.GAME_ID FROM {C}.GAME_GAMEPLAY gg
  JOIN {C}.GAMEPLAY_TYPES gt ON gt.GAMEPLAY_TYPE_ID = gg.GAMEPLAY_TYPE_ID
  WHERE gt.GAMEPLAY_TYPE_NAME IN ('agonistic', 'corpo_a_corpo', 'free_shooting')),
romance AS (
  SELECT gc.GAME_ID FROM {C}.GAME_CONTEXTS gc
  JOIN {C}.CONTEXTS c ON c.CONTEXT_ID = gc.CONTEXT_ID WHERE c.CONTEXT_NAME = 'romance'
  UNION
  SELECT gg.GAME_ID FROM {C}.GAME_GAMEPLAY gg
  JOIN {C}.GAMEPLAY_TYPES gt ON gt.GAMEPLAY_TYPE_ID = gg.GAMEPLAY_TYPE_ID WHERE gt.GAMEPLAY_TYPE_NAME = 'romance_based'
  UNION
  SELECT GAME_ID FROM {C}.GAME_GENRE_CLASSIFICATION WHERE MATCH_STATUS = 'FULL' AND GENRE = 'DatingSim')
SELECT g.GAME_NAME,
       m.GAME_ID IS NOT NULL AS mature_rating,
       (vg.GAME_ID IS NOT NULL OR (gq.GAME_ID IS NOT NULL AND cb.GAME_ID IS NOT NULL)) AS violence,
       r.GAME_ID IS NOT NULL AS romance
FROM {C}.GAMES g
LEFT JOIN mature m ON m.GAME_ID = g.GAME_ID
LEFT JOIN violent_genre vg ON vg.GAME_ID = g.GAME_ID
LEFT JOIN grotesque gq ON gq.GAME_ID = g.GAME_ID
LEFT JOIN combat cb ON cb.GAME_ID = g.GAME_ID
LEFT JOIN romance r ON r.GAME_ID = g.GAME_ID
WHERE m.GAME_ID IS NOT NULL OR vg.GAME_ID IS NOT NULL
   OR (gq.GAME_ID IS NOT NULL AND cb.GAME_ID IS NOT NULL) OR r.GAME_ID IS NOT NULL
ORDER BY g.GAME_NAME"""),

    ("Live-service games: online required + recurring monetization", f"""
SELECT g.GAME_NAME, LISTAGG(DISTINCT mt.MONETIZATION_NAME, ', ') AS recurring_monetization
FROM {C}.GAMES g
JOIN {C}.GAME_MODES gm ON gm.GAME_ID = g.GAME_ID AND gm.ONLINE_REQUIRED = TRUE
JOIN {C}.GAME_MONETIZATION gmo ON gmo.GAME_ID = g.GAME_ID
JOIN {C}.MONETIZATION_TYPES mt ON mt.MONETIZATION_ID = gmo.MONETIZATION_ID
WHERE mt.MONETIZATION_NAME IN ('battle_pass', 'microtransactions', 'subscription', 'loot_boxes')
GROUP BY 1 ORDER BY 1"""),

    ("EU regulatory risk inputs: live-service games with PEGI 18, loot boxes, paid DLC, mobile", f"""
WITH live AS (
  SELECT DISTINCT gm.GAME_ID FROM {C}.GAME_MODES gm
  JOIN {C}.GAME_MONETIZATION gmo ON gmo.GAME_ID = gm.GAME_ID
  JOIN {C}.MONETIZATION_TYPES mt ON mt.MONETIZATION_ID = gmo.MONETIZATION_ID
  WHERE gm.ONLINE_REQUIRED = TRUE
    AND mt.MONETIZATION_NAME IN ('battle_pass', 'microtransactions', 'subscription', 'loot_boxes')),
monet AS (
  SELECT gmo.GAME_ID,
         BOOLOR_AGG(mt.MONETIZATION_NAME = 'loot_boxes') AS paid_loot_boxes,
         BOOLOR_AGG(mt.MONETIZATION_NAME = 'dlc') AS paid_dlc
  FROM {C}.GAME_MONETIZATION gmo
  JOIN {C}.MONETIZATION_TYPES mt ON mt.MONETIZATION_ID = gmo.MONETIZATION_ID GROUP BY 1),
pegi18 AS (
  SELECT DISTINCT gr.GAME_ID FROM {C}.GAME_RATINGS gr
  JOIN {C}.AGE_RATINGS ar ON ar.RATING_ID = gr.RATING_ID
  WHERE ar.RATING_SYSTEM = 'PEGI' AND ar.MIN_AGE >= 18),
mobile AS (
  SELECT DISTINCT gp.GAME_ID FROM {C}.GAME_PLATFORMS gp
  JOIN {C}.PLATFORMS p ON p.PLATFORM_ID = gp.PLATFORM_ID
  WHERE p.PLATFORM_NAME IN ('Android', 'Apple'))
SELECT g.GAME_NAME, p18.GAME_ID IS NOT NULL AS pegi_18,
       COALESCE(mo.paid_loot_boxes, FALSE) AS paid_loot_boxes,
       COALESCE(mo.paid_dlc, FALSE) AS paid_dlc,
       mb.GAME_ID IS NOT NULL AS on_mobile
FROM live l
JOIN {C}.GAMES g ON g.GAME_ID = l.GAME_ID
LEFT JOIN monet mo ON mo.GAME_ID = l.GAME_ID
LEFT JOIN pegi18 p18 ON p18.GAME_ID = l.GAME_ID
LEFT JOIN mobile mb ON mb.GAME_ID = l.GAME_ID
ORDER BY 1"""),

    ("Rating equivalence: ESRB to other systems by MIN_AGE", f"""
SELECT a.RATING_SYSTEM AS source_system, a.RATING_VALUE AS source_rating, a.MIN_AGE,
       b.RATING_SYSTEM AS equiv_system, b.RATING_VALUE AS equiv_rating, b.MIN_AGE AS equiv_min_age
FROM {C}.AGE_RATINGS a
JOIN {C}.AGE_RATINGS b ON a.RATING_SYSTEM != b.RATING_SYSTEM AND b.MIN_AGE <= a.MIN_AGE
WHERE a.RATING_SYSTEM = 'ESRB'
QUALIFY ROW_NUMBER() OVER (PARTITION BY a.RATING_ID, b.RATING_SYSTEM ORDER BY b.MIN_AGE DESC) = 1
ORDER BY a.MIN_AGE, b.RATING_SYSTEM"""),

    ("Awards: wins and nominations by awarding body", f"""
SELECT a.AWARDING_BODY,
       COUNT_IF(ga.WON_OR_NOMINATED = 'won') AS wins,
       COUNT_IF(ga.WON_OR_NOMINATED = 'nominated') AS nominations
FROM {C}.GAME_AWARDS ga
JOIN {C}.AWARDS a ON a.AWARD_ID = ga.AWARD_ID
GROUP BY 1 ORDER BY wins DESC"""),

    ("Accessibility: games missing each feature by category", f"""
SELECT FEATURE_CATEGORY, FEATURE_NAME, COUNT(*) AS games_missing
FROM {C}.VW_ACCESSIBILITY_GAPS
WHERE NOT IS_SUPPORTED
GROUP BY 1, 2 ORDER BY games_missing DESC"""),

    ("Audience profile: full genres, platform reach and narrative style per game", f"""
SELECT g.GAME_NAME, ns.STRUCTURE_NAME AS narrative_style,
       LISTAGG(DISTINCT gg.GENRE, ', ') AS full_genres,
       COUNT(DISTINCT gp.PLATFORM_ID) AS platforms
FROM {C}.GAMES g
LEFT JOIN {C}.NARRATIVE_STRUCTURES ns ON ns.STRUCTURE_ID = g.NARRATIVE_STRUCTURE_ID
LEFT JOIN {C}.GAME_GENRE_CLASSIFICATION gg ON gg.GAME_ID = g.GAME_ID AND gg.MATCH_STATUS = 'FULL'
LEFT JOIN {C}.GAME_PLATFORMS gp ON gp.GAME_ID = g.GAME_ID
GROUP BY 1, 2 ORDER BY 1"""),

    ("Audience comparison: similarity score for a pair, checked in both directions", f"""
SELECT GAME_A_NAME, GAME_B_NAME, WEIGHTED_OVERLAP, OVERLAP_TIER,
       GENRE_OVERLAP, PLATFORM_OVERLAP, MECHANIC_OVERLAP, GAMEPLAY_OVERLAP, NARRATIVE_MATCH
FROM {C}.GAME_SIMILARITY_SCORES
WHERE (GAME_A_NAME ILIKE '%god_of_war%' AND GAME_B_NAME ILIKE '%last_of_us%')
   OR (GAME_B_NAME ILIKE '%god_of_war%' AND GAME_A_NAME ILIKE '%last_of_us%')
ORDER BY WEIGHTED_OVERLAP DESC"""),

    ("Audience comparison: highly cannibalized pairs (OVERLAP_TIER = 'HIGH')", f"""
SELECT GAME_A_NAME, GAME_B_NAME, WEIGHTED_OVERLAP, OVERLAP_TIER
FROM {C}.GAME_SIMILARITY_SCORES
WHERE OVERLAP_TIER = 'HIGH'
ORDER BY WEIGHTED_OVERLAP DESC LIMIT 20"""),

    ("Franchise cannibalization: pre-filtered same-publisher candidates", f"""
SELECT GAME_A_NAME, GAME_B_NAME, PUBLISHER_NAME, WEIGHTED_OVERLAP,
       GENRE_OVERLAP, PLATFORM_OVERLAP, MECHANIC_OVERLAP, GAMEPLAY_OVERLAP, OVERLAP_TIER
FROM {C}.VW_CANNIBALIZATION_CANDIDATES
WHERE WEIGHTED_OVERLAP >= 0.3
ORDER BY WEIGHTED_OVERLAP DESC"""),

    ("Emerging genre proxy: underserved and whitespace genre pairs (supply, not demand)", f"""
SELECT GENRE_A, GENRE_B, GAME_COUNT, MARKET_STATUS
FROM {C}.GENRE_WHITESPACE_ANALYSIS
WHERE MARKET_STATUS IN ('UNDERSERVED', 'WHITESPACE')
ORDER BY GAME_COUNT, GENRE_A, GENRE_B"""),

    ("Engines: game counts by engine", f"""
SELECT e.ENGINE_NAME, COUNT(DISTINCT ge.GAME_ID) AS games
FROM {C}.GAME_ENGINES ge
JOIN {C}.ENGINES e ON e.ENGINE_ID = ge.ENGINE_ID
GROUP BY 1 ORDER BY games DESC"""),

    ("Release date: catalog games released in the last fiscal year", f"""
SELECT GAME_NAME, RELEASE_DATE
FROM {C}.GAMES
WHERE YEAR(RELEASE_DATE) = YEAR(CURRENT_DATE()) - 1
ORDER BY RELEASE_DATE"""),

    # ═══════════════════════════════════════════════════════════════
    # 4. Streamlit dashboard SQL (default filters: 3 years, monthly grain)
    # ═══════════════════════════════════════════════════════════════
    ("Dashboard overview: revenue by stream (each stream summed separately)", f"""
SELECT DATE_TRUNC('month', t.transaction_timestamp)::date AS period, 'Digital' AS stream,
       SUM(t.gross_revenue) AS revenue, SUM(t.quantity) AS units
FROM {S}.DIGITAL_PRODUCT_TRANSACTIONS t
WHERE t.transaction_timestamp >= '{START}' AND t.transaction_timestamp < '{END}'
GROUP BY 1,2
UNION ALL
SELECT DATE_TRUNC('month', t.sale_timestamp)::date, 'Hardware', SUM(t.gross_revenue), SUM(t.quantity)
FROM {S}.HARDWARE_SALES_TRANSACTIONS t
JOIN {S}.HARDWARE_PRODUCTS h ON h.hardware_product_id = t.hardware_product_id
WHERE t.sale_timestamp >= '{START}' AND t.sale_timestamp < '{END}'
GROUP BY 1,2
UNION ALL
SELECT DATE_TRUNC('month', charge_timestamp)::date, 'Subscription', SUM(gross_revenue), COUNT(*)
FROM {S}.SUBSCRIPTION_CHARGES
WHERE charge_timestamp >= '{START}' AND charge_timestamp < '{END}'
GROUP BY 1,2
ORDER BY 1,2"""),

    ("Dashboard overview: KPIs", f"""
SELECT
  (SELECT COALESCE(SUM(gross_revenue),0) FROM {S}.DIGITAL_PRODUCT_TRANSACTIONS
     WHERE transaction_timestamp >= '{START}' AND transaction_timestamp < '{END}') AS digital,
  (SELECT COALESCE(SUM(net_developer_revenue),0) FROM {S}.DIGITAL_PRODUCT_TRANSACTIONS
     WHERE transaction_timestamp >= '{START}' AND transaction_timestamp < '{END}') AS digital_net,
  (SELECT COALESCE(SUM(t.gross_revenue),0) FROM {S}.HARDWARE_SALES_TRANSACTIONS t
     JOIN {S}.HARDWARE_PRODUCTS h ON h.hardware_product_id = t.hardware_product_id
     WHERE t.sale_timestamp >= '{START}' AND t.sale_timestamp < '{END}') AS hardware,
  (SELECT COALESCE(SUM(t.quantity),0) FROM {S}.HARDWARE_SALES_TRANSACTIONS t
     JOIN {S}.HARDWARE_PRODUCTS h ON h.hardware_product_id = t.hardware_product_id
     WHERE t.sale_timestamp >= '{START}' AND t.sale_timestamp < '{END}') AS hw_units,
  (SELECT COALESCE(SUM(gross_revenue),0) FROM {S}.SUBSCRIPTION_CHARGES
     WHERE charge_timestamp >= '{START}' AND charge_timestamp < '{END}') AS subs,
  (SELECT COUNT(DISTINCT subscriber_id) FROM {S}.SUBSCRIPTION_CHARGES
     WHERE charge_timestamp >= '{START}' AND charge_timestamp < '{END}') AS subscribers"""),

    ("Dashboard digital: gross and net by platform over time", f"""
SELECT DATE_TRUNC('month', t.transaction_timestamp)::date AS period, pl.platform_name,
       SUM(t.gross_revenue) AS gross_revenue, SUM(t.net_developer_revenue) AS net_revenue
FROM {S}.DIGITAL_PRODUCT_TRANSACTIONS t JOIN {S}.PLATFORMS pl ON pl.platform_id = t.platform_id
WHERE t.transaction_timestamp >= '{START}' AND t.transaction_timestamp < '{END}'
GROUP BY 1,2 ORDER BY 1"""),

    # Dashboard joins TITLES on the transaction's TITLE_ID (NULL for ~10% of revenue);
    # the rule-compliant version takes the title from the product.
    ("Dashboard digital: top 15 products (title via product)", f"""
SELECT dp.product_name, ti.title_name, SUM(t.gross_revenue) AS gross_revenue, SUM(t.quantity) AS units
FROM {S}.DIGITAL_PRODUCT_TRANSACTIONS t
JOIN {S}.DIGITAL_PRODUCTS dp ON dp.digital_product_id = t.digital_product_id
JOIN {S}.TITLES ti ON ti.title_id = dp.title_id
WHERE t.transaction_timestamp >= '{START}' AND t.transaction_timestamp < '{END}'
GROUP BY 1,2 ORDER BY 3 DESC LIMIT 15"""),

    ("Dashboard digital: revenue by monetization type", f"""
SELECT rt.monetization_type, IFF(dp.is_consumable, 'Consumable', 'Durable') AS kind,
       SUM(t.gross_revenue) AS gross_revenue
FROM {S}.DIGITAL_PRODUCT_TRANSACTIONS t
JOIN {S}.DIGITAL_PRODUCTS dp ON dp.digital_product_id = t.digital_product_id
JOIN {S}.REVENUE_TYPES rt ON rt.category_id = dp.category_id
WHERE t.transaction_timestamp >= '{START}' AND t.transaction_timestamp < '{END}'
GROUP BY 1,2 ORDER BY 3 DESC"""),

    ("Dashboard digital: platform commission by platform", f"""
SELECT pl.platform_name, SUM(t.gross_revenue) AS gross_revenue,
       SUM(t.gross_revenue - t.net_developer_revenue) AS commission,
       AVG(t.platform_commission_pct) AS avg_commission_pct
FROM {S}.DIGITAL_PRODUCT_TRANSACTIONS t JOIN {S}.PLATFORMS pl ON pl.platform_id = t.platform_id
WHERE t.transaction_timestamp >= '{START}' AND t.transaction_timestamp < '{END}'
GROUP BY 1 ORDER BY 2 DESC"""),

    ("Dashboard digital: top 15 titles by net developer revenue (title via product)", f"""
SELECT ti.title_name, ti.studio, SUM(t.net_developer_revenue) AS net_revenue,
       COUNT(DISTINCT t.player_id) AS buyers
FROM {S}.DIGITAL_PRODUCT_TRANSACTIONS t
JOIN {S}.DIGITAL_PRODUCTS dp ON dp.digital_product_id = t.digital_product_id
JOIN {S}.TITLES ti ON ti.title_id = dp.title_id
WHERE t.transaction_timestamp >= '{START}' AND t.transaction_timestamp < '{END}'
GROUP BY 1,2 ORDER BY 3 DESC LIMIT 15"""),

    ("Dashboard digital: purchases by hour and weekday", f"""
SELECT DAYNAME(t.transaction_timestamp) AS weekday, DAYOFWEEKISO(t.transaction_timestamp) AS dow,
       HOUR(t.transaction_timestamp) AS hour, COUNT(*) AS transactions
FROM {S}.DIGITAL_PRODUCT_TRANSACTIONS t
WHERE t.transaction_timestamp >= '{START}' AND t.transaction_timestamp < '{END}'
GROUP BY 1,2,3"""),

    ("Dashboard hardware: revenue by product type over time", f"""
SELECT DATE_TRUNC('month', t.sale_timestamp)::date AS period, h.product_type,
       SUM(t.gross_revenue) AS gross_revenue, SUM(t.quantity) AS units
FROM {S}.HARDWARE_SALES_TRANSACTIONS t
JOIN {S}.HARDWARE_PRODUCTS h ON h.hardware_product_id = t.hardware_product_id
WHERE t.sale_timestamp >= '{START}' AND t.sale_timestamp < '{END}'
GROUP BY 1,2 ORDER BY 1"""),

    ("Dashboard hardware: revenue by region and product type", f"""
SELECT t.region, h.product_type, SUM(t.gross_revenue) AS gross_revenue
FROM {S}.HARDWARE_SALES_TRANSACTIONS t
JOIN {S}.HARDWARE_PRODUCTS h ON h.hardware_product_id = t.hardware_product_id
WHERE t.sale_timestamp >= '{START}' AND t.sale_timestamp < '{END}'
GROUP BY 1,2"""),

    ("Dashboard hardware: revenue by manufacturer", f"""
SELECT h.manufacturer, SUM(t.gross_revenue) AS gross_revenue, SUM(t.quantity) AS units
FROM {S}.HARDWARE_SALES_TRANSACTIONS t
JOIN {S}.HARDWARE_PRODUCTS h ON h.hardware_product_id = t.hardware_product_id
WHERE t.sale_timestamp >= '{START}' AND t.sale_timestamp < '{END}'
GROUP BY 1 ORDER BY 2 DESC"""),

    ("Dashboard hardware: realized vs list price", f"""
SELECT h.product_name, h.product_type, h.list_price,
       SUM(t.gross_revenue) / NULLIF(SUM(t.quantity),0) AS avg_selling_price,
       SUM(t.quantity) AS units, SUM(t.gross_revenue) AS gross_revenue
FROM {S}.HARDWARE_SALES_TRANSACTIONS t
JOIN {S}.HARDWARE_PRODUCTS h ON h.hardware_product_id = t.hardware_product_id
WHERE t.sale_timestamp >= '{START}' AND t.sale_timestamp < '{END}'
GROUP BY 1,2,3 ORDER BY gross_revenue DESC LIMIT 25"""),

    ("Dashboard subscriptions: revenue and subscribers by tier", f"""
SELECT DATE_TRUNC('month', c.charge_timestamp)::date AS period, sp.plan_tier,
       SUM(c.gross_revenue) AS revenue, COUNT(DISTINCT c.subscriber_id) AS subscribers
FROM {S}.SUBSCRIPTION_CHARGES c JOIN {S}.SUBSCRIPTION_PLANS sp ON sp.plan_id = c.plan_id
WHERE c.charge_timestamp >= '{START}' AND c.charge_timestamp < '{END}'
GROUP BY 1,2 ORDER BY 1"""),

    ("Dashboard subscriptions: top plans", f"""
SELECT sp.plan_name, sp.plan_tier, sp.billing_cycle, sp.list_price,
       SUM(c.gross_revenue) AS revenue, COUNT(DISTINCT c.subscriber_id) AS subscribers
FROM {S}.SUBSCRIPTION_CHARGES c JOIN {S}.SUBSCRIPTION_PLANS sp ON sp.plan_id = c.plan_id
WHERE c.charge_timestamp >= '{START}' AND c.charge_timestamp < '{END}'
GROUP BY 1,2,3,4 ORDER BY revenue DESC LIMIT 15"""),

    ("Dashboard titles: title leaderboard", f"""
SELECT t.title_name, t.studio, t.publisher_label, SUM(m.monthly_income) AS income
FROM {S}.MONTHLY_REVENUE m JOIN {S}.TITLES t ON t.title_id = m.title_id
WHERE m.revenue_month >= '{TITLE_START}' AND m.revenue_month <= '{TITLE_END}'
GROUP BY 1,2,3 ORDER BY income DESC LIMIT 20"""),

    ("Dashboard titles: income by revenue source (monetization type)", f"""
SELECT m.revenue_source, SUM(m.monthly_income) AS income
FROM {S}.MONTHLY_REVENUE m
WHERE m.revenue_month >= '{TITLE_START}' AND m.revenue_month <= '{TITLE_END}'
GROUP BY 1 ORDER BY 2 DESC"""),

    ("Dashboard titles: revenue source trend by quarter", f"""
SELECT DATE_TRUNC('quarter', m.revenue_month)::date AS period, m.revenue_source,
       SUM(m.monthly_income) AS income
FROM {S}.MONTHLY_REVENUE m
WHERE m.revenue_month >= '{TITLE_START}' AND m.revenue_month <= '{TITLE_END}'
GROUP BY 1,2 ORDER BY 1"""),

    ("Dashboard titles: quarterly income heatmap, top 20 titles", f"""
WITH top AS (
  SELECT title_id FROM {S}.QUARTERLY_REVENUE
  WHERE DATE_FROM_PARTS(revenue_year, revenue_quarter*3-2, 1) BETWEEN '{TITLE_START}' AND '{TITLE_END}'
  GROUP BY 1 ORDER BY SUM(quarterly_income) DESC LIMIT 20)
SELECT t.title_name, q.revenue_year || '-Q' || q.revenue_quarter AS quarter, q.quarterly_income
FROM {S}.QUARTERLY_REVENUE q JOIN top USING (title_id)
JOIN {S}.TITLES t ON t.title_id = q.title_id
WHERE DATE_FROM_PARTS(q.revenue_year, q.revenue_quarter*3-2, 1) BETWEEN '{TITLE_START}' AND '{TITLE_END}'"""),

    # Dashboard uses SUM(DISTINCT income), which merges titles with equal income;
    # the rule-compliant version dedupes to one row per title first.
    ("Dashboard titles: exclusive vs multi-platform (income once per title)", f"""
SELECT exclusivity_type, COUNT(*) AS titles, SUM(income) AS income
FROM (SELECT DISTINCT title_id, COALESCE(exclusivity_type, 'NONE') AS exclusivity_type, income
      FROM {S}.VW_PLATFORM_EXCLUSIVITY)
GROUP BY 1 ORDER BY income DESC"""),

    ("Dashboard titles: lifetime income by studio", f"""
SELECT t.studio, SUM(r.income) AS income, COUNT(*) AS titles
FROM {S}.GAME_REVENUE r JOIN {S}.TITLES t ON t.title_id = r.title_id
GROUP BY 1 ORDER BY 2 DESC LIMIT 15"""),

    ("Dashboard customers: new accounts by region", f"""
SELECT DATE_TRUNC('month', a.account_created_date)::date AS period, a.region, COUNT(*) AS accounts
FROM {S}.CUSTOMER_ACCOUNTS a
WHERE a.account_created_date >= '{START}' AND a.account_created_date < '{END}'
GROUP BY 1,2 ORDER BY 1"""),

    ("Dashboard customers: accounts by platform", f"""
SELECT pl.platform_name, COUNT(*) AS accounts
FROM {S}.CUSTOMER_ACCOUNTS a JOIN {S}.PLATFORMS pl ON pl.platform_id = a.platform_id
WHERE a.account_created_date >= '{START}' AND a.account_created_date < '{END}'
GROUP BY 1 ORDER BY 2 DESC"""),

    ("Dashboard customers: platform revenue summary", f"""
SELECT DATE_TRUNC('month', revenue_month)::date AS period, category_group,
       SUM(gross_revenue) AS gross_revenue, SUM(platform_revenue) AS platform_revenue
FROM {S}.VW_PLATFORM_REVENUE_SUMMARY
WHERE revenue_month >= '{START}' AND revenue_month < '{END}'
GROUP BY 1,2 ORDER BY 1"""),

    ("Dashboard franchises: revenue by franchise", f"""
WITH title_map AS ({TITLE_MAP})
SELECT COALESCE(g.franchise_name, 'Unmapped') AS franchise,
       SUM(m.monthly_income) AS income, COUNT(DISTINCT m.title_id) AS titles
FROM {S}.MONTHLY_REVENUE m
LEFT JOIN title_map x ON x.title_id = m.title_id
LEFT JOIN {C}.GAMES g ON g.game_id = x.catalog_game_id
WHERE m.revenue_month >= '{TITLE_START}' AND m.revenue_month <= '{TITLE_END}'
GROUP BY 1 ORDER BY income DESC LIMIT 20"""),

    ("Dashboard genres: top 5 detailed genres by revenue, by year", f"""
WITH title_map AS ({TITLE_MAP}),
genre_rev AS (
  SELECT YEAR(m.revenue_month) AS revenue_year, gg.genre AS genre,
         SUM(m.monthly_income) AS income, COUNT(DISTINCT gg.game_id) AS games
  FROM {S}.MONTHLY_REVENUE m
  JOIN title_map x ON x.title_id = m.title_id
  JOIN {C}.GAME_GENRE_CLASSIFICATION gg ON gg.game_id = x.catalog_game_id AND gg.match_status = 'FULL'
  WHERE m.revenue_month >= '{TITLE_START}' AND m.revenue_month <= '{TITLE_END}'
  GROUP BY 1, 2)
SELECT revenue_year, genre, income, games,
       RANK() OVER (PARTITION BY revenue_year ORDER BY income DESC) AS genre_rank
FROM genre_rev
QUALIFY genre_rank <= 5
ORDER BY revenue_year, genre_rank"""),

    ("Dashboard genres: top 5 top-level genres by revenue, by year", f"""
WITH title_map AS ({TITLE_MAP}),
genre_rev AS (
  SELECT YEAR(m.revenue_month) AS revenue_year, gg.rollup_genre AS genre,
         SUM(m.monthly_income) AS income, COUNT(DISTINCT gg.game_id) AS games
  FROM {S}.MONTHLY_REVENUE m
  JOIN title_map x ON x.title_id = m.title_id
  JOIN {C}.VW_GAME_GENRE_ROLLUP gg ON gg.game_id = x.catalog_game_id AND gg.rollup_depth = 1
  WHERE m.revenue_month >= '{TITLE_START}' AND m.revenue_month <= '{TITLE_END}'
  GROUP BY 1, 2)
SELECT revenue_year, genre, income, games,
       RANK() OVER (PARTITION BY revenue_year ORDER BY income DESC) AS genre_rank
FROM genre_rev
QUALIFY genre_rank <= 5
ORDER BY revenue_year, genre_rank"""),
]


def main():
    # Same auth path as the other scripts: the snow CLI with a named connection.
    print(f"Running {len(QUERIES)} queries against {DB} (connection {CONNECTION})...")
    errors = 0
    for i, (label, sql) in enumerate(QUERIES, 1):
        r = subprocess.run(
            ["snow", "sql", "-c", CONNECTION, "--enable-templating", "NONE", "--format", "json", "-q", sql],
            capture_output=True, text=True, timeout=300,
        )
        if r.returncode == 0:
            rows = json.loads(r.stdout or "[]")
            print(f"  [{i}/{len(QUERIES)}] OK ({len(rows)} rows) {label}")
        else:
            print(f"  [{i}/{len(QUERIES)}] ERROR {label}: {(r.stderr or r.stdout).strip()[:300]}")
            errors += 1
    print(f"\nDone: {len(QUERIES) - errors} succeeded, {errors} failed out of {len(QUERIES)} total")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
