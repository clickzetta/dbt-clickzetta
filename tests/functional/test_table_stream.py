import pytest
from dbt.tests.util import run_dbt, relation_from_name


# ── SQL templates ──────────────────────────────────────────────────────────────

# View that reads from a stream source — exercises stream-as-source path
_stream_view_sql = """
{{ config(materialized='view') }}
select
    __change_type,
    __commit_timestamp,
    id,
    name,
    amount
from {{ source('raw', 'orders_stream') }}
"""

# Incremental model that consumes stream via MERGE INTO pattern
_stream_consumer_sql = """
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='id'
) }}
select
    id,
    name,
    amount
from {{ source('raw', 'orders_stream') }}
where __change_type in ('INSERT', 'UPDATE_AFTER')
"""

_schema_yml = """
version: 2
sources:
  - name: raw
    schema: "{{ target.schema }}"
    tables:
      - name: orders_stream
"""


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestTableStreamLifecycle:
    """
    Verify the full Table Stream lifecycle:
    1. Create source table + stream
    2. Stream appears in list_relations (SHOW STREAMS path)
    3. INSERT into source → stream captures changes
    4. drop_relation removes the stream
    """

    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"name": "stream_lifecycle_test"}

    @pytest.fixture(scope="class", autouse=True)
    def clean_up(self, project):
        yield
        with project.adapter.connection_named("__test"):
            relation = project.adapter.Relation.create(
                database=project.database, schema=project.test_schema
            )
            project.adapter.drop_schema(relation)

    def test_stream_create_and_list(self, project):
        """Stream created with correct syntax appears in list_relations."""
        schema = project.test_schema
        db = project.database

        # Create source table with change_tracking enabled
        project.run_sql(
            f"create table if not exists {db}.{schema}.src_orders "
            f"(id int, name string, amount int)"
        )
        project.run_sql(
            f"alter table {db}.{schema}.src_orders "
            f"set properties ('change_tracking' = 'true')"
        )

        # Create stream — this is the syntax that was broken before the fix
        project.run_sql(
            f"create table stream if not exists {db}.{schema}.orders_stream "
            f"on table {db}.{schema}.src_orders "
            f"with properties ('TABLE_STREAM_MODE' = 'STANDARD')"
        )

        # Verify stream appears in list_relations (exercises SHOW STREAMS path in impl.py)
        with project.adapter.connection_named("__test"):
            relations = project.adapter.list_relations(
                database=db, schema=schema
            )

        stream_names = [r.identifier for r in relations if r.type and 'stream' in str(r.type).lower()]
        assert 'orders_stream' in stream_names, (
            f"orders_stream not found in list_relations. Found: {stream_names}"
        )

    def test_stream_captures_insert(self, project):
        """INSERT into source table → stream contains the new rows with __change_type=INSERT."""
        schema = project.test_schema
        db = project.database

        project.run_sql(
            f"insert into {db}.{schema}.src_orders values "
            f"(1, 'Alice', 100), (2, 'Bob', 200)"
        )

        # Stream should show the inserts (offset not yet consumed)
        rows = project.run_sql(
            f"select id, __change_type from {db}.{schema}.orders_stream "
            f"order by id",
            fetch="all"
        )
        assert len(rows) == 2, f"expected 2 rows in stream after insert, got {len(rows)}"
        change_types = {r[1] for r in rows}
        assert 'INSERT' in change_types, f"expected INSERT in change_types, got {change_types}"

    def test_stream_captures_update(self, project):
        """UPDATE source row → stream contains UPDATE_BEFORE + UPDATE_AFTER rows."""
        schema = project.test_schema
        db = project.database

        # Consume the previous inserts first (advance offset via DML)
        project.run_sql(
            f"merge into {db}.{schema}.src_orders t "
            f"using (select id, name, amount from {db}.{schema}.orders_stream "
            f"       where __change_type in ('INSERT', 'UPDATE_AFTER')) s "
            f"on t.id = s.id "
            f"when not matched then insert (id, name, amount) values (s.id, s.name, s.amount)"
        )

        # Now update a row — stream should capture the change
        project.run_sql(
            f"update {db}.{schema}.src_orders set amount = 999 where id = 1"
        )

        rows = project.run_sql(
            f"select id, __change_type from {db}.{schema}.orders_stream "
            f"order by id, __change_type",
            fetch="all"
        )
        change_types = {r[1] for r in rows}
        assert 'UPDATE_AFTER' in change_types, (
            f"expected UPDATE_AFTER after update, got {change_types}"
        )

    def test_stream_drop(self, project):
        """drop_relation on a stream removes it from list_relations."""
        schema = project.test_schema
        db = project.database

        with project.adapter.connection_named("__test"):
            stream_rel = project.adapter.Relation.create(
                database=db,
                schema=schema,
                identifier='orders_stream',
                quote_policy=project.adapter.config.quoting,
            )
            # Set type to stream so drop_relation uses DROP STREAM path
            stream_rel = stream_rel.incorporate(type='stream')
            project.adapter.drop_relation(stream_rel)

            relations = project.adapter.list_relations(database=db, schema=schema)

        stream_names = [r.identifier for r in relations if r.type and 'stream' in str(r.type).lower()]
        assert 'orders_stream' not in stream_names, (
            f"orders_stream still in list_relations after drop: {stream_names}"
        )


class TestTableStreamAsSource:
    """
    Verify stream can be used as a dbt source:
    - A view model reading from stream source compiles and runs
    - System columns (__change_type, __commit_timestamp) are accessible
    - An incremental model consuming stream via MERGE advances the offset
    """

    @pytest.fixture(scope="class")
    def models(self):
        return {
            "stream_view.sql": _stream_view_sql,
            "stream_consumer.sql": _stream_consumer_sql,
            "schema.yml": _schema_yml,
        }

    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"name": "stream_source_test"}

    @pytest.fixture(scope="class", autouse=True)
    def clean_up(self, project):
        yield
        with project.adapter.connection_named("__test"):
            relation = project.adapter.Relation.create(
                database=project.database, schema=project.test_schema
            )
            project.adapter.drop_schema(relation)

    @pytest.fixture(autouse=True)
    def setup_stream(self, project):
        """Recreate source table and stream before each test to ensure fresh offset.

        Order matters: INSERT data first, then create stream with SHOW_INITIAL_ROWS=TRUE.
        ClickZetta only shows pre-existing rows via SHOW_INITIAL_ROWS — rows inserted
        after stream creation appear as normal change events (not immediately visible).
        """
        schema = project.test_schema
        db = project.database
        # Drop stream first (depends on table), then drop and recreate table
        project.run_sql(f"drop stream if exists {db}.{schema}.orders_stream")
        project.run_sql(f"drop table if exists {db}.{schema}.src_events")
        project.run_sql(
            f"create table {db}.{schema}.src_events "
            f"(id int, name string, amount int)"
        )
        project.run_sql(
            f"alter table {db}.{schema}.src_events "
            f"set properties ('change_tracking' = 'true')"
        )
        # Insert data BEFORE creating stream — SHOW_INITIAL_ROWS only captures pre-existing rows
        project.run_sql(
            f"insert into {db}.{schema}.src_events values "
            f"(1, 'Alice', 100), (2, 'Bob', 200), (3, 'Charlie', 300)"
        )
        project.run_sql(
            f"create table stream {db}.{schema}.orders_stream "
            f"on table {db}.{schema}.src_events "
            f"with properties ('TABLE_STREAM_MODE' = 'STANDARD', 'SHOW_INITIAL_ROWS' = 'TRUE')"
        )

    def test_stream_view_reads_system_columns(self, project):
        """View model reading from stream source returns __change_type column."""
        results = run_dbt(["run", "--select", "stream_view"])
        assert results[0].status == "success"

        relation = relation_from_name(project.adapter, "stream_view")
        rows = project.run_sql(
            f"select id, __change_type from {relation} order by id",
            fetch="all"
        )
        assert len(rows) == 3, f"expected 3 rows in stream_view, got {len(rows)}"
        change_types = {r[1] for r in rows}
        assert 'INSERT' in change_types, f"expected INSERT rows, got {change_types}"

    def test_stream_consumer_advances_offset(self, project):
        """Incremental model consuming stream via MERGE advances the stream offset."""
        results = run_dbt(["run", "--select", "stream_consumer"])
        assert results[0].status == "success"

        consumer = relation_from_name(project.adapter, "stream_consumer")
        n = project.run_sql(f"select count(*) from {consumer}", fetch="one")[0]
        assert n == 3, f"expected 3 rows in stream_consumer after first run, got {n}"

        # After MERGE consumed the stream, stream should be empty (offset advanced)
        schema = project.test_schema
        db = project.database
        remaining = project.run_sql(
            f"select count(*) from {db}.{schema}.orders_stream",
            fetch="one"
        )[0]
        assert remaining == 0, (
            f"expected stream to be empty after consumption, got {remaining} rows"
        )

    def test_stream_consumer_incremental_new_rows(self, project):
        """After consuming initial rows, new inserts are captured and merged on next run."""
        schema = project.test_schema
        db = project.database

        # First run: consume the 3 initial rows from stream
        run_dbt(["run", "--select", "stream_consumer"])

        consumer = relation_from_name(project.adapter, "stream_consumer")
        n = project.run_sql(f"select count(*) from {consumer}", fetch="one")[0]
        assert n == 3, f"expected 3 rows after first run, got {n}"

        # Insert new row — this is a new change event after stream creation,
        # so it will appear in the stream immediately
        project.run_sql(
            f"insert into {db}.{schema}.src_events values (4, 'Dave', 400)"
        )

        # Verify new row appears in stream before second run
        stream_count = project.run_sql(
            f"select count(*) from {db}.{schema}.orders_stream",
            fetch="one"
        )[0]
        assert stream_count == 1, f"expected 1 new row in stream after insert, got {stream_count}"

        results = run_dbt(["run", "--select", "stream_consumer"])
        assert results[0].status == "success"

        n = project.run_sql(f"select count(*) from {consumer}", fetch="one")[0]
        assert n == 4, f"expected 4 rows after second run with new insert, got {n}"

        dave = project.run_sql(
            f"select amount from {consumer} where id = 4", fetch="one"
        )
        assert dave is not None and int(dave[0]) == 400, (
            f"expected Dave amount=400, got {dave}"
        )
