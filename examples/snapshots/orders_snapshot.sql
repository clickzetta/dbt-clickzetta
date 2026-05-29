{% snapshot orders_snapshot %}

{{ config(
    target_schema='example_snapshots',
    unique_key='order_id',
    strategy='timestamp',
    updated_at='updated_at'
) }}

-- 追踪订单状态变化历史（SCD Type 2）
-- 每次 dbt snapshot 运行时，变化的行会新增一条记录
-- dbt_valid_from / dbt_valid_to 自动维护
select
    order_id,
    customer_id,
    amount,
    status,
    updated_at
from {{ ref('stg_orders') }}

{% endsnapshot %}
