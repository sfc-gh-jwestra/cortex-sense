"""
Record the GAME_ANALYTICS_CTX_V2 business rules as durable feedback records
via SYSTEM$CORTEX_AGENT_CORTEX_CONTEXT_BUILDER record-feedback.

Each record is a feedback record with:
  - type: definition | procedural | retrieval_steer | annotation
  - feedback_rule: the imperative instruction
  - indexed_text: the question this should match against (no FQNs)
  - raw_feedback: the original rule text verbatim

RECORDS is the source of truth for the rules. A full install records all of them through
install/08-record-feedback.sql (generated from RECORDS by scripts/generate_install_sql.py).
This script records them directly, which is handy for adding one new rule to a live context:

Usage: python3 scripts/record_feedback.py [--context <name>] [--only "concept1,concept2"]
"""
import json
import subprocess
import tempfile
import os
import sys
import time

DB = "CORTEX_SENSE_DEMO"
SCHEMA = "CONTEXTS"
CONTEXT = "GAME_ANALYTICS_CTX_V2"  # override with --context <name>
CONNECTION = os.environ.get("SNOWFLAKE_CONNECTION_NAME", "CORTEX_SENSE_DEMO_CONN")

RECORDS = [
    # ── Fiscal Year ──
    {
        "type": "definition",
        "raw_feedback": 'FISCAL YEAR: Fiscal year equals calendar year (January 1 through December 31). "This fiscal year" = YEAR(CURRENT_DATE()). "Next fiscal year" = YEAR(CURRENT_DATE()) + 1. "Last fiscal year" = YEAR(CURRENT_DATE()) - 1.',
        "feedback_rule": "Fiscal year equals calendar year (January 1 through December 31). This fiscal year = YEAR(CURRENT_DATE()). Next fiscal year = YEAR(CURRENT_DATE()) + 1. Last fiscal year = YEAR(CURRENT_DATE()) - 1.",
        "indexed_text": "User is asking about fiscal year, this year, next year, last year, annual periods, or year-based time ranges for filtering games or revenue. The fiscal year aligns with the calendar year from January through December.",
        "concepts": ["fiscal year"],
    },
    # ── Release Date ──
    {
        "type": "annotation",
        "raw_feedback": "RELEASE DATE: GAMES.RELEASE_DATE is a DATE column. Use it directly in date functions like YEAR(), QUARTER(), DATEDIFF() without TRY_TO_DATE(). Use RELEASE_DATE for time-based filtering.",
        "feedback_rule": "CORTEX_SENSE_DEMO.GAME_CATALOG.GAMES.RELEASE_DATE is a DATE column. Use it directly in date functions like YEAR(), QUARTER(), DATEDIFF() without TRY_TO_DATE(). Use RELEASE_DATE for all time-based filtering of games.",
        "indexed_text": "User is asking about game release dates, when games launched, filtering games by date or time period, or using date functions on game data. The release date column is already a proper DATE type and needs no conversion.",
        "entity_keys": ["CORTEX_SENSE_DEMO.GAME_CATALOG.GAMES"],
        "concepts": ["release date"],
    },
    # ── Publisher and Studio Names Across Schemas ──
    {
        "type": "definition",
        "raw_feedback": "PUBLISHER AND STUDIO NAMES: Sales and catalog spell the same publisher and studios differently. Sales uses SIE and studio names with spaces; the catalog uses Sony Interactive Entertainment and developer names with underscores. Join by ID, not by name.",
        "feedback_rule": "Publisher and studio names differ between schemas. CORTEX_SENSE_DEMO.GAME_SALES.TITLES.PUBLISHER_LABEL = 'SIE' and CORTEX_SENSE_DEMO.GAME_CATALOG.GAMES.PUBLISHER_NAME = 'Sony Interactive Entertainment' are the same publisher. TITLES.STUDIO uses spaces ('Naughty Dog') and GAMES.DEVELOPER_NAME uses underscores ('Naughty_Dog') for the same studio. To combine sales and catalog data, join by ID through SELECT DISTINCT TITLE_ID, CATALOG_GAME_ID FROM CORTEX_SENSE_DEMO.GAME_SALES.TITLE_CODE_XREF, then CATALOG_GAME_ID = GAMES.GAME_ID; never join PUBLISHER_LABEL to PUBLISHER_NAME or STUDIO to DEVELOPER_NAME. When a user names a publisher or studio, filter each schema using its own form: 'Sony', 'SIE' or 'Sony Interactive Entertainment' means PUBLISHER_LABEL = 'SIE' in GAME_SALES and PUBLISHER_NAME = 'Sony Interactive Entertainment' in GAME_CATALOG; a studio name is used as typed for TITLES.STUDIO and with spaces replaced by underscores for GAMES.DEVELOPER_NAME. Display developer names with REPLACE(DEVELOPER_NAME, '_', ' '). All titles in this data belong to Sony Interactive Entertainment, so there are no competitor publishers to compare against; say so if asked.",
        "indexed_text": "User is asking about a publisher or studio by name, Sony or SIE, a specific developer studio, combining sales revenue with catalog attributes for a publisher or studio, or comparing a publisher against competitors. Names are spelled differently in the sales and catalog data, so data must be linked by ID.",
        "entity_keys": ["CORTEX_SENSE_DEMO.GAME_SALES.TITLES", "CORTEX_SENSE_DEMO.GAME_CATALOG.GAMES", "CORTEX_SENSE_DEMO.GAME_SALES.TITLE_CODE_XREF"],
        "concepts": ["publisher names", "Sony Interactive Entertainment", "SIE", "studio names"],
    },
    # ── Revenue Analysis ──
    {
        "type": "retrieval_steer",
        "raw_feedback": "REVENUE ANALYSIS: Title-level and total company revenue are modeled in the SV_GAME_SALES semantic view. For revenue by franchise, publisher, developer or indie vs studio, map sales titles to catalog games through the title-code xref. 'Top revenue earners' means the top 5 titles by lifetime income; no quartile cutoff unless asked.",
        "feedback_rule": "Revenue by title, gross vs net, and total company revenue are modeled in CORTEX_SENSE_DEMO.GAME_SALES.SV_GAME_SALES; follow it. Lifetime game revenue is CORTEX_SENSE_DEMO.GAME_SALES.GAME_REVENUE.INCOME (digital gross revenue, one row per TITLE_ID); it excludes hardware and subscriptions. For revenue by franchise, publisher, developer or indie vs studio, map titles with SELECT DISTINCT TITLE_ID, CATALOG_GAME_ID FROM CORTEX_SENSE_DEMO.GAME_SALES.TITLE_CODE_XREF, join CATALOG_GAME_ID = CORTEX_SENSE_DEMO.GAME_CATALOG.GAMES.GAME_ID, and group by GAMES.FRANCHISE_NAME, PUBLISHER_NAME, DEVELOPER_NAME or DEVELOPER_IS_INDIE. Never use TITLES.CATALOG_GAME_ID, and never join revenue to the xref without DISTINCT. Two titles have no catalog mapping; report them as 'Unmapped' so totals still match GAME_REVENUE. 'Top revenue earners' means ORDER BY INCOME DESC LIMIT 5 at title level; never apply a top-quartile or percentile cutoff unless the user asks.",
        "indexed_text": "User is asking about game revenue, total income, lifetime sales, earnings by game, top revenue earners, highest-grossing games, franchise revenue, publisher revenue, developer or studio revenue, or comparing indie versus studio revenue. Top earners are a simple ranked list, not a percentile band.",
        "entity_keys": ["CORTEX_SENSE_DEMO.GAME_SALES.GAME_REVENUE", "CORTEX_SENSE_DEMO.GAME_SALES.TITLE_CODE_XREF", "CORTEX_SENSE_DEMO.GAME_CATALOG.GAMES"],
        "concepts": ["revenue", "income", "lifetime revenue", "franchise revenue", "top revenue earners"],
    },
    # ── Genre Revenue ──
    {
        "type": "procedural",
        "raw_feedback": "GENRE REVENUE: Revenue by genre must use fully matched genres only. A game belongs to several genres, so its full revenue counts in each one and genre totals add up to more than total revenue; never present them as a split of total revenue. Report games with no fully matched genre separately.",
        "feedback_rule": "For revenue by genre, map revenue titles to catalog games with SELECT DISTINCT TITLE_ID, CATALOG_GAME_ID FROM CORTEX_SENSE_DEMO.GAME_SALES.TITLE_CODE_XREF, then join CATALOG_GAME_ID to CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_GENRE_CLASSIFICATION.GAME_ID with MATCH_STATUS = 'FULL' (PARTIAL and NONE rows are not genre membership). Sum INCOME from CORTEX_SENSE_DEMO.GAME_SALES.GAME_REVENUE and also report COUNT(DISTINCT GAME_ID) per genre. For broad or top-level genres (Action, Adventure, RPG, Horror, ...), use CORTEX_SENSE_DEMO.GAME_CATALOG.VW_GAME_GENRE_ROLLUP (one row per GAME_ID and ROLLUP_GENRE, including parent genres; ROLLUP_DEPTH = 1 is top level) instead of GAME_GENRE_CLASSIFICATION. A game belongs to several genres (about 3 fully matched on average), so its full revenue counts in every genre it belongs to: genre totals add up to roughly 3 times total revenue and must never be presented as shares of total revenue or summed into a total. State this whenever genre revenue is shown. Ten mapped titles (about $2.8M) have no fully matched genre and two titles (about $230K) have no catalog mapping; report them as 'No full genre match' and 'Unmapped' rather than dropping them silently. For a single game's genre, use its fully matched genres only.",
        "indexed_text": "User is asking about revenue by genre, which genres earn the most, genre revenue share, top-grossing genres, revenue for a broad genre like action or RPG, or comparing revenue across genres. Games belong to several genres, so genre revenue overlaps and does not add up to total revenue.",
        "entity_keys": ["CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_GENRE_CLASSIFICATION", "CORTEX_SENSE_DEMO.GAME_CATALOG.VW_GAME_GENRE_ROLLUP", "CORTEX_SENSE_DEMO.GAME_SALES.GAME_REVENUE", "CORTEX_SENSE_DEMO.GAME_SALES.TITLE_CODE_XREF"],
        "concepts": ["genre revenue", "revenue by genre", "top-grossing genres"],
    },
    # ── Monthly Revenue ──
    {
        "type": "retrieval_steer",
        "raw_feedback": "MONTHLY REVENUE ANALYSIS: Monthly revenue detail (grain, REVENUE_SOURCE values, lifecycle phases) is modeled in the SV_GAME_SALES semantic view. This rule is a short pointer to it.",
        "feedback_rule": "For monthly game revenue and lifecycle phases, use CORTEX_SENSE_DEMO.GAME_SALES.MONTHLY_REVENUE as modeled in CORTEX_SENSE_DEMO.GAME_SALES.SV_GAME_SALES. REVENUE_SOURCE is the monetization type, not a lifecycle phase; derive launch, early-life and tail phases from months since TITLES.RELEASE_DATE (a YYYYMMDD string). Sum MONTHLY_INCOME, never CUMULATIVE_INCOME. It is the same revenue as digital transactions; never add the two.",
        "indexed_text": "User is asking about monthly revenue trends, revenue over time, revenue curves, launch revenue, DLC revenue, microtransaction or loot box revenue over time, tail revenue, or time-series analysis of game sales. Monthly data is broken down by monetization type, and launch or tail phases are derived from the release date.",
        "entity_keys": ["CORTEX_SENSE_DEMO.GAME_SALES.MONTHLY_REVENUE", "CORTEX_SENSE_DEMO.GAME_SALES.TITLES"],
        "concepts": ["monthly revenue", "revenue source", "launch revenue", "tail revenue"],
    },
    # ── Quarterly Revenue ──
    {
        "type": "retrieval_steer",
        "raw_feedback": "QUARTERLY REVENUE: QUARTERLY_REVENUE is a rollup of MONTHLY_REVENUE by REVENUE_YEAR and REVENUE_QUARTER (1-4). Use for YoY comparisons, trend analysis, and quarterly reporting.",
        "feedback_rule": "For quarterly revenue, use CORTEX_SENSE_DEMO.GAME_SALES.QUARTERLY_REVENUE which is a rollup of monthly data by REVENUE_YEAR and REVENUE_QUARTER (1-4). Use for YoY comparisons, trend analysis, and quarterly reporting.",
        "indexed_text": "User is asking about quarterly revenue, year-over-year comparisons, Q1/Q2/Q3/Q4 performance, quarterly trends, or quarterly reporting of game sales. Quarterly data is a pre-aggregated rollup of monthly revenue.",
        "entity_keys": ["CORTEX_SENSE_DEMO.GAME_SALES.QUARTERLY_REVENUE"],
        "concepts": ["quarterly revenue", "YoY comparison"],
    },
    # ── Time Series Best Practices ──
    {
        "type": "procedural",
        "raw_feedback": "TIME SERIES BEST PRACTICES: For monthly trends, GROUP BY REVENUE_MONTH. For quarterly trends, use QUARTERLY_REVENUE and GROUP BY REVENUE_YEAR, REVENUE_QUARTER. For YoY comparison, compare same REVENUE_QUARTER across different REVENUE_YEARs. Launch windows follow the SV_GAME_SALES semantic view.",
        "feedback_rule": "For monthly trends, SUM(MONTHLY_INCOME) GROUP BY REVENUE_MONTH from CORTEX_SENSE_DEMO.GAME_SALES.MONTHLY_REVENUE. For quarterly trends, use CORTEX_SENSE_DEMO.GAME_SALES.QUARTERLY_REVENUE and GROUP BY REVENUE_YEAR, REVENUE_QUARTER. For YoY comparison, compare same REVENUE_QUARTER across different REVENUE_YEARs. Derive launch windows from months since release as in CORTEX_SENSE_DEMO.GAME_SALES.SV_GAME_SALES; never filter REVENUE_SOURCE for lifecycle phases.",
        "indexed_text": "User is asking about time series analysis, revenue trends over time, year-over-year comparisons, launch window performance, or how to group revenue data by time period. Different time granularities require different tables and grouping strategies.",
    },
    # ── Exclusivity Revenue ──
    {
        "type": "retrieval_steer",
        "raw_feedback": "EXCLUSIVITY REVENUE: To calculate revenue from exclusive games, join PLATFORM_EXCLUSIVITY to GAME_REVENUE on GAME_ID and filter by IS_CURRENTLY_EXCLUSIVE = TRUE.",
        "feedback_rule": "To calculate revenue from exclusive titles, use CORTEX_SENSE_DEMO.GAME_SALES.VW_PLATFORM_EXCLUSIVITY filtered to IS_CURRENTLY_EXCLUSIVE = TRUE; it already carries lifetime INCOME per TITLE_ID, so no join to GAME_REVENUE is needed. A title can have more than one exclusivity row, so count each TITLE_ID's INCOME once.",
        "indexed_text": "User is asking about exclusive game revenue, platform exclusivity deals, revenue from exclusive titles, or financial impact of exclusivity agreements. Join the exclusivity view to revenue data filtering for currently active exclusives.",
        "entity_keys": ["CORTEX_SENSE_DEMO.GAME_SALES.VW_PLATFORM_EXCLUSIVITY"],
        "concepts": ["exclusivity revenue", "platform exclusivity"],
    },
    # ── Monetization Risk ──
    {
        "type": "procedural",
        "raw_feedback": "MONETIZATION RISK: Cross-reference MONETIZATION_TYPES with platform exclusivity to identify revenue concentration risks.",
        "feedback_rule": "To assess monetization risk, join CORTEX_SENSE_DEMO.GAME_SALES.MONETIZATION_TYPES through CORTEX_SENSE_DEMO.GAME_SALES.GAME_MONETIZATION to CORTEX_SENSE_DEMO.GAME_SALES.VW_PLATFORM_EXCLUSIVITY on TITLE_ID to identify revenue concentration risks.",
        "indexed_text": "User is asking about monetization risk, revenue concentration, dependency on specific monetization models, or financial risk from platform-specific monetization strategies. Cross-reference monetization types with exclusivity data.",
        "concepts": ["monetization risk", "revenue concentration"],
    },
    # ── Revenue by Monetization Model ──
    {
        "type": "definition",
        "raw_feedback": "REVENUE BY MONETIZATION MODEL: 'Monetization model' means the model tags assigned to each title, not the transaction or product type. Sum each tagged title's lifetime income per model; titles carry several models, so totals overlap.",
        "feedback_rule": "Revenue by monetization model means the models tagged on each title, not transaction or product types. Join CORTEX_SENSE_DEMO.GAME_SALES.GAME_MONETIZATION to CORTEX_SENSE_DEMO.GAME_SALES.MONETIZATION_TYPES on MONETIZATION_ID, then to CORTEX_SENSE_DEMO.GAME_SALES.GAME_REVENUE on TITLE_ID, and report SUM(INCOME) and COUNT(DISTINCT TITLE_ID) per MONETIZATION_NAME. Do not use DIGITAL_PRODUCT_TRANSACTIONS, DIGITAL_PRODUCTS or REVENUE_TYPES.MONETIZATION_TYPE for this. A title can use several models, so its full lifetime income counts under each one: totals overlap, must not be summed or shown as shares of total revenue, and the answer must say so.",
        "indexed_text": "User is asking for total or lifetime revenue by monetization model, revenue per business model (premium, DLC, microtransactions, loot boxes, battle pass, subscription), or how much titles using each monetization model earn.",
        "entity_keys": ["CORTEX_SENSE_DEMO.GAME_SALES.GAME_MONETIZATION", "CORTEX_SENSE_DEMO.GAME_SALES.MONETIZATION_TYPES", "CORTEX_SENSE_DEMO.GAME_SALES.GAME_REVENUE"],
        "concepts": ["revenue by monetization model", "monetization model"],
    },
    # ── Content Rating Risk ──
    {
        "type": "definition",
        "raw_feedback": "CONTENT RATING RISK: A game poses a content rating risk when it carries a mature age rating (MIN_AGE >= 16 in any rating system), or has violent, gory, or romantic/sexual themes. The descriptor table is gone, so infer content type from genre, theme, and gameplay. Include romance even though no games are tagged with it yet.",
        "feedback_rule": "A game poses a content rating risk when ANY of these apply: (1) MATURE RATING: MIN_AGE >= 16 in CORTEX_SENSE_DEMO.GAME_CATALOG.AGE_RATINGS via CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_RATINGS (ESRB M/AO, PEGI 16/18, CERO D/Z); (2) VIOLENCE: a FULL match (MATCH_STATUS = 'FULL') for GENRE in ('Gore', 'Shooter', 'FPS', 'TPS', 'Fighting', 'Horror', 'SurvivalHorror') in CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_GENRE_CLASSIFICATION, or a 'Grotesque' theme (CONTEXT_NAME in ('monster_invasion', 'zombies_invasion') in CORTEX_SENSE_DEMO.GAME_CATALOG.CONTEXTS via CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_CONTEXTS) combined with 'Combat' gameplay (GAMEPLAY_TYPE_NAME in ('agonistic', 'corpo_a_corpo', 'free_shooting') in CORTEX_SENSE_DEMO.GAME_CATALOG.GAMEPLAY_TYPES via CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_GAMEPLAY); (3) ROMANTIC OR SEXUAL CONTENT: CONTEXT_NAME = 'romance' via GAME_CONTEXTS, GAMEPLAY_TYPE_NAME = 'romance_based' via GAME_GAMEPLAY, or a FULL match for GENRE = 'DatingSim'. Report which of the three criteria each game meets. There is no content-descriptor data, so violence and romance are inferred from genre, theme and gameplay, not stated; PEGI 16/18 descriptions mix violence and sexual content and cannot separate them. If no games meet the romance criterion, say so rather than inferring sexual content from the rating alone.",
        "indexed_text": "User is asking about content rating risk, mature-rated games, games with violent, gory, sexual or romantic content, adult content, or regulatory risk from game content ratings. A game is at risk when it has a mature age rating or its genre, themes or gameplay indicate violence or romance.",
        "entity_keys": ["CORTEX_SENSE_DEMO.GAME_CATALOG.AGE_RATINGS", "CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_RATINGS", "CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_GENRE_CLASSIFICATION", "CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_CONTEXTS", "CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_GAMEPLAY"],
        "concepts": ["content rating risk", "mature rating", "violent content", "romantic content"],
    },
    # ── EU Regulatory Risk Assessment ──
    {
        "type": "procedural",
        "raw_feedback": "EU REGULATORY RISK: Assess EU risk using the tiers in the EU loot box regulatory brief (eu_regulatory_brief_loot_boxes.md). Find live-service games first, apply HIGH, ELEVATED, WATCH in order, name the trigger and the regulation, say plainly when nothing is HIGH, and note the brief is not legal advice.",
        "feedback_rule": "To assess EU regulatory risk, retrieve eu_regulatory_brief_loot_boxes.md and use it as the only source for the risk tiers, the conditions for each tier, the regulations and the required mitigations; do not answer from memory. Steps: (1) Identify live-service games first: ONLINE_REQUIRED = TRUE in CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_MODES AND recurring monetization (MONETIZATION_NAME in ('battle_pass', 'microtransactions', 'subscription', 'loot_boxes') in CORTEX_SENSE_DEMO.GAME_CATALOG.MONETIZATION_TYPES via CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_MONETIZATION). (2) Apply the brief's tiers in order (HIGH, then ELEVATED, then WATCH) and give each game the first tier it meets. (3) Name the condition that triggered each tier and the regulation from the brief it relates to. (4) If no live-service game meets HIGH, say so plainly before reporting lower tiers. (5) Report the brief's required mitigations for each tier. (6) State that the brief is a simplified internal summary, not legal advice. To evaluate the brief's terms in the data: 'PEGI 18' = RATING_SYSTEM = 'PEGI' AND MIN_AGE >= 18 in CORTEX_SENSE_DEMO.GAME_CATALOG.AGE_RATINGS via CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_RATINGS; 'paid loot boxes' = MONETIZATION_NAME = 'loot_boxes'; 'paid DLC' = MONETIZATION_NAME = 'dlc'; 'available on mobile' = PLATFORM_NAME in ('Android', 'Apple') in CORTEX_SENSE_DEMO.GAME_CATALOG.PLATFORMS via CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_PLATFORMS. There is no content-descriptor data.",
        "indexed_text": "User is asking about EU regulatory risk, loot box regulation, EU risk tiers (HIGH, ELEVATED, WATCH, LOW), required mitigations, or which live-service or monetized games are exposed to EU, Belgium, Netherlands, DSA, consumer protection or PEGI rules.",
        "entity_keys": ["CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_MODES", "CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_MONETIZATION", "CORTEX_SENSE_DEMO.GAME_CATALOG.MONETIZATION_TYPES", "CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_RATINGS", "CORTEX_SENSE_DEMO.GAME_CATALOG.AGE_RATINGS", "CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_PLATFORMS", "CORTEX_SENSE_DEMO.GAME_CATALOG.PLATFORMS"],
        "concepts": ["EU regulatory risk", "loot boxes", "EU risk tier", "live-service"],
    },
    # ── Rating Equivalence ──
    {
        "type": "annotation",
        "raw_feedback": "RATING EQUIVALENCE: To find equivalent ratings across systems, join AGE_RATINGS to itself matching on MIN_AGE ranges.",
        "feedback_rule": "To find equivalent ratings across ESRB, PEGI, CERO, and other systems, self-join CORTEX_SENSE_DEMO.GAME_CATALOG.AGE_RATINGS matching on MIN_AGE ranges.",
        "indexed_text": "User is asking about rating equivalence, converting between ESRB and PEGI ratings, comparing age rating systems, or finding the PEGI equivalent of an ESRB rating. Self-join the age ratings table matching on minimum age thresholds.",
        "entity_keys": ["CORTEX_SENSE_DEMO.GAME_CATALOG.AGE_RATINGS"],
        "concepts": ["rating equivalence", "ESRB", "PEGI", "CERO"],
    },
    # ── Awards ──
    {
        "type": "retrieval_steer",
        "raw_feedback": "AWARDS: Use GAME_AWARDS joined to AWARDS. Filter WON_OR_NOMINATED = 'won' for wins only. Group by AWARDING_BODY for cross-award-show analysis.",
        "feedback_rule": "For award analysis, use CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_AWARDS joined to CORTEX_SENSE_DEMO.GAME_CATALOG.AWARDS. Filter WON_OR_NOMINATED = 'won' for wins only. Group by AWARDING_BODY for cross-award-show analysis.",
        "indexed_text": "User is asking about game awards, award winners, award nominations, Game of the Year, BAFTA, DICE awards, Golden Joystick, or which games or studios have won the most awards. Filter for wins versus nominations and group by awarding body.",
        "entity_keys": ["CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_AWARDS", "CORTEX_SENSE_DEMO.GAME_CATALOG.AWARDS"],
        "concepts": ["awards", "Game of the Year", "BAFTA"],
    },
    # ── Accessibility ──
    {
        "type": "retrieval_steer",
        "raw_feedback": "ACCESSIBILITY: ACCESSIBILITY_GAPS (VW_ACCESSIBILITY_GAPS) provides a complete matrix of games x features. IS_SUPPORTED = FALSE means the game lacks that feature.",
        "feedback_rule": "For accessibility analysis, use CORTEX_SENSE_DEMO.GAME_CATALOG.VW_ACCESSIBILITY_GAPS which provides a complete game-by-feature matrix. IS_SUPPORTED = FALSE means the game lacks that feature. Group by FEATURE_CATEGORY (visual, audio, motor) for category-level analysis.",
        "indexed_text": "User is asking about accessibility features, which games support accessibility, missing accessibility features, accessibility gaps, colorblind mode, subtitle options, control remapping, or inclusive design coverage. The accessibility gaps view shows a complete matrix of supported and missing features per game.",
        "entity_keys": ["CORTEX_SENSE_DEMO.GAME_CATALOG.VW_ACCESSIBILITY_GAPS"],
        "concepts": ["accessibility", "accessibility gaps"],
    },
    # ── Audience Profile Inference ──
    {
        "type": "procedural",
        "raw_feedback": "AUDIENCE PROFILE INFERENCE: When answering questions about target audience, audience overlap, player segments, or whether two games compete for the same players, infer the audience profile from genre clusters (GAME_GENRE_CLASSIFICATION where MATCH_STATUS = 'FULL'), platform reach (GAME_PLATFORMS/PLATFORMS), and narrative style (NARRATIVE_STRUCTURES.STRUCTURE_NAME).",
        "feedback_rule": "Infer audience profiles from three dimensions: genre clusters (CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_GENRE_CLASSIFICATION where MATCH_STATUS = 'FULL'), platform reach (CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_PLATFORMS joined to CORTEX_SENSE_DEMO.GAME_CATALOG.PLATFORMS), and narrative style (CORTEX_SENSE_DEMO.GAME_CATALOG.NARRATIVE_STRUCTURES.STRUCTURE_NAME).",
        "indexed_text": "User is asking about target audience, audience overlap, player segments, whether two games compete for the same players, or audience profiling. Audience is inferred from genre classification, platform availability, and narrative structure — not stored as a direct attribute.",
        "concepts": ["audience profile", "player segments", "audience overlap"],
    },
    # ── Franchise Cannibalization ──
    {
        "type": "definition",
        "raw_feedback": "FRANCHISE CANNIBALIZATION: When two franchises under the same publisher have WEIGHTED_OVERLAP >= 0.3 (from GAME_SIMILARITY_SCORES), evaluate: CONSOLIDATE when both share 3+ genres and one has declining performance. SUNSET when one franchise has <2 titles and the other covers its footprint. REPOSITION when overlap is concentrated in a single dimension. When none clearly apply, present the overlap data and flag for strategic review.",
        "feedback_rule": "Franchise cannibalization exists when same-publisher franchises have WEIGHTED_OVERLAP >= 0.3 in CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_SIMILARITY_SCORES. Recommend CONSOLIDATE when both share 3+ genres and one has declining performance. SUNSET when one has <2 titles and the other covers its footprint. REPOSITION when overlap is in a single dimension. Otherwise flag for strategic review. Use CORTEX_SENSE_DEMO.GAME_CATALOG.VW_CANNIBALIZATION_CANDIDATES for pre-filtered pairs.",
        "indexed_text": "User is asking about franchise cannibalization, whether franchises compete with each other internally, portfolio overlap, or whether to consolidate, sunset, or reposition a franchise. Same-publisher franchises with high similarity overlap are cannibalization candidates.",
        "entity_keys": ["CORTEX_SENSE_DEMO.GAME_CATALOG.VW_CANNIBALIZATION_CANDIDATES"],
        "concepts": ["franchise cannibalization", "consolidate", "sunset", "reposition"],
    },
    # ── Live-Service Games ──
    {
        "type": "definition",
        "raw_feedback": "LIVE-SERVICE GAMES: A game is live-service when ONLINE_REQUIRED = TRUE in GAME_MODES AND uses recurring monetization (battle_pass, microtransactions, subscription, or loot_boxes in MONETIZATION_TYPES via GAME_MONETIZATION).",
        "feedback_rule": "A game is live-service when ONLINE_REQUIRED = TRUE in CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_MODES AND uses recurring monetization (battle_pass, microtransactions, subscription, or loot_boxes) from CORTEX_SENSE_DEMO.GAME_CATALOG.MONETIZATION_TYPES via CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_MONETIZATION.",
        "indexed_text": "User is asking about live-service games, games-as-a-service, GaaS, online-required games, or games with recurring monetization models. A game qualifies as live-service when it requires online connection and uses recurring monetization like battle passes or microtransactions.",
        "concepts": ["live-service", "GaaS", "recurring monetization"],
    },
    # ── Proven Capability ──
    {
        "type": "definition",
        "raw_feedback": "PROVEN CAPABILITY: The data has no studio capability rating. Say so, then offer a labelled proxy: studios with award-winning games, top-quartile revenue, and 3+ genre classifications with MATCH_STATUS = 'FULL'.",
        "feedback_rule": "The data has no studio capability rating or development timeline data. When asked about proven capability, state this first, then use a clearly labelled proxy: award wins in CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_AWARDS (WON_OR_NOMINATED = 'won'), top-quartile INCOME in CORTEX_SENSE_DEMO.GAME_SALES.GAME_REVENUE, and 3+ genres with MATCH_STATUS = 'FULL' in CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_GENRE_CLASSIFICATION. Revenue tables in CORTEX_SENSE_DEMO.GAME_SALES are keyed by TITLE_ID; map them to catalog games with SELECT DISTINCT TITLE_ID, CATALOG_GAME_ID FROM CORTEX_SENSE_DEMO.GAME_SALES.TITLE_CODE_XREF, then CATALOG_GAME_ID = GAME_ID. Never present the proxy as an established fact.",
        "indexed_text": "User is asking about studio capability, proven studios, which developers can deliver quality titles, studio track record, or matching studios to opportunities. Proven capability is determined by award wins, revenue performance, and genre breadth.",
        "concepts": ["proven capability", "studio capability"],
    },
    # ── Emerging Genre ──
    {
        "type": "definition",
        "raw_feedback": "EMERGING GENRE: The data has no market-growth or trend data for genres. Say so, then offer a labelled proxy: MARKET_STATUS = 'UNDERSERVED' or 'WHITESPACE' in GENRE_WHITESPACE_ANALYSIS (few fully classified games), which measures supply, not demand.",
        "feedback_rule": "The data has no genre market-growth or demand data. When asked about emerging genres, state this first, then use a clearly labelled proxy: MARKET_STATUS = 'UNDERSERVED' or 'WHITESPACE' in CORTEX_SENSE_DEMO.GAME_CATALOG.GENRE_WHITESPACE_ANALYSIS. Explain that this measures low game supply, not proven demand.",
        "indexed_text": "User is asking about emerging genres, underserved markets, genre whitespace, untapped genre opportunities, or which genres have few games. Emerging genres are those with fewer than three fully classified games in the whitespace analysis.",
        "entity_keys": ["CORTEX_SENSE_DEMO.GAME_CATALOG.GENRE_WHITESPACE_ANALYSIS"],
        "concepts": ["emerging genre", "whitespace", "underserved genre"],
    },
    # ── Breakout Hit Prediction ──
    {
        "type": "definition",
        "raw_feedback": 'BREAKOUT HIT PREDICTION: A breakout hit is a game that achieves top-quartile INCOME or wins a major award (AWARD_NAME = \'Game_of_the_Year\' from any AWARDING_BODY). The award-winning formula is the set of genre + mechanic + narrative combinations most common among past award winners. This top-quartile threshold applies only to breakout hits, not to "top revenue earners".',
        "feedback_rule": "A breakout hit achieves top-quartile INCOME in CORTEX_SENSE_DEMO.GAME_SALES.GAME_REVENUE or wins Game_of_the_Year from any AWARDING_BODY in CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_AWARDS. This top-quartile threshold applies only to breakout hits; do not use it for 'top revenue earners'. The award-winning formula is computed by joining GAME_AWARDS (WON_OR_NOMINATED = 'won') through CORTEX_SENSE_DEMO.GAME_CATALOG.GAMES to CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_GENRE_CLASSIFICATION, CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_MECHANICS, and CORTEX_SENSE_DEMO.GAME_CATALOG.NARRATIVE_STRUCTURES. Compare indie studio trajectories (GAMES.DEVELOPER_IS_INDIE) against this formula. Revenue tables in CORTEX_SENSE_DEMO.GAME_SALES are keyed by TITLE_ID; map them to catalog games with SELECT DISTINCT TITLE_ID, CATALOG_GAME_ID FROM CORTEX_SENSE_DEMO.GAME_SALES.TITLE_CODE_XREF, then CATALOG_GAME_ID = GAME_ID.",
        "indexed_text": "User is asking about breakout hits, predicting which games or studios will succeed, the award-winning formula, what makes a hit game, or identifying indie studios likely to produce top games. Breakout hits are defined by top revenue or major award wins.",
        "concepts": ["breakout hit", "award-winning formula"],
    },
    # ── Release Calendar Optimization ──
    {
        "type": "procedural",
        "raw_feedback": "RELEASE CALENDAR OPTIMIZATION: When asked about scheduling conflicts, analyze historical release patterns using RELEASE_DATE grouped by YEAR and QUARTER. Two releases conflict when they fall in the same quarter AND share the same inferred audience profile. Use GAME_SIMILARITY_SCORES with WEIGHTED_OVERLAP >= 0.3 to confirm overlap. Major release means INCOME in the top quartile or belonging to a franchise with 3+ titles. This threshold applies only to release planning.",
        "feedback_rule": "For release calendar conflicts, analyze CORTEX_SENSE_DEMO.GAME_CATALOG.GAMES.RELEASE_DATE grouped by YEAR and QUARTER. Two releases conflict when in same quarter AND WEIGHTED_OVERLAP >= 0.3 in CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_SIMILARITY_SCORES (check both GAME_A and GAME_B directions). Major release means top-quartile INCOME or franchise with 3+ titles; this threshold applies only to release planning, not to 'top revenue earners'. Join through CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_FRANCHISES to identify involved franchises. INCOME comes from CORTEX_SENSE_DEMO.GAME_SALES.GAME_REVENUE. Revenue tables in CORTEX_SENSE_DEMO.GAME_SALES are keyed by TITLE_ID; map them to catalog games with SELECT DISTINCT TITLE_ID, CATALOG_GAME_ID FROM CORTEX_SENSE_DEMO.GAME_SALES.TITLE_CODE_XREF, then CATALOG_GAME_ID = GAME_ID.",
        "indexed_text": "User is asking about release calendar optimization, scheduling conflicts, whether two releases compete for the same audience in the same quarter, or how to avoid internal competition on the release schedule. Analyze release dates with audience overlap to detect conflicts.",
        "concepts": ["release calendar", "scheduling conflicts"],
    },
    # ── Accessibility Investment Priority ──
    {
        "type": "procedural",
        "raw_feedback": "ACCESSIBILITY INVESTMENT PRIORITY: Rank accessibility features by a relative priority score: (number of games missing the feature) * (average INCOME of those games). This is a ranking proxy only. The data has no market-size, player-disability, or implementation-cost data, so say so and never present the score as dollars of market or revenue impact. Group by FEATURE_CATEGORY (visual, audio, motor). Prioritize features where the gap is largest in games rated for Family/All-ages (MIN_AGE <= 10).",
        "feedback_rule": "Rank accessibility features by a relative priority score: (count of games missing the feature from CORTEX_SENSE_DEMO.GAME_CATALOG.VW_ACCESSIBILITY_GAPS) * (average INCOME of those games from CORTEX_SENSE_DEMO.GAME_SALES.GAME_REVENUE). Present it as a ranking only; state that the data has no market-size or implementation-cost data and never report the score as dollar market or revenue impact. Group by FEATURE_CATEGORY. Prioritize gaps in Family/All-ages games (MIN_AGE <= 10 in CORTEX_SENSE_DEMO.GAME_CATALOG.AGE_RATINGS via CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_RATINGS). Revenue tables in CORTEX_SENSE_DEMO.GAME_SALES are keyed by TITLE_ID; map them to catalog games with SELECT DISTINCT TITLE_ID, CATALOG_GAME_ID FROM CORTEX_SENSE_DEMO.GAME_SALES.TITLE_CODE_XREF, then CATALOG_GAME_ID = GAME_ID.",
        "indexed_text": "User is asking about accessibility investment strategy, which accessibility features to prioritize, ROI of accessibility, maximizing addressable market through inclusive design, or budget allocation for accessibility improvements. Rank features by revenue-weighted gap coverage.",
        "concepts": ["accessibility investment", "inclusive design ROI"],
    },
    # ── Audience Comparison ──
    {
        "type": "procedural",
        "raw_feedback": "AUDIENCE COMPARISON: When comparing whether two games target the same audience, always check GAME_SIMILARITY_SCORES for their WEIGHTED_OVERLAP score first, in both pair directions. Cite the score and the OVERLAP_TIER column value (HIGH >= 0.6, MEDIUM 0.3 to under 0.6, LOW < 0.3); never re-derive the tier. Then supplement with audience dimension analysis (genre clusters, platform reach, narrative style) to explain why they overlap or differ.",
        "feedback_rule": "When comparing whether two games target the same audience, ALWAYS check CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_SIMILARITY_SCORES for their WEIGHTED_OVERLAP score first. Each pair is stored in one direction only, so match GAME_A/GAME_B both ways. Cite the score and the OVERLAP_TIER column value (HIGH >= 0.6, MEDIUM 0.3 to under 0.6, LOW < 0.3); never re-derive the tier from thresholds. 'Highly cannibalized' means OVERLAP_TIER = 'HIGH'. Then supplement with audience dimension analysis from CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_GENRE_CLASSIFICATION (genre clusters), CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_PLATFORMS (platform reach), and CORTEX_SENSE_DEMO.GAME_CATALOG.NARRATIVE_STRUCTURES (narrative style) to explain WHY they overlap or differ.",
        "indexed_text": "User is asking whether two games target the same audience, comparing audiences between games, audience similarity, do these games compete for the same players, or whether two titles overlap in their target market. Check pre-computed similarity scores first, then explain the overlap dimensions.",
        "entity_keys": ["CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_SIMILARITY_SCORES"],
        "concepts": ["audience comparison", "audience similarity", "weighted overlap"],
    },
    {
        "type": "retrieval_steer",
        "raw_feedback": "ENGINE REVENUE: The engine data exists. Games link to engines through DEMO.GAMES_CORE.GAME_ENGINES. For engine revenue, join GAME_REVENUE to GAME_ENGINES on GAME_ID and to ENGINES on ENGINE_ID.",
        "feedback_rule": "Game engine data exists: CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_ENGINES maps each game to its engine (GAME_ID, ENGINE_ID, ENGINE_VERSION, CUSTOM_FORK), and CORTEX_SENSE_DEMO.GAME_CATALOG.ENGINES holds ENGINE_NAME. For game counts by engine, join CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_ENGINES to CORTEX_SENSE_DEMO.GAME_CATALOG.ENGINES on ENGINE_ID and COUNT(DISTINCT GAME_ID) by ENGINE_NAME. For revenue by engine, revenue tables in CORTEX_SENSE_DEMO.GAME_SALES are keyed by TITLE_ID; map them to catalog games with SELECT DISTINCT TITLE_ID, CATALOG_GAME_ID FROM CORTEX_SENSE_DEMO.GAME_SALES.TITLE_CODE_XREF, then CATALOG_GAME_ID = GAME_ID. Join that to GAME_ENGINES and ENGINES, then SUM(CORTEX_SENSE_DEMO.GAME_SALES.GAME_REVENUE.INCOME) grouped by ENGINE_NAME. Never say engine data is unavailable.",
        "indexed_text": "User is asking about game engines: which engines power the most revenue, games per engine, engine adoption, which engine a game uses, or revenue by engine.",
        "entity_keys": ["CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_ENGINES", "CORTEX_SENSE_DEMO.GAME_CATALOG.ENGINES", "CORTEX_SENSE_DEMO.GAME_SALES.TITLE_CODE_XREF"],
        "concepts": ["engine revenue", "game engines"],
    },
]


def record_feedback(record):
    payload = {
        "action": "record-feedback",
        "parameters": {
            "name": CONTEXT,
            "database_name": DB,
            "schema_name": SCHEMA,
            "type": record["type"],
            "raw_feedback": record["raw_feedback"],
            "feedback_rule": record["feedback_rule"],
            "indexed_text": record["indexed_text"],
        }
    }
    if "entity_keys" in record:
        payload["parameters"]["entity_keys"] = record["entity_keys"]
    if "concepts" in record:
        payload["parameters"]["concepts"] = record["concepts"]

    payload_json = json.dumps(payload, ensure_ascii=False)

    # Check for $$ in payload which would break dollar quoting
    if "$$" in payload_json:
        return None, "Payload contains $$ which breaks dollar quoting"

    sql = f"SELECT SYSTEM$CORTEX_AGENT_CORTEX_CONTEXT_BUILDER($${payload_json}$$) AS result;"

    fd, sql_path = tempfile.mkstemp(suffix=".sql")
    with os.fdopen(fd, "w") as f:
        f.write(sql)

    try:
        result = subprocess.run(
            ["snow", "sql", "-c", CONNECTION, "--enable-templating", "NONE", "--format", "json", "-f", sql_path],
            capture_output=True, text=True, timeout=60
        )
        os.unlink(sql_path)
        if result.returncode != 0:
            return None, result.stderr.strip()
        return result.stdout.strip(), None
    except Exception as e:
        os.unlink(sql_path)
        return None, str(e)


def main():
    global CONTEXT
    if "--context" in sys.argv:
        CONTEXT = sys.argv[sys.argv.index("--context") + 1]
    # Optional: --only "label1,label2" records just the records whose first concept matches
    records = RECORDS
    if "--only" in sys.argv:
        wanted = set(sys.argv[sys.argv.index("--only") + 1].split(","))
        records = [r for r in RECORDS if r.get("concepts", [""])[0] in wanted]
    print(f"Recording {len(records)} feedback records for {CONTEXT}...")
    success = 0
    errors = 0

    for i, record in enumerate(records, 1):
        concept_label = record.get("concepts", [""])[0] if record.get("concepts") else record["type"]
        stdout, err = record_feedback(record)
        if err:
            print(f"  [{i}/{len(records)}] ERROR ({concept_label}): {err[:200]}")
            errors += 1
        else:
            print(f"  [{i}/{len(records)}] OK ({concept_label})")
            success += 1
        time.sleep(0.5)  # small delay to avoid rate limiting

    print(f"\nDone: {success} succeeded, {errors} failed out of {len(records)} total")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
