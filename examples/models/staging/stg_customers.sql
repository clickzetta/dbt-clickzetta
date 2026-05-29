{{ config(materialized='view') }}

select
    customer_id,
    name,
    email,
    phone,
    city,
    updated_at
from {{ ref('raw_customers') }}
