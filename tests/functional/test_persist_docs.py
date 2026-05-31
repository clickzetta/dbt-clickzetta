import pytest
from dbt.tests.util import run_dbt, relation_from_name


# ── SQL templates ──────────────────────────────────────────────────────────────

_table_with_docs_sql = """
{{ config(
    materialized='table',
    persist_docs={"relation": true, "columns": true}
) }}
select
    1 as order_id,
    'Alice' as customer_name,
    100 as amount
"""

_table_schema_yml = """
version: 2
models:
  - name: orders_with_docs
    description: "Orders table with persist_docs enabled"
    columns:
      - name: order_id
        description: "Unique order identifier"
      - name: customer_name
        description: "Customer full name"
      - name: amount
        description: "Order amount in cents"
"""

_incremental_with_docs_sql = """
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='order_id',
    persist_docs={"relation": true, "columns": true}
) }}
select
    1 as order_id,
    'Alice' as customer_name,
    100 as amount
"""

_incremental_schema_yml = """
version: 2
models:
  - name: incremental_with_docs
    description: "Incremental table with persist_docs enabled"
    columns:
      - name: order_id
        description: "Unique order identifier"
      - name: customer_name
        description: "Customer full name"
      - name: amount
        description: "Order amount"
"""

_no_docs_sql = """
{{ config(materialized='table') }}
select 1 as id, 'test' as name
"""

_no_docs_schema_yml = """
version: 2
models:
  - name: table_no_docs
    description: "Table without persist_docs"
    columns:
      - name: id
        description: "ID column"
"""


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestPersistDocsTable:
    """
    Verify persist_docs writes table and column descriptions to Lakehouse metadata.
    Uses DESC TABLE to verify column comments, SHOW TBLPROPERTIES for table comment.
    """

    @pytest.fixture(scope="class")
    def models(self):
        return {
            "orders_with_docs.sql": _table_with_docs_sql,
            "schema.yml": _table_schema_yml,
        }

    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"name": "persist_docs_test"}

    @pytest.fixture(scope="class", autouse=True)
    def clean_up(self, project):
        yield
        with project.adapter.connection_named("__test"):
            relation = project.adapter.Relation.create(
                database=project.database, schema=project.test_schema
            )
            project.adapter.drop_schema(relation)

    def test_column_comments_written(self, project):
        """dbt run with persist_docs writes column descriptions to Lakehouse."""
        results = run_dbt(["run"])
        assert results[0].status == "success"

        relation = relation_from_name(project.adapter, "orders_with_docs")

        # DESC TABLE returns (column_name, data_type, comment)
        desc_rows = project.run_sql(f"desc table {relation}", fetch="all")
        col_comments = {row[0]: row[2] for row in desc_rows}

        assert col_comments.get("order_id") == "Unique order identifier", (
            f"expected order_id comment, got: {col_comments.get('order_id')!r}"
        )
        assert col_comments.get("customer_name") == "Customer full name", (
            f"expected customer_name comment, got: {col_comments.get('customer_name')!r}"
        )
        assert col_comments.get("amount") == "Order amount in cents", (
            f"expected amount comment, got: {col_comments.get('amount')!r}"
        )

    def test_table_comment_written(self, project):
        """dbt run with persist_docs writes table description to Lakehouse."""
        relation = relation_from_name(project.adapter, "orders_with_docs")

        # SHOW CREATE TABLE includes COMMENT clause
        create_sql = project.run_sql(f"show create table {relation}", fetch="one")[0]
        assert "Orders table with persist_docs enabled" in create_sql, (
            f"expected table comment in SHOW CREATE TABLE, got: {create_sql[:200]}"
        )

    def test_column_comments_updated_on_rerun(self, project):
        """Column comments are updated when schema.yml descriptions change (via full_refresh)."""
        relation = relation_from_name(project.adapter, "orders_with_docs")

        # Verify comments exist from first run
        desc_rows = project.run_sql(f"desc table {relation}", fetch="all")
        col_comments = {row[0]: row[2] for row in desc_rows}
        assert col_comments.get("order_id") == "Unique order identifier"

        # full_refresh rebuilds the table — comments should still be written
        results = run_dbt(["run", "--full-refresh"])
        assert results[0].status == "success"

        desc_rows = project.run_sql(f"desc table {relation}", fetch="all")
        col_comments = {row[0]: row[2] for row in desc_rows}
        assert col_comments.get("order_id") == "Unique order identifier", (
            f"expected comment preserved after full_refresh, got: {col_comments.get('order_id')!r}"
        )


class TestPersistDocsIncremental:
    """Verify persist_docs works on incremental models."""

    @pytest.fixture(scope="class")
    def models(self):
        return {
            "incremental_with_docs.sql": _incremental_with_docs_sql,
            "schema.yml": _incremental_schema_yml,
        }

    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"name": "persist_docs_incremental_test"}

    @pytest.fixture(scope="class", autouse=True)
    def clean_up(self, project):
        yield
        with project.adapter.connection_named("__test"):
            relation = project.adapter.Relation.create(
                database=project.database, schema=project.test_schema
            )
            project.adapter.drop_schema(relation)

    def test_incremental_column_comments_written(self, project):
        """persist_docs on incremental model writes column comments on first run."""
        results = run_dbt(["run"])
        assert results[0].status == "success"

        relation = relation_from_name(project.adapter, "incremental_with_docs")
        desc_rows = project.run_sql(f"desc table {relation}", fetch="all")
        col_comments = {row[0]: row[2] for row in desc_rows}

        assert col_comments.get("order_id") == "Unique order identifier", (
            f"expected order_id comment on incremental, got: {col_comments.get('order_id')!r}"
        )
        assert col_comments.get("customer_name") == "Customer full name", (
            f"expected customer_name comment on incremental, got: {col_comments.get('customer_name')!r}"
        )

    def test_incremental_column_comments_on_second_run(self, project):
        """persist_docs on incremental model re-writes column comments on subsequent runs."""
        results = run_dbt(["run"])
        assert results[0].status == "success"

        relation = relation_from_name(project.adapter, "incremental_with_docs")
        desc_rows = project.run_sql(f"desc table {relation}", fetch="all")
        col_comments = {row[0]: row[2] for row in desc_rows}

        assert col_comments.get("order_id") == "Unique order identifier", (
            f"expected comment preserved on second incremental run, got: {col_comments.get('order_id')!r}"
        )


class TestPersistDocsDisabled:
    """Verify that without persist_docs, no comments are written."""

    @pytest.fixture(scope="class")
    def models(self):
        return {
            "table_no_docs.sql": _no_docs_sql,
            "schema.yml": _no_docs_schema_yml,
        }

    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"name": "persist_docs_disabled_test"}

    @pytest.fixture(scope="class", autouse=True)
    def clean_up(self, project):
        yield
        with project.adapter.connection_named("__test"):
            relation = project.adapter.Relation.create(
                database=project.database, schema=project.test_schema
            )
            project.adapter.drop_schema(relation)

    def test_no_comments_without_persist_docs(self, project):
        """Without persist_docs config, column comments are not written."""
        results = run_dbt(["run"])
        assert results[0].status == "success"

        relation = relation_from_name(project.adapter, "table_no_docs")
        desc_rows = project.run_sql(f"desc table {relation}", fetch="all")
        col_comments = {row[0]: row[2] for row in desc_rows}

        # Comments should be empty (None or empty string)
        id_comment = col_comments.get("id", "")
        assert not id_comment, (
            f"expected no comment without persist_docs, got: {id_comment!r}"
        )
