-- Zero-copy clone: CREATE TABLE t CLONE source
-- Use case: CI/CD environment isolation, fast test copy creation
-- Feature: zero-copy, no extra storage, extremely fast creation
{{ config(
    materialized='clone',
    source=target.database ~ '.' ~ target.schema ~ '.fct_orders_partitioned'
) }}
