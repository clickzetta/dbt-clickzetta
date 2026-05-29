-- 验证 regional_revenue_with_grants 表已授权给 workspace_analyst（SELECT）
-- 返回 0 行 = 通过，返回 1 行 = 权限不存在（测试失败）
{{ check_grant(
    relation_name = target.schema ~ '.regional_revenue_with_grants',
    rel_type      = 'TABLE',
    privilege     = 'select',
    grantee       = 'workspace_analyst'
) }}
