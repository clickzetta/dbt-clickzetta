-- Clean up all objects created by the example project.
-- Run in the ClickZetta console or via CLI:
-- cz-cli sql "$(cat analyses/cleanup.sql)" --instance <instance> --workspace <workspace> --write

-- Views
DROP VIEW IF EXISTS example.stg_orders;
DROP VIEW IF EXISTS example.stg_customers;
DROP VIEW IF EXISTS example.stream_changes;

-- Tables
DROP TABLE IF EXISTS example.dim_customers;
DROP TABLE IF EXISTS example.fct_orders_partitioned;
DROP TABLE IF EXISTS example.fct_orders_incremental;
DROP TABLE IF EXISTS example.fct_orders_delete_insert;
DROP TABLE IF EXISTS example.daily_revenue;
DROP TABLE IF EXISTS example.regional_revenue_with_grants;
DROP TABLE IF EXISTS example.orders_with_indexes;
DROP TABLE IF EXISTS example.orders_vector_index;
DROP TABLE IF EXISTS example.orders_clone;
DROP TABLE IF EXISTS example.orders_clone_timetravel;

-- Dynamic tables and materialized views
DROP DYNAMIC TABLE IF EXISTS example.customer_stats_dynamic;
DROP MATERIALIZED VIEW IF EXISTS example.regional_daily_mv;

-- Streams
DROP STREAM IF EXISTS example.orders_stream;

-- Snapshots
DROP TABLE IF EXISTS example_snapshots.orders_snapshot;
DROP TABLE IF EXISTS example_snapshots.customers_snapshot;

-- Seeds
DROP TABLE IF EXISTS example_raw.raw_orders;
DROP TABLE IF EXISTS example_raw.raw_customers;
DROP TABLE IF EXISTS example_raw.raw_events;

-- Schemas (only succeeds when schema is empty)
DROP SCHEMA IF EXISTS example;
DROP SCHEMA IF EXISTS example_snapshots;
DROP SCHEMA IF EXISTS example_raw;

