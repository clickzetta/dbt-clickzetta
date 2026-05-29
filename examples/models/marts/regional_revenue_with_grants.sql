-- grants 示例：授权给角色，运行后 workspace_analyst 可查询此表
-- 将 'workspace_analyst' 替换为你环境中实际存在的角色名
{{ config(
    materialized='table',
    grants={
        'select': ['workspace_analyst']
    }
) }}

select
    region,
    count(order_id)  as order_count,
    sum(amount)      as revenue
from {{ ref('stg_orders') }}
where status = 'completed'
group by region
