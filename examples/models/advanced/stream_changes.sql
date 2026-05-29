-- Table Stream 消费示例：读取 orders_stream 的变更数据
-- Stream 返回额外列：
--   __change_type: INSERT / UPDATE_BEFORE / UPDATE_AFTER / DELETE
--   __commit_version: 提交版本号
--   __commit_timestamp: 提交时间戳
--
-- 注意：SELECT 不会推进 stream 的 offset，只有 DML（INSERT/MERGE 等）才会推进
-- 典型用法：将 stream 数据 MERGE INTO 目标表，然后 offset 自动推进
{{ config(materialized='view') }}

select
    __change_type,
    __commit_timestamp,
    order_id,
    customer_id,
    amount,
    status,
    region,
    dt
from {{ source('example_streams', 'orders_stream') }}
