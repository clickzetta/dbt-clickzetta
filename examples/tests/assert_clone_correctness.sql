-- 验证克隆表与源表数据一致
select check_name, actual, expected
from (
    select 'orders_clone row_count' as check_name,
           count(*) as actual, 11 as expected
    from {{ ref('orders_clone') }}
) t where actual != expected

union all

select check_name, actual, expected
from (
    select 'orders_clone total_amount' as check_name,
           sum(amount) as actual, cast(2538.50 as decimal(20,2)) as expected
    from {{ ref('orders_clone') }}
) t where actual != expected

union all

select check_name, actual, expected
from (
    select 'orders_clone_timetravel row_count' as check_name,
           count(*) as actual, 11 as expected
    from {{ ref('orders_clone_timetravel') }}
) t where actual != expected

union all

-- 克隆表与源表数据完全一致
select
    'clone_vs_source_consistency' as check_name,
    clone_total as actual,
    source_total as expected
from (
    select
        (select sum(amount) from {{ ref('orders_clone') }})             as clone_total,
        (select sum(amount) from {{ ref('fct_orders_partitioned') }})   as source_total
) t
where clone_total != source_total
