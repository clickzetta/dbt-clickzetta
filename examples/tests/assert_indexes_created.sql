-- Verify that 3 indexes on orders_with_indexes were created correctly
{{ check_indexes(
    relation_name = target.database ~ '.' ~ target.schema ~ '.orders_with_indexes',
    expected_indexes = [
        {'name': 'example_orders_with_indexes_order_id_bloomfilter_idx',    'type': 'bloom_filter'},
        {'name': 'example_orders_with_indexes_customer_id_bloomfilter_idx', 'type': 'bloom_filter'},
        {'name': 'example_orders_with_indexes_status_inverted_idx',         'type': 'inverted'}
    ]
) }}
