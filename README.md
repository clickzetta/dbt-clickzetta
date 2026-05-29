# dbt-clickzetta

The [dbt](https://www.getdbt.com/) adapter for [ClickZetta Lakehouse](https://www.yunqi.tech/).

查看 **[examples/](./examples/)** 目录获取各功能的完整示例。

## Installation

```bash
pip install dbt-clickzetta
```

Requires Python 3.8+ and dbt-core 1.8+.

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
| `dbt docs generate` | ✅ |
| Partitioned tables | ✅ |
| Clustered tables | ✅ |
| Python models | ✅ |
| `on_schema_change` | ✅ (append_new_columns, sync_all_columns) |
| `grants` | ✅ |

## Incremental Strategies

| Strategy | Description |
|---|---|
| `merge` (default) | MERGE INTO with `unique_key` |
| `append` | INSERT INTO without deduplication |
| `insert_overwrite` | INSERT OVERWRITE with dynamic partition mode |

```sql
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='id'
) }}
```

## Dynamic Table

```sql
{{ config(
    materialized='dynamic_table',
    refresh_interval='5 minutes',
    refresh_vc='default_ap'
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

## Known Limitations

| 限制 | 说明 |
|---|---|
| `HAVING` 无 `GROUP BY` | ClickZetta 支持无 `GROUP BY` 的 `HAVING`，但 `SELECT` 中必须包含聚合函数。`SELECT` 只有常量或普通列时会报错。写 dbt test 时用子查询 + `WHERE` 替代。 |
| `SHOW GRANTS` 不支持子查询 | `SHOW GRANTS ON TABLE ...` 不能作为 CTE 或子查询使用，dbt generic test 无法直接验证权限。需用 `run_query` + `{% if execute %}` 的 singular test 方式。 |
| 动态表不支持 `ALTER` | 动态表创建后不支持修改定义，变更需 `--full-refresh` 重建。 |
| 物化视图不支持 `CREATE OR REPLACE` | 每次 `dbt run` 会先 `DROP` 再 `CREATE`，期间视图不可查询。 |

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
