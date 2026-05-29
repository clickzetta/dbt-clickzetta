# 05 物化视图（Materialized View）

物化视图将查询结果持久化存储，通过 `REFRESH MATERIALIZED VIEW` 手动刷新。与动态表的区别：动态表自动刷新，物化视图需手动触发。

## 运行

```bash
dbt run
```

## 注意事项

- ClickZetta 不支持 `CREATE OR REPLACE MATERIALIZED VIEW`，dbt 会先 DROP 再 CREATE
- 刷新数据需在 ClickZetta 控制台或通过 SQL 手动执行 `REFRESH MATERIALIZED VIEW schema.view_name`
