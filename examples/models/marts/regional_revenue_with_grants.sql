-- Grants example: grant SELECT to a role after each run.
-- Override the role name via dbt variable:
--   dbt run --vars '{"grant_role": "my_role"}' --select regional_revenue_with_grants
{{ config(
    materialized='table',
    grants={
        'select': [var('grant_role', 'workspace_analyst')]
    }
) }}

select
    region,
    count(order_id)  as order_count,
    sum(amount)      as revenue
from {{ ref('stg_orders') }}
where status = 'completed'
group by region
