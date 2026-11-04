-- Teardown: drops the entire workshop schema and everything in it
-- (CUSTOMER, PRODUCT, ORDERS, ORDER_ITEM, SV_PET_STORE, and any other objects).
-- Leaves the CORTEX_SENSE_DEMO database and its other schemas untouched.
-- Query history entries from prime_query_history.py remain in ACCOUNT_USAGE; they cannot be deleted.
DROP SCHEMA IF EXISTS CORTEX_SENSE_DEMO.WORKSHOP CASCADE;
