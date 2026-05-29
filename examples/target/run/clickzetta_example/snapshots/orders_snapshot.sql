
      
  
    
      create table example_snapshots.orders_snapshot
      
      
      
      
      
      
      as
      
    

    select *,
        md5(coalesce(cast(order_id as string ), '')
         || '|' || coalesce(cast(updated_at as string ), '')
        ) as dbt_scd_id,
        updated_at as dbt_updated_at,
        updated_at as dbt_valid_from,
        
  
  coalesce(nullif(updated_at, updated_at), null)
  as dbt_valid_to
from (
        



-- 追踪订单状态变化历史（SCD Type 2）
-- 每次 dbt snapshot 运行时，变化的行会新增一条记录
-- dbt_valid_from / dbt_valid_to 自动维护
select
    order_id,
    customer_id,
    amount,
    status,
    updated_at
from example.stg_orders

    ) sbq



  
  