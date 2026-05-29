-- insert_overwrite 策略：按分区覆盖，每次运行覆盖当天分区
-- 需要配合 partition_by 使用，ClickZetta 会自动开启 DYNAMIC 分区覆盖模式
{{ config(
    materialized='incremental',
    incremental_strategy='insert_overwrite',
    partition_by=['dt']
) }}

select
    order_id,
    customer_id,
    amount,
    dt   -- 分区列，格式如 '2024-01-01'
from {{ source('raw', 'orders') }}

{% if is_incremental() %}
-- 只处理最近 3 天的数据，覆盖对应分区
where dt >= date_sub(current_date(), 3)
{% endif %}
