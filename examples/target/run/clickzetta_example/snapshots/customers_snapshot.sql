
      
  
    
      create table example_snapshots.customers_snapshot
      
      
      
      
      
      
      as
      
    

    select *,
        md5(coalesce(cast(customer_id as string ), '')
         || '|' || coalesce(cast(
    current_timestamp()
 as string ), '')
        ) as dbt_scd_id,
        
    current_timestamp()
 as dbt_updated_at,
        
    current_timestamp()
 as dbt_valid_from,
        
  
  coalesce(nullif(
    current_timestamp()
, 
    current_timestamp()
), null)
  as dbt_valid_to
from (
        



-- 追踪客户信息变化历史（check 策略：指定列有变化就记录新版本）
select
    customer_id,
    name,
    email,
    phone,
    city,
    updated_at
from example.stg_customers

    ) sbq



  
  