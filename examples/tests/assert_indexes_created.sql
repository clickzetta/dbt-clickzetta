-- 验证 orders_with_indexes 表的 3 个索引已正确创建
{{ check_indexes(
    relation_name = target.schema ~ '.orders_with_indexes',
    expected_indexes = [
        {'name': 'example_orders_with_indexes_order_id_bloomfilter_idx',    'type': 'bloom_filter'},
        {'name': 'example_orders_with_indexes_customer_id_bloomfilter_idx', 'type': 'bloom_filter'},
        {'name': 'example_orders_with_indexes_status_inverted_idx',         'type': 'inverted'}
    ]
) }}
