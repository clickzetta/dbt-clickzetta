import pytest
import yaml
from dbt.tests.util import run_dbt, get_connection, write_file


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

# Model with grants removed — used to test revocation
_model_no_grants_sql = """
{{ config(materialized='table') }}
select 1 as id, 'hello' as name
"""


class TestGrantsTable:
    @pytest.fixture(scope="class")
    def models(self):
        return {"grants_model.sql": _model_sql}

    def test_grants_applied(self, project):
        run_dbt(["run"])
        schema = project.test_schema
        db = project.database
        with get_connection(project.adapter) as conn:
            _, table = project.adapter.execute(
                f"SHOW GRANTS ON TABLE {db}.{schema}.grants_model", fetch=True
            )
        rows = [dict(zip([c.lower() for c in table.column_names], r)) for r in table.rows]
        direct = [r for r in rows if r["granted_type"] == "PRIVILEGE"]
        privileges = {r["privilege"].split()[0].lower() for r in direct}
        grantees = {r["grantee_name"].split(".")[-1] for r in direct}
        assert "select" in privileges, f"Expected 'select' in {privileges}"
        assert "workspace_analyst" in grantees, f"Expected 'workspace_analyst' in {grantees}"

    def test_grants_revoked_on_change(self, project):
        # Re-run with grants removed — should revoke by rebuilding the table without grants
        write_file(_model_no_grants_sql, project.project_root, "models", "grants_model.sql")
        run_dbt(["run", "--full-refresh"])
        schema = project.test_schema
        db = project.database
        with get_connection(project.adapter) as conn:
            _, table = project.adapter.execute(
                f"SHOW GRANTS ON TABLE {db}.{schema}.grants_model", fetch=True
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
        schema = project.test_schema
        db = project.database
        with get_connection(project.adapter) as conn:
            _, table = project.adapter.execute(
                f"SHOW GRANTS ON VIEW {db}.{schema}.grants_view", fetch=True
            )
        rows = [dict(zip([c.lower() for c in table.column_names], r)) for r in table.rows]
        direct = [r for r in rows if r["granted_type"] == "PRIVILEGE"]
        privileges = {r["privilege"].split()[0].lower() for r in direct}
        grantees = {r["grantee_name"].split(".")[-1] for r in direct}
        assert "select" in privileges
        assert "workspace_analyst" in grantees
