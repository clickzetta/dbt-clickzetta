-- 验证 daily_revenue 按区域汇总正确
-- east 区域 completed 订单：1001(299) + 1007(175) + 1009(540) = 1014.00，共 3 笔
-- 如果此查询返回任何行，说明数据有误
select region, order_count, revenue
from {{ ref('regional_revenue_with_grants') }}
where
    (region = 'east'  and (order_count != 3 or revenue != 1014.00))
    or (region = 'north' and (order_count != 1 or revenue != 420.00))
    or (region = 'south' and (order_count != 2 or revenue != 530.00))
    or (region = 'west'  and (order_count != 1 or revenue != 150.50))
