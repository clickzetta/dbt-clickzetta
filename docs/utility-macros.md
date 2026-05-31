# Utility Macros

[← 文档首页](README.md) | 相关：[dynamic-table.md](dynamic-table.md) · [clone.md](clone.md)

Run via `dbt run-operation`.

## optimize_table

Compacts small files. Useful after high-frequency incremental writes.

```bash
# Compact all files in a table
dbt run-operation optimize_table --args '{relation: my_schema.my_table}'

# Compact only recent partitions
dbt run-operation optimize_table --args '{relation: my_schema.my_table, where: "ds >= current_date() - interval 7 days"}'
```

As a post-hook:

```sql
{{ config(
    materialized='incremental',
    post_hook="{{ optimize_table(this) }}"
) }}
```

## use_vcluster

Switches the active VCluster for the current session.

```bash
dbt run-operation use_vcluster --args '{vcluster: large_ap}'
```

## refresh_dynamic_table

Manually triggers a refresh of a dynamic table.

```bash
dbt run-operation refresh_dynamic_table --args '{model_name: my_dynamic_table}'
```

## show_tables_history

Lists recently dropped objects available for recovery.

```bash
dbt run-operation show_tables_history --args '{schema: my_schema}'
```

## undrop

Recovers a recently dropped object (table, dynamic table, materialized view, or stream).

```bash
dbt run-operation undrop --args '{relation: my_schema.my_table}'
```

> Recovery is only possible within the retention period (default: 1 day). Use `show_tables_history` first to confirm the object is recoverable.

## drop_object

Drops an object by type.

```bash
# Drop a table
dbt run-operation drop_object --args '{relation: my_schema.my_table, type: table}'

# Drop a view
dbt run-operation drop_object --args '{relation: my_schema.my_view, type: view}'

# Drop a dynamic table
dbt run-operation drop_object --args '{relation: my_schema.my_dt, type: dynamic_table}'

# Drop a stream
dbt run-operation drop_object --args '{relation: my_schema.my_stream, type: stream}'
```

Supported types: `table`, `view`, `dynamic_table`, `materialized_view`, `stream`.

> Tables, dynamic tables, materialized views, and streams support `undrop` recovery. Views do not.
