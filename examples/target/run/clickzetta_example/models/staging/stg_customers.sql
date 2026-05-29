create or replace view example.stg_customers
  
  as
    

select
    customer_id,
    name,
    email,
    phone,
    city,
    updated_at
from example_raw.raw_customers
