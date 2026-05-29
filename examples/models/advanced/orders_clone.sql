-- 零拷贝克隆：CREATE TABLE t CLONE source
-- 适用场景：CI/CD 环境隔离、快速创建测试副本
-- 特点：零拷贝，不占用额外存储，创建速度极快
{{ config(
    materialized='clone',
    source='example.fct_orders_partitioned'
) }}
