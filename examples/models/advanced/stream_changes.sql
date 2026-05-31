-- Table Stream source example: read change data from orders_stream.
-- Stream appends three system columns to every row:
--   __change_type:      INSERT / UPDATE_BEFORE / UPDATE_AFTER / DELETE
--   __commit_version:   commit version number
--   __commit_timestamp: commit timestamp
--
-- SELECT does NOT advance the stream offset — only DML (INSERT/MERGE etc.) does.
-- Typical pattern: MERGE stream data into a target table, which advances the offset.
--
-- TABLE_STREAM_MODE is REQUIRED — omitting it causes:
--   CZLH-42000: not supported feature - only support CREATE TABLE STREAM with PROPERTIES
--
-- SHOW_INITIAL_ROWS behavior:
--   To capture rows already in the source table at stream creation time, use:
--     WITH PROPERTIES ('TABLE_STREAM_MODE' = 'STANDARD', 'SHOW_INITIAL_ROWS' = 'TRUE')
--   IMPORTANT: SHOW_INITIAL_ROWS only works for data that exists BEFORE the stream
--   is created. Insert data first, then create the stream — not the other way around.
--
-- Stream COMMENT: supported via COMMENT 'description' clause (visible in DESC STREAM).
--
-- Three equivalent ways to query a stream:
--
-- 1. SELECT * — returns all user columns + system columns (works fine)
-- 2. SELECT * EXCEPT(...) — returns only user columns, no hardcoded column list
-- 3. Explicit column list — most portable, recommended for production
{{ config(
    materialized='view',
    pre_hook="CREATE TABLE STREAM IF NOT EXISTS {{ target.schema }}.orders_stream ON TABLE {{ target.schema }}.fct_orders_incremental WITH PROPERTIES ('TABLE_STREAM_MODE' = 'STANDARD')"
) }}

-- depends_on: {{ ref('fct_orders_incremental') }}
-- Ensures fct_orders_incremental is built before this model's pre_hook fires.

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
