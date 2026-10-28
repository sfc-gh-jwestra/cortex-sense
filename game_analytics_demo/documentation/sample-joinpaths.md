
# Sample Join Paths — Verified Query Candidates

> **Scope note:** these join paths cross from `GAME_SALES` into `GAME_CATALOG`. `semantic_views/SV_GAME_SALES.yaml` is intentionally limited to the `GAME_SALES` schema, so these VQRs do not belong in that semantic view. They suit a cross-domain artifact instead, such as a Cortex Sense context or an agent that spans both domains.

Using the four example questions in [title_code_xref.md](title_code_xref.md), three are worth a verified query (VQR) each. Each VQR adds a join lesson the others don't, so no join path is repeated.

| # | Example question | VQR? | Join lesson it adds |
|---|---|---|---|
| 1 | Revenue by publisher / developer / franchise | **Yes** | Base path: revenue → xref (made distinct) → `GAMES` |
| 2 | Revenue by genre / mechanic / mode | **Yes** | One-to-many genre table and its double-counting risk |
| 3 | Revenue of similar / cannibalizing games | **Yes** | Pair table that needs the xref joined twice |
| 4 | Platforms a game shipped on | **No** | Reads the xref alone with no revenue join, so it teaches no join path. Its real lesson ("don't split revenue by `PLATFORM_CODE`") is a warning and belongs in custom instructions. |


## VQR 1 — Base path: "What is total revenue by franchise?"

Teaches:
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

## VQR 2 — One-to-many genre: "What is revenue by genre?"

Doesn't repeat the `GAMES` hop: joins `CATALOG_GAME_ID` straight to the genre table, so the query shows only the new part.

Teaches:
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

Mechanics and modes use the same one-to-many shape, so they don't need VQRs of their own.

## VQR 3 — Pair table: "Which highly similar game pairs earn the most combined revenue?"

Teaches:
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

The `0.6` cutoff is a placeholder; `OVERLAP_TIER` may be the better filter.

All three queries were compiled against `CORTEX_SENSE_DEMO` but not executed.
