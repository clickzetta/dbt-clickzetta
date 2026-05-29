-- 清理示例项目创建的所有对象
-- 在 ClickZetta 控制台或 CLI 中执行此文件
-- 用法：cz-cli sql "$(cat analyses/cleanup.sql)" --profile your_profile --write

-- 删除模型
DROP VIEW  IF EXISTS example.stg_orders;
DROP VIEW  IF EXISTS example.stg_customers;
DROP TABLE IF EXISTS example.dim_customers;
DROP TABLE IF EXISTS example.fct_orders_partitioned;
DROP TABLE IF EXISTS example.fct_orders_incremental;
DROP TABLE IF EXISTS example.daily_revenue;
DROP TABLE IF EXISTS example.regional_revenue_with_grants;

-- 删除动态表和物化视图
DROP DYNAMIC TABLE    IF EXISTS example.customer_stats_dynamic;
DROP MATERIALIZED VIEW IF EXISTS example.regional_daily_mv;

-- 删除 snapshot 表
DROP TABLE IF EXISTS example_snapshots.orders_snapshot;
DROP TABLE IF EXISTS example_snapshots.customers_snapshot;

-- 删除 seed 原始数据
DROP TABLE IF EXISTS example_raw.raw_orders;
DROP TABLE IF EXISTS example_raw.raw_customers;
DROP TABLE IF EXISTS example_raw.raw_events;

-- 删除 schema（仅当 schema 下已无其他对象时才会成功）
DROP SCHEMA IF EXISTS example;
DROP SCHEMA IF EXISTS example_snapshots;
DROP SCHEMA IF EXISTS example_raw;
