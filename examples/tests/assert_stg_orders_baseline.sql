-- 验证源数据总量和各状态分布（11条订单，1003/1008已更新为completed，新增1011）
select check_name, actual, expected
from (
    select 'row_count' as check_name, count(*) as actual, 11 as expected
    from {{ ref('stg_orders') }}
) t where actual != expected

union all

select check_name, actual, expected
from (
    select 'total_amount' as check_name,
           sum(amount) as actual, cast(2538.50 as decimal(20,2)) as expected
    from {{ ref('stg_orders') }}
) t where actual != expected

union all

select check_name, actual, expected
from (
    select 'completed_count' as check_name,
           count(*) as actual, 10 as expected
    from {{ ref('stg_orders') }}
    where status = 'completed'
) t where actual != expected

union all

select check_name, actual, expected
from (
    select 'distinct_customers' as check_name,
           count(distinct customer_id) as actual, 5 as expected
    from {{ ref('stg_orders') }}
) t where actual != expected
