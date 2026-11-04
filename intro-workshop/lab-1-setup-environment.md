# Lab 1: Set Up the Environment

## The storyline

You are on the analytics team at **PawPrime**, an online retailer of pet products. Customers shop on the web, through the mobile app, or with **Autoship** (recurring deliveries). The catalog covers dog, cat, fish, bird, small-animal and reptile supplies across eight categories: Food, Treats, Toys, Health, Grooming, Beds & Furniture, Aquarium and Habitats.

Business users keep sending the same kinds of questions to the data team: which categories make money, how Autoship customers behave, who is about to churn. The goal of this workshop is to let them ask those questions in plain English with **conversational analytics** instead of waiting on SQL.

In this lab you build the data foundation:

| Object | What it holds |
|---|---|
| `CUSTOMER` | 500 customers: name, email, state, region, signup date, loyalty tier, primary pet type, Autoship enrollment |
| `PRODUCT` | 60 products: name, category, pet type, brand, list price, unit cost, active flag |
| `ORDERS` | 3,000 orders over two years: date, status, channel, shipping fee, discount |
| `ORDER_ITEM` | ~7,500 order lines: product, quantity, unit price paid, line total |
| `SV_PET_STORE` | Semantic view joining the four tables, with business metrics and synonyms |

All objects live in `CORTEX_SENSE_DEMO.WORKSHOP`. The data is synthetic and deterministic, so everyone in the workshop sees the same numbers.

> The order table is named `ORDERS` because `ORDER` is a reserved word in SQL.

### Business rules baked into the data

- **Revenue** is `SUM(ORDER_ITEM.LINE_TOTAL)`. Never sum columns on `ORDERS` as revenue.
- **Net sales** exclude orders with `ORDER_STATUS = 'Cancelled'`.
- **Gross margin** is `LINE_TOTAL - QUANTITY * PRODUCT.UNIT_COST`. Margins differ by category (Food is thin, Toys and Treats are rich).
- Shipping is free on orders over $49.

## Questions business users will ask

- What were our net sales last month, and how does that compare to the same month last year?
- Which product categories have the highest gross margin?
- What are our top 10 products by units sold?
- How much revenue comes from dog products versus cat products?
- What is the average order value by channel (Web, Mobile App, Autoship)?
- Do Autoship customers spend more per customer than one-time buyers?
- Which region and loyalty tier generate the most revenue?
- Who are our top 10 customers by lifetime spend?
- Which customers haven't ordered in the last 180 days?
- Which categories have the highest return rate?
- Are cat owners buying dog products (cross-sell)?
- Are discontinued products still selling?

## Setup steps

### Prerequisites

- A Snowflake role that can create databases and schemas (for example `ACCOUNTADMIN` or `SYSADMIN`) and a running warehouse
- The [Snowflake CLI](https://docs.snowflake.com/en/developer-guide/snowflake-cli/index) (`snow`) with a connection configured
- Python 3.9 or later

The commands below use the connection `CORTEX_SENSE_DEMO_CONN`. Swap in your own connection name, or set `SNOWFLAKE_CONNECTION_NAME` for the Python script.

### Step 1: Create the database, schema, tables and data

From the repository root:

```bash
snow sql -c CORTEX_SENSE_DEMO_CONN --enable-templating NONE -f intro-workshop/sql/01_create_tables.sql
```

This script:

1. Creates the `CORTEX_SENSE_DEMO` database and the `WORKSHOP` schema if they don't exist
2. Creates `CUSTOMER`, `PRODUCT`, `ORDERS` and `ORDER_ITEM`, with comments on every table and column
3. Loads synthetic data using `GENERATOR` with seeded randomness

It is rerunnable: each run recreates the tables with the same data.

### Step 2: Create the semantic view

```bash
snow sql -c CORTEX_SENSE_DEMO_CONN --enable-templating NONE -f intro-workshop/sql/02_create_semantic_view.sql
```

This creates `CORTEX_SENSE_DEMO.WORKSHOP.SV_PET_STORE`, which defines:

- **Relationships**: `ORDERS → CUSTOMER`, `ORDER_ITEM → ORDERS`, `ORDER_ITEM → PRODUCT`
- **Dimensions**: customer region, loyalty tier, primary pet type, Autoship flag; product category, pet type, brand; order date, month, status, channel
- **Metrics**: `revenue`, `units_sold`, `gross_margin`, `gross_margin_pct`, `order_count`, `total_discounts`, `total_shipping`, `customer_count`

> The `revenue` metric includes every order status. Add `WHERE orders.order_status <> 'Cancelled'` to get net sales.

### Step 3: Prime the query history

```bash
python3 intro-workshop/scripts/prime_query_history.py
```

This runs 22 realistic analyst queries (8 against the semantic view, 14 hand-written SQL against the tables) so `QUERY_HISTORY` and `ACCESS_HISTORY` show how the tables are really joined, filtered and aggregated. Cortex Sense learns from this history in later labs.

Expect `Done: 22 succeeded, 0 failed`. Running it again just adds more history.

> `ACCOUNT_USAGE` views can lag by up to a few hours, so run this step early.

### Step 4: Verify

```sql
SELECT
  (SELECT COUNT(*) FROM CORTEX_SENSE_DEMO.WORKSHOP.CUSTOMER)   AS customers,
  (SELECT COUNT(*) FROM CORTEX_SENSE_DEMO.WORKSHOP.PRODUCT)    AS products,
  (SELECT COUNT(*) FROM CORTEX_SENSE_DEMO.WORKSHOP.ORDERS)     AS orders,
  (SELECT COUNT(*) FROM CORTEX_SENSE_DEMO.WORKSHOP.ORDER_ITEM) AS order_items;

SHOW SEMANTIC VIEWS IN SCHEMA CORTEX_SENSE_DEMO.WORKSHOP;
```

You should see 500 customers, 60 products, 3,000 orders, about 7,500 order items, and `SV_PET_STORE`.

## Ask a question of the semantic view

**Question:** *"Which product categories have the highest gross margin, net of cancelled orders?"*

You can query the semantic view directly with the `SEMANTIC_VIEW` clause, choosing dimensions and metrics by name; Snowflake works out the joins:

```sql
SELECT *
FROM SEMANTIC_VIEW(
    CORTEX_SENSE_DEMO.WORKSHOP.SV_PET_STORE
    DIMENSIONS products.category
    METRICS order_items.revenue, order_items.gross_margin, order_items.gross_margin_pct
    WHERE orders.order_status <> 'Cancelled'
)
ORDER BY gross_margin_pct DESC;
```

Or ask the same thing in plain English through Cortex Analyst:

```bash
cortex analyst query "Which product categories have the highest gross margin, excluding cancelled orders?" --view=CORTEX_SENSE_DEMO.WORKSHOP.SV_PET_STORE
```

Cortex Analyst turns the question into SQL over `SV_PET_STORE` and returns the answer. That's conversational analytics.

## Teardown

When the workshop is over, drop the schema and everything in it:

```bash
snow sql -c CORTEX_SENSE_DEMO_CONN -f intro-workshop/sql/99_teardown.sql
```

The `CORTEX_SENSE_DEMO` database and its other schemas are left in place.
