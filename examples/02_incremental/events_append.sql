-- append 策略：只追加新行，不更新已有数据，适合日志、埋点等不可变数据
{{ config(
    materialized='incremental',
    incremental_strategy='append'
) }}

select
    event_id,
    user_id,
    event_type,
    event_time,
    properties
from {{ source('raw', 'events') }}

{% if is_incremental() %}
where event_time > (select max(event_time) from {{ this }})
{% endif %}
