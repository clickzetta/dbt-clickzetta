-- 验证 snapshot 完整性（第二轮：C001/C003 城市变更，各有历史+当前两条记录）
select check_name, actual, expected
from (
    -- 当前版本（dbt_valid_to IS NULL）应有 5 条（每个客户一条当前记录）
    select 'current_rows_count' as check_name,
           count(*) as actual, 5 as expected
    from {{ ref('customers_snapshot') }}
    where dbt_valid_to is null
) t where actual != expected

union all

select check_name, actual, expected
from (
    -- 历史版本（dbt_valid_to IS NOT NULL）应有 2 条（C001/C003 各一条旧记录）
    select 'historical_rows_count' as check_name,
           count(*) as actual, 2 as expected
    from {{ ref('customers_snapshot') }}
    where dbt_valid_to is not null
) t where actual != expected

union all

select check_name, actual, expected
from (
    -- 总行数应为 7
    select 'total_rows_count' as check_name,
           count(*) as actual, 7 as expected
    from {{ ref('customers_snapshot') }}
) t where actual != expected

union all

-- 每个 customer_id 最多只有一条 current 记录
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

-- C001 当前城市应为 Hangzhou（已从 Shanghai 变更）
select 'c001_current_city' as check_name,
       city as actual,
       'Hangzhou' as expected
from {{ ref('customers_snapshot') }}
where customer_id = 'C001' and dbt_valid_to is null
  and city != 'Hangzhou'

union all

-- C001 历史城市应为 Shanghai
select 'c001_historical_city' as check_name,
       city as actual,
       'Shanghai' as expected
from {{ ref('customers_snapshot') }}
where customer_id = 'C001' and dbt_valid_to is not null
  and city != 'Shanghai'

union all

-- C003 当前城市应为 Chengdu
select 'c003_current_city' as check_name,
       city as actual,
       'Chengdu' as expected
from {{ ref('customers_snapshot') }}
where customer_id = 'C003' and dbt_valid_to is null
  and city != 'Chengdu'
