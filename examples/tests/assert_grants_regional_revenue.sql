-- Verify regional_revenue_with_grants has been granted SELECT to workspace_analyst
-- Returns 0 rows = pass, 1 row = grant missing (test fails)
{{ check_grant(
    relation_name = target.database ~ '.' ~ target.schema ~ '.regional_revenue_with_grants',
    rel_type      = 'TABLE',
    privilege     = 'select',
    grantee       = 'workspace_analyst'
) }}
