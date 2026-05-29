create materialized view example.regional_daily_mv
    as
    -- 物化视图：手动刷新，适合对查询性能要求高但数据实时性要求不高的场景


select
    region,
    dt,
    count(order_id)  as order_count,
    sum(amount)      as revenue
from example.stg_orders
where status = 'completed'
group by region, dt