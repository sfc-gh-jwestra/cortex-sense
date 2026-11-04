"""
Prime QUERY_HISTORY and ACCESS_HISTORY for Cortex Sense discovery on the pet-store workshop schema.

Two groups of queries, written the way an analyst on the team would:

  1. SEMANTIC_VIEW(...) queries against CORTEX_SENSE_DEMO.WORKSHOP.SV_PET_STORE
  2. Hand-written SQL over CUSTOMER, PRODUCT, ORDERS and ORDER_ITEM

Conventions applied throughout (Cortex Sense learns join patterns and filters from history):
  - revenue = SUM(ORDER_ITEM.LINE_TOTAL); never sum ORDERS columns as revenue
  - net sales exclude ORDER_STATUS = 'Cancelled'
  - ORDERS joins CUSTOMER on CUSTOMER_ID; ORDER_ITEM joins ORDERS on ORDER_ID and PRODUCT on PRODUCT_ID
  - margin = LINE_TOTAL - QUANTITY * PRODUCT.UNIT_COST

Rerunnable -- executing multiple times just adds more history entries.

Usage:
    python3 intro-workshop/scripts/prime_query_history.py
"""

import json
import os
import subprocess
import sys

DB = "CORTEX_SENSE_DEMO"
W = f"{DB}.WORKSHOP"
SV = f"{W}.SV_PET_STORE"
CONNECTION = os.environ.get("SNOWFLAKE_CONNECTION_NAME", "CORTEX_SENSE_DEMO_CONN")
NOT_CANCELLED = "o.ORDER_STATUS <> 'Cancelled'"

QUERIES = [
    # ═══════════════════════════════════════════════════════════════
    # 1. SEMANTIC_VIEW queries against SV_PET_STORE
    # ═══════════════════════════════════════════════════════════════
    ("SV: revenue and margin by category", f"""
SELECT * FROM SEMANTIC_VIEW({SV}
    DIMENSIONS products.category
    METRICS order_items.revenue, order_items.gross_margin, order_items.gross_margin_pct)
ORDER BY revenue DESC"""),

    ("SV: monthly revenue trend (net of cancellations)", f"""
SELECT * FROM SEMANTIC_VIEW({SV}
    DIMENSIONS orders.order_month
    METRICS order_items.revenue, orders.order_count
    WHERE orders.order_status <> 'Cancelled')
ORDER BY order_month"""),

    ("SV: revenue by pet type", f"""
SELECT * FROM SEMANTIC_VIEW({SV}
    DIMENSIONS products.pet_type
    METRICS order_items.revenue, order_items.units_sold)
ORDER BY revenue DESC"""),

    ("SV: revenue by channel", f"""
SELECT * FROM SEMANTIC_VIEW({SV}
    DIMENSIONS orders.channel
    METRICS order_items.revenue, orders.order_count)
ORDER BY revenue DESC"""),

    ("SV: revenue by customer region and loyalty tier", f"""
SELECT * FROM SEMANTIC_VIEW({SV}
    DIMENSIONS customers.region, customers.loyalty_tier
    METRICS order_items.revenue)
ORDER BY region, revenue DESC"""),

    ("SV: top brands", f"""
SELECT * FROM SEMANTIC_VIEW({SV}
    DIMENSIONS products.brand
    METRICS order_items.revenue, order_items.gross_margin_pct)
ORDER BY revenue DESC LIMIT 10"""),

    ("SV: customers by primary pet type", f"""
SELECT * FROM SEMANTIC_VIEW({SV}
    DIMENSIONS customers.primary_pet_type
    METRICS customers.customer_count)
ORDER BY customer_count DESC"""),

    ("SV: orders by status", f"""
SELECT * FROM SEMANTIC_VIEW({SV}
    DIMENSIONS orders.order_status
    METRICS orders.order_count, order_items.revenue)
ORDER BY order_count DESC"""),

    # ═══════════════════════════════════════════════════════════════
    # 2. Hand-written SQL over the base tables
    # ═══════════════════════════════════════════════════════════════
    ("Top 10 customers by lifetime net sales", f"""
SELECT c.CUSTOMER_ID, c.FIRST_NAME || ' ' || c.LAST_NAME AS customer_name, c.LOYALTY_TIER,
       COUNT(DISTINCT o.ORDER_ID) AS orders, SUM(oi.LINE_TOTAL) AS net_sales
FROM {W}.CUSTOMER c
JOIN {W}.ORDERS o ON o.CUSTOMER_ID = c.CUSTOMER_ID
JOIN {W}.ORDER_ITEM oi ON oi.ORDER_ID = o.ORDER_ID
WHERE {NOT_CANCELLED}
GROUP BY 1, 2, 3 ORDER BY net_sales DESC LIMIT 10"""),

    ("Average order value by channel", f"""
WITH order_totals AS (
  SELECT o.ORDER_ID, o.CHANNEL, SUM(oi.LINE_TOTAL) AS order_total
  FROM {W}.ORDERS o JOIN {W}.ORDER_ITEM oi ON oi.ORDER_ID = o.ORDER_ID
  WHERE {NOT_CANCELLED}
  GROUP BY 1, 2)
SELECT CHANNEL, COUNT(*) AS orders, AVG(order_total) AS avg_order_value
FROM order_totals GROUP BY 1 ORDER BY avg_order_value DESC"""),

    ("Top 15 products by units sold", f"""
SELECT p.PRODUCT_NAME, p.CATEGORY, p.PET_TYPE, SUM(oi.QUANTITY) AS units, SUM(oi.LINE_TOTAL) AS revenue
FROM {W}.ORDER_ITEM oi
JOIN {W}.PRODUCT p ON p.PRODUCT_ID = oi.PRODUCT_ID
JOIN {W}.ORDERS o ON o.ORDER_ID = oi.ORDER_ID
WHERE {NOT_CANCELLED}
GROUP BY 1, 2, 3 ORDER BY units DESC LIMIT 15"""),

    ("Gross margin by category", f"""
SELECT p.CATEGORY, SUM(oi.LINE_TOTAL) AS revenue,
       SUM(oi.LINE_TOTAL - oi.QUANTITY * p.UNIT_COST) AS gross_margin,
       DIV0(SUM(oi.LINE_TOTAL - oi.QUANTITY * p.UNIT_COST), SUM(oi.LINE_TOTAL)) AS margin_pct
FROM {W}.ORDER_ITEM oi
JOIN {W}.PRODUCT p ON p.PRODUCT_ID = oi.PRODUCT_ID
JOIN {W}.ORDERS o ON o.ORDER_ID = oi.ORDER_ID
WHERE {NOT_CANCELLED}
GROUP BY 1 ORDER BY margin_pct DESC"""),

    ("Monthly net sales, last 12 months", f"""
SELECT DATE_TRUNC('MONTH', o.ORDER_DATE) AS month, SUM(oi.LINE_TOTAL) AS net_sales,
       COUNT(DISTINCT o.ORDER_ID) AS orders
FROM {W}.ORDERS o JOIN {W}.ORDER_ITEM oi ON oi.ORDER_ID = o.ORDER_ID
WHERE {NOT_CANCELLED} AND o.ORDER_DATE >= DATEADD(MONTH, -12, CURRENT_DATE())
GROUP BY 1 ORDER BY 1"""),

    ("Year-over-year net sales by quarter", f"""
SELECT YEAR(o.ORDER_DATE) AS yr, QUARTER(o.ORDER_DATE) AS qtr, SUM(oi.LINE_TOTAL) AS net_sales,
       net_sales - LAG(net_sales) OVER (PARTITION BY qtr ORDER BY yr) AS yoy_change
FROM {W}.ORDERS o JOIN {W}.ORDER_ITEM oi ON oi.ORDER_ID = o.ORDER_ID
WHERE {NOT_CANCELLED}
GROUP BY 1, 2 ORDER BY 1, 2"""),

    ("Autoship vs non-autoship customers: spend per customer", f"""
SELECT IFF(c.IS_AUTOSHIP, 'Autoship', 'One-time') AS customer_type,
       COUNT(DISTINCT c.CUSTOMER_ID) AS customers,
       SUM(oi.LINE_TOTAL) / COUNT(DISTINCT c.CUSTOMER_ID) AS sales_per_customer
FROM {W}.CUSTOMER c
JOIN {W}.ORDERS o ON o.CUSTOMER_ID = c.CUSTOMER_ID
JOIN {W}.ORDER_ITEM oi ON oi.ORDER_ID = o.ORDER_ID
WHERE {NOT_CANCELLED}
GROUP BY 1"""),

    ("Cross-sell: customers buying for a pet type other than their primary pet", f"""
SELECT c.PRIMARY_PET_TYPE, p.PET_TYPE AS purchased_for, COUNT(DISTINCT c.CUSTOMER_ID) AS customers,
       SUM(oi.LINE_TOTAL) AS net_sales
FROM {W}.CUSTOMER c
JOIN {W}.ORDERS o ON o.CUSTOMER_ID = c.CUSTOMER_ID
JOIN {W}.ORDER_ITEM oi ON oi.ORDER_ID = o.ORDER_ID
JOIN {W}.PRODUCT p ON p.PRODUCT_ID = oi.PRODUCT_ID
WHERE {NOT_CANCELLED} AND p.PET_TYPE <> c.PRIMARY_PET_TYPE
GROUP BY 1, 2 ORDER BY net_sales DESC"""),

    ("Return and cancellation rate by category", f"""
SELECT p.CATEGORY, COUNT(DISTINCT o.ORDER_ID) AS orders,
       DIV0(COUNT(DISTINCT IFF(o.ORDER_STATUS = 'Returned', o.ORDER_ID, NULL)), COUNT(DISTINCT o.ORDER_ID)) AS return_rate,
       DIV0(COUNT(DISTINCT IFF(o.ORDER_STATUS = 'Cancelled', o.ORDER_ID, NULL)), COUNT(DISTINCT o.ORDER_ID)) AS cancel_rate
FROM {W}.ORDERS o
JOIN {W}.ORDER_ITEM oi ON oi.ORDER_ID = o.ORDER_ID
JOIN {W}.PRODUCT p ON p.PRODUCT_ID = oi.PRODUCT_ID
GROUP BY 1 ORDER BY return_rate DESC"""),

    ("New customer signups by month and region", f"""
SELECT DATE_TRUNC('MONTH', SIGNUP_DATE) AS month, REGION, COUNT(*) AS new_customers
FROM {W}.CUSTOMER
GROUP BY 1, 2 ORDER BY 1, 2"""),

    ("Customers with no orders in the last 180 days (churn risk)", f"""
SELECT c.CUSTOMER_ID, c.EMAIL, c.LOYALTY_TIER, MAX(o.ORDER_DATE) AS last_order_date
FROM {W}.CUSTOMER c
LEFT JOIN {W}.ORDERS o ON o.CUSTOMER_ID = c.CUSTOMER_ID AND {NOT_CANCELLED}
GROUP BY 1, 2, 3
HAVING last_order_date IS NULL OR last_order_date < DATEADD(DAY, -180, CURRENT_DATE())
ORDER BY last_order_date NULLS FIRST"""),

    ("Discounts and shipping fees by month", f"""
SELECT DATE_TRUNC('MONTH', ORDER_DATE) AS month, SUM(DISCOUNT_AMOUNT) AS discounts,
       SUM(SHIPPING_FEE) AS shipping_fees, COUNT_IF(SHIPPING_FEE = 0) AS free_shipping_orders
FROM {W}.ORDERS o
WHERE {NOT_CANCELLED}
GROUP BY 1 ORDER BY 1"""),

    ("Discontinued products still selling", f"""
SELECT p.PRODUCT_NAME, p.BRAND, SUM(oi.QUANTITY) AS units, MAX(o.ORDER_DATE) AS last_sold
FROM {W}.PRODUCT p
JOIN {W}.ORDER_ITEM oi ON oi.PRODUCT_ID = p.PRODUCT_ID
JOIN {W}.ORDERS o ON o.ORDER_ID = oi.ORDER_ID
WHERE NOT p.IS_ACTIVE AND {NOT_CANCELLED}
GROUP BY 1, 2 ORDER BY units DESC"""),

    ("Basket size: items per order distribution", f"""
SELECT lines, COUNT(*) AS orders
FROM (SELECT ORDER_ID, COUNT(*) AS lines FROM {W}.ORDER_ITEM GROUP BY 1)
GROUP BY 1 ORDER BY 1"""),
]


def main():
    print(f"Running {len(QUERIES)} queries against {W} (connection {CONNECTION})...")
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
