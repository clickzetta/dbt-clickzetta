# Table Stream as Source

[← 文档首页](README.md) | 相关：[incremental.md](incremental.md) · [dynamic-table.md](dynamic-table.md)

ClickZetta Table Streams capture row-level changes (INSERT/UPDATE/DELETE) from a source table. In dbt, you declare a stream as a source and reference it with `source()` — the stream is consumed by incremental models or dynamic tables to build CDC pipelines.

## How it works

A Table Stream appends three system columns to every row it returns:

| Column | Type | Values |
|---|---|---|
| `` `__change_type` `` | string | `INSERT`, `UPDATE_BEFORE`, `UPDATE_AFTER`, `DELETE` |
| `` `__commit_version` `` | bigint | Internal version number |
| `` `__commit_timestamp` `` | timestamp | When the change was committed |

> `SELECT` does not advance the stream offset. Only DML statements (INSERT, MERGE, etc.) advance it.

## Step 1: Create the stream

Streams are not created by dbt — create them manually or via a `pre_hook`:

```sql
-- Standard mode: captures INSERT, UPDATE, DELETE
CREATE TABLE STREAM my_schema.orders_stream
ON TABLE my_schema.orders
WITH PROPERTIES ('TABLE_STREAM_MODE' = 'STANDARD');

-- Append-only mode: captures INSERT only (lower overhead)
CREATE TABLE STREAM my_schema.orders_stream
ON TABLE my_schema.orders
WITH PROPERTIES ('TABLE_STREAM_MODE' = 'APPEND_ONLY');
```

> `TABLE_STREAM_MODE` is mandatory. ClickZetta does not support Snowflake's `SHOW_INITIAL_ROWS` behavior — rows inserted before stream creation are not captured.

## Step 2: Declare in sources.yml

```yaml
version: 2
sources:
  - name: streams
    schema: my_schema
    tables:
      - name: orders_stream
        description: "CDC stream on the orders table"
```

## Step 3: Consume in a model

```sql
-- Recommended: SELECT * EXCEPT to avoid hardcoding column names
select
    `__change_type`      as cdc_change_type,
    `__commit_timestamp` as cdc_commit_ts,
    * except (`__change_type`, `__commit_timestamp`, `__commit_version`)
from {{ source('streams', 'orders_stream') }}
```

> System column names start with `__` and must be quoted with backticks when referenced directly.

## CDC pipeline example

A typical pattern: stream → incremental model that applies changes to a target table.

```sql
-- models/dwd_orders.sql
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='order_id'
) }}

with changes as (
    select
        `__change_type` as change_type,
        order_id,
        customer_id,
        amount,
        status,
        `__commit_timestamp` as changed_at
    from {{ source('streams', 'orders_stream') }}
)
-- Apply only the latest state per order_id
select order_id, customer_id, amount, status, changed_at
from changes
where change_type in ('INSERT', 'UPDATE_AFTER')
```

## SHOW_INITIAL_ROWS behavior

If you need the stream to capture rows that already exist in the source table at creation time:

```sql
CREATE TABLE STREAM my_schema.orders_stream
ON TABLE my_schema.orders
WITH PROPERTIES (
    'TABLE_STREAM_MODE' = 'STANDARD',
    'SHOW_INITIAL_ROWS' = 'TRUE'
);
```

> **Important:** `SHOW_INITIAL_ROWS` only captures rows that exist **at the time the stream is created**. Insert your data **before** creating the stream, not after.

## Utility macros

```bash
# Drop a stream
dbt run-operation drop_object --args '{relation: my_schema.orders_stream, type: stream}'

# Recover a dropped stream
dbt run-operation undrop --args '{relation: my_schema.orders_stream}'
```
