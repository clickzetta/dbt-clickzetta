-- Table Stream source example: read change data from orders_stream.
-- Stream appends three system columns to every row:
--   __change_type:      INSERT / UPDATE_BEFORE / UPDATE_AFTER / DELETE
--   __commit_version:   commit version number
--   __commit_timestamp: commit timestamp
--
-- SELECT does NOT advance the stream offset — only DML (INSERT/MERGE etc.) does.
-- Typical pattern: MERGE stream data into a target table, which advances the offset.
--
-- Three equivalent ways to query a stream:
--
-- 1. SELECT * — returns all user columns + system columns (works fine)
-- 2. SELECT * EXCEPT(...) — returns only user columns, no hardcoded column list
-- 3. Explicit column list — most portable, recommended for production
{{ config(materialized='view') }}

-- Pattern 1: explicit columns (production-safe, schema changes require manual update)
select
    __change_type,
    __commit_timestamp,
    order_id,
    customer_id,
    amount,
    status,
    region,
    dt
from {{ source('example_streams', 'orders_stream') }}

-- Pattern 2 (alternative): SELECT * EXCEPT to drop system columns
-- Useful when the base table schema changes frequently — no column list to maintain.
--
-- select * except(__change_type, __commit_timestamp, __commit_version)
-- from {{ source('example_streams', 'orders_stream') }}
