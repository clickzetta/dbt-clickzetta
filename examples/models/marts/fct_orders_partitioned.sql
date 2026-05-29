-- 分区表：按 dt 分区，适合大数据量按日期查询
{{ config(
    materialized='table',
    partition_by='dt'
) }}

select
    o.order_id,
    o.customer_id,
    c.name       as customer_name,
    c.city,
    o.amount,
    o.status,
    o.region,
    o.dt,
    o.updated_at
from {{ ref('stg_orders') }} o
left join {{ ref('stg_customers') }} c using (customer_id)
