-- 动态表：每 5 分钟自动刷新，无需外部调度
-- refresh_vc 替换为你环境中实际的 vcluster 名称
{{ config(
    materialized='dynamic_table',
    refresh_interval='5 MINUTE',
    refresh_vc='default'
) }}

select
    customer_id,
    count(order_id)  as order_count,
    sum(amount)      as total_amount,
    max(updated_at)  as last_order_time
from {{ ref('stg_orders') }}
group by customer_id
