
  
    
      create table example.regional_revenue_with_grants
      
      
      
      
      
      
      as
      -- grants 示例：授权给角色，运行后 workspace_analyst 可查询此表
-- 将 'workspace_analyst' 替换为你环境中实际存在的角色名


select
    region,
    count(order_id)  as order_count,
    sum(amount)      as revenue
from example.stg_orders
where status = 'completed'
group by region
  