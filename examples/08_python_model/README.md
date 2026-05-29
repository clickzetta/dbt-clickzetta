# 08 Python 模型

ClickZetta 支持用 Python 编写 dbt 模型，底层通过 ZettaPark（兼容 Snowpark API）执行。

## 运行

```bash
dbt run
```

## 注意事项

- Python 模型函数名必须是 `model`，接收 `dbt` 和 `session` 两个参数
- 返回值必须是 DataFrame
- 支持 `table` 和 `incremental` materialization
- 可以调用 `dbt.ref()` 和 `dbt.source()` 引用其他模型
