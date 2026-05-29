-- 增量模型（insert_overwrite 策略）：按 dt 分区覆盖
-- 增量时只重算目标表中已有的最近 N 天分区，避免全量扫描
-- 注意：过滤条件基于目标表已有数据的最大日期，而非 current_date()
--       这样在历史数据回测时也能正确工作
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
-- 只重算目标表中最近 3 天的分区
and dt >= (select date_sub(max(dt), 3) from {{ this }})
{% endif %}

group by dt, region
