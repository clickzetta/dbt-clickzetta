-- Vector index example: demonstrates CREATE VECTOR INDEX on a table column.
-- Uses a computed embedding column (simulated as an array of floats from order data).
{{ config(
    materialized='table',
    indexes=[
        {'type': 'vector', 'columns': ['embedding'], 'distance_function': 'cosine_distance', 'scalar_type': 'f32'}
    ]
) }}

select
    order_id as id,
    -- Simulate a 3-dimensional embedding vector from order features
    array(cast(amount as float), cast(length(status) as float), cast(length(region) as float)) as embedding
from {{ ref('fct_orders_incremental') }}

