-- 带分区的动态表：按 dt 分区，每小时刷新
{{ config(
    materialized='dynamic_table',
    refresh_interval='1 hour',
    refresh_vc='default_ap',
    partition_by='dt'
) }}

select
    dt,
    region,
    sum(amount)  as daily_revenue,
    count(*)     as order_count
from {{ source('raw', 'orders') }}
group by dt, region
