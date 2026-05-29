-- 验证 dim_customers 聚合数据正确性
-- C001 有 3 笔订单，总金额 563.00（299+89+175）
-- 如果此查询返回任何行，说明数据有误（dbt test 期望返回 0 行）
select
    customer_id,
    order_count,
    total_amount
from {{ ref('dim_customers') }}
where
    (customer_id = 'C001' and (order_count != 3 or total_amount != 563.00))
    or (customer_id = 'C002' and (order_count != 2 or total_amount != 210.50))
    or (customer_id = 'C005' and (order_count != 1 or total_amount != 540.00))
