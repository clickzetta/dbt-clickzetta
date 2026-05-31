# Python Models

[← 文档首页](README.md) | 相关：[materializations.md](materializations.md)

dbt-clickzetta supports Python models via ZettaPark — ClickZetta's DataFrame API. Python models run in the current Python environment (local or Studio), not in a remote Spark/Snowpark cluster.

## Installation

```bash
pip install "dbt-clickzetta[python]"
```

Requires Python 3.10+ (3.12 recommended).

## Basic usage

A Python model is a `.py` file in your `models/` directory with a `model(dbt, session)` function:

```python
def model(dbt, session):
    dbt.config(materialized="table")

    orders = dbt.ref("stg_orders").to_pandas()
    orders["tax"] = orders["amount"] * 0.1
    return session.createDataFrame(orders)
```

The function must return a ZettaPark DataFrame. dbt-clickzetta writes it to the target relation automatically.

## dbt object

The `dbt` argument provides the same interfaces as in SQL models:

```python
def model(dbt, session):
    dbt.config(materialized="table")

    # ref() — reference another dbt model
    orders = dbt.ref("stg_orders")

    # ref() with package name
    customers = dbt.ref("my_package", "stg_customers")

    # source() — reference a source
    raw = dbt.source("raw", "orders")

    # this — the target relation
    target = dbt.this()

    return orders
```

## Auto-installing packages

Declare packages in `dbt.config()` and they are installed automatically before the model runs:

```python
def model(dbt, session):
    dbt.config(
        materialized="table",
        packages=["scikit-learn", "pandas", "numpy"]
    )

    import pandas as pd
    from sklearn.cluster import KMeans

    df = dbt.ref("customer_features").to_pandas()
    df.columns = df.columns.str.upper()  # ZettaPark returns lowercase column names

    kmeans = KMeans(n_clusters=5, random_state=42)
    df["cluster"] = kmeans.fit_predict(df[["recency", "frequency", "monetary"]])

    return session.createDataFrame(df)
```

> **Note:** ZettaPark's `to_pandas()` returns **lowercase** column names. If your downstream SQL uses uppercase column names, normalize with `df.columns = df.columns.str.upper()`.

## write_mode

By default the result DataFrame overwrites the target table. To append instead:

```python
def model(dbt, session):
    dbt.config(materialized="table", write_mode="append")
    ...
```

## Studio environment

In ClickZetta Studio, the session is created automatically from the active Lakehouse engine — no credentials needed in the model code. The same model runs in both local and Studio environments without changes.

## Limitations

- Python models support `table` and `incremental` materializations only.
- `incremental` Python models support the same strategies as SQL models (merge, append, insert_overwrite, delete+insert). The Python model output is written to a temp table first, then the configured strategy is applied against the target — same execution path as SQL incremental models.
- Snowpark stored procedures (`session.sproc.register`) are not supported — use standard Python functions instead.
- ZettaPark returns lowercase column names from `to_pandas()`. Normalize if needed.
