{% snapshot orders_snapshot %}

{{ config(
    target_schema='snapshots',
    unique_key='order_id',
    strategy='timestamp',
    updated_at='updated_at'
) }}

select
    order_id,
    customer_id,
    status,
    amount,
    updated_at
from {{ source('raw', 'orders') }}

{% endsnapshot %}
