-- 验证增量模型无重复：merge 策略保证 order_id 唯一
-- 如果有重复，说明 merge 逻辑有问题
select order_id, count(*) as cnt
from {{ ref('fct_orders_incremental') }}
group by order_id
having count(*) > 1
