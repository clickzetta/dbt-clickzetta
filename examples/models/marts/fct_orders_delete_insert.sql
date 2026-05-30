{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key='order_id',
    vcluster='default'
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
