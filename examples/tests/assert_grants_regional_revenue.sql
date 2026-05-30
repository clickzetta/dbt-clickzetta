-- Verify regional_revenue_with_grants has been granted SELECT to the configured role.
-- The role defaults to 'workspace_analyst'. Override with:
--   dbt test --vars '{"grant_role": "my_role"}' --select assert_grants_regional_revenue
-- Returns 0 rows = pass, 1 row = grant missing (test fails)
{{ check_grant(
    relation_name = target.database ~ '.' ~ target.schema ~ '.regional_revenue_with_grants',
    rel_type      = 'TABLE',
    privilege     = 'select',
    grantee       = var('grant_role', 'workspace_analyst')
) }}
