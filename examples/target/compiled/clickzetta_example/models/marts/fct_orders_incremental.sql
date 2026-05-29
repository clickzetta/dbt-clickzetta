-- 增量模型（merge 策略）：按 order_id 做 MERGE INTO
-- 首次运行全量，后续只处理 updated_at 有变化的行


select
    order_id,
    customer_id,
    amount,
    status,
    region,
    dt,
    updated_at
from example.stg_orders

