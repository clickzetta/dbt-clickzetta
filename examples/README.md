# dbt-clickzetta 示例

每个子目录是一个独立的功能示例，包含可直接运行的模型文件和说明。

| 示例 | 说明 |
|---|---|
| [01_quickstart](./01_quickstart/) | 快速上手：table / view / ephemeral |
| [02_incremental](./02_incremental/) | 增量模型：merge / append / insert_overwrite |
| [03_partitioned_table](./03_partitioned_table/) | 分区表与分桶表 |
| [04_dynamic_table](./04_dynamic_table/) | 动态表（自动刷新） |
| [05_materialized_view](./05_materialized_view/) | 物化视图 |
| [06_snapshot](./06_snapshot/) | Snapshot（SCD Type 2） |
| [07_grants](./07_grants/) | 权限管理（grants） |
| [08_python_model](./08_python_model/) | Python 模型 |

## 前置条件

```bash
pip install dbt-clickzetta
```

在 `~/.dbt/profiles.yml` 中配置连接：

```yaml
my_project:
  target: dev
  outputs:
    dev:
      type: clickzetta
      service: cn-shanghai-alicloud.api.clickzetta.com  # 按实际环境填写
      instance: your_instance
      workspace: your_workspace
      username: your_username
      password: your_password
      schema: your_schema
      vcluster: default_ap
```

各区域 service 端点：

| 区域 | service |
|---|---|
| 阿里云上海 | `cn-shanghai-alicloud.api.clickzetta.com` |
| 腾讯云上海 | `ap-shanghai-tencentcloud.api.clickzetta.com` |
| 腾讯云北京 | `ap-beijing-tencentcloud.api.clickzetta.com` |
| 腾讯云广州 | `ap-guangzhou-tencentcloud.api.clickzetta.com` |
| AWS 宁夏 | `cn-north-1-aws.api.clickzetta.com` |
