-- 验证物化视图 regional_daily_mv 数值正确
-- 只统计 completed 订单，east 区域共 3 笔：299+175+540=1014
-- 此视图按 dt+region 明细，east 区域分布在 3 天
select region, dt, order_count, revenue
from {{ ref('regional_daily_mv') }}
where
    (region = 'east'  and dt = '2024-01-01' and (order_count != 1 or revenue != 299.00))
    or (region = 'west'  and dt = '2024-01-01' and (order_count != 1 or revenue != 150.50))
    or (region = 'north' and dt = '2024-01-02' and (order_count != 1 or revenue != 420.00))
    or (region = 'south' and dt = '2024-01-03' and (order_count != 1 or revenue != 310.00))
    or (region = 'east'  and dt = '2024-01-04' and (order_count != 1 or revenue != 175.00))
    or (region = 'east'  and dt = '2024-01-05' and (order_count != 1 or revenue != 540.00))
    or (region = 'south' and dt = '2024-01-05' and (order_count != 1 or revenue != 220.00))
