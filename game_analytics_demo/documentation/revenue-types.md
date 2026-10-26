# Revenue Types and How They're Calculated

All revenue in this project lives in `CORTEX_SENSE_DEMO.GAME_SALES`. There are three independent revenue streams. **Total company revenue is their sum: $230,527,280 gross**, all time, through 2026-10-08.

| Stream | What the business sells | Gross revenue | Share | Data from |
|---|---|---|---|---|
| **Hardware** | Consoles, controllers, VR headsets | $175,660,811 | 76.2% | 2000-03-04 |
| **Subscriptions** | Recurring membership plans | $35,634,617 | 15.5% | 2010-06-29 |
| **Digital game sales** | Games, DLC and in-game purchases | $19,231,852 | 8.3% | 2005-03-22 |
| **Total company revenue** | | **$230,527,280** | 100% | |

Hardware is three-quarters of the business; game sales are under a tenth. Questions about "revenue" need to be clear about which of these they mean.

## 1. Hardware revenue

**Business meaning:** money from selling physical devices to customers.

- **Source:** `HARDWARE_SALES_TRANSACTIONS` (one row per sale), with `HARDWARE_PRODUCTS` for product details.
- **Calculation:** `SUM(GROSS_REVENUE)`. Each row is `QUANTITY × UNIT_PRICE`, the realized price, which can differ from the product's `LIST_PRICE`.
- **Breakdowns:**

  | Product type | Gross revenue |
  |---|---|
  | Console | $160,459,732 |
  | Controller | $12,101,149 |
  | VR headset | $3,099,930 |

  Also by `REGION` (on the sale), `MANUFACTURER` and `PRODUCT_NAME` (on the product), or by buyer via `BUYER_ID` → `CUSTOMER_ACCOUNTS`.
- **Not available:** no net or cost figure, and hardware sales aren't tied to a game title.

## 2. Subscription revenue

**Business meaning:** recurring membership charges for a subscription plan.

- **Source:** `SUBSCRIPTION_CHARGES` (one row per billing charge), with `SUBSCRIPTION_PLANS` for plan details.
- **Calculation:** `SUM(GROSS_REVENUE)`, by `CHARGE_TIMESTAMP` for when the money was charged. `BILLING_PERIOD_START` / `BILLING_PERIOD_END` give the period each charge covers.
- **Breakdowns:**

  | Plan tier | Gross revenue |
  |---|---|
  | Legacy | $15,585,060 |
  | Essential | $9,186,206 |
  | Extra | $6,272,739 |
  | Premium | $4,590,612 |

  Also by `PLAN_NAME` or `BILLING_CYCLE`, or per subscriber via `SUBSCRIBER_ID`. Paying subscribers = `COUNT(DISTINCT SUBSCRIBER_ID)`. Average revenue per subscriber (ARPS) = revenue ÷ paying subscribers.
- **Not available:** subscription revenue can't be tied to a game title (`SUBSCRIPTION_PLANS.GAME_ID` is empty for every plan), and there's no net figure.

## 3. Digital game revenue

**Business meaning:** money from selling games and in-game content: base games, DLC and microtransactions.

- **Source:** `DIGITAL_PRODUCT_TRANSACTIONS` (one row per purchase), with `DIGITAL_PRODUCTS` and `REVENUE_TYPES` for product details.
- **Calculation:**
  - **Gross:** `SUM(GROSS_REVENUE)` = $19,231,852.
  - **Net developer revenue:** `SUM(NET_DEVELOPER_REVENUE)` = $19,119,345. This is gross minus platform commission ($112,507). It's the only stream with a net figure.
- **Breakdowns:**

  | Monetization type (`REVENUE_TYPES.MONETIZATION_TYPE` via the product) | Gross revenue |
  |---|---|
  | Base game, digital | $8,907,143 |
  | Base game, physical | $7,881,148 |
  | DLC | $1,077,516 |
  | Cosmetic microtransaction | $486,671 |
  | Loot box | $402,513 |
  | Consumable microtransaction | $188,130 |
  | Battle pass | $150,389 |
  | Virtual currency | $138,341 |

  Also by platform (`PLATFORM_ID` → `PLATFORMS`), by title, or by title code (PlayStation only).
- **Getting the title:** take it from `DIGITAL_PRODUCTS.TITLE_ID`, not `DIGITAL_PRODUCT_TRANSACTIONS.TITLE_ID`, which is empty for 10% of revenue ($1.92M). See [revenue-by-title-vs-title-code.md](revenue-by-title-vs-title-code.md).

### Pre-built digital revenue tables

These are all the **same digital revenue**, pre-aggregated. They're convenient for title-level and trend questions, but they are not separate revenue.

`MONTHLY_REVENUE` is modeled in `SV_GAME_SALES` (metric `TOTAL_MONTHLY_INCOME`, with `REVENUE_SOURCE` described as the monetization type), along with `TITLES.RELEASE_DATE_PARSED` for date math. The verified query **"What is digital revenue in the launch month, early life and tail?"** shows the lifecycle split: launch month $6,209,694, early life (months 1-5) $6,927,415, tail (month 6+) $6,094,744.

| Table | Grain | Use for |
|---|---|---|
| `MONTHLY_REVENUE` | Title × month × revenue source | Monthly trends; `REVENUE_SOURCE` holds the monetization type (same values and totals as above), not a lifecycle phase. Sum `MONTHLY_INCOME`, never `CUMULATIVE_INCOME`. For launch or tail phases, use months since `TITLES.RELEASE_DATE` (a `YYYYMMDD` string; month 0 = launch). |
| `QUARTERLY_REVENUE` | Title × year × quarter | Quarterly and year-over-year trends |
| `GAME_REVENUE` | Title | Lifetime game revenue (`INCOME`); equals digital gross for every title |
| `VW_PLATFORM_EXCLUSIVITY` | Title × exclusive platform | Revenue of exclusive titles (count each title once) |

## Calculating total company revenue

Sum **each stream separately**, then add the three totals:

```sql
SELECT 'Hardware' AS stream, SUM(gross_revenue) AS gross_revenue
FROM CORTEX_SENSE_DEMO.GAME_SALES.HARDWARE_SALES_TRANSACTIONS
UNION ALL
SELECT 'Subscriptions', SUM(gross_revenue)
FROM CORTEX_SENSE_DEMO.GAME_SALES.SUBSCRIPTION_CHARGES
UNION ALL
SELECT 'Digital game sales', SUM(gross_revenue)
FROM CORTEX_SENSE_DEMO.GAME_SALES.DIGITAL_PRODUCT_TRANSACTIONS;
```

`SV_GAME_SALES` has this as the verified query **"What is total company revenue by revenue stream?"**, which also returns each stream's share. The verified query **"What is total spend per customer across digital, hardware and subscriptions?"** gives the same $230.53M total, split by customer instead.

### Rules for getting it right

- **Never add the pre-built digital tables to the total.** `MONTHLY_REVENUE`, `QUARTERLY_REVENUE`, `GAME_REVENUE` and `VW_PLATFORM_EXCLUSIVITY` repeat the digital stream; adding any of them double-counts $19.2M.
- **Never join the three transaction tables together** before summing. Joining them (for example through customers) multiplies rows and inflates the total; aggregate each first.
- **Total company revenue is gross.** Only digital has a net figure. A "net" total could only be digital net + hardware gross + subscription gross, and must be labelled that way.
- **Use each stream's own date** for a period: `SALE_TIMESTAMP` (hardware), `CHARGE_TIMESTAMP` (subscriptions), `TRANSACTION_TIMESTAMP` (digital). For example, 2025 revenue was hardware $10,411,935, subscriptions $4,961,465 and digital $956,229, a total of $16,329,629.
- **Streams start in different years** (hardware 2000, digital 2005, subscriptions 2010), so all-time totals cover different spans of history per stream.

## Which revenue to use

| Question | Use |
|---|---|
| Total company revenue / revenue mix | All three streams, summed separately |
| Game, title, franchise or publisher revenue | Digital (`GAME_REVENUE` or digital transactions), mapped to the catalog via `TITLE_CODE_XREF` |
| Revenue by monetization model (DLC, loot boxes, ...) | Digital, via `DIGITAL_PRODUCTS` → `REVENUE_TYPES` |
| Console / device sales | Hardware |
| Membership revenue, ARPS, plan tiers | Subscriptions |
| Revenue per customer | All three streams per customer, summed separately |
| Net revenue | Digital only |

## Source

Figures are from `CORTEX_SENSE_DEMO.GAME_SALES`, queried on 2026-10-22.
