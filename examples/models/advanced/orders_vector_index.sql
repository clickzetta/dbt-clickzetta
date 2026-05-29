{{ config(
    materialized='table',
    indexes=[
        {'type': 'vector', 'columns': ['embedding'], 'distance_function': 'cosine_distance', 'scalar_type': 'f32'}
    ]
) }}

select id, embedding
from example.vector_test_src
