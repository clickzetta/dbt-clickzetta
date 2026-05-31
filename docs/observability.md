# Observability

[← 文档首页](README.md) | 相关：[utility-macros.md](utility-macros.md)

## query_tag

Tags every query in the session with a label. Visible in `SHOW JOBS` (real-time) and `information_schema.job_history` for filtering and cost attribution.

```yaml
# profiles.yml
my_project:
  target: dev
  outputs:
    dev:
      type: clickzetta
      # ... connection params ...
      query_tag: "dbt_{{ target.name }}"   # renders to dbt_dev / dbt_prod
```

After setting `query_tag`, every query from this connection carries the tag:

```sql
-- Real-time: SHOW JOBS
SELECT job_id, job_text, query_tag, start_time
FROM (SHOW JOBS)
WHERE query_tag = 'dbt_prod';

-- With ~15 min delay: information_schema.job_history
SELECT job_id, job_text, query_tag, start_time
FROM information_schema.job_history
WHERE query_tag = 'dbt_prod'
ORDER BY start_time DESC
LIMIT 100;
```

## query_comment

dbt automatically injects a JSON comment into every SQL query — **no configuration needed**. The comment appears in `SHOW JOBS` `job_text` in real-time.

Example of what you'll see in `SHOW JOBS`:

```sql
/* {"app": "dbt", "dbt_version": "1.8.9", "profile_name": "my_project",
    "target_name": "prod", "node_id": "model.my_project.orders"} */
CREATE TABLE quick_start.dbt_prod.orders AS ...
```

The default comment includes:

| Field | Description |
|---|---|
| `app` | Always `"dbt"` |
| `dbt_version` | dbt-core version |
| `profile_name` | Profile name from profiles.yml |
| `target_name` | Target name (dev / prod / etc.) |
| `node_id` | Fully qualified model ID (e.g. `model.my_project.orders`) |

### Customizing the comment

To add extra fields (e.g. `node_name`, `materialized`), override in profiles.yml:

```yaml
# profiles.yml
my_project:
  target: dev
  outputs:
    dev:
      type: clickzetta
      # ... connection params ...
      query_comment:
        comment: "{{ query_comment(node) }}"   # uses clickzetta__query_comment macro
        append: false                           # prepend (default) or append after SQL
```

The `clickzetta__query_comment` macro adds `node_name` and `materialized` for model nodes:

```json
{"app": "dbt", "dbt_version": "1.8.9", "target_name": "prod",
 "node_id": "model.my_project.orders", "node_name": "orders", "materialized": "table"}
```

To disable query comments entirely:

```yaml
query_comment: null
```

### append vs prepend

- `append: false` (default): comment is prepended — `/* ... */ SELECT ...`
- `append: true`: comment is appended — `SELECT ... /* ... */`

> Use `append: true` if you have `PUT` or `COPY INTO` statements that must start with the keyword (ClickZetta detects these by checking if the SQL starts with `PUT ` or `COPY `).

## query_tag vs query_comment

| | `query_tag` | `query_comment` |
|---|---|---|
| Setup | `query_tag:` in profiles.yml | Automatic (no setup needed) |
| Mechanism | `SET query_tag = '...'` on connection open | JSON comment injected into SQL text |
| Visible in | `SHOW JOBS` `query_tag` column | `SHOW JOBS` `job_text` column |
| Real-time | ✅ | ✅ |
| Best for | Filtering/grouping all jobs by project or environment | Tracing individual queries back to their dbt model |
