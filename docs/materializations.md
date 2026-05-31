# Materializations

[← 文档首页](README.md) | 相关：[incremental.md](incremental.md) · [dynamic-table.md](dynamic-table.md) · [snapshots.md](snapshots.md)

dbt-clickzetta supports all standard dbt materializations plus ClickZetta-specific ones.

## table

Creates or replaces the table on every run. Supports partitioning, clustering, and indexes.

```sql
{{ config(
    materialized='table',
    partition_by=['ds'],
    clustered_by=['customer_id'],
    buckets=16
) }}
select * from {{ ref('stg_orders') }}
```

## view

Creates or replaces a view. Lightweight, no data stored.

```sql
{{ config(materialized='view') }}
select * from {{ ref('stg_orders') }} where status = 'active'
```

## incremental

Appends or merges new rows into an existing table. See [incremental.md](incremental.md) for strategy details.

```sql
{{ config(
    materialized='incremental',
    unique_key='order_id'
) }}
select * from {{ ref('stg_orders') }}
{% if is_incremental() %}
  where updated_at > (select max(updated_at) from {{ this }})
{% endif %}
```

## ephemeral

A CTE-only model — no object is created in the database. Referenced models inline it as a subquery.

```sql
{{ config(materialized='ephemeral') }}
select order_id, amount * 0.1 as tax from {{ ref('stg_orders') }}
```

## dynamic_table

Automatically refreshes on a schedule. ClickZetta tracks upstream changes (INSERT/UPDATE/DELETE) and applies them incrementally. See [dynamic-table.md](dynamic-table.md).

```sql
{{ config(
    materialized='dynamic_table',
    refresh_interval='5 MINUTE',
    refresh_vc='default'
) }}
select * from {{ ref('stg_orders') }}
```

## materialized_view

Pre-computed aggregation view. Refreshed manually or on demand.

```sql
{{ config(materialized='materialized_view') }}
select customer_id, sum(amount) as total
from {{ ref('orders') }}
group by customer_id
```

## snapshot

SCD Type 2 history tracking via MERGE INTO. See [snapshots.md](snapshots.md).

## clone

Zero-copy clone or Time Travel clone of an existing relation. See [clone.md](clone.md).

---

## Partitioned Tables

ClickZetta CTAS does not support inline `PARTITIONED BY`. dbt-clickzetta handles this automatically by creating the table schema first, then inserting data.

```sql
{{ config(
    materialized='table',
    partition_by='ds'           -- single column
    -- partition_by=['year', 'month']  -- multiple columns
) }}
```

## Clustered Tables

```sql
{{ config(
    materialized='table',
    clustered_by=['customer_id', 'region'],
    buckets=32
) }}
```

## Indexes

Indexes are created automatically after the table is built. Supported types: `bloomfilter`, `inverted`, `vector`.

```sql
{{ config(
    materialized='table',
    indexes=[
        {'type': 'bloomfilter', 'columns': ['order_id']},
        {'type': 'inverted', 'columns': ['description'], 'analyzer': 'unicode'},
        {'type': 'vector', 'columns': ['embedding'],
         'distance_function': 'cosine_distance', 'scalar_type': 'f32'}
    ]
) }}
```

| Index type | Use case | Options |
|---|---|---|
| `bloomfilter` | Equality lookups on high-cardinality columns | `analyzer` (optional) |
| `inverted` | Full-text search | `analyzer`: `unicode`, `chinese`, `stemmer`, etc. |
| `vector` | Approximate nearest-neighbor search | `distance_function`: `cosine_distance`, `l2_distance`, `dot_product`; `scalar_type`: `f32`, `f16`, `b1` |
