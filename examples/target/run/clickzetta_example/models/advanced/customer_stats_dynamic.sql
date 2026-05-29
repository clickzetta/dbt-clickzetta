
        
  create dynamic table example.customer_stats_dynamic
    
    
  
    PROPERTIES('refresh_vc'='default_ap')
  
    
    
    
  
    refresh interval 5 minutes
  
    as
    -- 动态表：每 5 分钟自动刷新，无需外部调度
-- refresh_vc 替换为你环境中实际的 vcluster 名称


select
    customer_id,
    count(order_id)  as order_count,
    sum(amount)      as total_amount,
    max(updated_at)  as last_order_time
from example.stg_orders
group by customer_id
    