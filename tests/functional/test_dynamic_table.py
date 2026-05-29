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

materialized_view_sql = """
{{ config(materialized='materialized_view') }}
select
    id,
    name,
    amount * 2 as amount_doubled
from {{ ref('seed_base') }}
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

    @pytest.fixture(scope="class", autouse=True)
    def clean_up(self, project):
        yield
        with project.adapter.connection_named("__test"):
            relation = project.adapter.Relation.create(
                database=project.database, schema=project.test_schema
            )
            project.adapter.drop_schema(relation)

    def test_dynamic_table(self, project):
        """动态表：创建后自动刷新（initialize=ON_CREATE 语义），可直接查询"""
        run_dbt(["seed"])

        # 创建动态表（materialization 内部自动执行 REFRESH DYNAMIC TABLE）
        results = run_dbt(["run"])
        assert len(results) == 1
        assert results[0].status == "success"

        # 创建后无需手动刷新，直接查询
        relation = relation_from_name(project.adapter, "dynamic_table_model")
        result = project.run_sql(
            f"select count(*) as num_rows from {relation}", fetch="one"
        )
        assert result[0] == 3, f"expected 3 rows after create+auto-refresh, got {result[0]}"

        # full_refresh 重建（也会自动刷新）
        results = run_dbt(["run", "--full-refresh"])
        assert len(results) == 1
        assert results[0].status == "success"

        result = project.run_sql(
            f"select count(*) as num_rows from {relation}", fetch="one"
        )
        assert result[0] == 3, f"expected 3 rows after full_refresh, got {result[0]}"

        # 第二次 run（表已存在，no-op，不重建）
        results = run_dbt(["run"])
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

    @pytest.fixture(scope="class", autouse=True)
    def clean_up(self, project):
        yield
        with project.adapter.connection_named("__test"):
            relation = project.adapter.Relation.create(
                database=project.database, schema=project.test_schema
            )
            project.adapter.drop_schema(relation)

    def test_dynamic_table_with_partition(self, project):
        """分区动态表：创建后自动刷新，验证分区数据"""
        run_dbt(["seed"])
        results = run_dbt(["run"])
        assert len(results) == 1
        assert results[0].status == "success"

        # 创建后直接查询（无需手动刷新）
        relation = relation_from_name(project.adapter, "dynamic_table_partitioned")
        result = project.run_sql(
            f"select count(*) from {relation}", fetch="one"
        )
        assert result[0] == 3, f"expected 3 rows, got {result[0]}"

        ds1 = project.run_sql(
            f"select count(*) from {relation} where ds = '20240101'", fetch="one"
        )[0]
        assert ds1 == 2, f"expected 2 rows in ds=20240101, got {ds1}"


class TestMaterializedView:
    @pytest.fixture(scope="class")
    def seeds(self):
        return {"seed_base.csv": seeds_base_csv}

    @pytest.fixture(scope="class")
    def models(self):
        return {"mv_model.sql": materialized_view_sql}

    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"name": "materialized_view_test"}

    @pytest.fixture(scope="class", autouse=True)
    def clean_up(self, project):
        yield
        with project.adapter.connection_named("__test"):
            relation = project.adapter.Relation.create(
                database=project.database, schema=project.test_schema
            )
            project.adapter.drop_schema(relation)

    def test_materialized_view(self, project):
        """物化视图：创建、查询、刷新、数据正确性"""
        run_dbt(["seed"])
        results = run_dbt(["run"])
        assert len(results) == 1
        assert results[0].status == "success"

        relation = relation_from_name(project.adapter, "mv_model")

        # 行数
        n = project.run_sql(f"select count(*) from {relation}", fetch="one")[0]
        assert n == 3, f"expected 3 rows, got {n}"

        # 数据正确性：amount_doubled = amount * 2
        alice = project.run_sql(
            f"select amount_doubled from {relation} where id = 1", fetch="one"
        )[0]
        assert int(alice) == 200, f"expected amount_doubled=200 for Alice, got {alice}"

        # full_refresh 重建
        results = run_dbt(["run", "--full-refresh"])
        assert len(results) == 1
        assert results[0].status == "success"

        # 重建后数据仍然正确
        n = project.run_sql(f"select count(*) from {relation}", fetch="one")[0]
        assert n == 3, f"expected 3 rows after full_refresh, got {n}"
