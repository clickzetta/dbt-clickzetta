-- 授权给角色：workspace_analyst 可以查询此表
{{ config(
    materialized='table',
    grants={
        'select': ['workspace_analyst']
    }
) }}

select
    order_id,
    customer_id,
    amount,
    dt
from {{ source('raw', 'orders') }}
