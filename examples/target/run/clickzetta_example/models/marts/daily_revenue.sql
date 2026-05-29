insert into example.daily_revenue (dt, region, order_count, revenue)
    select dt, region, order_count, revenue from example.daily_revenue__dbt_tmp