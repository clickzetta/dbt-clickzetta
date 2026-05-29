{{ config(materialized='view') }}

select
    customer_id,
    count(order_id)  as order_count,
    sum(amount)      as total_amount
from {{ ref('stg_orders') }}
group by customer_id
