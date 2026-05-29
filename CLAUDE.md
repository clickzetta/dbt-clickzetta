# dbt-clickzetta 项目上下文

## 项目概述

ClickZetta Lakehouse 的 dbt adapter，基于 dbt-core 1.8，支持 Python 3.8+。
PyPI 包名：`dbt-clickzetta`，发布账号：`clickzetta`（非 `yunqiqiliang`）。

## 代码结构

```
dbt/adapters/clickzetta/     # Python adapter 核心
  impl.py                    # ClickZettaAdapter，含 standardize_grants_dict
  connections.py             # 连接管理
  relation.py                # Relation 类型定义（含 DynamicTable）
  column.py                  # 列类型映射

dbt/include/clickzetta/macros/
  adapters.sql               # grants macros（copy_grants/get_show_grant_sql/get_grant_sql/get_revoke_sql/call_dcl_statements）
  materializations/
    table.sql                # 含 apply_grants
    incremental/incremental.sql  # 含 apply_grants
    dynamic_table.sql
    materialized_view.sql    # DROP + CREATE（不支持 OR REPLACE）
    snapshot.sql
    view.sql                 # 委托给 create_or_replace_view()，已含 apply_grants

examples/                    # 完整可运行的 dbt 示例项目
  seeds/                     # 内置测试数据（11条订单，5个客户）
  models/staging/            # view
  models/marts/              # table / incremental
  models/advanced/           # dynamic_table / materialized_view
  snapshots/                 # SCD Type 2
  tests/                     # 38个数据正确性测试
  macros/check_grant.sql     # 权限验证宏
  analyses/cleanup.sql       # 清理所有示例对象
```

## ClickZetta SQL 已验证的行为

### HAVING
- 支持无 GROUP BY 的 HAVING，**但 SELECT 中必须包含聚合函数**
- SELECT 只有常量或普通列时报错：`having clause must be used with group by`
- 写 dbt test 时用子查询 + WHERE 替代：
  ```sql
  select check_name, actual, expected
  from (select 'x' as check_name, count(*) as actual, 10 as expected from t) t
  where actual != expected
  ```

### SHOW GRANTS
- `SHOW GRANTS ON TABLE/VIEW schema.table` 返回列：
  `granted_type, privilege, conditions, granted_on, object_name, granted_to, grantee_name, grantor_name, grant_option, granted_time`
- `granted_type`：`PRIVILEGE`（直接授权）或 `OBJECT_HIERARCHY`（继承），只处理 `PRIVILEGE`
- `privilege` 列值带对象类型后缀：`SELECT TABLE`、`SELECT VIEW`、`ALL` 等，取 `split()[0]` 规范化
- `grantee_name` 带 workspace 前缀：`quick_start.role_name`，取 `split('.')[-1]`
- GRANT 语法：`GRANT SELECT ON TABLE schema.t TO ROLE role_name`（必须带对象类型关键字和 ROLE/USER）
- **SHOW GRANTS 不能被 dbt generic test 的 `count(*) from (...)` 包装**，需用 `run_query` + `{% if execute %}` 的 singular test

### 动态表
- 支持 `ALTER DYNAMIC TABLE` 的 suspend/resume/rename column/set comment
- **不支持修改查询 SQL 或刷新间隔**，需 `--full-refresh` 重建
- 创建后立即触发一次 `REFRESH DYNAMIC TABLE`（adapter 已实现）
- `dbt run`（非 full-refresh）时已存在则 no-op

### 物化视图
- **不能直接 `CREATE OR REPLACE MATERIALIZED VIEW`**，需特定参数组合
- dbt 处理：先 DROP 再 CREATE，期间短暂不可查询
- 不会自动刷新，需手动 `REFRESH MATERIALIZED VIEW schema.view_name`

### 其他
- `SHOW GRANTS` 等大多数 SHOW 命令支持子查询包装（与 `SHOW CREATE TABLE` 不同）
- `float8` 类型不支持，seed 数据需在 schema.yml 中指定 `decimal(10,2)`
- 多条 DCL 语句不能批量执行，需逐条执行（`call_dcl_statements` 已实现）

## Grants 实现要点

- `copy_grants()` 返回 `False`：ClickZetta DROP+CREATE 不保留旧 grants
- `relation.type` 为 None 时 fallback 到 `TABLE`（incremental 场景）
- grantee 约定：角色直接写名称，用户加 `user:` 前缀（如 `user:alice`）
- `standardize_grants_dict` 过滤 `OBJECT_HIERARCHY`，只处理 `PRIVILEGE` 类型

## 增量模型注意事项

### merge 策略
- `updated_at > max(updated_at)` 过滤：如果源系统更新了旧记录但 `updated_at` 没有更新到最新时间戳，该更新会被漏掉
- 测试时需确保变更行的 `updated_at` 大于表中现有最大值

### insert_overwrite 策略
- **不要用 `current_date()` 做增量过滤**，历史数据测试时会导致增量完全不工作
- 正确做法：基于目标表已有数据的最大日期：
  ```sql
  and dt >= (select date_sub(max(dt), 3) from {{ this }})
  ```

## 测试规范

### 数据正确性测试（examples/tests/）
- `assert_stg_orders_baseline`：源数据行数、总金额、状态分布
- `assert_cross_model_consistency`：7个模型汇总金额互相一致
- `assert_numeric_precision`：decimal 聚合精度，跨 materialization 无漂移
- `assert_referential_integrity`：外键完整性
- `assert_incremental_no_duplicates`：merge 后无重复主键
- `assert_snapshot_integrity`：current 记录数、无重复、城市变更追踪
- `assert_grants_regional_revenue`：权限授予验证

### 当前测试数据状态（examples/seeds/）
- 11条订单（1003/1008 已从 pending→completed，新增 1011）
- 5个客户（C001: Shanghai→Hangzhou，C003: Guangzhou→Chengdu）
- 总金额：2538.50（全量），2478.50（completed）

## 已知武断判断（需持续验证）

1. `call_dcl_statements` 逐条执行——假设 ClickZetta 不支持批量 DCL，未直接验证
2. `grantee_name` 用 `split('.')[-1]` 去前缀——如果名字含 `.` 会截断错误（实际不常见）
3. snapshot `check` 策略——只验证了单字段变更，未验证多字段同时变更

## 开发环境

- venv：`.venv18/`（Python 3.12，shebang 路径已损坏，用 `.venv18/bin/python3 -c "..."` 调用 dbt）
- 测试连接：`aliyun_shanghai_prod` profile（instance: f8866243，workspace: quick_start）
- 测试 schema：`dbt_test`（adapter 测试），`example` / `example_raw` / `example_snapshots`（examples 项目）
- cz-cli：`~/.npm-global/bin/cz-cli`，写操作需加 `--write`
