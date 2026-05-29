{% snapshot customers_snapshot %}

{{ config(
    target_schema='example_snapshots',
    unique_key='customer_id',
    strategy='check',
    check_cols=['name', 'email', 'phone', 'city']
) }}

-- 追踪客户信息变化历史（check 策略：指定列有变化就记录新版本）
select
    customer_id,
    name,
    email,
    phone,
    city,
    updated_at
from {{ ref('stg_customers') }}

{% endsnapshot %}
