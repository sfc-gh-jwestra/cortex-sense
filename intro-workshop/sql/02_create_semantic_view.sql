-- Semantic view for conversational analytics over the pet-store tables.
CREATE OR REPLACE SEMANTIC VIEW CORTEX_SENSE_DEMO.WORKSHOP.SV_PET_STORE
  TABLES (
    customers AS CORTEX_SENSE_DEMO.WORKSHOP.CUSTOMER PRIMARY KEY (CUSTOMER_ID)
      COMMENT = 'Customers of the online pet store',
    products AS CORTEX_SENSE_DEMO.WORKSHOP.PRODUCT PRIMARY KEY (PRODUCT_ID)
      COMMENT = 'Pet supplies product catalog',
    orders AS CORTEX_SENSE_DEMO.WORKSHOP.ORDERS PRIMARY KEY (ORDER_ID)
      COMMENT = 'Order headers',
    order_items AS CORTEX_SENSE_DEMO.WORKSHOP.ORDER_ITEM PRIMARY KEY (ORDER_ITEM_ID)
      COMMENT = 'Order line items'
  )
  RELATIONSHIPS (
    orders_to_customers AS orders (CUSTOMER_ID) REFERENCES customers,
    items_to_orders AS order_items (ORDER_ID) REFERENCES orders,
    items_to_products AS order_items (PRODUCT_ID) REFERENCES products
  )
  FACTS (
    order_items.line_total AS LINE_TOTAL COMMENT = 'Line revenue in USD before order discount',
    order_items.quantity AS QUANTITY COMMENT = 'Units on the line',
    products.unit_cost AS UNIT_COST COMMENT = 'Current unit cost in USD',
    products.list_price AS UNIT_PRICE COMMENT = 'Current list price in USD',
    order_items.line_cost AS order_items.quantity * products.unit_cost COMMENT = 'Line cost in USD',
    orders.shipping_fee AS SHIPPING_FEE,
    orders.discount_amount AS DISCOUNT_AMOUNT
  )
  DIMENSIONS (
    customers.customer_id AS CUSTOMER_ID,
    customers.customer_name AS FIRST_NAME || ' ' || LAST_NAME WITH SYNONYMS = ('customer') COMMENT = 'Customer full name',
    customers.state AS STATE,
    customers.region AS REGION COMMENT = 'West, Midwest, South, Northeast',
    customers.signup_date AS SIGNUP_DATE,
    customers.loyalty_tier AS LOYALTY_TIER COMMENT = 'Bronze, Silver, Gold, Platinum',
    customers.primary_pet_type AS PRIMARY_PET_TYPE COMMENT = 'Pet type reported by the customer',
    customers.is_autoship AS IS_AUTOSHIP WITH SYNONYMS = ('subscriber', 'autoship member'),
    products.product_name AS PRODUCT_NAME WITH SYNONYMS = ('item', 'SKU'),
    products.category AS CATEGORY WITH SYNONYMS = ('product category'),
    products.pet_type AS PET_TYPE COMMENT = 'Pet type the product is for',
    products.brand AS BRAND,
    products.is_active AS IS_ACTIVE,
    orders.order_id AS ORDER_ID,
    orders.order_date AS ORDER_DATE,
    orders.order_month AS DATE_TRUNC('MONTH', ORDER_DATE),
    orders.order_status AS ORDER_STATUS COMMENT = 'Delivered, Shipped, Processing, Cancelled, Returned',
    orders.channel AS CHANNEL COMMENT = 'Web, Mobile App, Autoship'
  )
  METRICS (
    order_items.revenue AS SUM(order_items.line_total)
      WITH SYNONYMS = ('sales', 'gross sales') COMMENT = 'Product revenue in USD (all statuses; filter out Cancelled for net sales)',
    order_items.units_sold AS SUM(order_items.quantity),
    order_items.gross_margin AS SUM(order_items.line_total) - SUM(order_items.line_cost),
    order_items.gross_margin_pct AS DIV0(SUM(order_items.line_total) - SUM(order_items.line_cost), SUM(order_items.line_total)),
    orders.order_count AS COUNT(orders.order_id),
    orders.total_discounts AS SUM(orders.discount_amount),
    orders.total_shipping AS SUM(orders.shipping_fee),
    customers.customer_count AS COUNT(customers.customer_id)
  )
  COMMENT = 'Online pet-products retailer: customers, products, orders and order items';
