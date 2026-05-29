# 04 动态表（Dynamic Table）

动态表由 ClickZetta 自动按设定间隔刷新，无需外部调度。创建后立即触发一次刷新，之后按 `refresh_interval` 定时刷新。

## 运行

```bash
dbt run

# 强制重建（DROP + CREATE）
dbt run --full-refresh
```

## 注意事项

- 动态表创建后 dbt 会立即触发一次 `REFRESH DYNAMIC TABLE`，确保数据可查
- 再次 `dbt run`（非 `--full-refresh`）时，如果动态表已存在则跳过（no-op），由 ClickZetta 自动刷新
- `refresh_vc`：指定刷新使用的 VCluster，不填则使用默认
- `refresh_interval`：刷新间隔，如 `'5 minutes'`、`'1 hour'`
