# 06 Snapshot（SCD Type 2）

Snapshot 追踪数据变化历史，自动维护 `dbt_valid_from` / `dbt_valid_to` 字段，实现缓慢变化维度（SCD Type 2）。

## 运行

```bash
# 首次运行：全量快照
dbt snapshot

# 后续运行：只处理变化的行
dbt snapshot
```

## 策略说明

| 策略 | 说明 | 必填字段 |
|---|---|---|
| `timestamp` | 按 `updated_at` 字段判断变化 | `updated_at` |
| `check` | 按指定列的值判断变化 | `check_cols` |

## 注意事项

- ClickZetta 使用普通表 + MERGE INTO 实现，不需要 Delta/Iceberg 格式
- `target_schema` 建议与业务表分开，如 `snapshots`
