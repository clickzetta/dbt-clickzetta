# Incremental Models

[← 文档首页](README.md) | 相关：[materializations.md](materializations.md) · [dynamic-table.md](dynamic-table.md)

dbt-clickzetta supports four incremental strategies. The default is `merge`.

## Strategies

### merge (default)

MERGE INTO with a `unique_key`. Inserts new rows and updates existing ones.

```sql
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='order_id'
) }}
select order_id, customer_id, amount, updated_at
from {{ ref('stg_orders') }}
{% if is_incremental() %}
  where updated_at >= (select max(updated_at) from {{ this }})
{% endif %}
```

Composite key:

```sql
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key=['order_id', 'line_item_id']
) }}
```

Exclude columns from the UPDATE clause (e.g. preserve `created_at`):

```sql
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='order_id',
    merge_exclude_columns=['created_at']
) }}
```

### append

INSERT INTO without deduplication. Fastest option when duplicates are not a concern.

```sql
{{ config(
    materialized='incremental',
    incremental_strategy='append'
) }}
select * from {{ ref('stg_events') }}
{% if is_incremental() %}
  where event_date >= (select max(event_date) from {{ this }})
{% endif %}
```

### insert_overwrite

INSERT OVERWRITE with dynamic partition mode. Replaces entire partitions atomically.

```sql
{{ config(
    materialized='incremental',
    incremental_strategy='insert_overwrite',
    partition_by='ds'
) }}
select *, date_format(created_at, 'yyyyMMdd') as ds
from {{ ref('stg_orders') }}
{% if is_incremental() %}
  where ds >= date_format(current_date() - interval 3 days, 'yyyyMMdd')
{% endif %}
```

### delete+insert

DELETE matching rows then INSERT. Useful for partition replacement when there is no single primary key.

```sql
{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key='order_id'
) }}
select * from {{ ref('stg_orders') }}
{% if is_incremental() %}
  where updated_at >= (select max(updated_at) from {{ this }})
{% endif %}
```

> Note: ClickZetta does not support multi-statement execution. dbt-clickzetta splits DELETE and INSERT into two separate statements automatically.

## on_schema_change

Controls behavior when the source model adds or removes columns.

```sql
{{ config(
    materialized='incremental',
    unique_key='id',
    on_schema_change='append_new_columns'  -- ignore | append_new_columns | sync_all_columns | fail
) }}
```

| Value | Behavior |
|---|---|
| `ignore` (default) | Schema changes are ignored |
| `append_new_columns` | New columns are added to the target table |
| `sync_all_columns` | Adds new columns and removes dropped columns |
| `fail` | Raises an error if the schema changes |

## incremental_predicates

Add extra filter conditions to the MERGE or DELETE statement to limit the scan range (useful for large partitioned tables):

```sql
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='order_id',
    incremental_predicates=["ds >= '{{ var('start_date') }}'"]
) }}
```

## VCluster per-model

Run a specific model on a different compute cluster:

```sql
{{ config(
    materialized='incremental',
    unique_key='id',
    vcluster='large_ap'
) }}
```
