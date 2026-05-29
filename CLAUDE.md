# dbt-clickzetta 项目上下文

## 项目概述

ClickZetta Lakehouse 的 dbt adapter，基于 dbt-core 1.8+，支持 Python 3.8+。
PyPI 包名：`dbt-clickzetta`，发布账号：`clickzetta`（非开发者个人账号 `yunqiqiliang`）。

## 开发环境

- venv：`.venv18/`（shebang 路径已损坏，调用 dbt 用 `.venv18/bin/python3 -c "import sys; sys.argv=[...]; from dbt.cli.main import cli; cli(standalone_mode=False)"`）
- 测试连接：profile `aliyun_shanghai_prod`（instance: f8866243，workspace: quick_start）
- cz-cli 写操作需加 `--write` 参数

## 已知武断判断（需持续验证）

1. `call_dcl_statements` 逐条执行 DCL——假设 ClickZetta 不支持批量执行，未直接验证
2. `grantee_name` 用 `split('.')[-1]` 去 workspace 前缀——名字含 `.` 时会截断错误（实际不常见）
3. snapshot `check` 策略——只验证了单字段变更，未验证多字段同时变更

## examples 项目当前数据状态

seeds 已做过数据变更验证（第二轮），当前状态：
- 11条订单（1003/1008 从 pending→completed，新增 1011）
- 5个客户（C001: Shanghai→Hangzhou，C003: Guangzhou→Chengdu）
- 期望总金额：2538.50（全量），2478.50（completed）
- Lakehouse 上的测试对象已全部清理
