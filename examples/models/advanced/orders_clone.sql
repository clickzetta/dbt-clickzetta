-- Zero-copy clone: CREATE TABLE t CLONE source
-- Use case: CI/CD environment isolation, fast test copy creation
-- Feature: zero-copy, no extra storage, extremely fast creation
--
-- NOTE: 'source' is a plain string — dbt cannot infer the dependency automatically.
-- The depends_on comment below ensures fct_orders_partitioned is built first.
{{ config(
    materialized='clone',
    source=target.database ~ '.' ~ target.schema ~ '.fct_orders_partitioned'
) }}
-- depends_on: {{ ref('fct_orders_partitioned') }}
