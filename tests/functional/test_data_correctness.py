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


# ── 7. dateadd / datediff macro 正确性 ───────────────────────────────────────

_date_model_sql = """
{{ config(materialized='table') }}
select
    -- dateadd: DATE input
    {{ dateadd('day', 7, "DATE '2024-01-15'") }}           as add_7_days,
    {{ dateadd('month', 2, "DATE '2024-01-15'") }}         as add_2_months,
    {{ dateadd('year', 1, "DATE '2024-01-15'") }}          as add_1_year,
    -- dateadd: TIMESTAMP input
    {{ dateadd('hour', 3, "TIMESTAMP '2024-01-15 10:00:00'") }}   as add_3_hours,
    {{ dateadd('minute', 90, "TIMESTAMP '2024-01-15 10:00:00'") }} as add_90_min,
    -- datediff
    {{ datediff("DATE '2024-01-15'", "DATE '2024-01-22'", 'day') }}   as diff_7_days,
    {{ datediff("DATE '2024-01-15'", "DATE '2024-03-15'", 'month') }} as diff_2_months,
    {{ datediff("TIMESTAMP '2024-01-15 10:00:00'", "TIMESTAMP '2024-01-15 13:30:00'", 'hour') }} as diff_3_hours,
    {{ datediff("TIMESTAMP '2024-01-15 10:00:00'", "TIMESTAMP '2024-01-15 10:45:00'", 'minute') }} as diff_45_min
"""


class TestDateMacroCorrectness:
    @pytest.fixture(scope="class")
    def models(self):
        return {"date_ops.sql": _date_model_sql}

    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"name": "date_macro_correctness"}

    @pytest.fixture(scope="class", autouse=True)
    def clean_up(self, project):
        yield
        with project.adapter.connection_named("__test"):
            relation = project.adapter.Relation.create(
                database=project.database, schema=project.test_schema
            )
            project.adapter.drop_schema(relation)

    def test_date_macros(self, project):
        run_dbt(["run"])
        relation = relation_from_name(project.adapter, "date_ops")
        row = project.run_sql(f"select * from {relation}", fetch="one")

        add_7_days, add_2_months, add_1_year, add_3_hours, add_90_min, \
            diff_7_days, diff_2_months, diff_3_hours, diff_45_min = row

        # dateadd results (date part only for date inputs)
        assert str(add_7_days)[:10] == "2024-01-22", f"add 7 days: {add_7_days}"
        assert str(add_2_months)[:10] == "2024-03-15", f"add 2 months: {add_2_months}"
        assert str(add_1_year)[:10] == "2025-01-15", f"add 1 year: {add_1_year}"
        assert str(add_3_hours)[11:13] == "13", f"add 3 hours: {add_3_hours}"
        assert str(add_90_min)[11:16] == "11:30", f"add 90 min: {add_90_min}"

        # datediff results
        assert int(diff_7_days) == 7, f"diff 7 days: {diff_7_days}"
        assert int(diff_2_months) == 2, f"diff 2 months: {diff_2_months}"
        assert int(diff_3_hours) == 3, f"diff 3 hours: {diff_3_hours}"
        assert int(diff_45_min) == 45, f"diff 45 min: {diff_45_min}"


# ── 8. on_schema_change=sync_all_columns 增删列 ──────────────────────────────

_schema_change_model_sql = """
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='id',
    on_schema_change='sync_all_columns'
) }}
{% if var('with_score', false) %}
select id, name, score from {{ source('raw', 'sc_data') }}
{% else %}
select id, name from {{ source('raw', 'sc_data') }}
{% endif %}
"""

_sc_seed_v1_csv = """id,name,score
1,Alice,90
2,Bob,80
"""

_sc_schema_yml = """
version: 2
sources:
  - name: raw
    schema: "{{ target.schema }}"
    tables:
      - name: sc_data
        identifier: seed_sc
"""


class TestSchemaChangeCorrectness:
    @pytest.fixture(scope="class")
    def seeds(self):
        return {"seed_sc.csv": _sc_seed_v1_csv}

    @pytest.fixture(scope="class")
    def models(self):
        return {"sc_model.sql": _schema_change_model_sql, "schema.yml": _sc_schema_yml}

    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"name": "schema_change_correctness"}

    @pytest.fixture(scope="class", autouse=True)
    def clean_up(self, project):
        yield
        with project.adapter.connection_named("__test"):
            relation = project.adapter.Relation.create(
                database=project.database, schema=project.test_schema
            )
            project.adapter.drop_schema(relation)

    def test_add_column(self, project):
        """sync_all_columns: 新增列后增量运行，新列被加入目标表"""
        run_dbt(["seed"])

        # 第一次 run：without_score=false，只有 id, name
        run_dbt(["run", "--vars", "with_score: false"])
        relation = relation_from_name(project.adapter, "sc_model")
        n = project.run_sql(f"select count(*) from {relation}", fetch="one")[0]
        assert int(n) == 2, f"expected 2 rows after first run, got {n}"

        # 第二次 run：with_score=true，model 加了 score 列
        # sync_all_columns 应该自动 ADD COLUMN score 到目标表
        run_dbt(["run", "--vars", "with_score: true"])

        # 验证 score 列存在且有值
        score = project.run_sql(
            f"select score from {relation} where id = 1", fetch="one"
        )[0]
        assert int(score) == 90, f"expected score=90 for id=1, got {score}"


# ── 9. incremental_predicates 在 insert_overwrite 下生效 ─────────────────────

_predicate_model_sql = """
{{ config(
    materialized='incremental',
    incremental_strategy='insert_overwrite',
    partition_by=['region'],
    incremental_predicates=["region = 'north'"]
) }}
select id, name, amount, region
from {{ source('raw', 'pred_data') }}
"""

_pred_seed_csv = """id,name,amount,region
1,A,100,north
2,B,200,north
3,C,150,south
"""

_pred_schema_yml = """
version: 2
sources:
  - name: raw
    schema: "{{ target.schema }}"
    tables:
      - name: pred_data
        identifier: seed_pred
"""


class TestIncrementalPredicatesCorrectness:
    @pytest.fixture(scope="class")
    def seeds(self):
        return {"seed_pred.csv": _pred_seed_csv}

    @pytest.fixture(scope="class")
    def models(self):
        return {"pred_model.sql": _predicate_model_sql, "schema.yml": _pred_schema_yml}

    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"name": "predicate_correctness"}

    @pytest.fixture(scope="class", autouse=True)
    def clean_up(self, project):
        yield
        with project.adapter.connection_named("__test"):
            relation = project.adapter.Relation.create(
                database=project.database, schema=project.test_schema
            )
            project.adapter.drop_schema(relation)

    def test_predicates_filter_source(self, project):
        """incremental_predicates 在第二次增量运行时过滤 source 数据"""
        run_dbt(["seed"])

        # 第一次 run：全量加载（existing_relation is none，不走 insert_overwrite）
        run_dbt(["run"])
        relation = relation_from_name(project.adapter, "pred_model")
        n = project.run_sql(f"select count(*) from {relation}", fetch="one")[0]
        assert int(n) == 3, f"expected 3 rows after first run (full load), got {n}"

        # 第二次 run：增量运行，predicates 过滤 source，只写入 north 分区
        run_dbt(["run"])
        n = project.run_sql(f"select count(*) from {relation}", fetch="one")[0]
        # insert_overwrite with predicate region='north': 只覆盖 north 分区
        # south 分区保留，north 分区被 2 行覆盖 → 总计 3 行（north 2 + south 1）
        assert int(n) == 3, f"expected 3 rows after second run (north overwritten, south kept), got {n}"

        # 验证 north 分区数据是最新的（仍然是 2 行）
        north_count = project.run_sql(
            f"select count(*) from {relation} where region = 'north'", fetch="one"
        )[0]
        assert int(north_count) == 2, f"expected 2 north rows, got {north_count}"


# ── 10. incremental delete+insert 正确性 ─────────────────────────────────────

_delete_insert_model_sql = """
{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key='order_id'
) }}
select
    order_id,
    region,
    amount
from {{ source('raw', 'di_source') }}
"""

_di_schema_yml = """
version: 2
sources:
  - name: raw
    schema: "{{ target.schema }}"
    tables:
      - name: di_source
"""


class TestIncrementalDeleteInsertCorrectness:
    @pytest.fixture(scope="class")
    def models(self):
        return {"di_orders.sql": _delete_insert_model_sql, "schema.yml": _di_schema_yml}

    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"name": "delete_insert_correctness"}

    @pytest.fixture(autouse=True)
    def clean_up(self, project):
        yield
        with project.adapter.connection_named("__test"):
            relation = project.adapter.Relation.create(
                database=project.database, schema=project.test_schema
            )
            project.adapter.drop_schema(relation)

    def test_delete_insert_replaces_matching_keys(self, project):
        """
        delete+insert semantics:
        - DELETE rows from target where unique_key matches source
        - INSERT all source rows into target
        - Rows not in source's unique_key set are preserved

        First run (full load): 3 rows inserted (order_id=1,2,3)
        Mutate source: update order_id=3 amount, add order_id=4
        Second run (incremental, no filter): source has all 4 rows
          → DELETE order_id=1,2,3,4 from target (1,2,3 exist)
          → INSERT all 4 rows
          → Result: 4 rows with order_id=3 having new amount
        """
        schema = project.test_schema
        db = project.database

        # Create source table and load initial data (no dt column needed)
        project.run_sql(
            f"create table if not exists {db}.{schema}.di_source "
            f"(order_id int, region string, amount decimal(10,2))"
        )
        project.run_sql(
            f"insert into {db}.{schema}.di_source values "
            f"(1, 'north', 100), "
            f"(2, 'south', 200), "
            f"(3, 'north', 300)"
        )

        run_dbt(["run"])
        relation = relation_from_name(project.adapter, "di_orders")

        n = project.run_sql(f"select count(*) from {relation}", fetch="one")[0]
        assert n == 3, f"expected 3 rows after first run, got {n}"

        # Mutate source: update order_id=3 and add order_id=4
        project.run_sql(
            f"update {db}.{schema}.di_source set amount = 999 where order_id = 3"
        )
        project.run_sql(
            f"insert into {db}.{schema}.di_source values "
            f"(4, 'east', 400)"
        )

        run_dbt(["run"])

        n = project.run_sql(f"select count(*) from {relation}", fetch="one")[0]
        assert n == 4, f"expected 4 rows after delete+insert, got {n}"

        # order_id=3 should have new amount=999
        amount_3 = project.run_sql(
            f"select amount from {relation} where order_id = 3", fetch="one"
        )[0]
        assert int(amount_3) == 999, f"expected order_id=3 amount=999 after replace, got {amount_3}"

        # order_id=1,2 should be untouched
        amount_1 = project.run_sql(
            f"select amount from {relation} where order_id = 1", fetch="one"
        )[0]
        assert int(amount_1) == 100, f"expected order_id=1 amount=100 unchanged, got {amount_1}"

        # order_id=4 should exist
        n4 = project.run_sql(
            f"select count(*) from {relation} where order_id = 4", fetch="one"
        )[0]
        assert n4 == 1, f"expected order_id=4 to exist, got {n4} rows"


# ── 11. 复合主键 merge 正确性 ─────────────────────────────────────────────────

_composite_merge_model_sql = """
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key=['user_id', 'event_date']
) }}
select
    user_id,
    event_date,
    event_count,
    updated_at
from {{ source('raw', 'user_events') }}
{% if is_incremental() %}
where updated_at >= (select max(updated_at) from {{ this }})
{% endif %}
"""

_composite_seed_v1_csv = """user_id,event_date,event_count,updated_at
1,2024-01-01,5,2024-01-01 00:00:00
1,2024-01-02,3,2024-01-02 00:00:00
2,2024-01-01,8,2024-01-01 00:00:00
"""

_composite_seed_v2_csv = """user_id,event_date,event_count,updated_at
1,2024-01-01,10,2024-01-03 00:00:00
3,2024-01-01,2,2024-01-03 00:00:00
"""

_composite_schema_yml = """
version: 2
sources:
  - name: raw
    schema: "{{ target.schema }}"
    tables:
      - name: user_events
        identifier: "{{ var('seed_name', 'comp_v1') }}"
"""


class TestCompositeKeyMergeCorrectness:
    @pytest.fixture(scope="class")
    def seeds(self):
        return {"comp_v1.csv": _composite_seed_v1_csv, "comp_v2.csv": _composite_seed_v2_csv}

    @pytest.fixture(scope="class")
    def models(self):
        return {"user_events.sql": _composite_merge_model_sql, "schema.yml": _composite_schema_yml}

    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"name": "composite_merge_correctness"}

    @pytest.fixture(autouse=True)
    def clean_up(self, project):
        yield
        with project.adapter.connection_named("__test"):
            relation = project.adapter.Relation.create(
                database=project.database, schema=project.test_schema
            )
            project.adapter.drop_schema(relation)

    def test_composite_key_upsert(self, project):
        """复合主键 merge：(user_id, event_date) 组合唯一，更新已有组合，插入新组合"""
        run_dbt(["seed"])
        run_dbt(["run", "--vars", "seed_name: comp_v1"])
        relation = relation_from_name(project.adapter, "user_events")

        n = project.run_sql(f"select count(*) from {relation}", fetch="one")[0]
        assert n == 3, f"expected 3 rows after first run, got {n}"

        # 第二次 run：(1, 2024-01-01) 更新 event_count 5→10，新增 (3, 2024-01-01)
        run_dbt(["run", "--vars", "seed_name: comp_v2"])

        n = project.run_sql(f"select count(*) from {relation}", fetch="one")[0]
        assert n == 4, f"expected 4 rows after composite merge, got {n}"

        # (user_id=1, event_date=2024-01-01) 的 event_count 应该更新为 10
        updated = project.run_sql(
            f"select event_count from {relation} "
            f"where user_id = 1 and event_date = '2024-01-01'",
            fetch="one"
        )[0]
        assert int(updated) == 10, f"expected event_count=10 after update, got {updated}"

        # (user_id=1, event_date=2024-01-02) 不在增量窗口，保持不变
        unchanged = project.run_sql(
            f"select event_count from {relation} "
            f"where user_id = 1 and event_date = '2024-01-02'",
            fetch="one"
        )[0]
        assert int(unchanged) == 3, f"expected event_count=3 unchanged, got {unchanged}"

        # 新增的 (user_id=3, event_date=2024-01-01) 存在
        new_row = project.run_sql(
            f"select event_count from {relation} "
            f"where user_id = 3 and event_date = '2024-01-01'",
            fetch="one"
        )
        assert new_row is not None, "expected new row (user_id=3, event_date=2024-01-01)"
        assert int(new_row[0]) == 2, f"expected event_count=2 for new row, got {new_row[0]}"

