# dbt-clickzetta 项目上下文

## 项目概述

ClickZetta Lakehouse 的 dbt adapter，基于 dbt-core 1.8+，支持 Python 3.8+。
PyPI 包名：`dbt-clickzetta`，发布账号：`clickzetta`（非开发者个人账号 `yunqiqiliang`）。

## 开发环境

- venv：`.venv18/`（shebang 路径已损坏，调用 dbt 用 `.venv18/bin/python3 -c "import sys; sys.argv=[...]; from dbt.cli.main import cli; cli(standalone_mode=False)"`）
- 测试连接：profile 在 `examples/profiles.yml`（已 gitignore），从 `test.env` 生成（instance: f8866243，workspace: quick_start）
- cz-cli 写操作需加 `--write` 参数

## 发版流程

**发版前必须完整跑通所有三层测试（缺一不可）：**

```bash
# 1. Unit tests（无需连接）
.venv18/bin/python3 -m pytest tests/unit/
# 期望：92 passed

# 2. Examples 集成测试（需连接，必须按顺序跑全四步）
cd examples
.venv18/bin/python3 -c "import sys; sys.argv=['dbt','seed','--profiles-dir','.','--full-refresh']; from dbt.cli.main import cli; cli(standalone_mode=False)"
.venv18/bin/python3 -c "import sys; sys.argv=['dbt','run','--profiles-dir','.']; from dbt.cli.main import cli; cli(standalone_mode=False)"
.venv18/bin/python3 -c "import sys; sys.argv=['dbt','snapshot','--profiles-dir','.']; from dbt.cli.main import cli; cli(standalone_mode=False)"
.venv18/bin/python3 -c "import sys; sys.argv=['dbt','test','--profiles-dir','.']; from dbt.cli.main import cli; cli(standalone_mode=False)"
# 期望：seed 3/3，run 14/14，snapshot 2/2，test 49/49
cd ..
```

**测试完成后必须清理 Lakehouse 上的测试对象：**

```bash
cd examples
source ../test.env
while IFS= read -r line; do
  line=$(echo "$line" | sed 's/--.*$//' | xargs)
  [ -z "$line" ] && continue
  cz-cli sql "$line" --instance f8866243 --workspace quick_start --write 2>/dev/null
done < analyses/cleanup.sql
cd ..
```

测试全部通过且清理完毕后：

1. 修改 `dbt/adapters/clickzetta/__version__.py` 中的版本号（唯一版本号来源，setup.py 自动读取）
2. 提交并推送到 main：`git add ... && git commit && git push origin main`
3. 触发 GitHub Actions 发布：
   ```bash
   gh workflow run release.yml --repo clickzetta/dbt-clickzetta --field version=X.Y.Z
   ```
4. 查看发布进度：
   ```bash
   gh run list --repo clickzetta/dbt-clickzetta --workflow=release.yml --limit 3
   gh run watch <run_id> --repo clickzetta/dbt-clickzetta
   ```
5. 发布完成后自动：创建 git tag vX.Y.Z → 创建 GitHub Release → 发布到 PyPI

版本号规范：minor 升级（新功能）用 X.Y.0，patch 升级（bug fix）用 X.Y.Z。

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
