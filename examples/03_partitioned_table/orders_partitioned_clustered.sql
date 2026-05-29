-- 按多列分区 + 分桶
-- clustered_by 和 buckets 必须同时指定
{{ config(
    materialized='table',
    partition_by=['region', 'dt'],
    clustered_by='customer_id',
    buckets=32
) }}

select
    order_id,
    customer_id,
    region,
    amount,
    dt
from {{ source('raw', 'orders') }}
