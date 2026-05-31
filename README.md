# dbt-clickzetta

The [dbt](https://www.getdbt.com/) adapter for [ClickZetta Lakehouse](https://www.yunqi.tech/).

See the **[examples/](./examples/)** directory for complete, runnable examples of all features.

## Installation

```bash
# SQL models only (default)
pip install dbt-clickzetta

# Python models (requires ZettaPark)
pip install "dbt-clickzetta[python]"
```

Requires Python 3.10+ (3.12 recommended) and dbt-core 1.8+.

> **Note on versions:** The legacy `dbt-clickzetta 0.2.x` series on PyPI requires dbt-core ~1.5 and is no longer maintained. Use `dbt-clickzetta >= 1.6` which supports dbt-core 1.8+ and includes full three-part naming (`workspace.schema.table`), incremental strategies, snapshots, and all modern dbt features.

## Quickstart

### 1. Configure profiles.yml

```yaml
my_project:
  target: dev
  outputs:
    dev:
      type: clickzetta
      service: cn-shanghai-alicloud.api.clickzetta.com
      instance: your_instance
      workspace: your_workspace
      username: your_username
      password: your_password
      schema: your_schema
      vcluster: default_ap
```

### 2. Test connection

```bash
dbt debug
```

### 3. Run your project

```bash
dbt run
dbt test
dbt docs generate
```

## Supported Features

| Feature | Supported |
|---|---|
| `table` materialization | ✅ |
| `view` materialization | ✅ |
| `incremental` materialization | ✅ |
| `ephemeral` materialization | ✅ |
| `snapshot` (SCD Type 2) | ✅ |
| `dynamic_table` materialization | ✅ |
| `materialized_view` materialization | ✅ |
| `dbt test` (generic + singular) | ✅ |
| `dbt seed` | ✅ |
| `dbt docs generate` | ✅ (row count, size, last modified) |
| `dbt source freshness` | ✅ |
| `persist_docs` (relation + columns) | ✅ |
| Partitioned tables | ✅ |
| Clustered tables | ✅ |
| Python models | ✅ requires `pip install "dbt-clickzetta[python]"` |
| `on_schema_change` | ✅ (append_new_columns, sync_all_columns) |
| `grants` | ✅ |
| `clone` materialization | ✅ (zero-copy clone + Time Travel clone) |
| Indexes (Bloomfilter / Inverted / Vector) | ✅ (auto-created via `indexes` config) |
| Table Stream as source | ✅ (declare in `sources.yml`, reference via `source()`) |
| VCluster per-model | ✅ (via `vcluster` config) |

## Incremental Strategies

| Strategy | Description |
|---|---|
| `merge` (default) | MERGE INTO with `unique_key` |
| `append` | INSERT INTO without deduplication |
| `insert_overwrite` | INSERT OVERWRITE with dynamic partition mode |
| `delete+insert` | DELETE matching keys then INSERT, suitable for partition replacement without a primary key |

```sql
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='id'
) }}
```

## Indexes

Supports Bloomfilter, Inverted, and Vector index types. Indexes are created automatically after the table is built:

```sql
{{ config(
    materialized='table',
    indexes=[
        {'type': 'bloomfilter', 'columns': ['order_id']},
        {'type': 'inverted', 'columns': ['status'], 'analyzer': 'unicode'},
        {'type': 'vector', 'columns': ['embedding'], 'distance_function': 'cosine_distance', 'scalar_type': 'f32'}
    ]
) }}
```

## VCluster per-model

Assign a specific VCluster to a model for compute resource isolation:

```sql
{{ config(
    materialized='table',
    vcluster='large_ap'   -- this model runs on the large_ap cluster
) }}
```

## Utility Macros

Run via `dbt run-operation`:

```bash
# Compact small files (useful after high-frequency incremental writes)
dbt run-operation optimize_table --args '{relation: my_schema.my_table}'
dbt run-operation optimize_table --args '{relation: my_schema.my_table, where: "dt >= current_date() - interval 7 days"}'

# Switch VCluster for the current session
dbt run-operation use_vcluster --args '{vcluster: large_ap}'

# List recently dropped objects available for recovery
dbt run-operation show_tables_history --args '{schema: my_schema}'

# Recover a dropped object (table, dynamic table, materialized view, or stream)
dbt run-operation undrop --args '{relation: my_schema.my_table}'

# Drop an object (type: table | view | dynamic_table | materialized_view | stream)
dbt run-operation drop_object --args '{relation: my_schema.my_table, type: table}'

# Manually refresh a dynamic table
dbt run-operation refresh_dynamic_table --args '{model_name: my_dynamic_table}'
```

## Table Stream as Source

Declare a Table Stream in `sources.yml` and reference it via `source()`. The stream appends three system columns to every row: `__change_type`, `__commit_version`, `__commit_timestamp`.

```yaml
# sources.yml
sources:
  - name: my_streams
    schema: my_schema
    tables:
      - name: orders_stream
```

```sql
-- Option 1: explicit columns (production-safe)
select __change_type, __commit_timestamp, order_id, amount
from {{ source('my_streams', 'orders_stream') }}

-- Option 2: SELECT * EXCEPT — returns only user columns, no hardcoded list
select * except(__change_type, __commit_timestamp, __commit_version)
from {{ source('my_streams', 'orders_stream') }}
```

> Note: `SELECT` does not advance the stream offset. Only DML statements (INSERT, MERGE, etc.) advance it.

## Dynamic Table

```sql
{{ config(
    materialized='dynamic_table',
    refresh_interval='5 minutes',
    refresh_vc='default'
) }}
select id, name, amount
from {{ ref('orders') }}
```

After creation, the table is automatically refreshed once (equivalent to Snowflake's `initialize=ON_CREATE`). Subsequent refreshes run on the configured interval.

## Snapshot

Snapshots use standard dbt SCD Type 2 via MERGE INTO on regular tables (no delta/iceberg required).

```sql
{% snapshot orders_snapshot %}
{{ config(
    target_schema='snapshots',
    unique_key='id',
    strategy='timestamp',
    updated_at='updated_at'
) }}
select * from {{ source('raw', 'orders') }}
{% endsnapshot %}
```

## Connection Parameters

| Parameter | Required | Description |
|---|---|---|
| `type` | ✅ | Must be `clickzetta` |
| `service` | ✅ | API endpoint, e.g. `cn-shanghai-alicloud.api.clickzetta.com` |
| `instance` | ✅ | Instance name |
| `workspace` | ✅ | Workspace name |
| `username` | ✅ | Username |
| `password` | ✅ | Password |
| `schema` | ✅ | Default schema |
| `vcluster` | ✅ | VCluster name, e.g. `default_ap` |
| `connect_retries` | ❌ | Connection retry count (default: 3) |

## Development

```bash
# Clone
git clone https://github.com/clickzetta/dbt-clickzetta.git
cd dbt-clickzetta

# Install in editable mode
pip install -e .

# Run unit tests
pip install pytest
pytest tests/unit/

# Run functional tests (requires a real Lakehouse connection)
cp test.env.example test.env
# Fill in test.env with your connection details
pytest tests/functional/
```

## License

Apache 2.0
