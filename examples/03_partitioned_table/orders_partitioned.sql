-- 按单列分区
{{ config(
    materialized='table',
    partition_by='dt'
) }}

select
    order_id,
    customer_id,
    amount,
    dt
from {{ source('raw', 'orders') }}
