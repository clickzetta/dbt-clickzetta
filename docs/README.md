# dbt-clickzetta 文档

## 从哪里开始？

**第一次使用** → 看主 [README](../README.md) 完成安装和连接配置，然后回来这里。

**从 Snowflake 迁移** → 参考 [Snowflake 迁移指南](https://github.com/clickzetta/snowflake-dbt2lakehouse-dbt)。

**想了解某个具体功能** → 直接看下面的文档列表。

---

## 功能文档

### 数据建模

| 文档 | 解决什么问题 |
|---|---|
| [materializations.md](materializations.md) | 选哪种物化方式？table / view / incremental / ephemeral / materialized_view 的区别，以及分区、聚簇、索引怎么配 |
| [incremental.md](incremental.md) | 增量模型的四种策略（merge / append / insert_overwrite / delete+insert），以及 on_schema_change、incremental_predicates |
| [dynamic-table.md](dynamic-table.md) | 动态表自动刷新，适合实时/准实时管道，不需要手动调度 |
| [snapshots.md](snapshots.md) | SCD Type 2 历史拉链表，追踪数据变更历史 |
| [clone.md](clone.md) | 零拷贝克隆，秒级创建开发/测试环境，支持 Time Travel |

### 数据摄取

| 文档 | 解决什么问题 |
|---|---|
| [table-stream.md](table-stream.md) | 用 Table Stream 捕获 CDC 变更（INSERT/UPDATE/DELETE），构建实时数据管道 |

### 配置与环境

| 文档 | 解决什么问题 |
|---|---|
| [profiles-and-environments.md](profiles-and-environments.md) | 多环境配置（dev/prod/ci）、分层模式选择、schema 拼接规则、各区域端点 |
| [observability.md](observability.md) | query_tag 和 query_comment，在作业历史里追踪每条 SQL 来自哪个 dbt 模型 |
| [utility-macros.md](utility-macros.md) | 常用运维操作：压缩小文件、恢复误删对象、手动刷新动态表等 |

### 高级功能

| 文档 | 解决什么问题 |
|---|---|
| [python-models.md](python-models.md) | 在 dbt 里写 Python 模型，用 ZettaPark 做机器学习、复杂转换 |

---

## 常见场景

### 我想做实时/准实时数据管道

用**动态表**。上游数据变更后自动增量刷新，不需要 Studio 调度任务。

```sql
{{ config(
    materialized='dynamic_table',
    refresh_interval='5 MINUTE',
    refresh_vc='default'
) }}
select customer_id, sum(amount) as total
from {{ ref('orders') }}
group by customer_id
```

→ 详见 [dynamic-table.md](dynamic-table.md)

### 我想做批量增量 ETL

用 **incremental** 物化 + merge 策略。

```sql
{{ config(
    materialized='incremental',
    unique_key='order_id'
) }}
select * from {{ ref('stg_orders') }}
{% if is_incremental() %}
  where updated_at >= (select max(updated_at) from {{ this }})
{% endif %}
```

→ 详见 [incremental.md](incremental.md)

### 我想捕获数据变更（CDC）

用 **Table Stream** 作为 source，配合 incremental 模型消费变更。

→ 详见 [table-stream.md](table-stream.md)

### 我想追踪数据历史（SCD Type 2）

用 **snapshot**。

→ 详见 [snapshots.md](snapshots.md)

### 我想在 dbt 里跑 Python / 机器学习

用 **Python 模型**，需要 `pip install "dbt-clickzetta[python]"`。

→ 详见 [python-models.md](python-models.md)

### 我想知道某条 SQL 是哪个 dbt 模型发出的

dbt 默认会在每条 SQL 里注入 JSON 注释，在 `SHOW JOBS` 的 `job_text` 列实时可见。

→ 详见 [observability.md](observability.md)

### 我想快速创建一个开发环境（不复制数据）

用 **clone** 物化，零拷贝克隆生产表。

→ 详见 [clone.md](clone.md)

---

## 选哪种物化方式？

```
数据需要实时/准实时自动刷新？
  ├─ 是 → dynamic_table（声明式，系统自动增量刷新）
  └─ 否 → 需要追踪历史变更？
            ├─ 是 → snapshot（SCD Type 2）
            └─ 否 → 数据量大，需要增量写入？
                      ├─ 是 → incremental（merge / append / insert_overwrite / delete+insert）
                      └─ 否 → 数据量小或全量重算？
                                ├─ 需要存储 → table
                                ├─ 不需要存储 → view 或 ephemeral
                                └─ 预计算聚合 → materialized_view
```

---

## 多环境架构

ClickZetta 的对象层级是 `Instance → Workspace → Schema`。推荐用**同一 Workspace、不同 Schema 后缀**区分 dev/prod/ci 环境。

分层方式不限：dbt 推荐 `staging/intermediate/marts`，也可以用大奖牌模式 `bronze/silver/gold`，或传统 `ods/dwd/ads`。

→ 详见 [profiles-and-environments.md](profiles-and-environments.md)
