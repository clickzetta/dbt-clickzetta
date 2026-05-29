# dbt-clickzetta 示例项目

这是一个完整可运行的 dbt 项目，包含 ClickZetta adapter 所有主要功能的示例。
数据通过 seeds 内置，无需准备外部数据源，克隆后按步骤即可运行。

## 项目结构

```
examples/
├── dbt_project.yml
├── profiles.yml          # 连接配置模板
├── seeds/                # 内置测试数据
│   ├── raw_orders.csv
│   ├── raw_customers.csv
│   └── raw_events.csv
├── models/
│   ├── staging/          # view：数据清洗层
│   │   ├── stg_orders.sql
│   │   └── stg_customers.sql
│   ├── marts/            # table / incremental：业务模型层
│   │   ├── dim_customers.sql              # 基础 table
│   │   ├── fct_orders_partitioned.sql     # 分区表
│   │   ├── fct_orders_incremental.sql     # 增量（merge）
│   │   ├── daily_revenue.sql              # 增量（insert_overwrite）
│   │   └── regional_revenue_with_grants.sql  # grants 示例
│   └── advanced/         # 动态表 / 物化视图
│       ├── customer_stats_dynamic.sql     # 动态表
│       └── regional_daily_mv.sql         # 物化视图
└── snapshots/            # SCD Type 2
    ├── orders_snapshot.sql    # timestamp 策略
    └── customers_snapshot.sql # check 策略
```

## 快速开始

### 第一步：安装

```bash
pip install dbt-clickzetta
```

### 第二步：配置连接

编辑 `profiles.yml`，填入你的 ClickZetta 连接信息：

```yaml
clickzetta_example:
  target: dev
  outputs:
    dev:
      type: clickzetta
      service: cn-shanghai-alicloud.api.clickzetta.com
      instance: your_instance      # ClickZetta 实例 ID
      workspace: your_workspace    # 工作空间名称
      username: your_username
      password: your_password
      schema: example              # 模型写入的 schema（会自动创建）
      vcluster: default_ap         # 计算集群名称
```

各区域 service 端点：

| 区域 | service |
|---|---|
| 阿里云上海 | `cn-shanghai-alicloud.api.clickzetta.com` |
| 腾讯云上海 | `ap-shanghai-tencentcloud.api.clickzetta.com` |
| 腾讯云北京 | `ap-beijing-tencentcloud.api.clickzetta.com` |
| 腾讯云广州 | `ap-guangzhou-tencentcloud.api.clickzetta.com` |
| AWS 宁夏 | `cn-north-1-aws.api.clickzetta.com` |

### 第三步：验证连接

```bash
cd examples
dbt debug --profiles-dir .
```

看到 `All checks passed!` 即连接成功。

### 第四步：加载测试数据

```bash
dbt seed --profiles-dir .
```

这会在 `example_raw` schema 下创建 `raw_orders`、`raw_customers`、`raw_events` 三张表。

### 第五步：运行模型

```bash
# 运行所有模型
dbt run --profiles-dir .

# 只运行基础模型（跳过动态表和物化视图）
dbt run --profiles-dir . --exclude advanced

# 强制全量刷新
dbt run --profiles-dir . --full-refresh
```

### 第六步：运行 snapshot

```bash
dbt snapshot --profiles-dir .
```

---

## 功能说明

### 基础 materialization

| 模型 | 类型 | 说明 |
|---|---|---|
| `stg_orders` | view | 订单清洗视图 |
| `stg_customers` | view | 客户清洗视图 |
| `dim_customers` | table | 客户汇总宽表 |

### 分区表

`fct_orders_partitioned` 按 `dt` 列分区：

```sql
{{ config(
    materialized='table',
    partition_by='dt'          -- 单列分区
    -- partition_by=['region', 'dt']  -- 多列分区
    -- clustered_by='customer_id',    -- 分桶（需同时指定 buckets）
    -- buckets=32
) }}
```

### 增量模型

**merge 策略**（`fct_orders_incremental`）：有主键、需要更新历史数据时使用：

```sql
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='order_id'       -- 必填
) }}
...
{% if is_incremental() %}
where updated_at > (select max(updated_at) from {{ this }})
{% endif %}
```

**insert_overwrite 策略**（`daily_revenue`）：按分区覆盖，适合按天汇总的事实表：

```sql
{{ config(
    materialized='incremental',
    incremental_strategy='insert_overwrite',
    partition_by='dt'
) }}
```

### 动态表

`customer_stats_dynamic` 每 5 分钟自动刷新，无需外部调度：

```sql
{{ config(
    materialized='dynamic_table',
    refresh_interval='5 minutes',
    refresh_vc='default_ap'     -- 指定刷新使用的 vcluster
) }}
```

> 注意：`dbt run` 时如果动态表已存在则跳过（no-op），由 ClickZetta 自动刷新。
> 使用 `dbt run --full-refresh` 强制重建。

### 物化视图

`regional_daily_mv` 将查询结果持久化，需手动刷新：

```sql
{{ config(materialized='materialized_view') }}
```

刷新数据：
```sql
REFRESH MATERIALIZED VIEW example.regional_daily_mv;
```

### Snapshot（SCD Type 2）

`orders_snapshot` 追踪订单状态变化历史：

```bash
# 首次运行：全量快照
dbt snapshot --profiles-dir .

# 后续运行：只处理变化的行
dbt snapshot --profiles-dir .
```

查询历史版本：
```sql
-- 查看某订单的所有历史状态
select * from example_snapshots.orders_snapshot
where order_id = '1001'
order by dbt_valid_from;
```

### Grants（权限管理）

`regional_revenue_with_grants` 演示自动授权：

```sql
{{ config(
    materialized='table',
    grants={
        'select': ['workspace_analyst'],        -- 授权给角色
        -- 'select': ['user:alice'],            -- 授权给用户（加 user: 前缀）
        -- 'insert': ['workspace_dev']          -- 多种权限
    }
) }}
```

> 注意：将 `workspace_analyst` 替换为你环境中实际存在的角色名。
> grants 变更后重新运行，dbt 自动 REVOKE 旧权限、GRANT 新权限。

---

## 常见问题

**Q: `dbt debug` 报 `Could not find adapter type clickzetta`**

```bash
pip install dbt-clickzetta
```

**Q: `dbt seed` 报 schema 不存在**

seed 会自动创建 schema，确认 `profiles.yml` 中的用户有 `CREATE SCHEMA` 权限。

**Q: 动态表运行后数据为空**

动态表创建后会立即触发一次刷新，如果数据仍为空，手动执行：
```sql
REFRESH DYNAMIC TABLE example.customer_stats_dynamic;
```

**Q: grants 报 `user 'xxx' isn't allowed`**

授权操作需要当前用户对目标表有 `GRANT OPTION`，即表的 owner 才能授权。
