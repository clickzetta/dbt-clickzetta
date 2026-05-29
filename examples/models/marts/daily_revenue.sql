-- 增量模型（insert_overwrite 策略）：按 dt 分区覆盖
{{ config(
    materialized='incremental',
    incremental_strategy='insert_overwrite',
    partition_by='dt'
) }}

select
    dt,
    region,
    count(order_id)  as order_count,
    sum(amount)      as revenue
from {{ ref('stg_orders') }}
where status = 'completed'

{% if is_incremental() %}
and dt >= date_sub(current_date(), 3)
{% endif %}

group by dt, region
