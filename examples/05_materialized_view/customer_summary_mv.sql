{{ config(materialized='materialized_view') }}

select
    customer_id,
    count(order_id)  as order_count,
    sum(amount)      as total_amount
from {{ source('raw', 'orders') }}
group by customer_id
