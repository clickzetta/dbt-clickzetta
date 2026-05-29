-- 验证物化视图 regional_daily_mv 数值正确（第二轮）
-- 新增行：2024-01-02 east(1003 completed,89)，2024-01-04 north(1008 completed,95)
-- 变更行：2024-01-05 east 从 1笔/540 变为 2笔/720（新增1011）
select region, dt, order_count, revenue
from {{ ref('regional_daily_mv') }}
where
    (region = 'east'  and dt = '2024-01-01' and (order_count != 1 or revenue != 299.00))
    or (region = 'west'  and dt = '2024-01-01' and (order_count != 1 or revenue != 150.50))
    or (region = 'east'  and dt = '2024-01-02' and (order_count != 1 or revenue != 89.00))
    or (region = 'north' and dt = '2024-01-02' and (order_count != 1 or revenue != 420.00))
    or (region = 'south' and dt = '2024-01-03' and (order_count != 1 or revenue != 310.00))
    or (region = 'east'  and dt = '2024-01-04' and (order_count != 1 or revenue != 175.00))
    or (region = 'north' and dt = '2024-01-04' and (order_count != 1 or revenue != 95.00))
    or (region = 'east'  and dt = '2024-01-05' and (order_count != 2 or revenue != 720.00))
    or (region = 'south' and dt = '2024-01-05' and (order_count != 1 or revenue != 220.00))
