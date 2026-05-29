-- 增量模型（merge 策略）：按 order_id 做 MERGE INTO
-- 首次运行全量，后续只处理 updated_at 有变化的行
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
    region,
    dt,
    updated_at
from {{ ref('stg_orders') }}

{% if is_incremental() %}
where updated_at > (select max(updated_at) from {{ this }})
{% endif %}
