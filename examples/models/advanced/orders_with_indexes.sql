-- 演示索引自动创建：建表后自动创建 Bloomfilter 和倒排索引
-- Bloomfilter 索引适合等值查询（WHERE order_id = 'xxx'）
-- 倒排索引适合全文搜索（match_all, match_any 等函数）
{{ config(
    materialized='table',
    indexes=[
        {'type': 'bloomfilter', 'columns': ['order_id']},
        {'type': 'bloomfilter', 'columns': ['customer_id']},
        {'type': 'inverted',    'columns': ['status']}
    ]
) }}

select
    order_id,
    customer_id,
    amount,
    status,
    region,
    dt
from {{ ref('stg_orders') }}
