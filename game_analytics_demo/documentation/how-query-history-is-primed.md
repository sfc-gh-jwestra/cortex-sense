# How query history is primed

Cortex Sense learns join paths and query patterns from `QUERY_HISTORY` / `ACCESS_HISTORY`
(the `query_history` source in `context/scope.yaml`). `scripts/prime_query_history.py` seeds
that history with 73 queries over `CORTEX_SENSE_DEMO` that demonstrate correct usage. Every
query follows the rules in `scripts/record_feedback.py`: Cortex Sense copies what it sees in
history, so a rule-breaking query here would teach it the wrong pattern.

## Files

| File | Role |
| --- | --- |
| `scripts/prime_query_history.py` | Single source of truth. Defines `QUERIES` as `(label, sql)` pairs and can run them directly. |
| `install/05-prime-query-history.sql` | Generated from `QUERIES` by `scripts/generate_install_sql.py`; do not edit by hand. |

```bash
python3 scripts/prime_query_history.py                 # run all queries directly
python3 scripts/generate_install_sql.py                # regenerate install/05 (and the other generated steps)
snow sql -c CORTEX_SENSE_DEMO_CONN --enable-templating NONE -f install/05-prime-query-history.sql
```

The runner calls `snow sql -c $SNOWFLAKE_CONNECTION_NAME` (default `CORTEX_SENSE_DEMO_CONN`) once per
query, the same path as the other scripts. The script is rerunnable; each run just adds more history.

## The four query groups

### 1. Semantic view (12 queries)

These use the literal `SELECT * FROM SEMANTIC_VIEW(CORTEX_SENSE_DEMO.GAME_SALES.SV_GAME_SALES DIMENSIONS ... METRICS ... [WHERE ...])` syntax:

- revenue by title, monetization type and platform (gross and net);
- total company revenue by stream: hardware, subscription and digital metrics, each summed separately;
- hardware revenue by product type and by region;
- subscription revenue by plan tier;
- monthly trend, and monthly revenue by `REVENUE_SOURCE`;
- Sony revenue by studio (`WHERE titles.publisher_label = 'SIE'`);
- customers by region and status;
- titles by exclusivity type.

The SV must be deployed (`install/03-deploy-semantic-view.sql`) before these run.

### 2. Cross-domain: GAME_SALES revenue x GAME_CATALOG attributes (25 queries)

- top 5 earners, revenue by franchise, developer, indie vs studio and publisher;
- genre revenue (detailed and top level), engine revenue, exclusivity revenue, monetization risk;
- lifecycle phases, award winners' launch-month revenue;
- quarterly revenue (Sony by quarter, Q1 YoY, franchise by year);
- accessibility gaps in top earners, accessibility investment priority;
- proven capability, breakout hits, release-calendar conflicts, fiscal year.

### 3. Catalog only (12 queries)

Content rating risk (all three criteria), live-service games, EU risk inputs (PEGI 18,
loot boxes, paid DLC, mobile), rating equivalence, awards by awarding body, accessibility
gaps, audience profile, audience comparison (both pair directions), high-overlap pairs,
franchise cannibalization, emerging-genre whitespace, engine counts, last fiscal year's
releases.

### 4. Streamlit dashboard SQL (24 queries)

These are the queries from `streamlits/streamlit_app.py`. The dashboard's default filters are
written in as fixed values: 2023-10-09 to 2026-10-09 (titles tab 2023-10-01 to 2026-10-08),
monthly grain, no platform or region filter.

Three dashboard queries break a rule, so the primed versions are corrected:

| Dashboard query | Problem in the app | Primed version |
| --- | --- | --- |
| Top 15 digital products | Joins `TITLES` on the transaction's `TITLE_ID`, which is NULL for ~10% of revenue | Title via `DIGITAL_PRODUCTS.TITLE_ID` |
| Top 15 titles by net revenue | Same | Title via `DIGITAL_PRODUCTS.TITLE_ID` |
| Exclusive vs multi-platform | `SUM(DISTINCT income)` merges titles that happen to have equal income | Dedupe to one row per title, then `SUM` |

The app itself still contains these three issues.

## Rules every query follows

| Rule (record_feedback.py) | How the primed SQL applies it |
| --- | --- |
| Publisher and studio names | Filter each schema with its own spelling: `PUBLISHER_LABEL = 'SIE'` in sales, `PUBLISHER_NAME = 'Sony Interactive Entertainment'` in the catalog. Never join on names. Show developers with `REPLACE(DEVELOPER_NAME, '_', ' ')`. |
| Revenue analysis | Map sales to catalog only through `SELECT DISTINCT TITLE_ID, CATALOG_GAME_ID FROM TITLE_CODE_XREF`. Never use `TITLES.CATALOG_GAME_ID`. Keep the two unmapped titles ($229,800) as `'Unmapped'`. "Top earners" is `ORDER BY INCOME DESC LIMIT 5`. |
| Digital title path (SV instruction) | A transaction's title comes from `DIGITAL_PRODUCTS.TITLE_ID`. |
| Genre revenue | `MATCH_STATUS = 'FULL'` or `VW_GAME_GENRE_ROLLUP` with `ROLLUP_DEPTH = 1`. Report `'No full genre match'` and `'Unmapped'`. Totals overlap and are never used as shares. |
| Monthly revenue / time series | Sum `MONTHLY_INCOME`, never `CUMULATIVE_INCOME`. `REVENUE_SOURCE` is the monetization type. Phases come from months since `TO_DATE(TITLES.RELEASE_DATE, 'YYYYMMDD')`: launch = 0, early life = 1-5, tail = 6+. Never add monthly revenue to transaction revenue. |
| Quarterly revenue | `QUARTERLY_REVENUE` grouped by `REVENUE_YEAR`, `REVENUE_QUARTER`. YoY compares the same quarter. |
| Total company revenue | Hardware, subscription and digital gross are each summed separately. |
| Exclusivity revenue | `IS_CURRENTLY_EXCLUSIVE = TRUE`, income counted once per `TITLE_ID`. |
| Monetization risk | `GAME_SALES.MONETIZATION_TYPES` → `GAME_MONETIZATION` → `VW_PLATFORM_EXCLUSIVITY` on `TITLE_ID`. |
| Content rating risk | `MIN_AGE >= 16`; violence from FULL genres or Grotesque + Combat; romance from context, gameplay or DatingSim. Each criterion is flagged separately. |
| Live-service / EU risk | `ONLINE_REQUIRED = TRUE` plus recurring monetization. Flags PEGI 18, loot boxes, paid DLC and mobile (`'Android'`, `'Apple'`). |
| Rating equivalence | Self-join `AGE_RATINGS` on `MIN_AGE`. |
| Awards | `GAME_AWARDS` → `AWARDS`, `WON_OR_NOMINATED = 'won'`, grouped by `AWARDING_BODY`. |
| Accessibility / investment | `VW_ACCESSIBILITY_GAPS`, `IS_SUPPORTED = FALSE`. Priority score = gap count × average income, used as a ranking only. Family flag = `MIN_AGE <= 10`. |
| Audience comparison | `GAME_SIMILARITY_SCORES` matched in both directions. Cite `OVERLAP_TIER`; never re-derive it. |
| Franchise cannibalization | `VW_CANNIBALIZATION_CANDIDATES`, `WEIGHTED_OVERLAP >= 0.3`. |
| Proven capability / breakout hits / release calendar | Top-quartile income (`NTILE(4)`) is used only in these rules. Release-calendar conflicts require the same quarter and `WEIGHTED_OVERLAP >= 0.3`. |
| Emerging genre | `MARKET_STATUS IN ('UNDERSERVED', 'WHITESPACE')`; this measures supply, not demand. |
| Engine revenue | xref → `GAME_ENGINES` → `ENGINES`. |
| Fiscal year / release date | Fiscal year = calendar year. `GAMES.RELEASE_DATE` is a DATE and is used directly. |

## Reconciliation checks

| Check | Expected |
| --- | --- |
| Revenue by title (SV) | 87 titles, $19,231,852 |
| Franchise total including Unmapped | $19,231,852, of which Unmapped is $229,800 |
| Total company revenue (SV) | Hardware $175,660,811 / Subscriptions $35,634,617 / Digital $19,231,852 |
| Currently exclusive income, once per title | $6,807,969 |

## Semantic view change made for this

The SV relationship `TXN_TITLE` (`DIGITAL_TRANSACTIONS` → `TITLES`) was removed. Together
with `TXN_PRODUCT` → `PRODUCT_TITLE`, it gave transactions two paths to `TITLES`. Any
`SEMANTIC_VIEW` query of transaction revenue by title then failed with *"Multi-path
relationship ... is not supported"*. Titles now resolve only through `DIGITAL_PRODUCTS`,
which is the complete path.

## Adding a query

1. Add a `(label, sql)` pair to `QUERIES` in the right section of the `.py`, using the `S`, `C`, `SV` and `TITLE_MAP` constants.
2. Check it against every rule above. If it contradicts one, don't add it.
3. Run `python3 scripts/prime_query_history.py` and confirm it succeeds and returns rows.
4. Run `python3 scripts/generate_install_sql.py` to regenerate `install/05-prime-query-history.sql`.
