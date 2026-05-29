-- Time Travel 克隆：CLONE source TIMESTAMP AS OF <expression>
-- 适用场景：数据误操作恢复、历史版本对比
--
-- 注意：
--   1. 时间点必须在数据保留周期（data_retention_days）内
--   2. 源表在该时间点必须已存在
--   3. 时间戳使用数据库服务器时区（通常为 UTC+8）
--
-- 常用时间表达式：
--   current_timestamp() - interval 1 hours   -- 1小时前
--   current_timestamp() - interval 1 days    -- 1天前
--   '2024-01-05 15:00:00'                    -- 固定时间点（本地时区）
--   date_sub(current_date(), 1)              -- 昨天
--
-- 使用前请将 at_timestamp 替换为实际有效的时间点
{{ config(
    materialized='clone',
    source='example.fct_orders_partitioned',
    at_timestamp="current_timestamp() - interval 1 minutes"
) }}
