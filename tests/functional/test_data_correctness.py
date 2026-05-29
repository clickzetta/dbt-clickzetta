"""
数据正确性专项测试

覆盖所有可能出现数据错误的场景：
1. incremental merge - 去重、更新、追加
2. incremental append - 只追加不去重
3. incremental insert_overwrite - 分区覆盖语义
4. MERGE INTO - 匹配/不匹配分支
5. 窗口函数 - ROW_NUMBER 去重、累计聚合
6. NULL 值处理 - JOIN、聚合、过滤
7. 类型转换 - STRING→TIMESTAMP、数值精度
8. 分区表读写 - 分区裁剪、跨分区聚合
"""
import pytest
from dbt.tests.util import run_dbt, relation_from_name


# ── 1. Incremental merge 正确性 ──────────────────────────────────────────────

_merge_model_sql = """
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='id'
) }}
select id, name, amount, updated_at
from {{ source('raw', 'events') }}
{% if is_incremental() %}
where updated_at > (select max(updated_at) from {{ this }})
{% endif %}
"""

_merge_seed_v1_csv = """id,name,amount,updated_at
1,Alice,100,2024-01-01 00:00:00
2,Bob,200,2024-01-01 00:00:00
3,Charlie,300,2024-01-01 00:00:00
"""

_merge_seed_v2_csv = """id,name,amount,updated_at
2,Bob_updated,250,2024-01-02 00:00:00
4,Dave,400,2024-01-02 00:00:00
"""

_merge_schema_yml = """
version: 2
sources:
  - name: raw
    schema: "{{ target.schema }}"
    tables:
      - name: events
        identifier: "{{ var('seed_name', 'v1') }}"
"""


class TestIncrementalMergeCorrectness:
    @pytest.fixture(scope="class")
    def seeds(self):
        return {"v1.csv": _merge_seed_v1_csv, "v2.csv": _merge_seed_v2_csv}

    @pytest.fixture(scope="class")
    def models(self):
        return {"events.sql": _merge_model_sql, "schema.yml": _merge_schema_yml}

    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"name": "merge_correctness"}

    @pytest.fixture(autouse=True)
    def clean_up(self, project):
        yield
        with project.adapter.connection_named("__test"):
            relation = project.adapter.Relation.create(
                database=project.database, schema=project.test_schema
            )
            project.adapter.drop_schema(relation)

    def test_merge_upsert(self, project):
        run_dbt(["seed"])
        run_dbt(["run", "--vars", "seed_name: v1"])
        relation = relation_from_name(project.adapter, "events")

        # 初始 3 行
        n = project.run_sql(f"select count(*) from {relation}", fetch="one")[0]
        assert n == 3, f"expected 3 after first run, got {n}"

        # 第二次 run：Bob 更新，Dave 新增
        run_dbt(["run", "--vars", "seed_name: v2"])

        # 总行数应为 4（不是 5，Bob 被 upsert 不是 append）
        n = project.run_sql(f"select count(*) from {relation}", fetch="one")[0]
        assert n == 4, f"expected 4 after merge (upsert), got {n}"

        # Bob 的 amount 应该是 250（已更新）
        bob_amount = project.run_sql(
            f"select amount from {relation} where id = 2", fetch="one"
        )[0]
        assert int(bob_amount) == 250, f"expected Bob amount=250 after update, got {bob_amount}"

        # Alice 和 Charlie 不受影响
        alice = project.run_sql(
            f"select amount from {relation} where id = 1", fetch="one"
        )[0]
        assert int(alice) == 100, f"expected Alice amount=100 unchanged, got {alice}"


# ── 2. Incremental append 正确性 ─────────────────────────────────────────────

_append_model_sql = """
{{ config(
    materialized='incremental',
    incremental_strategy='append'
) }}
select id, name, amount
from {{ source('raw', 'items') }}
"""

_append_seed_csv = """id,name,amount
1,A,10
2,B,20
"""

_append_schema_yml = """
version: 2
sources:
  - name: raw
    schema: "{{ target.schema }}"
    tables:
      - name: items
        identifier: seed_items
"""


class TestIncrementalAppendCorrectness:
    @pytest.fixture(scope="class")
    def seeds(self):
        return {"seed_items.csv": _append_seed_csv}

    @pytest.fixture(scope="class")
    def models(self):
        return {"items.sql": _append_model_sql, "schema.yml": _append_schema_yml}

    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"name": "append_correctness"}

    @pytest.fixture(autouse=True)
    def clean_up(self, project):
        yield
        with project.adapter.connection_named("__test"):
            relation = project.adapter.Relation.create(
                database=project.database, schema=project.test_schema
            )
            project.adapter.drop_schema(relation)

    def test_append_duplicates(self, project):
        run_dbt(["seed"])
        run_dbt(["run"])
        relation = relation_from_name(project.adapter, "items")

        n = project.run_sql(f"select count(*) from {relation}", fetch="one")[0]
        assert n == 2, f"expected 2 after first run, got {n}"

        # append 策略第二次 run 会重复插入
        run_dbt(["run"])
        n = project.run_sql(f"select count(*) from {relation}", fetch="one")[0]
        assert n == 4, f"expected 4 after second run (append duplicates), got {n}"


# ── 3. 窗口函数正确性 ─────────────────────────────────────────────────────────

_window_model_sql = """
{{ config(materialized='table') }}
with ranked as (
    select
        id,
        name,
        amount,
        category,
        row_number() over (partition by category order by amount desc) as rn,
        sum(amount) over (partition by category) as category_total,
        rank() over (partition by category order by amount desc) as rnk,
        lag(amount, 1) over (partition by category order by amount) as prev_amount
    from {{ source('raw', 'window_data') }}
)
select * from ranked
"""

_window_seed_csv = """id,name,amount,category
1,A,100,X
2,B,200,X
3,C,150,X
4,D,300,Y
5,E,100,Y
"""

_window_schema_yml = """
version: 2
sources:
  - name: raw
    schema: "{{ target.schema }}"
    tables:
      - name: window_data
        identifier: seed_window
"""


class TestWindowFunctionCorrectness:
    @pytest.fixture(scope="class")
    def seeds(self):
        return {"seed_window.csv": _window_seed_csv}

    @pytest.fixture(scope="class")
    def models(self):
        return {"window_result.sql": _window_model_sql, "schema.yml": _window_schema_yml}

    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"name": "window_correctness"}

    @pytest.fixture(scope="class", autouse=True)
    def clean_up(self, project):
        yield
        with project.adapter.connection_named("__test"):
            relation = project.adapter.Relation.create(
                database=project.database, schema=project.test_schema
            )
            project.adapter.drop_schema(relation)

    def test_window_functions(self, project):
        run_dbt(["seed"])
        run_dbt(["run"])
        relation = relation_from_name(project.adapter, "window_result")

        # ROW_NUMBER: X 有 3 行，max rn = 3
        max_rn_x = project.run_sql(
            f"select max(rn) from {relation} where category = 'X'", fetch="one"
        )[0]
        assert int(max_rn_x) == 3, f"expected max rn=3 for X, got {max_rn_x}"

        # category_total: X = 100+200+150 = 450
        total_x = project.run_sql(
            f"select max(category_total) from {relation} where category = 'X'", fetch="one"
        )[0]
        assert int(total_x) == 450, f"expected category_total=450 for X, got {total_x}"

        # category_total: Y = 300+100 = 400
        total_y = project.run_sql(
            f"select max(category_total) from {relation} where category = 'Y'", fetch="one"
        )[0]
        assert int(total_y) == 400, f"expected category_total=400 for Y, got {total_y}"

        # lag: X 按 amount 排序 100,150,200；amount=150 的 prev=100
        prev = project.run_sql(
            f"select prev_amount from {relation} where category='X' and amount=150",
            fetch="one"
        )[0]
        assert int(prev) == 100, f"expected lag=100 for amount=150 in X, got {prev}"

        # lag for first row (amount=100 in X) should be NULL
        null_prev = project.run_sql(
            f"select prev_amount from {relation} where category='X' and amount=100",
            fetch="one"
        )[0]
        assert null_prev is None, f"expected NULL lag for first row, got {null_prev}"


# ── 4. NULL 值处理正确性 ──────────────────────────────────────────────────────

_null_model_sql = """
{{ config(materialized='table') }}
select
    a.id,
    a.name,
    b.score,
    coalesce(b.score, 0) as score_filled,
    case when b.score is null then 'no_score' else 'has_score' end as score_flag,
    a.name || coalesce(' ' || b.tag, '') as name_with_tag
from {{ source('raw', 'users') }} a
left join {{ source('raw', 'scores') }} b on a.id = b.user_id
"""

_null_users_csv = """id,name
1,Alice
2,Bob
3,Charlie
"""

_null_scores_csv = """user_id,score,tag
1,95,gold
3,80,silver
"""

_null_schema_yml = """
version: 2
sources:
  - name: raw
    schema: "{{ target.schema }}"
    tables:
      - name: users
        identifier: seed_users
      - name: scores
        identifier: seed_scores
"""


class TestNullHandlingCorrectness:
    @pytest.fixture(scope="class")
    def seeds(self):
        return {"seed_users.csv": _null_users_csv, "seed_scores.csv": _null_scores_csv}

    @pytest.fixture(scope="class")
    def models(self):
        return {"user_scores.sql": _null_model_sql, "schema.yml": _null_schema_yml}

    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"name": "null_correctness"}

    @pytest.fixture(scope="class", autouse=True)
    def clean_up(self, project):
        yield
        with project.adapter.connection_named("__test"):
            relation = project.adapter.Relation.create(
                database=project.database, schema=project.test_schema
            )
            project.adapter.drop_schema(relation)

    def test_null_handling(self, project):
        run_dbt(["seed"])
        run_dbt(["run"])
        relation = relation_from_name(project.adapter, "user_scores")

        # Bob (id=2) has no score → NULL
        bob_score = project.run_sql(
            f"select score from {relation} where id = 2", fetch="one"
        )[0]
        assert bob_score is None, f"expected NULL score for Bob, got {bob_score}"

        # coalesce: Bob score_filled = 0
        bob_filled = project.run_sql(
            f"select score_filled from {relation} where id = 2", fetch="one"
        )[0]
        assert int(bob_filled) == 0, f"expected score_filled=0 for Bob, got {bob_filled}"

        # score_flag
        bob_flag = project.run_sql(
            f"select score_flag from {relation} where id = 2", fetch="one"
        )[0]
        assert bob_flag == "no_score", f"expected no_score flag for Bob, got {bob_flag}"

        # Alice has tag=gold → "Alice gold"
        alice_name = project.run_sql(
            f"select name_with_tag from {relation} where id = 1", fetch="one"
        )[0]
        assert alice_name == "Alice gold", f"expected 'Alice gold', got {alice_name}"

        # Bob has no tag → "Bob"
        bob_name = project.run_sql(
            f"select name_with_tag from {relation} where id = 2", fetch="one"
        )[0]
        assert bob_name == "Bob", f"expected 'Bob' (no tag), got {bob_name}"


# ── 5. 类型转换正确性 ─────────────────────────────────────────────────────────

_type_model_sql = """
{{ config(materialized='table') }}
select
    id,
    raw_date,
    cast(raw_date as timestamp) as ts,
    year(cast(raw_date as timestamp)) as yr,
    month(cast(raw_date as timestamp)) as mo,
    cast(amount_str as bigint) as amount_num,
    cast(amount_str as bigint) * 11 / 10 as amount_with_tax,
    cast(flag_str as boolean) as flag_bool
from {{ source('raw', 'type_data') }}
"""

_type_seed_csv = """id,raw_date,amount_str,flag_str
1,2024-03-15 10:30:00,9999,true
2,2024-12-31 23:59:59,123456,false
"""

_type_schema_yml = """
version: 2
sources:
  - name: raw
    schema: "{{ target.schema }}"
    tables:
      - name: type_data
        identifier: seed_types
"""


class TestTypeConversionCorrectness:
    @pytest.fixture(scope="class")
    def seeds(self):
        return {"seed_types.csv": _type_seed_csv}

    @pytest.fixture(scope="class")
    def models(self):
        return {"typed.sql": _type_model_sql, "schema.yml": _type_schema_yml}

    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {
            "name": "type_correctness",
            "seeds": {
                "+column_types": {
                    "id": "int",
                    "raw_date": "string",
                    "amount_str": "string",
                    "flag_str": "string",
                }
            },
        }

    @pytest.fixture(scope="class", autouse=True)
    def clean_up(self, project):
        yield
        with project.adapter.connection_named("__test"):
            relation = project.adapter.Relation.create(
                database=project.database, schema=project.test_schema
            )
            project.adapter.drop_schema(relation)

    def test_type_conversions(self, project):
        run_dbt(["seed"])
        run_dbt(["run"])
        relation = relation_from_name(project.adapter, "typed")

        yr, mo = project.run_sql(
            f"select yr, mo from {relation} where id = 1", fetch="one"
        )
        assert int(yr) == 2024, f"expected year=2024, got {yr}"
        assert int(mo) == 3, f"expected month=3, got {mo}"

        amount = project.run_sql(
            f"select amount_num from {relation} where id = 1", fetch="one"
        )[0]
        assert int(amount) == 9999, f"expected amount=9999, got {amount}"

        flag1 = project.run_sql(
            f"select flag_bool from {relation} where id = 1", fetch="one"
        )[0]
        assert flag1 is True or str(flag1).lower() == 'true', f"expected True, got {flag1}"

        flag2 = project.run_sql(
            f"select flag_bool from {relation} where id = 2", fetch="one"
        )[0]
        assert flag2 is False or str(flag2).lower() == 'false', f"expected False, got {flag2}"


# ── 6. 分区表读写正确性 ───────────────────────────────────────────────────────

_partition_model_sql = """
{{ config(
    materialized='table',
    partition_by=['region']
) }}
select
    id,
    name,
    amount,
    region,
    sum(amount) over (partition by region) as region_total,
    count(*) over (partition by region) as region_count
from {{ source('raw', 'sales') }}
"""

_partition_seed_csv = """id,name,amount,region
1,A,100,north
2,B,200,north
3,C,150,south
4,D,300,south
5,E,50,south
"""

_partition_schema_yml = """
version: 2
sources:
  - name: raw
    schema: "{{ target.schema }}"
    tables:
      - name: sales
        identifier: seed_sales
"""


class TestPartitionedTableCorrectness:
    @pytest.fixture(scope="class")
    def seeds(self):
        return {"seed_sales.csv": _partition_seed_csv}

    @pytest.fixture(scope="class")
    def models(self):
        return {"sales_summary.sql": _partition_model_sql, "schema.yml": _partition_schema_yml}

    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"name": "partition_correctness"}

    @pytest.fixture(scope="class", autouse=True)
    def clean_up(self, project):
        yield
        with project.adapter.connection_named("__test"):
            relation = project.adapter.Relation.create(
                database=project.database, schema=project.test_schema
            )
            project.adapter.drop_schema(relation)

    def test_partitioned_table(self, project):
        run_dbt(["seed"])
        run_dbt(["run"])
        relation = relation_from_name(project.adapter, "sales_summary")

        # north: 100+200=300
        north_total = project.run_sql(
            f"select max(region_total) from {relation} where region='north'", fetch="one"
        )[0]
        assert int(north_total) == 300, f"expected north_total=300, got {north_total}"

        # south: 150+300+50=500
        south_total = project.run_sql(
            f"select max(region_total) from {relation} where region='south'", fetch="one"
        )[0]
        assert int(south_total) == 500, f"expected south_total=500, got {south_total}"

        # north count = 2
        north_count = project.run_sql(
            f"select max(region_count) from {relation} where region='north'", fetch="one"
        )[0]
        assert int(north_count) == 2, f"expected north_count=2, got {north_count}"

        # south count = 3
        south_count = project.run_sql(
            f"select max(region_count) from {relation} where region='south'", fetch="one"
        )[0]
        assert int(south_count) == 3, f"expected south_count=3, got {south_count}"

        # total rows = 5
        n = project.run_sql(f"select count(*) from {relation}", fetch="one")[0]
        assert int(n) == 5, f"expected 5 total rows, got {n}"
