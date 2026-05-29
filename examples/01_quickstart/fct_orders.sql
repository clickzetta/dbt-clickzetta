{{ config(materialized='table') }}

select
    o.order_id,
    o.order_date,
    o.amount,
    c.order_count,
    c.total_amount as customer_total
from {{ ref('stg_orders') }}  o
join {{ ref('dim_customers') }} c using (customer_id)
