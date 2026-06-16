# Dynamic Table

[← 文档首页](README.md) | 相关：[incremental.md](incremental.md) · [table-stream.md](table-stream.md) · [utility-macros.md](utility-macros.md)

Dynamic tables are ClickZetta's declarative incremental materialization. The system automatically tracks upstream changes (INSERT/UPDATE/DELETE) and refreshes the table on a schedule — no dbt scheduling or Studio tasks needed.

## Basic usage

```sql
{{ config(
    materialized='dynamic_table',
    refresh_interval='5 MINUTE',
    refresh_vc='default'
) }}
select
    customer_id,
    sum(amount) as total_amount,
    count(*) as order_count
from {{ ref('orders') }}
group by customer_id
```

After creation, dbt triggers an immediate refresh so the table is queryable right away. Subsequent refreshes run automatically on the configured interval.

## Configuration options

| Option | Required | Description |
|---|---|---|
| `refresh_interval` | ✅ | Refresh schedule, e.g. `'5 MINUTE'`, `'1 HOUR'`, `'30 MINUTE'` |
| `refresh_vc` | ❌ | VCluster used for refresh jobs, e.g. `'default'`. Omit to use the session default |
| `on_configuration_change` | ❌ | What to do when the model config changes (see below) |
| `full_refresh_strategy` | ❌ | `replace` (default) or `recreate` — see Escape Hatch below |
| `partition_by` | ❌ | Partition columns |
| `clustered_by` + `buckets` | ❌ | Clustering columns and bucket count |

### refresh_interval format

Use `N MINUTE`, `N HOUR`, or `N DAY` (singular, uppercase):

```sql
refresh_interval='5 MINUTE'    -- every 5 minutes
refresh_interval='1 HOUR'      -- every hour
refresh_interval='1 DAY'       -- daily
```

## on_configuration_change

Controls what happens when you run `dbt run` and the dynamic table already exists.

```sql
{{ config(
    materialized='dynamic_table',
    refresh_interval='10 MINUTE',
    refresh_vc='default',
    on_configuration_change='apply'
) }}
```

| Value | Behavior |
|---|---|
| `continue` (default) | No-op — the existing table keeps refreshing on its current schedule |
| `apply` | Recreates the table with `CREATE OR REPLACE DYNAMIC TABLE` to apply config or SQL changes |
| `fail` | Raises a compiler error — forces you to run `dbt run --full-refresh` explicitly |

> **Note:** ClickZetta does not support `ALTER DYNAMIC TABLE` for refresh config changes. `apply` uses `CREATE OR REPLACE`, which triggers a full refresh of the table data.

## Escape Hatch: full_refresh_strategy

`CREATE OR REPLACE DYNAMIC TABLE` can fail at semantic analysis when the engine's incremental maintenance plan is rejected — even though the SQL itself is valid (e.g. models with OUTER/SEMI/ANTI joins). When this happens, use `full_refresh_strategy: recreate` to force a DROP + fresh CREATE instead.

```sql
{{ config(
    materialized='dynamic_table',
    refresh_interval='1 HOUR',
    refresh_vc='default',
    full_refresh_strategy='recreate'    # escape hatch for CZLH-42000
) }}
```

| Value | Behavior |
|---|---|
| `replace` (default) | `CREATE OR REPLACE DYNAMIC TABLE` — preserves data and grants |
| `recreate` | `DROP DYNAMIC TABLE` + `CREATE DYNAMIC TABLE` — works when OR REPLACE's incremental plan is rejected |

`recreate` trade-offs:
- **Loses grants** — dbt re-applies grants from config, but any manual grants are lost
- **Downstream DTs rebuild** — any dynamic table that reads from this table will do a full refresh on its next scheduled run
- Only use when `replace` fails with `CZLH-42000`

## Schema changes

Dynamic table schema is fixed at creation time. If an upstream source adds a column, the dynamic table will **not** pick it up automatically — even if the model uses `SELECT *`.

To pick up schema changes:

```bash
dbt run --full-refresh
```

## Partitioned dynamic table

```sql
{{ config(
    materialized='dynamic_table',
    refresh_interval='1 HOUR',
    refresh_vc='default',
    partition_by=['ds']
) }}
select
    date_format(order_date, 'yyyyMMdd') as ds,
    customer_id,
    sum(amount) as daily_total
from {{ ref('orders') }}
group by ds, customer_id
```

## Manual refresh

```bash
dbt run-operation refresh_dynamic_table --args '{model_name: my_dynamic_table}'
```

Or directly in SQL:

```sql
REFRESH DYNAMIC TABLE my_schema.my_dynamic_table;
```

## Dynamic table pipeline

Dynamic tables can read from other dynamic tables. Refresh each layer in dependency order — ClickZetta does not cascade refreshes automatically.

```sql
-- Layer 1: staging (refresh every 5 min)
{{ config(materialized='dynamic_table', refresh_interval='5 MINUTE', refresh_vc='default') }}
select * from {{ source('raw', 'orders') }}

-- Layer 2: aggregation (refresh every 10 min, reads from layer 1)
{{ config(materialized='dynamic_table', refresh_interval='10 MINUTE', refresh_vc='default') }}
select customer_id, sum(amount) as total
from {{ ref('dt_staging') }}
group by customer_id
```

## Comparison with other materializations

| | `dynamic_table` | `incremental` | `materialized_view` |
|---|---|---|---|
| Refresh trigger | Scheduled (automatic) | `dbt run` | Manual / on-demand |
| Incremental logic | Declarative (system-managed) | Explicit SQL | N/A |
| Schema changes | Fixed at creation | `on_schema_change` config | Fixed at creation |
| Best for | Real-time pipelines, ODS→DWD | Batch ETL with custom logic | Pre-computed aggregations |
