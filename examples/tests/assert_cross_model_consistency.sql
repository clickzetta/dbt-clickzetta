-- 验证跨模型汇总一致性：
-- 所有包含全量订单的模型，总金额都应该等于源数据 2358.50
-- 所有只统计 completed 的模型，总金额都应该等于 2114.50

select check_name, actual, expected
from (
    select 'fct_orders_incremental total_amount' as check_name,
           sum(amount) as actual, cast(2358.50 as decimal(20,2)) as expected
    from {{ ref('fct_orders_incremental') }}
) t where actual != expected

union all

select check_name, actual, expected
from (
    select 'fct_orders_partitioned total_amount' as check_name,
           sum(amount) as actual, cast(2358.50 as decimal(20,2)) as expected
    from {{ ref('fct_orders_partitioned') }}
) t where actual != expected

union all

select check_name, actual, expected
from (
    select 'dim_customers total_amount' as check_name,
           sum(total_amount) as actual, cast(2358.50 as decimal(20,2)) as expected
    from {{ ref('dim_customers') }}
) t where actual != expected

union all

select check_name, actual, expected
from (
    select 'customer_stats_dynamic total_amount' as check_name,
           sum(total_amount) as actual, cast(2358.50 as decimal(20,2)) as expected
    from {{ ref('customer_stats_dynamic') }}
) t where actual != expected

union all

select check_name, actual, expected
from (
    select 'daily_revenue completed_amount' as check_name,
           sum(revenue) as actual, cast(2114.50 as decimal(20,2)) as expected
    from {{ ref('daily_revenue') }}
) t where actual != expected

union all

select check_name, actual, expected
from (
    select 'regional_revenue_with_grants completed_amount' as check_name,
           sum(revenue) as actual, cast(2114.50 as decimal(20,2)) as expected
    from {{ ref('regional_revenue_with_grants') }}
) t where actual != expected

union all

select check_name, actual, expected
from (
    select 'regional_daily_mv completed_amount' as check_name,
           sum(revenue) as actual, cast(2114.50 as decimal(20,2)) as expected
    from {{ ref('regional_daily_mv') }}
) t where actual != expected
