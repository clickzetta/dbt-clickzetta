# Snapshots

[← 文档首页](README.md) | 相关：[materializations.md](materializations.md) · [incremental.md](incremental.md)

Snapshots implement SCD Type 2 history tracking via MERGE INTO on regular tables. No special table format (delta/iceberg) is required.

## timestamp strategy

Tracks changes based on an `updated_at` column.

```sql
{% snapshot orders_snapshot %}
{{ config(
    target_schema='snapshots',
    unique_key='order_id',
    strategy='timestamp',
    updated_at='updated_at'
) }}
select * from {{ source('raw', 'orders') }}
{% endsnapshot %}
```

## check strategy

Tracks changes by comparing a list of columns. Use when there is no reliable `updated_at` column.

```sql
{% snapshot customers_snapshot %}
{{ config(
    target_schema='snapshots',
    unique_key='customer_id',
    strategy='check',
    check_cols=['name', 'email', 'address']
) }}
select * from {{ source('raw', 'customers') }}
{% endsnapshot %}
```

Or check all columns:

```sql
{{ config(
    strategy='check',
    check_cols='all'
) }}
```

## Running snapshots

```bash
dbt snapshot
```

## Output columns

dbt adds four columns to every snapshot table:

| Column | Description |
|---|---|
| `dbt_scd_id` | Unique identifier for each snapshot row |
| `dbt_updated_at` | When this snapshot row was last updated |
| `dbt_valid_from` | When this version became active |
| `dbt_valid_to` | When this version was superseded (`null` = current) |

## Querying current state

```sql
select * from {{ ref('orders_snapshot') }}
where dbt_valid_to is null
```

## Querying historical state

```sql
select * from {{ ref('orders_snapshot') }}
where '2024-06-01' between dbt_valid_from and coalesce(dbt_valid_to, current_timestamp())
```
