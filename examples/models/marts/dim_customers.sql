-- 基础 table materialization
{{ config(materialized='table') }}

select
    c.customer_id,
    c.name,
    c.city,
    count(o.order_id)              as order_count,
    sum(o.amount)                  as total_amount,
    max(o.updated_at)              as last_order_time
from {{ ref('stg_customers') }} c
left join {{ ref('stg_orders') }} o using (customer_id)
group by c.customer_id, c.name, c.city
