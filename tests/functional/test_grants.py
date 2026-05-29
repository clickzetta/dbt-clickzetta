import pytest
from dbt.tests.util import run_dbt, get_connection


_model_sql = """
{{ config(
    materialized='table',
    grants={'select': ['workspace_analyst']}
) }}
select 1 as id, 'hello' as name
"""

_model_view_sql = """
{{ config(
    materialized='view',
    grants={'select': ['workspace_analyst']}
) }}
select 1 as id, 'hello' as name
"""


class TestGrantsTable:
    @pytest.fixture(scope="class")
    def models(self):
        return {"grants_model.sql": _model_sql}

    def test_grants_applied(self, project):
        run_dbt(["run"])
        # verify grants were applied by checking SHOW GRANTS
        with get_connection(project.adapter) as conn:
            _, table = project.adapter.execute(
                "SHOW GRANTS ON TABLE dbt_test.grants_model", fetch=True
            )
        rows = [dict(zip([c.lower() for c in table.column_names], r)) for r in table.rows]
        direct = [r for r in rows if r["granted_type"] == "PRIVILEGE"]
        privileges = {r["privilege"].split()[0].lower() for r in direct}
        grantees = {r["grantee_name"].split(".")[-1] for r in direct}
        assert "select" in privileges, f"Expected 'select' in {privileges}"
        assert "workspace_analyst" in grantees, f"Expected 'workspace_analyst' in {grantees}"

    def test_grants_revoked_on_change(self, project):
        # re-run with empty grants — should revoke
        project.update_config("models", {"grants_model": {"grants": {}}})
        run_dbt(["run"])
        with get_connection(project.adapter) as conn:
            _, table = project.adapter.execute(
                "SHOW GRANTS ON TABLE dbt_test.grants_model", fetch=True
            )
        rows = [dict(zip([c.lower() for c in table.column_names], r)) for r in table.rows]
        direct = [r for r in rows if r["granted_type"] == "PRIVILEGE"]
        analyst_grants = [
            r for r in direct if "workspace_analyst" in r.get("grantee_name", "")
        ]
        assert len(analyst_grants) == 0, f"Expected no grants for workspace_analyst, got {analyst_grants}"


class TestGrantsView:
    @pytest.fixture(scope="class")
    def models(self):
        return {"grants_view.sql": _model_view_sql}

    def test_grants_applied_view(self, project):
        run_dbt(["run"])
        with get_connection(project.adapter) as conn:
            _, table = project.adapter.execute(
                "SHOW GRANTS ON VIEW dbt_test.grants_view", fetch=True
            )
        rows = [dict(zip([c.lower() for c in table.column_names], r)) for r in table.rows]
        direct = [r for r in rows if r["granted_type"] == "PRIVILEGE"]
        privileges = {r["privilege"].split()[0].lower() for r in direct}
        grantees = {r["grantee_name"].split(".")[-1] for r in direct}
        assert "select" in privileges
        assert "workspace_analyst" in grantees
