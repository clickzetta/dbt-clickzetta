-- 增量模型（insert_overwrite 策略）：按 dt 分区覆盖


select
    dt,
    region,
    count(order_id)  as order_count,
    sum(amount)      as revenue
from example.stg_orders
where status = 'completed'



group by dt, region