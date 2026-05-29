{% snapshot customers_snapshot %}

{{ config(
    target_schema='snapshots',
    unique_key='customer_id',
    strategy='check',
    check_cols=['name', 'email', 'phone', 'address']
) }}

select
    customer_id,
    name,
    email,
    phone,
    address
from {{ source('raw', 'customers') }}

{% endsnapshot %}
