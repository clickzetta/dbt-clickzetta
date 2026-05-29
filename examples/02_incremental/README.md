# 02 增量模型

三种增量策略：`merge`（默认）、`append`、`insert_overwrite`。

## 运行

```bash
# 首次运行（全量）
dbt run

# 增量运行（只处理新数据）
dbt run

# 强制全量刷新
dbt run --full-refresh
```

## 策略说明

| 策略 | 适用场景 | 是否需要 unique_key |
|---|---|---|
| `merge` | 有主键、需要更新历史数据 | ✅ 必填 |
| `append` | 只追加、不更新，如日志流水 | ❌ |
| `insert_overwrite` | 按分区覆盖，如按天分区的事实表 | ❌ |
