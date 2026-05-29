-- 同时授权给多个角色和用户，并授予多种权限
{{ config(
    materialized='table',
    grants={
        'select': ['workspace_analyst', 'workspace_dev', 'user:alice'],
        'insert': ['workspace_dev']
    }
) }}

select
    customer_id,
    name,
    email
from {{ source('raw', 'customers') }}
