# 03 分区表与分桶表

## 运行

```bash
dbt run
```

## 说明

- `partition_by`：按列分区，支持字符串或列表
- `clustered_by` + `buckets`：分桶，需同时指定，适合大表 JOIN 优化
- 两者可以组合使用
