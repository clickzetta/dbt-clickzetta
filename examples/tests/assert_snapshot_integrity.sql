-- Structural snapshot integrity test — passes on any valid snapshot state.
-- Verifies SCD Type 2 invariants regardless of how many history records exist.
--
-- For history-specific checks (C001/C003 city change verification), see:
-- examples/README.md — "Snapshot History Verification" section.

-- Each customer_id must have exactly one current record (dbt_valid_to IS NULL)
select check_name, actual, expected
from (
    select 'duplicate_current_records' as check_name,
           count(*) as actual, 0 as expected
    from (
        select customer_id, count(*) as cnt
        from {{ ref('customers_snapshot') }}
        where dbt_valid_to is null
        group by customer_id
        having count(*) > 1
    ) t
) t2 where actual != expected

union all

-- Must have exactly 5 current records (one per customer)
select check_name, actual, expected
from (
    select 'current_rows_count' as check_name,
           count(*) as actual, 5 as expected
    from {{ ref('customers_snapshot') }}
    where dbt_valid_to is null
) t where actual != expected

union all

-- Historical records must have dbt_valid_to < dbt_valid_from of the next record
-- (no overlapping validity periods for the same customer)
select 'overlapping_validity_periods' as check_name,
       count(*) as actual,
       0 as expected
from (
    select a.customer_id
    from {{ ref('customers_snapshot') }} a
    join {{ ref('customers_snapshot') }} b
      on a.customer_id = b.customer_id
     and a.dbt_scd_id != b.dbt_scd_id
     and a.dbt_valid_from < b.dbt_valid_to
     and b.dbt_valid_from < a.dbt_valid_to
    where b.dbt_valid_to is not null
) t
having count(*) != 0
