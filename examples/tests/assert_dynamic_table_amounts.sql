-- 验证动态表 customer_stats_dynamic 聚合数值正确（第二轮）
-- C001: 299+89+175+180 = 743.00，4笔
select customer_id, order_count, total_amount
from {{ ref('customer_stats_dynamic') }}
where
    (customer_id = 'C001' and (order_count != 4 or total_amount != 743.00))
    or (customer_id = 'C002' and (order_count != 2 or total_amount != 210.50))
    or (customer_id = 'C003' and (order_count != 2 or total_amount != 515.00))
    or (customer_id = 'C004' and (order_count != 2 or total_amount != 530.00))
    or (customer_id = 'C005' and (order_count != 1 or total_amount != 540.00))
