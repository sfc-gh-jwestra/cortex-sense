# TITLE_CODE_XREF — Linking Sales Revenue to the Game Catalog

`CORTEX_SENSE_DEMO.GAME_SALES.TITLE_CODE_XREF` is the bridge between the sales world and the catalog world. Revenue is keyed by sales `TITLE_ID`, while genre, developer, publisher, franchise, etc. live in the catalog under `GAME_ID`. This table connects the two.

## Structure

| Column | Meaning |
|---|---|
| `TITLE_CODE` | Platform product code (e.g. `CUSA86104`, `PPSA97532`). One row per code. |
| `TITLE_ID` | Sales title — the key used by all revenue tables |
| `PLATFORM_CODE` | PS2 / PS3 / PS4 / PS5 |
| `CATALOG_GAME_ID` | Maps to `GAME_CATALOG.GAMES.GAME_ID` |

- 100 codes covering 88 titles. A title can have multiple codes, one per platform (e.g. title 5063 has both a PS4 and a PS5 code).
- Every row has a catalog ID, every catalog ID resolves to a real game, and each title maps to exactly one game.

## How it answers revenue questions

Join path:

```
GAME_REVENUE / QUARTERLY_REVENUE / DIGITAL_PRODUCT_TRANSACTIONS
   → TITLE_CODE_XREF (on TITLE_ID)
   → GAME_CATALOG.GAMES (on CATALOG_GAME_ID)
```

This enables questions such as:

- Revenue by publisher, developer, franchise, or indie vs. non-indie
- Revenue by genre, mechanic, or game mode (via the catalog classification tables)
- Revenue of similar / cannibalizing games (via `GAME_SIMILARITY_SCORES`, `VW_CANNIBALIZATION_CANDIDATES`)
- Which platforms or codes a revenue-earning game shipped on

Always take the **distinct** title → game mapping first. Otherwise a game released on both PS4 and PS5 gets its revenue counted twice.

```sql
with map as (
    select distinct title_id, catalog_game_id
    from CORTEX_SENSE_DEMO.GAME_SALES.TITLE_CODE_XREF
)
select g.franchise_name, sum(r.income) as revenue
from CORTEX_SENSE_DEMO.GAME_SALES.GAME_REVENUE r
join map m on m.title_id = r.title_id
join CORTEX_SENSE_DEMO.GAME_CATALOG.GAMES g on g.game_id = m.catalog_game_id
group by 1
order by 2 desc;
```

## Caveats

- **Use the xref, not `TITLES.CATALOG_GAME_ID`.** That column is NULL for 13 titles the xref does map (including *The Last of Us Part II* and *God of War: Ascension*). Joining through `TITLES` silently drops them.
- **Small coverage gap.** Two titles with revenue have no xref row: about $230K of $19.2M (1.2%). Catalog-level breakdowns will come up slightly short unless those titles are added or reported as "unmapped".
- **`PLATFORM_CODE` does not split revenue.** `GAME_REVENUE` has no platform column. For a platform split, use `DIGITAL_PRODUCT_TRANSACTIONS.PLATFORM_ID`.
- **The semantic view doesn't use this link yet.** `semantic_views/SV_GAME_SALES.yaml` describes itself as having "No link to the Catalog". Adding `TITLE_CODE_XREF` and `GAMES` with these relationships would let Cortex Analyst answer catalog-level revenue questions directly.

## Using TITLE_CODE_XREF within the GAME_SALES schema only

Within `GAME_SALES`, the xref adds one join that answers new questions: digital revenue broken down by the individual product code each title shipped under. Its other uses either have no data behind them or need no xref at all.

### What the xref connects to inside GAME_SALES

| Join | Works? | Finding |
|---|---|---|
| `PLATFORM_CODE` → `PLATFORMS.PLATFORM_CODE` | **Yes** | All 100 codes match a platform (PS2, PS3, PS4, PS5). Each title has at most one code per platform. |
| `(TITLE_ID, PLATFORM_CODE)` → `DIGITAL_PRODUCT_TRANSACTIONS` (title via `DIGITAL_PRODUCTS`, platform via `PLATFORM_ID`) | **Yes** | The useful one: attributes each digital sale to an exact product code. |
| `CATALOG_GAME_ID` → `SUBSCRIPTION_PLANS.GAME_ID` | **No** | All 4 plans have NULL `GAME_ID`, so the $35.6M of subscription revenue can't be tied to a title. |
| `GAME_REVENUE` / `QUARTERLY_REVENUE` | Not needed | Keyed by `TITLE_ID` only, with no platform column, so they join to `TITLES` directly. |
| `HARDWARE_SALES_TRANSACTIONS` | Not applicable | Hardware sales have no title, so there's nothing for the xref to match. |

### Recommended verified query: "What is digital revenue by title code?"

Cortex Analyst can't infer this join from the semantic view's relationships:

- **Two-column match:** a transaction belongs to a code only when *both* the title and the platform match.
- **Indirect platform match:** transactions carry `PLATFORM_ID` and the xref carries `PLATFORM_CODE`, so the join has to pass through `PLATFORMS`.
- **What goes wrong otherwise:** joining on `TITLE_ID` alone gives cross-generation titles every code, so their revenue appears under both the PS4 and PS5 codes.
- **Take the title from the product:** `DIGITAL_PRODUCT_TRANSACTIONS.TITLE_ID` is NULL for 10% of revenue, but `DIGITAL_PRODUCTS.TITLE_ID` is always populated and agrees wherever both exist.

```sql
SELECT x.title_code, t.title_name, p.platform_name,
       SUM(d.gross_revenue)         AS gross_revenue,
       SUM(d.net_developer_revenue) AS net_developer_revenue
FROM CORTEX_SENSE_DEMO.GAME_SALES.DIGITAL_PRODUCT_TRANSACTIONS d
JOIN CORTEX_SENSE_DEMO.GAME_SALES.DIGITAL_PRODUCTS pr
  ON pr.digital_product_id = d.digital_product_id
JOIN CORTEX_SENSE_DEMO.GAME_SALES.PLATFORMS p
  ON p.platform_id = d.platform_id
JOIN CORTEX_SENSE_DEMO.GAME_SALES.TITLE_CODE_XREF x
  ON x.title_id = pr.title_id AND x.platform_code = p.platform_code
JOIN CORTEX_SENSE_DEMO.GAME_SALES.TITLES t
  ON t.title_id = pr.title_id
GROUP BY 1, 2, 3
ORDER BY gross_revenue DESC;
```

Top result: Horizon Zero Dawn (`CUSA86215`, PS4) at $1.46M, followed by God of War (2018) and Marvel's Spider-Man at $1.38M each.

**Coverage caveat:** $603K of the $19.2M digital revenue (3.1%) was sold on platforms that have no code for that title (Switch, PC, Xbox), or for titles with no codes. Those sales drop out of this query, so it is not a total-revenue figure. The question wording says "by title code" to make that clear. See [revenue-by-title-vs-title-code.md](revenue-by-title-vs-title-code.md).

### Questions not added as verified queries

- **"PS4 vs PS5 revenue for cross-gen titles", or "revenue for code `CUSA86955`".** Same join path, so they'd only repeat it; Cortex Analyst can adapt the main query with a filter.
- **"Which title is `CUSA86955`?"** A single-table lookup Cortex Analyst handles already.
- **Subscription revenue by title.** No data to support it until `SUBSCRIPTION_PLANS.GAME_ID` is populated.

### Semantic view changes

Applied to `SV_GAME_SALES.yaml`:

1. The verified query above.
2. Custom instructions: get a transaction's title through `DIGITAL_PRODUCTS`; never join `TITLE_CODE_XREF` to revenue on `TITLE_ID` alone; title-code revenue is PlayStation-only and not a total.

Not applied: a relationship `XREF_PLATFORM` from `TITLE_CODE_XREF.PLATFORM_CODE` to `SALES_PLATFORMS.PLATFORM_CODE`. It would help simple code-by-platform questions, but requires declaring `PLATFORM_CODE` as a unique key on `SALES_PLATFORMS`, and it does not by itself make revenue-by-code questions work.
