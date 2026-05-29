-- Time Travel clone: CLONE source AT (timestamp => <expression>)
-- Use case: data recovery, historical version comparison
--
-- PREREQUISITE: The source table must have existed for at least 1 hour before
-- running this model. Run `dbt run --select fct_orders_partitioned` first,
-- wait 1 hour, then run this model separately:
--   dbt run --select orders_clone_timetravel
--
-- This model is disabled by default (enabled: false) to prevent it from
-- failing in a fresh environment where the source table has no history yet.
{{ config(
    materialized='clone',
    source=target.database ~ '.' ~ target.schema ~ '.fct_orders_partitioned',
    at_timestamp="current_timestamp() - interval 1 hours",
    enabled=false
) }}
