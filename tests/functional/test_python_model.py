"""
Functional tests for Python model support via ZettaPark.

These tests run inside ClickZetta Studio Python Task environments where
clickzetta-zettapark-python is pre-installed. They verify:
1. A simple Python model can be exec()'d and returns a DataFrame
2. The DataFrame is written to the target table
3. dbt.config(), dbt.ref() interfaces work correctly
"""

import pytest

try:
    from clickzetta.zettapark.session import Session
    ZETTAPARK_AVAILABLE = True
except ImportError:
    ZETTAPARK_AVAILABLE = False

from dbt.tests.util import run_dbt, relation_from_name


# ── Python model SQL templates ─────────────────────────────────────────────────

_simple_python_model = """
import pandas as pd

def model(dbt, session):
    dbt.config(materialized='table')
    df = session.sql("select 1 as id, 'hello from python' as msg")
    return df
"""

_python_model_with_ref = """
def model(dbt, session):
    dbt.config(materialized='table')
    # Read from a SQL staging model
    stg = dbt.ref('stg_source')
    # Filter and transform
    result = stg.filter(stg['amount'] > 0)
    return result
"""

_stg_source_sql = """
{{ config(materialized='table') }}
select 1 as id, 'Alice' as name, 100 as amount
union all
select 2, 'Bob', -50
union all
select 3, 'Charlie', 200
"""

_schema_yml = """
version: 2
models:
  - name: simple_python_model
    columns:
      - name: id
        tests:
          - not_null
"""


# ── Tests ──────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(
    not ZETTAPARK_AVAILABLE,
    reason="clickzetta-zettapark-python not available — Python models only run in Studio environment"
)
class TestPythonModelSimple:
    """Simple Python model: session.sql() → return DataFrame → write table."""

    @pytest.fixture(scope="class")
    def models(self):
        return {
            "simple_python_model.py": _simple_python_model,
            "schema.yml": _schema_yml,
        }

    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"name": "python_model_test"}

    @pytest.fixture(scope="class", autouse=True)
    def clean_up(self, project):
        yield
        with project.adapter.connection_named("__test"):
            relation = project.adapter.Relation.create(
                database=project.database, schema=project.test_schema
            )
            project.adapter.drop_schema(relation)

    def test_python_model_runs(self, project):
        """Python model executes and writes table."""
        results = run_dbt(["run"])
        assert results[0].status == "success"

        relation = relation_from_name(project.adapter, "simple_python_model")
        row = project.run_sql(f"select id, msg from {relation}", fetch="one")
        assert row[0] == 1
        assert row[1] == "hello from python"

    def test_python_model_dbt_test(self, project):
        """dbt test passes on Python model output."""
        results = run_dbt(["test"])
        assert all(r.status == "pass" for r in results)


@pytest.mark.skipif(
    not ZETTAPARK_AVAILABLE,
    reason="clickzetta-zettapark-python not available — Python models only run in Studio environment"
)
class TestPythonModelWithRef:
    """Python model using dbt.ref() to read from a SQL model."""

    @pytest.fixture(scope="class")
    def models(self):
        return {
            "stg_source.sql": _stg_source_sql,
            "filtered_model.py": _python_model_with_ref,
        }

    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"name": "python_ref_test"}

    @pytest.fixture(scope="class", autouse=True)
    def clean_up(self, project):
        yield
        with project.adapter.connection_named("__test"):
            relation = project.adapter.Relation.create(
                database=project.database, schema=project.test_schema
            )
            project.adapter.drop_schema(relation)

    def test_python_model_with_ref(self, project):
        """Python model reads from SQL model via dbt.ref() and filters correctly."""
        results = run_dbt(["run"])
        assert all(r.status == "success" for r in results)

        relation = relation_from_name(project.adapter, "filtered_model")
        count = project.run_sql(f"select count(*) from {relation}", fetch="one")[0]
        # Only rows with amount > 0: Alice (100) and Charlie (200), not Bob (-50)
        assert count == 2, f"expected 2 rows after filter, got {count}"
