# dbt-clickzetta 示例项目

这是一个完整可运行的 dbt 项目，覆盖 ClickZetta adapter 的所有主要功能。
项目内置了测试数据（seeds），无需准备外部数据源，按步骤即可从零跑通。

---

## 项目结构

```
examples/
├── dbt_project.yml          # 项目配置
├── profiles.yml.example     # 连接配置模板（cp 成 profiles.yml 后填入真实信息）
├── profiles.yml             # 本地连接配置（已 gitignore，不提交）
├── seeds/                   # 内置测试数据（CSV 文件，dbt seed 自动导入）
│   ├── raw_orders.csv       # 10 条订单数据
│   ├── raw_customers.csv    # 5 条客户数据
│   ├── raw_events.csv       # 8 条事件数据
│   └── schema.yml           # 指定列类型，避免类型推断错误
├── models/
│   ├── staging/             # 数据清洗层（view）
│   │   ├── stg_orders.sql
│   │   └── stg_customers.sql
│   ├── marts/               # 业务模型层（table / incremental）
│   │   ├── dim_customers.sql              # 客户汇总宽表（table）
│   │   ├── fct_orders_partitioned.sql     # 按日期分区的订单表（table + partition_by）
│   │   ├── fct_orders_incremental.sql     # 增量订单表（incremental merge）
│   │   ├── daily_revenue.sql              # 按日期区域汇总（incremental insert_overwrite）
│   │   └── regional_revenue_with_grants.sql  # 带权限授权的汇总表（grants）
│   ├── advanced/            # 高级功能
│   │   ├── customer_stats_dynamic.sql     # 动态表（每 5 分钟自动刷新）
│   │   └── regional_daily_mv.sql         # 物化视图（手动刷新）
│   └── schema.yml           # 模型描述和数据测试定义
├── snapshots/               # 历史追踪（SCD Type 2）
│   ├── orders_snapshot.sql  # 订单状态变化历史（timestamp 策略）
│   └── customers_snapshot.sql  # 客户信息变化历史（check 策略）
├── tests/                   # 数据正确性验证（singular tests）
│   ├── assert_dim_customers_amounts.sql   # 验证客户聚合金额
│   └── assert_regional_revenue.sql       # 验证区域营收汇总
└── analyses/
    └── cleanup.sql          # 清理所有示例对象的 SQL 脚本
```

---

## 快速开始

### 第一步：安装

```bash
pip install dbt-clickzetta
```

### 第二步：配置连接

复制模板文件并填入你的实际连接信息：

```bash
cp profiles.yml.example profiles.yml
```

然后编辑 `profiles.yml`（此文件已加入 `.gitignore`，不会被提交到 git）：

```yaml
clickzetta_example:
  target: dev
  outputs:
    dev:
      type: clickzetta
      service: cn-shanghai-alicloud.api.clickzetta.com  # 见下方区域端点表
      instance: your_instance      # ClickZetta 实例 ID，如 f8866243
      workspace: your_workspace    # 工作空间名称，如 quick_start
      username: your_username
      password: your_password
      schema: example              # 模型写入的 schema，不存在会自动创建
      vcluster: default_ap         # 计算集群名称，如 default_ap
```

**各区域 service 端点：**

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

看到 `All checks passed!` 说明连接成功，可以继续。

### 第四步：加载测试数据

```bash
dbt seed --profiles-dir .
```

这一步会在 `example_raw` schema 下创建三张原始数据表：

| 表名 | 行数 | 说明 |
|---|---|---|
| `example_raw.raw_orders` | 10 | 订单数据，含金额、状态、区域、日期 |
| `example_raw.raw_customers` | 5 | 客户数据，含姓名、邮箱、城市 |
| `example_raw.raw_events` | 8 | 用户行为事件数据 |

### 第五步：运行模型

```bash
# 运行所有模型（不含动态表和物化视图）
dbt run --profiles-dir . --exclude advanced

# 运行动态表和物化视图
dbt run --profiles-dir . --select advanced

# 或一次运行全部
dbt run --profiles-dir .
```

运行完成后，`example` schema 下会创建以下对象：

| 对象 | 类型 | 说明 |
|---|---|---|
| `stg_orders` | view | 订单清洗视图 |
| `stg_customers` | view | 客户清洗视图 |
| `dim_customers` | table | 客户汇总：订单数、总金额 |
| `fct_orders_partitioned` | table（分区） | 按 dt 分区的订单宽表 |
| `fct_orders_incremental` | table（增量） | 增量订单表（merge 策略） |
| `daily_revenue` | table（增量） | 按日期区域汇总（insert_overwrite） |
| `regional_revenue_with_grants` | table | 区域营收，已授权给 workspace_analyst |
| `customer_stats_dynamic` | 动态表 | 每 5 分钟自动刷新的客户统计 |
| `regional_daily_mv` | 物化视图 | 区域日营收物化视图 |

### 第六步：验证数据正确性

```bash
dbt test --profiles-dir .
```

共 22 个测试，全部通过说明数据正确：

- **not_null / unique**：主键完整性检查
- **accepted_values**：status 字段只允许 completed / pending / cancelled
- **assert_dim_customers_amounts**：验证 C001 客户有 3 笔订单、总金额 563.00
- **assert_regional_revenue**：验证 east 区域 3 笔完成订单、营收 1014.00

### 第七步：运行 Snapshot

```bash
dbt snapshot --profiles-dir .
```

在 `example_snapshots` schema 下创建两张历史追踪表：

- `orders_snapshot`：追踪订单状态变化（timestamp 策略，按 updated_at 判断）
- `customers_snapshot`：追踪客户信息变化（check 策略，按 name/email/phone/city 判断）

查询历史版本：

```sql
-- 查看某订单的所有历史状态
SELECT order_id, status, dbt_valid_from, dbt_valid_to
FROM example_snapshots.orders_snapshot
WHERE order_id = '1001'
ORDER BY dbt_valid_from;
```

### Snapshot History Verification（可选）

`assert_snapshot_integrity` 测试验证 SCD Type 2 结构性约束，任何时候都能通过。

如果需要验证城市变更历史（C001: Shanghai→Hangzhou，C003: Guangzhou→Chengdu），需要手动执行两轮 seed+snapshot：

```bash
# 第一轮：加载原始城市数据（Shanghai/Guangzhou），建立 snapshot baseline
dbt seed --profiles-dir . --select v1/raw_customers --full-refresh
dbt snapshot --profiles-dir .

# 第二轮：加载变更后城市数据（Hangzhou/Chengdu），产生历史记录
dbt seed --profiles-dir . --select raw_customers --full-refresh
dbt snapshot --profiles-dir .

# 验证：customers_snapshot 应有 7 行（5 current + 2 historical）
```

`seeds/v1/raw_customers.csv` 是原始城市数据（默认 disabled），`seeds/raw_customers.csv` 是变更后数据（当前状态）。

---

## 功能详解

### 分区表

`fct_orders_partitioned` 按 `dt` 列分区，大数据量下按日期过滤查询效率更高：

```sql
{{ config(
    materialized='table',
    partition_by='dt'           -- 单列分区
    -- partition_by=['region', 'dt']  -- 多列分区
    -- clustered_by='customer_id',    -- 分桶（需同时指定 buckets）
    -- buckets=32
) }}
```

### 增量模型

**merge 策略**（`fct_orders_incremental`）：有主键、需要更新历史数据时使用。
每次运行只处理 `updated_at` 有变化的行，已有记录按 `order_id` 更新，新记录插入：

```sql
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='order_id'    -- 必填，用于匹配已有记录
) }}

select ...
{% if is_incremental() %}
-- 增量运行时只取上次之后更新的数据
where updated_at > (select max(updated_at) from {{ this }})
{% endif %}
```

**insert_overwrite 策略**（`daily_revenue`）：按分区整体覆盖，适合每天重算的汇总表：

```sql
{{ config(
    materialized='incremental',
    incremental_strategy='insert_overwrite',
    partition_by='dt'        -- 按 dt 分区覆盖，不影响其他分区
) }}
```

首次运行：`dbt run --profiles-dir .`（全量）
后续运行：`dbt run --profiles-dir .`（增量，只处理新数据）
强制全量：`dbt run --profiles-dir . --full-refresh`

### 动态表

`customer_stats_dynamic` 由 ClickZetta 自动按设定间隔刷新，无需外部调度：

```sql
{{ config(
    materialized='dynamic_table',
    refresh_interval='5 minutes',  -- 刷新间隔，支持 minutes / hours
    refresh_vc='default_ap'        -- 指定刷新使用的 vcluster
) }}
```

> **注意**：`dbt run` 时如果动态表已存在则跳过（no-op），由 ClickZetta 自动刷新。
> 使用 `dbt run --full-refresh` 强制重建。

需要立即刷新时，使用内置的 `refresh_dynamic_table` macro：

```bash
dbt run-operation refresh_dynamic_table --args '{model_name: customer_stats_dynamic}' --profiles-dir .
```

### 物化视图

`regional_daily_mv` 将查询结果持久化，查询速度快，但需要手动触发刷新：

```sql
{{ config(materialized='materialized_view') }}
```

刷新数据：
```sql
REFRESH MATERIALIZED VIEW example.regional_daily_mv;
```

### Grants（权限管理）

`regional_revenue_with_grants` 演示自动授权，每次 `dbt run` 后自动执行 GRANT/REVOKE：

```sql
{{ config(
    materialized='table',
    grants={
        'select': ['workspace_analyst'],     -- 授权给角色
        -- 'select': ['user:alice'],         -- 授权给用户（加 user: 前缀）
        -- 'insert': ['workspace_dev']       -- 支持多种权限类型
    }
) }}
```

> **注意**：将 `workspace_analyst` 替换为你环境中实际存在的角色名。
> grants 配置变更后重新运行，dbt 自动 REVOKE 旧权限、GRANT 新权限。

---

## 新功能详解

### Clone（零拷贝克隆）

`orders_clone` 演示零拷贝克隆，创建速度极快，不占用额外存储：

```bash
# 包含在默认 dbt run 里，直接运行即可
dbt run --profiles-dir . --select orders_clone
```

`orders_clone_timetravel` 演示 Time Travel 克隆（克隆某个历史时间点的数据）。**此模型默认 disabled**，因为它要求源表在目标时间点之前已存在至少 1 小时，无法在全量 `dbt run` 里自动通过。

单独运行步骤：

```bash
# 第一步：确保源表已存在
dbt run --profiles-dir . --select fct_orders_partitioned

# 第二步：等待至少 1 小时（让源表积累历史版本）

# 第三步：在 orders_clone_timetravel.sql 里把 enabled=false 改成 enabled=true

# 第四步：运行
dbt run --profiles-dir . --select orders_clone_timetravel
```

> Time Travel 克隆依赖 ClickZetta 的数据保留机制，目标时间点必须在 `data_retention_days` 范围内。

### Vector Index（向量索引）

`orders_vector_index` 演示向量索引，适合 AI/语义搜索场景：

```sql
{{ config(
    materialized='table',
    indexes=[
        {'type': 'vector', 'columns': ['embedding'],
         'distance_function': 'cosine_distance',  -- cosine_distance / l2_distance / dot_product
         'scalar_type': 'f32'}                    -- f32 / f16 / b1
    ]
) }}
```

支持的距离函数：`cosine_distance`（语义相似度）、`l2_distance`（图像特征）、`dot_product`（已归一化向量）、`jaccard_distance`、`hamming_distance`（二进制向量）。

### delete+insert 增量策略

`fct_orders_delete_insert` 演示 delete+insert 策略，先删除匹配行再插入，适合无主键的分区替换场景：

```sql
{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key='order_id'
) }}
```

与 `merge` 的区别：merge 是单条 MERGE INTO 语句；delete+insert 是先 DELETE 再 INSERT，在某些场景下性能更好，且不依赖 MERGE 语法。

### VCluster per-model 切换

为单个模型指定计算集群，实现大小模型资源隔离：

```sql
{{ config(
    materialized='table',
    vcluster='large_ap'   -- 该模型运行时切换到 large_ap 集群
) }}
```

### persist_docs 列注释

在 `schema.yml` 中为列添加 `description`，并在模型 config 中开启 `persist_docs`，dbt 会自动将注释写入 Lakehouse 表的列元数据：

```yaml
- name: dim_customers
  config:
    persist_docs:
      columns: true
  columns:
    - name: customer_id
      description: "客户唯一标识"
```

运行后可通过 `DESCRIBE TABLE example.dim_customers` 验证注释已写入。

### 运维宏（run-operation）

```bash
# 小文件合并（高频增量写入后使用）
dbt run-operation optimize_table --args '{relation: example.fct_orders_incremental}' --profiles-dir .

# 按分区合并（只合并近 7 天）
dbt run-operation optimize_table --args '{relation: example.daily_revenue, where: "dt >= current_date() - interval 7 days"}' --profiles-dir .

# 查看可恢复的已删除对象
dbt run-operation show_tables_history --args '{schema: example}' --profiles-dir .

# 恢复误删对象（支持普通表、动态表、物化视图、Table Stream）
dbt run-operation undrop --args '{relation: example.my_table}' --profiles-dir .

# 删除对象（type: table | view | dynamic_table | materialized_view | stream）
dbt run-operation drop_object --args '{relation: example.my_table, type: table}' --profiles-dir .
```

> **注意**：`undrop` 支持恢复普通表、动态表、物化视图、Table Stream，统一使用 `UNDROP TABLE` 语法。视图、外部表、Schema 不支持恢复。

---

## Cleanup — Required After Testing

**Always clean up Lakehouse objects after running the examples.** Leaving test objects
behind wastes storage and can interfere with future test runs.

```bash
# Run each statement in cleanup.sql individually (recommended — handles errors per statement)
source ../test.env   # or set CLICKZETTA_INSTANCE / CLICKZETTA_WORKSPACE manually
while IFS= read -r line; do
  line=$(echo "$line" | sed 's/--.*$//' | xargs)
  [ -z "$line" ] && continue
  cz-cli sql "$line" --instance <your_instance> --workspace <your_workspace> --write 2>/dev/null
done < analyses/cleanup.sql

# Alternative: run the whole file at once via ClickZetta console SQL editor
```

`cleanup.sql` removes:

| Schema | Objects |
|---|---|
| `example` | stg_orders, stg_customers, dim_customers, fct_orders_*, orders_clone, orders_vector_index, stream_changes, etc. |
| `example_snapshots` | orders_snapshot, customers_snapshot |
| `example_raw` | raw_orders, raw_customers, raw_events (seed data) |

---

## 常见问题

**Q: `dbt debug` 报 `Could not find adapter type clickzetta`**

```bash
pip install dbt-clickzetta
```

**Q: `dbt seed` 报类型错误（如 `unknown type: float8`）**

seeds/schema.yml 已指定所有列类型，确保使用 `--full-refresh` 重新创建：
```bash
dbt seed --profiles-dir . --full-refresh
```

**Q: 动态表运行后数据为空**

动态表创建后会立即触发一次刷新。如果数据仍为空，手动执行：
```sql
REFRESH DYNAMIC TABLE example.customer_stats_dynamic;
```

**Q: grants 报 `403 Forbidden` 或权限不足**

授权操作需要当前用户对目标表有 `GRANT OPTION`（即表的 owner）。
确认 profiles.yml 中的用户是表的创建者。

**Q: snapshot 报 schema 不存在**

snapshot 会自动创建 `example_snapshots` schema，确认用户有 `CREATE SCHEMA` 权限。

**Q: 写 `dbt test` 时 `HAVING` 报错 `having clause must be used with group by`**

ClickZetta 对 `HAVING` 有限制：**SELECT 中必须包含聚合函数才能使用无 GROUP BY 的 HAVING**。

```sql
-- ✅ 支持：SELECT 含聚合函数
select count(*) as cnt from my_table having count(*) != 10

-- ✅ 支持：SELECT 含聚合函数 + 别名
select count(*) as cnt from my_table having cnt != 10

-- ❌ 报错：SELECT 只有常量
select 'check_name' as name, 10 as expected from my_table having expected != 10

-- ❌ 报错：SELECT 只有普通列
select order_id from my_table having order_id is null
```

解决方法：用子查询 + `WHERE` 替代：

```sql
-- ✅ 正确写法
select check_name, actual, expected
from (
    select 'row_count' as check_name, count(*) as actual, 10 as expected
    from my_table
) t
where actual != expected
```

