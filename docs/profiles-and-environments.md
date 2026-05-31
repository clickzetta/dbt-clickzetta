# 多环境配置

[← 文档首页](README.md) | 相关：[materializations.md](materializations.md) · [dynamic-table.md](dynamic-table.md)

---

## ClickZetta 对象层级

理解多环境配置前，先了解 ClickZetta 的对象层级：

```
Instance（实例）
  └── Workspace（工作空间）   ← dbt 的 database
        ├── VCluster          ← dbt 的 vcluster，计算资源
        └── Schema            ← dbt 的 schema，按层或业务域划分
```

dbt 的三段式命名 `database.schema.table` 对应 ClickZetta 的 `workspace.schema.table`。

---

## 多环境策略

推荐方案：**同一 Workspace，用 schema 后缀区分环境**，而不是用不同 Workspace。

```
Workspace: my_workspace
  ├── staging_dev / marts_dev   ← dev 环境（开发调试）
  ├── staging     / marts       ← prod 环境（正式数据）
  └── ci_123      / ci_124      ← CI 环境（PR 测试，用完清理）
```

用不同 Workspace 隔离环境也可以，但会增加跨 Workspace 权限管理的复杂度，通常不推荐。

---

## profiles.yml 配置

```yaml
my_project:
  target: dev
  outputs:

    # 开发环境：schema 加 _dev 后缀，与生产完全隔离
    dev:
      type: clickzetta
      service: cn-shanghai-alicloud.api.clickzetta.com
      instance: your_instance
      workspace: your_workspace
      username: your_username
      password: your_password
      schema: dev          # 基础 schema，dbt_project.yml 里各层拼接为 staging_dev / marts_dev
      vcluster: default
      query_tag: "dbt_dev"

    # 生产环境：通过 CI/CD 触发，不在本地直接运行
    prod:
      type: clickzetta
      service: cn-shanghai-alicloud.api.clickzetta.com
      instance: your_instance
      workspace: your_workspace
      username: your_username
      password: your_password
      schema: default      # 各层直接用 staging / marts，不加后缀
      vcluster: default
      query_tag: "dbt_prod"

    # CI 环境（可选）：每个 PR 独立 schema，测试完自动清理
    ci:
      type: clickzetta
      service: cn-shanghai-alicloud.api.clickzetta.com
      instance: your_instance
      workspace: your_workspace
      username: your_username
      password: your_password
      schema: "ci_{{ var('pr_number', 'local') }}"
      vcluster: default
      query_tag: "dbt_ci"
```

切换环境：

```bash
dbt run                    # 使用 target: dev
dbt run --target prod      # 切换到生产环境
dbt run --target ci --vars '{"pr_number": "42"}'
```

---

## dbt_project.yml 分层配置

在 `dbt_project.yml` 里用 `+schema` 给每层指定 schema 名，dbt 会自动拼接 profiles.yml 里的基础 schema：

**dbt 推荐模式（staging → intermediate → marts）：**

```yaml
# dbt_project.yml
models:
  my_project:
    staging:
      +materialized: view
      +schema: staging       # dev → staging_dev，prod → staging
    intermediate:
      +materialized: ephemeral
      +schema: intermediate
    marts:
      +materialized: table
      +schema: marts         # dev → marts_dev，prod → marts
```

**大奖牌模式（Bronze → Silver → Gold）：**

```yaml
models:
  my_project:
    bronze:
      +materialized: table
      +schema: bronze
    silver:
      +materialized: dynamic_table
      +schema: silver
      +refresh_interval: "10 MINUTE"
      +refresh_vc: default
    gold:
      +materialized: table
      +schema: gold
```

**传统数仓分层（ODS → DWD → ADS）：**

```yaml
models:
  my_project:
    ods:
      +materialized: table
      +schema: ods
    dwd:
      +materialized: dynamic_table
      +schema: dwd
    dws:
      +materialized: dynamic_table
      +schema: dws
    ads:
      +materialized: table
      +schema: ads
```

三种模式在 ClickZetta 上都能跑，选适合你团队的即可。

---

## schema 拼接规则

dbt 默认的 schema 拼接规则：最终 schema = `{target.schema}_{+schema 配置}`。

| target.schema | +schema 配置 | 最终 schema |
|---|---|---|
| `dev` | `staging` | `dev_staging` |
| `dev` | `marts` | `dev_marts` |
| `default` | `staging` | `default_staging` |
| `default` | `marts` | `default_marts` |

如果希望 prod 环境直接用 `staging`（不加 `default_` 前缀），可以在 `macros/` 里覆盖 `generate_schema_name`：

```sql
-- macros/generate_schema_name.sql
{% macro generate_schema_name(custom_schema_name, node) %}
  {%- if custom_schema_name is none -%}
    {{ target.schema }}
  {%- elif target.name == 'prod' -%}
    {{ custom_schema_name | trim }}
  {%- else -%}
    {{ target.schema }}_{{ custom_schema_name | trim }}
  {%- endif -%}
{% endmacro %}
```

这样 dev 环境写 `dev_staging`，prod 环境直接写 `staging`。

---

## 各区域 service 端点

| 云厂商 | 区域 | service |
|---|---|---|
| 阿里云 | 华东2（上海） | `cn-shanghai-alicloud.api.clickzetta.com` |
| 腾讯云 | 华东（上海） | `ap-shanghai-tencentcloud.api.clickzetta.com` |
| 腾讯云 | 华北（北京） | `ap-beijing-tencentcloud.api.clickzetta.com` |
| 腾讯云 | 华南（广州） | `ap-guangzhou-tencentcloud.api.clickzetta.com` |
| AWS | 华北（宁夏） | `cn-north-1-aws.api.clickzetta.com` |
