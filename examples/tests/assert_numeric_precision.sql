-- 验证数值精度（第二轮）
select check_name, actual, expected
from (
    -- C001 四笔订单：299+89+175+180 = 743.00
    select 'c001_sum_precision' as check_name,
           sum(amount) as actual, cast(743.00 as decimal(20,2)) as expected
    from {{ ref('stg_orders') }}
    where customer_id = 'C001'
) t where actual != expected

union all

select check_name, actual, expected
from (
    select 'total_amount_precision' as check_name,
           sum(amount) as actual, cast(2538.50 as decimal(20,2)) as expected
    from {{ ref('stg_orders') }}
) t where actual != expected

union all

select
    'dim_vs_dynamic_precision' as check_name,
    dim_total as actual,
    dynamic_total as expected
from (
    select
        (select sum(total_amount) from {{ ref('dim_customers') }})         as dim_total,
        (select sum(total_amount) from {{ ref('customer_stats_dynamic') }}) as dynamic_total
) t
where dim_total != dynamic_total

union all

select
    'mv_vs_table_revenue_precision' as check_name,
    mv_total as actual,
    tbl_total as expected
from (
    select
        (select sum(revenue) from {{ ref('regional_daily_mv') }})  as mv_total,
        (select sum(revenue) from {{ ref('daily_revenue') }})       as tbl_total
) t
where mv_total != tbl_total

union all

select
    'partitioned_vs_incremental_precision' as check_name,
    part_total as actual,
    incr_total as expected
from (
    select
        (select sum(amount) from {{ ref('fct_orders_partitioned') }}) as part_total,
        (select sum(amount) from {{ ref('fct_orders_incremental') }})  as incr_total
) t
where part_total != incr_total
