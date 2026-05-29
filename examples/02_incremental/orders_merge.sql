-- merge 策略：按 order_id 做 MERGE INTO，已有记录更新，新记录插入
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='order_id'
) }}

select
    order_id,
    customer_id,
    amount,
    status,
    updated_at
from {{ source('raw', 'orders') }}

{% if is_incremental() %}
-- 增量运行时只取上次运行之后更新的数据
where updated_at > (select max(updated_at) from {{ this }})
{% endif %}
