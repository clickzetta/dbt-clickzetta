-- 验证数值精度：decimal 聚合过程中不应有精度丢失

select check_name, actual, expected
from (
    -- 含小数的金额聚合精度：150.50 + 60.00 = 210.50
    select 'c002_sum_precision' as check_name,
           sum(amount) as actual, cast(210.50 as decimal(20,2)) as expected
    from {{ ref('stg_orders') }}
    where customer_id = 'C002'
) t where actual != expected

union all

select check_name, actual, expected
from (
    -- 全量汇总精度
    select 'total_amount_precision' as check_name,
           sum(amount) as actual, cast(2358.50 as decimal(20,2)) as expected
    from {{ ref('stg_orders') }}
) t where actual != expected

union all

-- 跨模型精度一致：dim_customers（table）vs customer_stats_dynamic（动态表）
select
    'dim_vs_dynamic_precision'  as check_name,
    dim_total                   as actual,
    dynamic_total               as expected
from (
    select
        (select sum(total_amount) from {{ ref('dim_customers') }})          as dim_total,
        (select sum(total_amount) from {{ ref('customer_stats_dynamic') }})  as dynamic_total
) t
where dim_total != dynamic_total

union all

-- 物化视图 vs 普通 table 的 revenue 精度一致
select
    'mv_vs_table_revenue_precision' as check_name,
    mv_total                        as actual,
    tbl_total                       as expected
from (
    select
        (select sum(revenue) from {{ ref('regional_daily_mv') }})  as mv_total,
        (select sum(revenue) from {{ ref('daily_revenue') }})       as tbl_total
) t
where mv_total != tbl_total

union all

-- 分区表 vs 增量表的 amount 精度一致
select
    'partitioned_vs_incremental_precision' as check_name,
    part_total                             as actual,
    incr_total                             as expected
from (
    select
        (select sum(amount) from {{ ref('fct_orders_partitioned') }})  as part_total,
        (select sum(amount) from {{ ref('fct_orders_incremental') }})   as incr_total
) t
where part_total != incr_total
