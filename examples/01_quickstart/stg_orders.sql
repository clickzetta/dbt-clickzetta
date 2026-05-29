-- ephemeral：只在查询时展开，不产生实体表
{{ config(materialized='ephemeral') }}

select
    order_id,
    customer_id,
    amount,
    order_date
from {{ source('raw', 'orders') }}
where order_id is not null
