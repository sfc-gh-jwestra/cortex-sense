# Digital Revenue by Title vs. by Title Code

`semantic_views/SV_GAME_SALES.yaml` has two verified queries that look similar but answer different business questions:

1. **"What is digital revenue by title?"** (onboarding question): how much each game earned.
2. **"What is digital revenue by title code?"**: how much each PlayStation product listing earned.

On amounts, the title query returns all **$19.23M** of digital revenue. The title-code query returns **$18.63M (96.9%)**.

## How a sale gets its title

Both queries take a transaction's title from its **product**: `DIGITAL_TRANSACTIONS → DIGITAL_PRODUCTS → TITLES`.

`DIGITAL_PRODUCT_TRANSACTIONS.TITLE_ID` is NULL on 53,444 transactions ($1.92M, 10% of revenue), but `DIGITAL_PRODUCTS.TITLE_ID` is always populated, and the two agree on every transaction where both exist. Joining on the transaction's own `TITLE_ID` (the `TXN_TITLE` relationship) wrongly leaves that $1.92M without a title. The semantic view's custom instructions tell Cortex Analyst to use the product path.

## Business standpoint

| | **By title** | **By title code** |
|---|---|---|
| Question it answers | How much did each game earn? | How much did each PlayStation product listing earn? |
| Unit | One row per game (87 titles) | One row per code, i.e. per title on one platform (e.g. `CUSA87843` = PS4) |
| Typical users | Executives, portfolio and franchise reviews, budgeting | Platform partnerships, storefront operations, reconciling against platform payout reports, PS4 vs PS5 performance |
| Includes | Every digital sale | Only sales on a platform where the title has a code |

## Amount returned

| Revenue | Amount | % | By title | By title code |
|---|---|---|---|---|
| Sales that match a title code | $18,628,366 | 96.9% | ✓ | ✓ |
| Title has codes, but not for this platform (Switch, PC, Xbox) | $373,687 | 1.9% | ✓ | — |
| Title has no codes at all | $229,800 | 1.2% | ✓ | — |
| **Total** | **$19,231,852** | | **$19.23M** | **$18.63M** |

The difference is **$603K (3.1%)**. `TITLE_CODE_XREF` only holds PlayStation codes (PS2 to PS5), so Switch, PC and Xbox sales can never match one, and two titles have no codes at all.

## Example: MLB The Show 21

| Platform | Code | Gross revenue |
|---|---|---|
| PlayStation 4 | `CUSA87843` | $85,315 |
| PlayStation 5 | `PPSA97236` | $45,519 |
| Xbox Series X\|S | none | $12,602 |
| Xbox One | none | $6,565 |

- **By title:** one row for MLB The Show 21, at **$150,001**.
- **By title code:** two rows, $85,315 (PS4) and $45,519 (PS5), for **$130,834**. The $19,167 of Xbox revenue doesn't appear, because those sales have no code.

## What this means for users

- **Totals:** never use the title-code query to answer "what did we earn". It leaves out non-PlayStation sales.
- **Platform comparisons:** it is the right query for "how did the PS5 version compare to the PS4 version", and for matching revenue to a PlayStation product code.
- **Non-PlayStation revenue:** the title-code query will never show it. For a full platform split including Xbox, PC and Switch, use digital revenue by title and platform (`DIGITAL_TRANSACTIONS` joined to `SALES_PLATFORMS`, title via `DIGITAL_PRODUCTS`), with no xref involved.

## Source

Figures are gross revenue from `CORTEX_SENSE_DEMO.GAME_SALES.DIGITAL_PRODUCT_TRANSACTIONS`, with titles taken from `DIGITAL_PRODUCTS` and reconciled against `TITLE_CODE_XREF`, `PLATFORMS` and `TITLES` on 2026-10-22.
