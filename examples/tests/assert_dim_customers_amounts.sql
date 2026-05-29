-- 验证 dim_customers 聚合数值正确（第二轮：1003/1008/1011 均为 completed）
-- C001: 1001(299) + 1003(89) + 1007(175) + 1011(180) = 743.00，4笔
-- C002: 1002(150.50) + 1005(60) = 210.50，2笔（1005 cancelled 也计入 total_amount）
-- C003: 1004(420) + 1008(95) = 515.00，2笔
select customer_id, order_count, total_amount
from {{ ref('dim_customers') }}
where
    (customer_id = 'C001' and (order_count != 4 or total_amount != 743.00))
    or (customer_id = 'C002' and (order_count != 2 or total_amount != 210.50))
    or (customer_id = 'C003' and (order_count != 2 or total_amount != 515.00))
    or (customer_id = 'C004' and (order_count != 2 or total_amount != 530.00))
    or (customer_id = 'C005' and (order_count != 1 or total_amount != 540.00))
