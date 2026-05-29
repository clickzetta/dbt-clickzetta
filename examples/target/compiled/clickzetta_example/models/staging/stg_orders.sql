

select
    order_id,
    customer_id,
    cast(amount as decimal(10,2)) as amount,
    status,
    region,
    dt,
    updated_at
from example_raw.raw_orders
where order_id is not null