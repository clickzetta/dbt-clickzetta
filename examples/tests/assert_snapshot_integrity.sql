-- 验证 snapshot 完整性
-- 1. 当前版本（dbt_valid_to IS NULL）的行数应等于源数据行数（10 条）
-- 2. 每个 order_id 有且只有一条当前记录
-- 3. 所有记录的 dbt_valid_from 不为空

select 'current_rows_count' as check_name, count(*) as actual, 10 as expected
from {{ ref('orders_snapshot') }}
where dbt_valid_to is null
having count(*) != 10

union all

-- 每个 order_id 最多只有一条 current 记录
select 'duplicate_current_records', count(*), 0
from (
    select order_id, count(*) as cnt
    from {{ ref('orders_snapshot') }}
    where dbt_valid_to is null
    group by order_id
    having count(*) > 1
) t
having count(*) != 0

union all

-- dbt_valid_from 不能为空
select 'null_valid_from', count(*), 0
from {{ ref('orders_snapshot') }}
where dbt_valid_from is null
having count(*) != 0
