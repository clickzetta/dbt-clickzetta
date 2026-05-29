import models.config as config

def model(dbt, session):
    dbt.config(materialized="table")

    # 引用其他 dbt 模型
    orders_df = dbt.ref("stg_orders")

    # 用 DataFrame API 做转换
    from zettapark.functions import col, sum as _sum, count

    result = (
        orders_df
        .groupBy("customer_id")
        .agg(
            count("order_id").alias("order_count"),
            _sum("amount").alias("total_amount"),
        )
        .filter(col("total_amount") > 0)
    )

    return result
