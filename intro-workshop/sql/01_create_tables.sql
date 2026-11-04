-- Pet-products online retailer: customers, products, orders, order items.
-- Rerunnable: tables are recreated with deterministic synthetic data (seeded RANDOM).
CREATE DATABASE IF NOT EXISTS CORTEX_SENSE_DEMO;
CREATE SCHEMA IF NOT EXISTS CORTEX_SENSE_DEMO.WORKSHOP;
USE SCHEMA CORTEX_SENSE_DEMO.WORKSHOP;

-- ── CUSTOMER (500) ───────────────────────────────────────────────
CREATE OR REPLACE TABLE CUSTOMER (
    CUSTOMER_ID      NUMBER PRIMARY KEY COMMENT 'Unique customer identifier',
    FIRST_NAME       VARCHAR COMMENT 'Customer first name',
    LAST_NAME        VARCHAR COMMENT 'Customer last name',
    EMAIL            VARCHAR COMMENT 'Customer email address',
    STATE            VARCHAR COMMENT 'US state code of the shipping address',
    REGION           VARCHAR COMMENT 'US sales region: West, Midwest, South, Northeast',
    SIGNUP_DATE      DATE    COMMENT 'Date the customer created an account',
    LOYALTY_TIER     VARCHAR COMMENT 'Loyalty program tier: Bronze, Silver, Gold, Platinum',
    PRIMARY_PET_TYPE VARCHAR COMMENT 'Pet type the customer reported at signup: Dog, Cat, Fish, Bird, Small Animal, Reptile',
    IS_AUTOSHIP      BOOLEAN COMMENT 'TRUE if the customer is enrolled in recurring Autoship delivery'
) COMMENT = 'Customers of the online pet-products store';

INSERT INTO CUSTOMER
WITH s AS (
  SELECT SEQ4() + 1 AS id,
         ARRAY_CONSTRUCT('Emma','Liam','Olivia','Noah','Ava','Mason','Sophia','Lucas','Mia','Ethan',
                         'Harper','James','Ella','Logan','Grace','Ben','Chloe','Jack','Zoe','Owen') AS fn,
         ARRAY_CONSTRUCT('Smith','Johnson','Lee','Garcia','Brown','Davis','Miller','Wilson','Moore','Taylor',
                         'Anderson','Thomas','Martin','Clark','Lewis','Walker','Young','King','Hill','Scott') AS ln,
         ARRAY_CONSTRUCT('CA','WA','OR','CO','TX','FL','GA','NC','IL','OH','MI','MN','NY','MA','PA','NJ') AS st,
         ABS(RANDOM(11)) AS r1, ABS(RANDOM(12)) AS r2, ABS(RANDOM(13)) AS r3, UNIFORM(0, 99, RANDOM(14)) AS p
  FROM TABLE(GENERATOR(ROWCOUNT => 500)))
SELECT id,
       fn[r1 % 20]::VARCHAR,
       ln[r2 % 20]::VARCHAR,
       LOWER(fn[r1 % 20]::VARCHAR || '.' || ln[r2 % 20]::VARCHAR || id || '@example.com'),
       st[r3 % 16]::VARCHAR,
       CASE WHEN r3 % 16 < 4 THEN 'West' WHEN r3 % 16 < 8 THEN 'South'
            WHEN r3 % 16 < 12 THEN 'Midwest' ELSE 'Northeast' END,
       DATEADD(DAY, -UNIFORM(30, 1460, RANDOM(15)), '2026-10-31'::DATE),
       CASE WHEN p < 50 THEN 'Bronze' WHEN p < 80 THEN 'Silver' WHEN p < 95 THEN 'Gold' ELSE 'Platinum' END,
       CASE WHEN p % 10 < 5 THEN 'Dog' WHEN p % 10 < 8 THEN 'Cat' WHEN p % 10 = 8 THEN 'Fish'
            ELSE ARRAY_CONSTRUCT('Bird','Small Animal','Reptile')[r1 % 3]::VARCHAR END,
       UNIFORM(0, 99, RANDOM(16)) < 30
FROM s;

-- ── PRODUCT (60) ─────────────────────────────────────────────────
CREATE OR REPLACE TABLE PRODUCT (
    PRODUCT_ID   NUMBER PRIMARY KEY COMMENT 'Unique product identifier (SKU)',
    PRODUCT_NAME VARCHAR COMMENT 'Product display name',
    CATEGORY     VARCHAR COMMENT 'Product category: Food, Treats, Toys, Health, Grooming, Beds & Furniture, Aquarium, Habitats',
    PET_TYPE     VARCHAR COMMENT 'Pet type the product is for: Dog, Cat, Fish, Bird, Small Animal, Reptile',
    BRAND        VARCHAR COMMENT 'Product brand',
    UNIT_PRICE   NUMBER(10,2) COMMENT 'Current list price in USD',
    UNIT_COST    NUMBER(10,2) COMMENT 'Current unit cost in USD',
    IS_ACTIVE    BOOLEAN COMMENT 'FALSE if the product is discontinued'
) COMMENT = 'Product catalog of pet supplies';

INSERT INTO PRODUCT
WITH s AS (
  SELECT SEQ4() AS i, ABS(RANDOM(21)) AS r
  FROM TABLE(GENERATOR(ROWCOUNT => 60))),
d AS (
  SELECT i,
         ARRAY_CONSTRUCT('Dog','Dog','Dog','Cat','Cat','Fish','Bird','Small Animal','Reptile','Dog')[i % 10]::VARCHAR AS pet,
         ARRAY_CONSTRUCT('Food','Treats','Toys','Health','Grooming','Beds & Furniture')[FLOOR(i / 10)]::VARCHAR AS cat,
         ARRAY_CONSTRUCT('PawPrime','Whisker Co','TailWag','NatureNibble','FurEver','AquaPure')[r % 6]::VARCHAR AS brand,
         r
  FROM s)
SELECT i + 1,
       brand || ' ' || pet || ' ' ||
         CASE cat WHEN 'Food' THEN IFF(pet IN ('Fish','Reptile','Bird'), 'Pellets', 'Dry Food 15lb')
                  WHEN 'Treats' THEN 'Crunchy Treats' WHEN 'Toys' THEN 'Chew Toy'
                  WHEN 'Health' THEN 'Multivitamin' WHEN 'Grooming' THEN 'Grooming Kit'
                  ELSE IFF(pet = 'Fish', 'Aquarium 20gal', IFF(pet IN ('Bird','Small Animal','Reptile'), 'Habitat', 'Cozy Bed')) END,
       CASE WHEN cat = 'Beds & Furniture' AND pet = 'Fish' THEN 'Aquarium'
            WHEN cat = 'Beds & Furniture' AND pet IN ('Bird','Small Animal','Reptile') THEN 'Habitats'
            ELSE cat END,
       pet, brand,
       ROUND(CASE cat WHEN 'Food' THEN 25 WHEN 'Treats' THEN 8 WHEN 'Toys' THEN 12
                      WHEN 'Health' THEN 20 WHEN 'Grooming' THEN 18 ELSE 60 END * (0.7 + (r % 60) / 100), 2) + 0.99,
       NULL, (r % 12) <> 0
FROM d;
-- Cost ratio varies by category so margins differ (treats/toys high margin, food low).
UPDATE PRODUCT SET UNIT_COST = ROUND(UNIT_PRICE * (CASE CATEGORY
    WHEN 'Food' THEN 0.72 WHEN 'Treats' THEN 0.45 WHEN 'Toys' THEN 0.40 WHEN 'Health' THEN 0.50
    WHEN 'Grooming' THEN 0.48 WHEN 'Aquarium' THEN 0.65 WHEN 'Habitats' THEN 0.62 ELSE 0.58 END
    + (MOD(PRODUCT_ID, 7) - 3) / 100), 2);

-- ── ORDERS (3,000) ───────────────────────────────────────────────
-- Named ORDERS because ORDER is a reserved word.
CREATE OR REPLACE TABLE ORDERS (
    ORDER_ID        NUMBER PRIMARY KEY COMMENT 'Unique order identifier',
    CUSTOMER_ID     NUMBER COMMENT 'Customer who placed the order (FK to CUSTOMER)',
    ORDER_DATE      DATE COMMENT 'Date the order was placed',
    ORDER_STATUS    VARCHAR COMMENT 'Order status: Delivered, Shipped, Processing, Cancelled, Returned',
    CHANNEL         VARCHAR COMMENT 'Purchase channel: Web, Mobile App, Autoship',
    SHIPPING_FEE    NUMBER(10,2) COMMENT 'Shipping fee charged in USD (free over $49)',
    DISCOUNT_AMOUNT NUMBER(10,2) COMMENT 'Order-level promo discount in USD'
) COMMENT = 'Order headers; revenue is computed from ORDER_ITEM. Exclude Cancelled orders from revenue.';

INSERT INTO ORDERS
SELECT SEQ4() + 1,
       UNIFORM(1, 500, RANDOM(31)),
       DATEADD(DAY, -UNIFORM(0, 730, RANDOM(32)), '2026-10-31'::DATE),
       CASE WHEN p < 80 THEN 'Delivered' WHEN p < 86 THEN 'Shipped' WHEN p < 90 THEN 'Processing'
            WHEN p < 95 THEN 'Cancelled' ELSE 'Returned' END,
       CASE WHEN c < 50 THEN 'Web' WHEN c < 80 THEN 'Mobile App' ELSE 'Autoship' END,
       IFF(c % 3 = 0, 0, 6.99),
       IFF(UNIFORM(0, 99, RANDOM(35)) < 15, 5.00, 0)
FROM (SELECT UNIFORM(0, 99, RANDOM(33)) AS p, UNIFORM(0, 99, RANDOM(34)) AS c
      FROM TABLE(GENERATOR(ROWCOUNT => 3000)));

-- ── ORDER_ITEM (1-4 lines per order) ─────────────────────────────
CREATE OR REPLACE TABLE ORDER_ITEM (
    ORDER_ITEM_ID NUMBER PRIMARY KEY COMMENT 'Unique order line identifier',
    ORDER_ID      NUMBER COMMENT 'Order this line belongs to (FK to ORDERS)',
    PRODUCT_ID    NUMBER COMMENT 'Product purchased (FK to PRODUCT)',
    QUANTITY      NUMBER COMMENT 'Units purchased',
    UNIT_PRICE    NUMBER(10,2) COMMENT 'Price per unit paid at time of order in USD',
    LINE_TOTAL    NUMBER(12,2) COMMENT 'QUANTITY * UNIT_PRICE in USD (before order-level discount)'
) COMMENT = 'Order line items; use LINE_TOTAL for product revenue';

INSERT INTO ORDER_ITEM
WITH lines AS (
  SELECT o.ORDER_ID, l.n
  FROM ORDERS o
  JOIN (SELECT SEQ4() + 1 AS n FROM TABLE(GENERATOR(ROWCOUNT => 4))) l
    ON l.n <= 1 + MOD(ABS(HASH(o.ORDER_ID)), 4)),
picked AS (
  SELECT ORDER_ID, n, 1 + MOD(ABS(HASH(ORDER_ID, n)), 60) AS PRODUCT_ID,
         1 + MOD(ABS(HASH(n, ORDER_ID)), 3) AS QUANTITY
  FROM lines)
SELECT ROW_NUMBER() OVER (ORDER BY pk.ORDER_ID, pk.n),
       pk.ORDER_ID, pk.PRODUCT_ID, pk.QUANTITY, p.UNIT_PRICE, pk.QUANTITY * p.UNIT_PRICE
FROM picked pk JOIN PRODUCT p ON p.PRODUCT_ID = pk.PRODUCT_ID;

-- Waive shipping on orders over $49.
UPDATE ORDERS o SET SHIPPING_FEE = 0
FROM (SELECT ORDER_ID, SUM(LINE_TOTAL) AS t FROM ORDER_ITEM GROUP BY 1) i
WHERE i.ORDER_ID = o.ORDER_ID AND i.t > 49;
