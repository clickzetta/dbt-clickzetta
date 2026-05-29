-- 验证引用完整性：订单里的 customer_id 必须都在客户表里存在
select
    o.order_id,
    o.customer_id,
    'customer_id not found in stg_customers' as reason
from {{ ref('fct_orders_partitioned') }} o
left join {{ ref('stg_customers') }} c on o.customer_id = c.customer_id
where c.customer_id is null
