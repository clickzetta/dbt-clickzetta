-- Time Travel clone: CLONE source AT (timestamp => <expression>)
-- Use case: data recovery, historical version comparison
--
-- PREREQUISITE: The source table must have existed for at least 1 hour before
-- running this model. Run fct_orders_partitioned first, wait 1 hour, then:
--   dbt run --profiles-dir . --select orders_clone_timetravel
--
-- This model is disabled by default. To run it:
--   1. Set enabled=true below (or pass --vars '{"enable_timetravel": true}')
--   2. Ensure fct_orders_partitioned has existed for >= 1 hour
{{ config(
    materialized='clone',
    source=target.database ~ '.' ~ target.schema ~ '.fct_orders_partitioned',
    at_timestamp="current_timestamp() - interval 1 hours",
    enabled=false
) }}
