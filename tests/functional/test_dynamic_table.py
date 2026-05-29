import pytest

from dbt.tests.util import run_dbt, relation_from_name


dynamic_table_sql = """
{{ config(
    materialized='dynamic_table',
    refresh_interval='5 minutes'
) }}
select
    id,
    name,
    amount
from {{ ref('seed_base') }}
"""

dynamic_table_with_partition_sql = """
{{ config(
    materialized='dynamic_table',
    refresh_interval='5 minutes',
    partition_by=['ds']
) }}
select
    id,
    name,
    amount,
    ds
from {{ ref('seed_partitioned') }}
"""

seeds_base_csv = """id,name,amount
1,Alice,100
2,Bob,200
3,Charlie,300
"""

seeds_partitioned_csv = """id,name,amount,ds
1,Alice,100,20240101
2,Bob,200,20240101
3,Charlie,300,20240102
"""

schema_yml = """
version: 2
models:
  - name: dynamic_table_model
    columns:
      - name: id
        tests:
          - not_null
"""


class TestDynamicTable:
    @pytest.fixture(scope="class")
    def seeds(self):
        return {
            "seed_base.csv": seeds_base_csv,
            "seed_partitioned.csv": seeds_partitioned_csv,
        }

    @pytest.fixture(scope="class")
    def models(self):
        return {
            "dynamic_table_model.sql": dynamic_table_sql,
            "schema.yml": schema_yml,
        }

    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"name": "dynamic_table_test"}

    @pytest.fixture(autouse=True)
    def clean_up(self, project):
        yield
        with project.adapter.connection_named("__test"):
            relation = project.adapter.Relation.create(
                database=project.database, schema=project.test_schema
            )
            project.adapter.drop_schema(relation)

    def test_dynamic_table_create(self, project):
        run_dbt(["seed"])
        results = run_dbt(["run"])
        assert len(results) == 1
        assert results[0].status == "success"

    def test_dynamic_table_rowcount(self, project):
        run_dbt(["seed"])
        run_dbt(["run"])
        relation = relation_from_name(project.adapter, "dynamic_table_model")
        result = project.run_sql(
            f"select count(*) as num_rows from {relation}", fetch="one"
        )
        assert result[0] == 3

    def test_dynamic_table_full_refresh(self, project):
        run_dbt(["seed"])
        run_dbt(["run"])
        results = run_dbt(["run", "--full-refresh"])
        assert len(results) == 1
        assert results[0].status == "success"


class TestDynamicTableWithPartition:
    @pytest.fixture(scope="class")
    def seeds(self):
        return {
            "seed_partitioned.csv": seeds_partitioned_csv,
        }

    @pytest.fixture(scope="class")
    def models(self):
        return {
            "dynamic_table_partitioned.sql": dynamic_table_with_partition_sql,
        }

    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"name": "dynamic_table_partition_test"}

    @pytest.fixture(autouse=True)
    def clean_up(self, project):
        yield
        with project.adapter.connection_named("__test"):
            relation = project.adapter.Relation.create(
                database=project.database, schema=project.test_schema
            )
            project.adapter.drop_schema(relation)

    def test_dynamic_table_with_partition(self, project):
        run_dbt(["seed"])
        results = run_dbt(["run"])
        assert len(results) == 1
        assert results[0].status == "success"
