# dbt-clickzetta

The [dbt](https://www.getdbt.com/) adapter for [ClickZetta Lakehouse](https://www.yunqi.tech/).

## Installation

```bash
# SQL models only (default)
pip install dbt-clickzetta

# Python models (requires ZettaPark)
pip install "dbt-clickzetta[python]"
```

Requires Python 3.10+ (3.12 recommended) and dbt-core 1.8+.

> **Note on versions:** The legacy `dbt-clickzetta 0.2.x` series requires dbt-core ~1.5 and is no longer maintained. Use `dbt-clickzetta >= 1.6`.

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
      vcluster: default
      query_tag: "dbt_{{ target.name }}"   # optional
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

See the **[examples/](./examples/)** directory for complete, runnable examples.

**→ [完整功能文档](docs/README.md)**

## Supported Features

| Feature | Description | Docs |
|---|---|---|
| `table` / `view` / `ephemeral` | Standard dbt materializations | [materializations.md](docs/materializations.md) |
| `incremental` | Incremental load: merge / append / insert_overwrite / delete+insert | [incremental.md](docs/incremental.md) |
| `dynamic_table` | Auto-refresh on schedule, no manual scheduling needed | [dynamic-table.md](docs/dynamic-table.md) |
| `materialized_view` | Pre-computed aggregation view | [materializations.md](docs/materializations.md) |
| `snapshot` | SCD Type 2 history tracking | [snapshots.md](docs/snapshots.md) |
| `clone` | Zero-copy clone + Time Travel clone | [clone.md](docs/clone.md) |
| Python models | Run Python/ML models via ZettaPark | [python-models.md](docs/python-models.md) |
| Table Stream | CDC source: capture INSERT/UPDATE/DELETE | [table-stream.md](docs/table-stream.md) |
| Indexes | Bloomfilter / Inverted / Vector indexes | [materializations.md](docs/materializations.md#indexes) |
| Partitioned & clustered tables | Partition by column, cluster by bucket | [materializations.md](docs/materializations.md#partitioned-tables) |
| `persist_docs` | Sync model/column descriptions to Lakehouse | — |
| `on_schema_change` | Handle schema drift in incremental models | [incremental.md](docs/incremental.md#on_schema_change) |
| `grants` | Column/table-level access control | — |
| VCluster per-model | Assign compute cluster per model | [incremental.md](docs/incremental.md#vcluster-per-model) |
| `query_tag` | Tag all queries for job history filtering | [observability.md](docs/observability.md) |
| `query_comment` | Auto-inject dbt metadata into every SQL (on by default) | [observability.md](docs/observability.md) |
| Utility macros | optimize, undrop, clone, refresh, etc. | [utility-macros.md](docs/utility-macros.md) |

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
| `vcluster` | ✅ | VCluster name, e.g. `default` |
| `connect_retries` | ❌ | Connection retry count (default: 3) |
| `query_tag` | ❌ | Tag applied to every query; visible in job history |

## Development

```bash
git clone https://github.com/clickzetta/dbt-clickzetta.git
cd dbt-clickzetta
pip install -e .

# Unit tests (no connection required)
pytest tests/unit/

# Functional tests (requires a real Lakehouse connection)
cp test.env.example test.env
# Fill in test.env with your connection details
pytest tests/functional/
```

## License

Apache 2.0
