-- 验证 regional_revenue_with_grants 区域营收（第二轮：1003/1008 completed，新增1011）
-- east:  1001(299)+1003(89)+1007(175)+1009(540)+1011(180) = 1283.00，5笔
-- north: 1004(420)+1008(95) = 515.00，2笔
-- south: 1006(310)+1010(220) = 530.00，2笔
-- west:  1002(150.50)，1笔（1005 cancelled 不计入）
select region, order_count, revenue
from {{ ref('regional_revenue_with_grants') }}
where
    (region = 'east'  and (order_count != 5 or revenue != 1283.00))
    or (region = 'north' and (order_count != 2 or revenue != 515.00))
    or (region = 'south' and (order_count != 2 or revenue != 530.00))
    or (region = 'west'  and (order_count != 1 or revenue != 150.50))
