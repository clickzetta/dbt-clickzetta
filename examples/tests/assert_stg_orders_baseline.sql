-- 验证源数据总量和各状态分布
-- 这是所有下游模型的基准：10 条订单，总金额 2358.50
select 'row_count' as check_name, count(*) as actual, 10 as expected
from {{ ref('stg_orders') }}
having count(*) != 10

union all

select 'total_amount', sum(amount), 2358.50
from {{ ref('stg_orders') }}
having sum(amount) != 2358.50

union all

select 'completed_count', count(*), 7
from {{ ref('stg_orders') }}
where status = 'completed'
having count(*) != 7

union all

select 'distinct_customers', count(distinct customer_id), 5
from {{ ref('stg_orders') }}
having count(distinct customer_id) != 5
