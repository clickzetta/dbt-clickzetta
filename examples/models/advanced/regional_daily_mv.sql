-- 物化视图：手动刷新，适合对查询性能要求高但数据实时性要求不高的场景
{{ config(materialized='materialized_view') }}

select
    region,
    dt,
    count(order_id)  as order_count,
    sum(amount)      as revenue
from {{ ref('stg_orders') }}
where status = 'completed'
group by region, dt
