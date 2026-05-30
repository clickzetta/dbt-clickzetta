import pytest
import time

from dbt.tests.util import run_dbt, relation_from_name


# ── SQL templates ─────────────────────────────────────────────────────────────

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

# Reads from a raw source table so we can INSERT directly and observe DT updating
dynamic_table_upstream_sql = """
{{ config(
    materialized='dynamic_table',
    refresh_interval='1 minutes'
) }}
select id, name, amount
from {{ source('raw', 'raw_orders') }}
"""

# Downstream DT that aggregates the upstream DT
# Note: use int amount to avoid Lakehouse optimizer bug CZLH-66000
# "bad integral cast decimal(20,2) to i" when aggregating decimal columns in DT-on-DT
dynamic_table_downstream_sql = """
{{ config(
    materialized='dynamic_table',
    refresh_interval='1 minutes'
) }}
select
    name,
    sum(amount) as total_amount,
    count(*) as order_count
from {{ ref('dt_upstream') }}
group by name
"""

upstream_schema_yml = """
version: 2
sources:
  - name: raw
    schema: "{{ target.schema }}"
    tables:
      - name: raw_orders
"""

# ── Seed data ─────────────────────────────────────────────────────────────────

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


# ── Tests ─────────────────────────────────────────────────────────────────────

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

        results = run_dbt(["run"])
        assert len(results) == 1
        assert results[0].status == "success"

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

        relation = relation_from_name(project.adapter, "dynamic_table_partitioned")
        result = project.run_sql(
            f"select count(*) from {relation}", fetch="one"
        )
        assert result[0] == 3, f"expected 3 rows, got {result[0]}"

        ds1 = project.run_sql(
            f"select count(*) from {relation} where ds = '20240101'", fetch="one"
        )[0]
        assert ds1 == 2, f"expected 2 rows in ds=20240101, got {ds1}"


class TestDynamicTableUpstreamChange:
    """
    动态表核心特性：上游数据变更后自动增量刷新。
    直接 INSERT/UPDATE 源表，触发手动 REFRESH，验证动态表数据正确更新。
    注意：使用手动 REFRESH 而非等待定时刷新，避免测试耗时过长。
    """

    @pytest.fixture(scope="class")
    def models(self):
        return {
            "dt_upstream.sql": dynamic_table_upstream_sql,
            "schema.yml": upstream_schema_yml,
        }

    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"name": "dt_upstream_change_test"}

    @pytest.fixture(scope="class", autouse=True)
    def clean_up(self, project):
        yield
        with project.adapter.connection_named("__test"):
            relation = project.adapter.Relation.create(
                database=project.database, schema=project.test_schema
            )
            project.adapter.drop_schema(relation)

    def _refresh(self, project, relation):
        """手动触发动态表刷新并等待完成"""
        project.run_sql(f"refresh dynamic table {relation}")

    def test_insert_new_rows(self, project):
        """上游新增行 → 动态表刷新后包含新行"""
        # 建源表并插入初始数据
        schema = project.test_schema
        db = project.database
        project.run_sql(
            f"create table if not exists {db}.{schema}.raw_orders "
            f"(id int, name string, amount decimal(10,2))"
        )
        project.run_sql(
            f"insert into {db}.{schema}.raw_orders values (1, 'Alice', 100), (2, 'Bob', 200)"
        )

        run_dbt(["run"])
        relation = relation_from_name(project.adapter, "dt_upstream")

        n = project.run_sql(f"select count(*) from {relation}", fetch="one")[0]
        assert n == 2, f"expected 2 rows after initial create, got {n}"

        # 上游新增一行
        project.run_sql(
            f"insert into {db}.{schema}.raw_orders values (3, 'Charlie', 300)"
        )
        self._refresh(project, relation)

        n = project.run_sql(f"select count(*) from {relation}", fetch="one")[0]
        assert n == 3, f"expected 3 rows after upstream insert + refresh, got {n}"

        charlie = project.run_sql(
            f"select amount from {relation} where id = 3", fetch="one"
        )
        assert charlie is not None, "Charlie row not found after refresh"
        assert int(charlie[0]) == 300, f"expected amount=300 for Charlie, got {charlie[0]}"

    def test_update_existing_rows(self, project):
        """上游行更新 → 动态表刷新后反映最新值（声明式增量，无需 merge 逻辑）"""
        schema = project.test_schema
        db = project.database
        relation = relation_from_name(project.adapter, "dt_upstream")

        # 更新 Bob 的 amount
        project.run_sql(
            f"update {db}.{schema}.raw_orders set amount = 999 where id = 2"
        )
        self._refresh(project, relation)

        bob_amount = project.run_sql(
            f"select amount from {relation} where id = 2", fetch="one"
        )[0]
        assert int(bob_amount) == 999, f"expected Bob amount=999 after update+refresh, got {bob_amount}"

        # 其他行不受影响
        alice_amount = project.run_sql(
            f"select amount from {relation} where id = 1", fetch="one"
        )[0]
        assert int(alice_amount) == 100, f"expected Alice amount=100 unchanged, got {alice_amount}"

    def test_delete_rows(self, project):
        """上游行删除 → 动态表刷新后行消失"""
        schema = project.test_schema
        db = project.database
        relation = relation_from_name(project.adapter, "dt_upstream")

        n_before = project.run_sql(f"select count(*) from {relation}", fetch="one")[0]

        project.run_sql(f"delete from {db}.{schema}.raw_orders where id = 3")
        self._refresh(project, relation)

        n_after = project.run_sql(f"select count(*) from {relation}", fetch="one")[0]
        assert n_after == n_before - 1, (
            f"expected {n_before - 1} rows after delete+refresh, got {n_after}"
        )

        charlie = project.run_sql(
            f"select count(*) from {relation} where id = 3", fetch="one"
        )[0]
        assert charlie == 0, f"expected Charlie to be gone after delete, got {charlie} rows"


class TestDynamicTablePipeline:
    """
    动态表 pipeline：上游 DT → 下游聚合 DT。
    验证级联刷新：上游数据变更后，手动刷新上游，再刷新下游，下游聚合结果正确。
    """

    @pytest.fixture(scope="class")
    def models(self):
        return {
            "dt_upstream.sql": dynamic_table_upstream_sql,
            "dt_downstream.sql": dynamic_table_downstream_sql,
            "schema.yml": upstream_schema_yml,
        }

    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"name": "dt_pipeline_test"}

    @pytest.fixture(scope="class", autouse=True)
    def clean_up(self, project):
        yield
        with project.adapter.connection_named("__test"):
            relation = project.adapter.Relation.create(
                database=project.database, schema=project.test_schema
            )
            project.adapter.drop_schema(relation)

    def test_pipeline_cascade_refresh(self, project):
        """上游变更 → 刷新上游 → 刷新下游 → 下游聚合结果正确"""
        schema = project.test_schema
        db = project.database

        # Use int amount to avoid Lakehouse optimizer bug CZLH-66000
        # ("bad integral cast decimal(20,2) to i" when aggregating decimal in DT-on-DT)
        project.run_sql(
            f"create table if not exists {db}.{schema}.raw_orders "
            f"(id int, name string, amount int)"
        )
        project.run_sql(
            f"insert into {db}.{schema}.raw_orders values "
            f"(1, 'Alice', 100), (2, 'Alice', 200), (3, 'Bob', 300)"
        )

        run_dbt(["run"])

        upstream = relation_from_name(project.adapter, "dt_upstream")
        downstream = relation_from_name(project.adapter, "dt_downstream")

        # 初始聚合：Alice=300, Bob=300
        alice_total = project.run_sql(
            f"select total_amount from {downstream} where name = 'Alice'", fetch="one"
        )[0]
        assert int(alice_total) == 300, f"expected Alice total=300, got {alice_total}"

        # 上游新增一行 Alice
        project.run_sql(
            f"insert into {db}.{schema}.raw_orders values (4, 'Alice', 500)"
        )

        # 级联刷新：先上游，再下游
        project.run_sql(f"refresh dynamic table {upstream}")
        project.run_sql(f"refresh dynamic table {downstream}")

        alice_total = project.run_sql(
            f"select total_amount from {downstream} where name = 'Alice'", fetch="one"
        )[0]
        assert int(alice_total) == 800, f"expected Alice total=800 after cascade refresh, got {alice_total}"

        alice_count = project.run_sql(
            f"select order_count from {downstream} where name = 'Alice'", fetch="one"
        )[0]
        assert int(alice_count) == 3, f"expected Alice order_count=3, got {alice_count}"


class TestDynamicTableDownstream:
    """
    Verify cascade refresh in a two-layer DT pipeline.

    Note: ClickZetta does NOT support refresh_interval='DOWNSTREAM' (Snowflake-specific syntax).
    Both layers use a fixed refresh_interval. The cascade behavior is verified by
    manually refreshing the downstream DT and confirming it reflects upstream changes.
    """

    # Intermediate layer: fixed interval (DOWNSTREAM not supported in ClickZetta)
    _dt_intermediate_sql = """
{{ config(
    materialized='dynamic_table',
    refresh_interval='1 minutes',
    refresh_vc='default_ap'
) }}
select id, name, amount * 2 as doubled_amount
from {{ source('raw', 'raw_source') }}
"""

    # Downstream layer: fixed interval, reads from intermediate
    _dt_downstream_sql = """
{{ config(
    materialized='dynamic_table',
    refresh_interval='1 minutes',
    refresh_vc='default_ap'
) }}
select name, sum(doubled_amount) as total
from {{ ref('dt_intermediate') }}
group by name
"""

    _schema_yml = """
version: 2
sources:
  - name: raw
    schema: "{{ target.schema }}"
    tables:
      - name: raw_source
"""

    @pytest.fixture(scope="class")
    def models(self):
        return {
            "dt_intermediate.sql": self._dt_intermediate_sql,
            "dt_downstream.sql": self._dt_downstream_sql,
            "schema.yml": self._schema_yml,
        }

    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"name": "dt_downstream_test"}

    @pytest.fixture(scope="class", autouse=True)
    def clean_up(self, project):
        yield
        with project.adapter.connection_named("__test"):
            relation = project.adapter.Relation.create(
                database=project.database, schema=project.test_schema
            )
            project.adapter.drop_schema(relation)

    def test_downstream_refresh_propagates(self, project):
        """
        Two-layer DT pipeline: intermediate → downstream aggregation.

        ClickZetta manual REFRESH behavior:
        - REFRESH DYNAMIC TABLE only refreshes the specified table, NOT its upstream dependencies.
        - To propagate upstream changes through a pipeline, each layer must be refreshed
          in dependency order: intermediate first, then downstream.

        This test verifies:
        1. Initial data flows correctly through the pipeline
        2. After upstream change, refreshing intermediate then downstream gives correct results
        """
        schema = project.test_schema
        db = project.database

        project.run_sql(
            f"create table if not exists {db}.{schema}.raw_source "
            f"(id int, name string, amount int)"
        )
        project.run_sql(
            f"insert into {db}.{schema}.raw_source values "
            f"(1, 'Alice', 10), (2, 'Alice', 20), (3, 'Bob', 30)"
        )

        run_dbt(["run"])

        intermediate = relation_from_name(project.adapter, "dt_intermediate")
        downstream = relation_from_name(project.adapter, "dt_downstream")

        # Initial state: Alice doubled = (10+20)*2 = 60, Bob doubled = 30*2 = 60
        alice_total = project.run_sql(
            f"select total from {downstream} where name = 'Alice'", fetch="one"
        )[0]
        assert int(alice_total) == 60, f"expected Alice total=60 initially, got {alice_total}"

        # Upstream change: add a new Alice row (amount=50)
        project.run_sql(
            f"insert into {db}.{schema}.raw_source values (4, 'Alice', 50)"
        )

        # Must refresh in dependency order: intermediate first, then downstream
        # (REFRESH does NOT cascade automatically in ClickZetta)
        project.run_sql(f"refresh dynamic table {intermediate}")
        project.run_sql(f"refresh dynamic table {downstream}")

        alice_total = project.run_sql(
            f"select total from {downstream} where name = 'Alice'", fetch="one"
        )[0]
        # Alice: (10+20+50)*2 = 160
        assert int(alice_total) == 160, (
            f"expected Alice total=160 after ordered refresh (intermediate→downstream), got {alice_total}"
        )


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

        n = project.run_sql(f"select count(*) from {relation}", fetch="one")[0]
        assert n == 3, f"expected 3 rows, got {n}"

        alice = project.run_sql(
            f"select amount_doubled from {relation} where id = 1", fetch="one"
        )[0]
        assert int(alice) == 200, f"expected amount_doubled=200 for Alice, got {alice}"

        results = run_dbt(["run", "--full-refresh"])
        assert len(results) == 1
        assert results[0].status == "success"

        n = project.run_sql(f"select count(*) from {relation}", fetch="one")[0]
        assert n == 3, f"expected 3 rows after full_refresh, got {n}"
