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
| `dbt docs generate` | ✅ (含行数、大小、最后修改时间) |
| `dbt source freshness` | ✅ |
| `persist_docs` (relation + columns) | ✅ |
| Partitioned tables | ✅ |
| Clustered tables | ✅ |
| Python models | ✅ |
| `on_schema_change` | ✅ (append_new_columns, sync_all_columns) |
| `grants` | ✅ |
| `clone` materialization | ✅ (零拷贝克隆 + Time Travel 克隆) |
| Indexes (Bloomfilter / Inverted / Vector) | ✅ (通过 `indexes` config 自动创建) |
| Table Stream as source | ✅ (通过 `sources.yml` 声明，`source()` 引用) |
| VCluster per-model 切换 | ✅ (通过 `vcluster` config) |

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

支持 Bloomfilter、Inverted、Vector 三种索引，建表后自动创建：

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

为单个模型指定计算集群，实现大小模型资源隔离：

```sql
{{ config(
    materialized='table',
    vcluster='large_ap'   -- 该模型使用 large_ap 集群运行
) }}
```

## Utility Macros

通过 `dbt run-operation` 调用的运维宏：

```bash
# 小文件合并（高频增量写入后使用）
dbt run-operation optimize_table --args '{relation: my_schema.my_table}'
dbt run-operation optimize_table --args '{relation: my_schema.my_table, where: "dt >= current_date() - interval 7 days"}'

# 切换 VCluster
dbt run-operation use_vcluster --args '{vcluster: large_ap}'

# 查看可恢复的已删除对象
dbt run-operation show_tables_history --args '{schema: my_schema}'

# 恢复误删对象（支持普通表、动态表、物化视图、Table Stream）
dbt run-operation undrop --args '{relation: my_schema.my_table}'

# 删除对象（type: table | view | dynamic_table | materialized_view | stream）
dbt run-operation drop_relation --args '{relation: my_schema.my_table, type: table}'

# 手动刷新动态表
dbt run-operation refresh_dynamic_table --args '{model_name: my_dynamic_table}'
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
| `SHOW GRANTS` 在 dbt generic test 中不可用 | dbt generic test 会将 SQL 包裹在 `select count(*) from (...)` 中，而 `SHOW GRANTS` 不支持被这种方式包装。需用 `run_query` + `{% if execute %}` 的 singular test 方式验证权限。注意：ClickZetta 大多数 `SHOW` 命令支持子查询，`SHOW GRANTS` 是例外。 |
| 动态表不支持修改 SQL 定义 | 支持 `ALTER DYNAMIC TABLE` 的 suspend / resume / rename column / set comment，但不支持修改查询 SQL 或刷新间隔。需变更定义时使用 `dbt run --full-refresh` 重建。 |
| 物化视图 `CREATE OR REPLACE` 有限制 | 不能直接 `CREATE OR REPLACE MATERIALIZED VIEW`，需要特定参数组合才能使用。dbt 的处理方式是先 `DROP` 再 `CREATE`，期间视图短暂不可查询。 |

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
