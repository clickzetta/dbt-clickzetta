"""
Functional tests for query_tag connection parameter.

query_tag is set via SET query_tag = '...' after connection open.
SHOW JOBS returns real-time results including query_tag — no delay.
"""
import pytest

from dbt.tests.util import run_dbt


simple_model_sql = """
select 1 as id, 'hello' as msg
"""


class TestQueryTagSet:
    """Verify that query_tag is SET on connection and visible in SHOW JOBS."""

    @pytest.fixture(scope="class")
    def models(self):
        return {"simple_model.sql": simple_model_sql}

    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"name": "query_tag_test"}

    @pytest.fixture(scope="class", autouse=True)
    def clean_up(self, project):
        yield
        with project.adapter.connection_named("__test"):
            relation = project.adapter.Relation.create(
                database=project.database, schema=project.test_schema
            )
            project.adapter.drop_schema(relation)

    def test_run_succeeds_with_query_tag(self, project):
        """dbt run completes successfully when query_tag is configured."""
        results = run_dbt(["run"])
        assert len(results) == 1
        assert results[0].status == "success"

    def test_query_tag_visible_in_show_jobs(self, project):
        """
        SHOW JOBS returns real-time results. After running with a query_tag,
        the tag must appear in SHOW JOBS output immediately.
        """
        tag = project.adapter.config.credentials.query_tag
        if not tag:
            pytest.skip("query_tag not configured in test profile")

        run_dbt(["run"])

        # SHOW JOBS is real-time — query_tag should appear immediately
        # Run a query through the adapter connection so it carries the tag
        with project.adapter.connection_named("__test_tag"):
            result = project.adapter.execute(
                "SHOW JOBS", fetch=True
            )

        _, table = result if isinstance(result, tuple) else (None, result)
        rows = table.rows if hasattr(table, "rows") else []

        # Find rows with our tag
        tagged = [
            r for r in rows
            if len(r) >= 10 and str(r[9]).strip("'") == tag
        ]
        assert len(tagged) > 0, (
            f"Expected SHOW JOBS to contain rows with query_tag='{tag}'. "
            f"Got tags: {list(set(str(r[9]) for r in rows if len(r) >= 10))[:10]}"
        )

    def test_query_tag_in_show_jobs_via_sql(self, project):
        """
        Verify query_tag via direct SQL: run a query then check SHOW JOBS.
        Uses project.run_sql which goes through the adapter connection (with query_tag set).
        """
        tag = project.adapter.config.credentials.query_tag
        if not tag:
            pytest.skip("query_tag not configured in test profile")

        # Run a simple query — it will carry the query_tag
        project.run_sql("SELECT 1 as ping", fetch="one")

        # SHOW JOBS is real-time
        rows = project.run_sql("SHOW JOBS", fetch="all")
        assert rows is not None

        # Find a row with our tag (column index 9 = query_tag)
        tagged = [r for r in rows if len(r) >= 10 and str(r[9]).strip("'") == tag]
        assert len(tagged) > 0, (
            f"Expected at least one job with query_tag='{tag}' in SHOW JOBS. "
            f"Sample tags seen: {list(set(str(r[9]) for r in rows if len(r) >= 10))[:5]}"
        )


class TestQueryTagNone:
    """Verify dbt runs normally when query_tag is not set."""

    @pytest.fixture(scope="class")
    def dbt_profile_target(self):
        """Override profile to have no query_tag."""
        import os
        return {
            "type": "clickzetta",
            "service": os.getenv("CLICKZETTA_TEST_SERVICE"),
            "instance": os.getenv("CLICKZETTA_TEST_INSTANCE"),
            "workspace": os.getenv("CLICKZETTA_TEST_WORKSPACE"),
            "username": os.getenv("CLICKZETTA_TEST_USERNAME"),
            "password": os.getenv("CLICKZETTA_TEST_PASSWORD"),
            "vcluster": os.getenv("CLICKZETTA_TEST_VCLUSTER", "default"),
            "schema": os.getenv("CLICKZETTA_TEST_SCHEMA", "dbt_test"),
            # no query_tag
        }

    @pytest.fixture(scope="class")
    def models(self):
        return {"simple_model.sql": simple_model_sql}

    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"name": "query_tag_none_test"}

    @pytest.fixture(scope="class", autouse=True)
    def clean_up(self, project):
        yield
        with project.adapter.connection_named("__test"):
            relation = project.adapter.Relation.create(
                database=project.database, schema=project.test_schema
            )
            project.adapter.drop_schema(relation)

    def test_run_succeeds_without_query_tag(self, project):
        """dbt run works normally when query_tag is not configured."""
        results = run_dbt(["run"])
        assert len(results) == 1
        assert results[0].status == "success"


class TestQueryTagSqlInjection:
    """Verify single quotes in query_tag are safely escaped."""

    @pytest.fixture(scope="class")
    def dbt_profile_target(self):
        import os
        return {
            "type": "clickzetta",
            "service": os.getenv("CLICKZETTA_TEST_SERVICE"),
            "instance": os.getenv("CLICKZETTA_TEST_INSTANCE"),
            "workspace": os.getenv("CLICKZETTA_TEST_WORKSPACE"),
            "username": os.getenv("CLICKZETTA_TEST_USERNAME"),
            "password": os.getenv("CLICKZETTA_TEST_PASSWORD"),
            "vcluster": os.getenv("CLICKZETTA_TEST_VCLUSTER", "default"),
            "schema": os.getenv("CLICKZETTA_TEST_SCHEMA", "dbt_test"),
            "query_tag": "dbt's tag",  # contains single quote
        }

    @pytest.fixture(scope="class")
    def models(self):
        return {"simple_model.sql": simple_model_sql}

    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"name": "query_tag_escape_test"}

    @pytest.fixture(scope="class", autouse=True)
    def clean_up(self, project):
        yield
        with project.adapter.connection_named("__test"):
            relation = project.adapter.Relation.create(
                database=project.database, schema=project.test_schema
            )
            project.adapter.drop_schema(relation)

    def test_single_quote_in_tag_does_not_break_connection(self, project):
        """Single quote in query_tag is escaped — connection succeeds."""
        results = run_dbt(["run"])
        assert len(results) == 1
        assert results[0].status == "success"

    def test_single_quote_tag_visible_in_show_jobs(self, project):
        """The escaped tag appears correctly in SHOW JOBS."""
        project.run_sql("SELECT 1 as ping", fetch="one")

        rows = project.run_sql("SHOW JOBS", fetch="all")
        # query_tag column is index 9; stored with surrounding quotes in ClickZetta
        tagged = [
            r for r in rows
            if len(r) >= 10 and "dbt" in str(r[9]) and "tag" in str(r[9])
        ]
        assert len(tagged) > 0, (
            "Expected job with query_tag containing 'dbt' and 'tag' in SHOW JOBS. "
            f"Tags seen: {list(set(str(r[9]) for r in rows if len(r) >= 10))[:5]}"
        )
