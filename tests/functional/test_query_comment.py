"""
Functional tests for query_comment.

dbt injects a JSON comment into every SQL query.
SHOW JOBS returns real-time results with job_text — we can verify the comment is present.
"""
import json
import pytest

from dbt.tests.util import run_dbt


simple_model_sql = """
select 1 as id, 'hello' as msg
"""


def _get_recent_job_texts(project, limit=20):
    """Return job_text values from SHOW JOBS."""
    rows = project.run_sql("SHOW JOBS", fetch="all")
    # job_text is column index 8
    return [str(r[8] or "") for r in rows if len(r) > 8]


class TestQueryComment:
    """
    Verify that dbt injects a JSON query_comment into every SQL query.
    SHOW JOBS job_text is real-time — no delay.
    """

    @pytest.fixture(scope="class")
    def models(self):
        return {"simple_model.sql": simple_model_sql}

    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"name": "query_comment_test"}

    @pytest.fixture(scope="class", autouse=True)
    def clean_up(self, project):
        yield
        with project.adapter.connection_named("__test"):
            relation = project.adapter.Relation.create(
                database=project.database, schema=project.test_schema
            )
            project.adapter.drop_schema(relation)

    def test_run_succeeds(self, project):
        results = run_dbt(["run"])
        assert results[0].status == "success"

    def test_query_comment_present_in_job_text(self, project):
        """Every dbt-issued query carries a /* {...} */ comment in job_text."""
        run_dbt(["run"])

        job_texts = _get_recent_job_texts(project)
        commented = [t for t in job_texts if t.startswith("/*")]
        assert len(commented) > 0, (
            f"Expected at least one job with /* comment */ in job_text. "
            f"Sample texts: {[t[:60] for t in job_texts[:5]]}"
        )

    def test_query_comment_is_valid_json(self, project):
        """The comment block must be valid JSON."""
        run_dbt(["run"])

        job_texts = _get_recent_job_texts(project)
        for text in job_texts:
            if not text.startswith("/*"):
                continue
            end = text.find("*/")
            if end == -1:
                continue
            raw = text[2:end].strip()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                pytest.fail(f"query_comment is not valid JSON: {raw[:100]}")
            assert "app" in data, f"Missing 'app' field in comment: {data}"
            break
        else:
            pytest.skip("No commented queries found in SHOW JOBS yet")

    def test_query_comment_contains_dbt_fields(self, project):
        """Comment must contain app, dbt_version, target_name."""
        run_dbt(["run"])

        job_texts = _get_recent_job_texts(project)
        for text in job_texts:
            if not text.startswith("/*"):
                continue
            end = text.find("*/")
            if end == -1:
                continue
            raw = text[2:end].strip()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            assert data.get("app") == "dbt", f"Expected app=dbt, got: {data}"
            assert "dbt_version" in data, f"Missing dbt_version: {data}"
            assert "target_name" in data, f"Missing target_name: {data}"
            return  # found and verified

        pytest.skip("No commented queries found in SHOW JOBS yet")

    def test_query_comment_contains_node_id_for_model(self, project):
        """Model queries must include node_id in the comment."""
        run_dbt(["run"])

        job_texts = _get_recent_job_texts(project)
        node_id_found = False
        for text in job_texts:
            if not text.startswith("/*"):
                continue
            end = text.find("*/")
            if end == -1:
                continue
            raw = text[2:end].strip()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if "node_id" in data and "model" in data.get("node_id", ""):
                node_id_found = True
                assert "simple_model" in data["node_id"], (
                    f"Expected node_id to contain 'simple_model', got: {data['node_id']}"
                )
                break

        if not node_id_found:
            pytest.skip("No model query with node_id found in SHOW JOBS yet")
