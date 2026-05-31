# Clone

[← 文档首页](README.md) | 相关：[utility-macros.md](utility-macros.md)

Zero-copy clone creates a new relation that shares the underlying data files with the source — no data is copied. Useful for creating dev/test environments from production data instantly.

## Zero-copy clone

```sql
-- depends_on: {{ ref('orders') }}
{{ config(
    materialized='clone',
    source='my_schema.orders'
) }}
```

`source` is a plain string with the fully-qualified table name. Because dbt cannot infer the dependency automatically, you must declare it explicitly with `-- depends_on:` if the source is also a dbt model.

## Time Travel clone

Clone a relation as it existed at a specific point in time:

```sql
-- depends_on: {{ ref('orders') }}
{{ config(
    materialized='clone',
    source='my_schema.orders',
    at_timestamp="'2024-06-01 00:00:00'"
) }}
```

`at_timestamp` is a SQL timestamp expression passed directly to `TIMESTAMP AS OF`. Examples:

```sql
at_timestamp="'2024-06-01 00:00:00'"                        -- literal timestamp
at_timestamp="current_timestamp() - interval 1 hours"       -- relative
```

> The timestamp must be >= the table's creation time, and within the retention period (default: 1 day, up to 90 days).

## Configuration options

| Option | Required | Description |
|---|---|---|
| `source` | ✅ | Fully-qualified source table name, e.g. `'my_schema.orders'` |
| `at_timestamp` | ❌ | SQL timestamp expression for Time Travel clone |

## Use cases

- **Dev/test environments**: clone production tables instantly without copying data
- **Point-in-time analysis**: clone a table as it was before a bad migration
- **Rollback**: clone yesterday's snapshot and swap it in

## Limitations

- Clones share storage with the source. Modifying the clone may trigger copy-on-write for changed files.
- Time Travel is limited by the table's retention period (default: 1 day, configurable up to 90 days).
- `CLONE` does not support `OR REPLACE` — if the target already exists, it is dropped first.
- Dynamic tables and materialized views cannot be cloned.
