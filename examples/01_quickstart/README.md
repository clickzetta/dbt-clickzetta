# 01 快速上手

三种基础 materialization：table、view、ephemeral。

## 运行

```bash
dbt run
```

## 模型说明

- `stg_orders.sql` — ephemeral，作为中间层，不产生实体表
- `dim_customers.sql` — view
- `fct_orders.sql` — table，引用上面两个模型
