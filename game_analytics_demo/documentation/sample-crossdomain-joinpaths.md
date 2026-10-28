
# Sample Cross-Domain Join Paths

These join paths cross from `GAME_SALES` into `GAME_CATALOG`. No semantic view covers them: `semantic_views/SV_GAME_SALES.yaml` is limited to the `GAME_SALES` schema on purpose. Instead, Cortex Sense learns them, which is why the Sense agent joins the two domains correctly and the other agents often don't.

## How Cortex Sense learns these joins

Two install steps teach the patterns below:

1. **Query history** (`scripts/prime_query_history.py`, run by `install/05-prime-query-history.sql`). The script runs cross-domain queries that follow these join paths, so they land in `QUERY_HISTORY` and `ACCESS_HISTORY`. Cortex Sense mines that history for the tables that are joined together and the keys they are joined on. Every primed query follows the feedback rules, because Sense learns from whatever is in the history, including mistakes.
2. **Feedback rules** (`scripts/record_feedback.py`, run by `install/08-record-feedback.sql`). The rules state each lesson explicitly: map titles only through `SELECT DISTINCT TITLE_ID, CATALOG_GAME_ID FROM TITLE_CODE_XREF`, never use `TITLES.CATALOG_GAME_ID`, keep genres to `MATCH_STATUS = 'FULL'`, and so on. They apply as soon as they are recorded.

History shows Sense *how* the tables are joined; the rules tell it *why*, and which tempting shortcuts are wrong. The deterministic checks in `scripts/rule_checks.py` then confirm that the agents' SQL follows the rules.

## The patterns

The examples cover the questions the xref opens up (see [Joining across domains](database-design.md#joining-across-domains)). Each one adds a join lesson the others don't.

| # | Example question | Join lesson |
|---|---|---|
| 1 | Revenue by publisher / developer / franchise | Base path: revenue → xref (made distinct) → `GAMES` |
| 2 | Revenue by genre / mechanic / mode | One-to-many genre table and its double-counting risk |
| 3 | Revenue of similar / cannibalizing games | Pair table that needs the xref joined twice |

A fourth question, which platforms a game shipped on, reads the xref alone with no revenue join, so it teaches no join path. Its lesson ("don't split revenue by `PLATFORM_CODE`") is a warning rather than a join.

The queries below use inner joins to keep them short. The feedback rules go further: they use a `LEFT JOIN` and report titles with no catalog mapping as `'Unmapped'` (and genre gaps as `'No full genre match'`) so totals still match `GAME_REVENUE`.

## 1. Base path: "What is total revenue by franchise?"

Lessons:
- Go through `TITLE_CODE_XREF`, not `TITLES.CATALOG_GAME_ID` (NULL for 13 mapped titles).
- Make the xref distinct on `(TITLE_ID, CATALOG_GAME_ID)` so games on two platforms aren't counted twice.

```sql
with map as (select distinct title_id, catalog_game_id from CORTEX_SENSE_DEMO.GAME_SALES.TITLE_CODE_XREF)
select g.franchise_name, sum(r.income) as total_revenue
from CORTEX_SENSE_DEMO.GAME_SALES.GAME_REVENUE r
join map m on m.title_id = r.title_id
join CORTEX_SENSE_DEMO.GAME_CATALOG.GAMES g on g.game_id = m.catalog_game_id
group by 1 order by 2 desc;
```

## 2. One-to-many genre: "What is revenue by genre?"

Doesn't repeat the `GAMES` hop: joins `CATALOG_GAME_ID` straight to the genre table, so the query shows only the new part.

Lessons:
- **Filter to `MATCH_STATUS = 'FULL'`.** Without it there are about 38 genre rows per game, mostly `NONE` / `PARTIAL`. Even with it, a game averages 3.2 genres.
- **Each game's revenue counts once in every genre it belongs to.** Genre totals deliberately add up to more than total revenue.

```sql
with map as (select distinct title_id, catalog_game_id from CORTEX_SENSE_DEMO.GAME_SALES.TITLE_CODE_XREF)
select gc.genre, sum(r.income) as genre_revenue, count(distinct gc.game_id) as games
from CORTEX_SENSE_DEMO.GAME_SALES.GAME_REVENUE r
join map m on m.title_id = r.title_id
join CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_GENRE_CLASSIFICATION gc
  on gc.game_id = m.catalog_game_id and gc.match_status = 'FULL'
group by 1 order by 2 desc;
-- A game in several genres contributes its full revenue to each; genre totals exceed overall revenue.
```

Mechanics and modes use the same one-to-many shape.

## 3. Pair table: "Which highly similar game pairs earn the most combined revenue?"

Lessons:
- `GAME_SIMILARITY_SCORES` has two game keys, `GAME_A_ID` and `GAME_B_ID`.
- Sum revenue per game first, then map it onto each side of the pair with two aliases. This avoids double counting.
- Use `WEIGHTED_OVERLAP` or `OVERLAP_TIER` to keep only strongly similar pairs.

```sql
with map as (select distinct title_id, catalog_game_id from CORTEX_SENSE_DEMO.GAME_SALES.TITLE_CODE_XREF),
game_rev as (
  select m.catalog_game_id as game_id, sum(r.income) as revenue
  from CORTEX_SENSE_DEMO.GAME_SALES.GAME_REVENUE r join map m on m.title_id = r.title_id
  group by 1)
select s.game_a_name, s.game_b_name, s.weighted_overlap,
       a.revenue as game_a_revenue, b.revenue as game_b_revenue,
       a.revenue + b.revenue as combined_revenue
from CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_SIMILARITY_SCORES s
join game_rev a on a.game_id = s.game_a_id
join game_rev b on b.game_id = s.game_b_id
where s.weighted_overlap >= 0.6
order by combined_revenue desc limit 20;
```

The `0.6` cutoff is a placeholder; `OVERLAP_TIER` may be the better filter. The franchise cannibalization feedback rule uses `WEIGHTED_OVERLAP >= 0.3` for same-publisher franchises.

All three queries were compiled against `CORTEX_SENSE_DEMO` but not executed.
