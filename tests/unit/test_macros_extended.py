"""Tests for ClickZetta adapter macros: drop/rename relation, safe_cast,
incremental strategies (delete+insert), and indexes."""
import unittest
from unittest import mock
import re
import os
from jinja2 import Environment, FileSystemLoader


def _norm(sql):
    """Normalize whitespace for SQL comparison."""
    return re.sub(r"\s+", " ", sql).strip().lower()


def _make_statement_capturer(captured_list):
    """Return a Jinja-compatible statement mock that captures SQL from call blocks."""
    def statement(name, auto_begin=True, fetch_result=False, caller=None):
        if caller is not None:
            sql = caller()
            if sql and sql.strip():
                captured_list.append(_norm(sql))
        # Return empty string so the macro can use the result in string contexts
        return ""
    return statement


class MacroTestBase(unittest.TestCase):
    """Base class providing Jinja environment and SQL rendering helpers."""

    def setUp(self):
        project_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        self.jinja_env = Environment(
            loader=FileSystemLoader(project_path + "/dbt/include/clickzetta/macros"),
            extensions=["jinja2.ext.do"],
        )
        self.config = {}
        self.exceptions = mock.Mock()
        self.exceptions.raise_compiler_error = mock.Mock(side_effect=Exception("compiler error"))
        self.exceptions.raise_database_error = mock.Mock(side_effect=Exception("db error"))

        self.default_context = {
            "validation": mock.Mock(),
            "model": mock.Mock(),
            "exceptions": self.exceptions,
            "config": mock.Mock(),
            "adapter": mock.Mock(),
            "return": lambda r: r,
            "log": mock.Mock(),
        }
        self.default_context["config"].get = lambda key, default=None, **kw: self.config.get(key, default)

    def _get_template(self, filename, extra_ctx=None):
        ctx = dict(self.default_context)
        if extra_ctx:
            ctx.update(extra_ctx)
        return self.jinja_env.get_template(filename, globals=ctx)

    def _make_relation(self, rel_type=None, database="ws", schema="s", identifier="t"):
        rel = mock.Mock()
        rel.type = rel_type
        rel.database = database
        rel.schema = schema
        rel.identifier = identifier
        rel.__str__ = lambda self: (
            f"{database}.{schema}.{identifier}" if database else f"{schema}.{identifier}"
        )
        return rel


class TestSafeCastMacro(MacroTestBase):
    """Tests for clickzetta__safe_cast — strips 'not null' from type."""

    def _safe_cast(self, field, type_str):
        template = self._get_template("adapters.sql")
        result = template.module.clickzetta__safe_cast(field, type_str)
        return _norm(result)

    def test_safe_cast_plain_type(self):
        self.assertEqual(self._safe_cast("myfield", "string"), "cast(myfield as string)")

    def test_safe_cast_removes_not_null_lowercase(self):
        result = self._safe_cast("myfield", "string not null")
        self.assertNotIn("not null", result)
        self.assertIn("cast(myfield as string)", result)

    def test_safe_cast_removes_not_null_uppercase(self):
        result = self._safe_cast("myfield", "STRING NOT NULL")
        self.assertNotIn("not null", result)
        self.assertIn("string", result)

    def test_safe_cast_null_value(self):
        self.assertEqual(self._safe_cast("null", "bigint"), "cast(null as bigint)")

    def test_safe_cast_timestamp_ltz_not_null(self):
        result = self._safe_cast("null", "timestamp_ltz not null")
        self.assertNotIn("not null", result)
        self.assertIn("timestamp_ltz", result)


class TestDropRelationMacro(MacroTestBase):
    """Tests for clickzetta__drop_relation SQL generation.

    drop_relation behavior:
    - Known non-table types (view, dynamic_table, materialized_view, stream):
      issue DROP directly without DB lookup.
    - type=None or type='table': query SHOW TABLES LIKE to discover actual type,
      then issue the correct DROP. This handles dbt unit test fixtures which have
      type='table' but ClickZetta creates them as VIEWs (no temp table support).
    """

    def _drop_sqls(self, rel_type):
        captured = []
        template = self._get_template("adapters.sql", {
            "statement": _make_statement_capturer(captured),
        })
        rel = self._make_relation(rel_type)
        try:
            template.module.clickzetta__drop_relation(rel)
        except Exception:
            pass
        return captured

    def test_drop_view(self):
        sqls = self._drop_sqls("view")
        self.assertTrue(any("drop view if exists" in s for s in sqls), f"Got: {sqls}")

    def test_drop_dynamic_table(self):
        sqls = self._drop_sqls("dynamic_table")
        self.assertTrue(any("drop dynamic table if exists" in s for s in sqls), f"Got: {sqls}")

    def test_drop_materialized_view(self):
        sqls = self._drop_sqls("materialized_view")
        self.assertTrue(any("drop materialized view if exists" in s for s in sqls), f"Got: {sqls}")

    def test_drop_stream(self):
        sqls = self._drop_sqls("stream")
        self.assertTrue(any("drop stream if exists" in s for s in sqls), f"Got: {sqls}")

    def test_drop_table_and_none_require_db_lookup(self):
        """type='table' and type=None both use SHOW TABLES to find actual type.
        Without execute=True context, no SQL is issued (DB lookup skipped).
        The actual DROP is verified by functional tests (full-refresh pipeline)."""
        for rel_type in ["table", None]:
            sqls = self._drop_sqls(rel_type)
            self.assertEqual(sqls, [],
                f"type={rel_type!r}: expected no SQL without execute context, got: {sqls}")

    def test_drop_none_type_requires_db_lookup(self):
        """When type=None, drop_relation uses SHOW TABLES to discover the actual type.
        This path requires a real DB connection and is covered by functional tests.
        Unit test just verifies no SQL is issued without execute=True context."""
        sqls = self._drop_sqls(None)
        # Without execute=True in context, no DROP should be issued
        self.assertEqual(sqls, [], f"Expected no SQL without execute context, got: {sqls}")


class TestRenameRelationMacro(MacroTestBase):
    """Tests for clickzetta__rename_relation SQL generation."""

    def _rename_sqls(self, rel_type):
        captured = []
        template = self._get_template("adapters.sql", {
            "statement": _make_statement_capturer(captured)
        })
        from_rel = self._make_relation(rel_type, identifier="old_t")
        to_rel = self._make_relation(rel_type, identifier="new_t")
        try:
            template.module.clickzetta__rename_relation(from_rel, to_rel)
        except Exception:
            pass
        return captured

    def test_rename_table(self):
        sqls = self._rename_sqls("table")
        self.assertTrue(any("alter table" in s and "rename to" in s for s in sqls), f"Got: {sqls}")

    def test_rename_view(self):
        sqls = self._rename_sqls("view")
        self.assertTrue(any("alter view" in s and "rename to" in s for s in sqls), f"Got: {sqls}")

    def test_rename_dynamic_table(self):
        sqls = self._rename_sqls("dynamic_table")
        self.assertTrue(any("alter dynamic table" in s and "rename to" in s for s in sqls), f"Got: {sqls}")

    def test_rename_materialized_view(self):
        sqls = self._rename_sqls("materialized_view")
        self.assertTrue(any("alter materialized view" in s and "rename to" in s for s in sqls), f"Got: {sqls}")

    def test_rename_stream_raises_error(self):
        self._rename_sqls("stream")
        self.exceptions.raise_compiler_error.assert_called_once()
        msg = self.exceptions.raise_compiler_error.call_args[0][0]
        self.assertIn("cannot be renamed", msg.lower())

    def test_rename_none_type_raises_error(self):
        self._rename_sqls(None)
        self.exceptions.raise_database_error.assert_called_once()
        msg = self.exceptions.raise_database_error.call_args[0][0]
        self.assertIn("blank type", msg.lower())


class TestDeleteInsertStrategy(MacroTestBase):
    """Tests for get_delete_insert_sql incremental strategy."""

    def _make_col(self, name):
        col = mock.Mock()
        col.quoted = f"`{name}`"
        col.name = name
        return col

    def _run(self, src_name, tgt_name, unique_key, predicates=None):
        # Mock adapter.get_columns_in_relation to return column list
        cols = [self._make_col("id"), self._make_col("amount"), self._make_col("status")]
        self.default_context["adapter"].get_columns_in_relation = mock.Mock(return_value=cols)

        template = self._get_template("materializations/incremental/strategies.sql")
        src = mock.Mock()
        src.__str__ = lambda self: src_name
        tgt = mock.Mock()
        tgt.__str__ = lambda self: tgt_name
        result = template.module.get_delete_insert_sql(src, tgt, unique_key, predicates)
        return _norm(result) if result else ""

    def test_single_key_delete(self):
        sql = self._run("src", "tgt", "order_id")
        self.assertIn("delete from tgt", sql)
        self.assertIn("order_id", sql)

    def test_single_key_insert(self):
        sql = self._run("src", "tgt", "order_id")
        self.assertIn("insert into", sql)
        self.assertIn("src", sql)

    def test_composite_key(self):
        sql = self._run("src", "tgt", ["col1", "col2"])
        self.assertIn("col1", sql)
        self.assertIn("col2", sql)
        self.assertIn("delete from tgt", sql)

    def test_no_key_raises_compiler_error(self):
        with self.assertRaises(Exception):
            self._run("src", "tgt", None)
        self.exceptions.raise_compiler_error.assert_called_once()

    def test_with_incremental_predicates(self):
        sql = self._run("src", "tgt", "id", ["dt >= '2024-01-01'"])
        self.assertIn("2024-01-01", sql)


class TestCreateIndexesMacro(MacroTestBase):
    """Tests for clickzetta__create_indexes — bloomfilter, inverted, vector."""

    def _run_indexes(self, indexes, database="ws"):
        captured = []
        self.config["indexes"] = indexes
        template = self._get_template("adapters.sql", {
            "statement": _make_statement_capturer(captured)
        })
        rel = self._make_relation(database=database)
        template.module.clickzetta__create_indexes(rel)
        return captured

    def test_bloomfilter_index(self):
        sqls = self._run_indexes([{"type": "bloomfilter", "columns": ["order_id"]}])
        self.assertTrue(any("create bloomfilter index" in s for s in sqls), f"Got: {sqls}")
        self.assertTrue(any("order_id" in s for s in sqls))

    def test_inverted_index(self):
        sqls = self._run_indexes([{"type": "inverted", "columns": ["status"]}])
        self.assertTrue(any("create inverted index" in s for s in sqls), f"Got: {sqls}")

    def test_inverted_index_with_analyzer(self):
        sqls = self._run_indexes([{"type": "inverted", "columns": ["body"], "analyzer": "unicode"}])
        joined = " ".join(sqls)
        self.assertIn("unicode", joined)

    def test_vector_index(self):
        sqls = self._run_indexes([
            {"type": "vector", "columns": ["embedding"], "distance_function": "cosine_distance"}
        ])
        joined = " ".join(sqls)
        self.assertIn("create vector index", joined)
        self.assertIn("cosine_distance", joined)

    def test_vector_index_with_scalar_type(self):
        sqls = self._run_indexes([
            {"type": "vector", "columns": ["emb"], "distance_function": "l2_distance", "scalar_type": "f32"}
        ])
        joined = " ".join(sqls)
        self.assertIn("f32", joined)

    def test_multiple_columns_creates_multiple_indexes(self):
        sqls = self._run_indexes([{"type": "bloomfilter", "columns": ["col1", "col2"]}])
        bloom_stmts = [s for s in sqls if "create bloomfilter index" in s]
        self.assertEqual(len(bloom_stmts), 2)

    def test_qualified_name_with_database(self):
        sqls = self._run_indexes([{"type": "bloomfilter", "columns": ["id"]}], database="myws")
        joined = " ".join(sqls)
        self.assertIn("myws.s.", joined)

    def test_if_not_exists_clause(self):
        sqls = self._run_indexes([{"type": "bloomfilter", "columns": ["id"]}])
        self.assertTrue(any("if not exists" in s for s in sqls))

    def test_no_indexes_produces_no_statements(self):
        sqls = self._run_indexes([])
        self.assertEqual(sqls, [])


class TestAlterDynamicTableMacro(MacroTestBase):
    """
    clickzetta__alter_dynamic_table was removed — ClickZetta does not support
    ALTER DYNAMIC TABLE for refresh config changes. on_configuration_change='apply'
    uses CREATE OR REPLACE instead. These tests verify replace_dynamic_table_as.
    """

    def _run_replace(self, refresh_interval=None, refresh_vc=None):
        if refresh_interval is not None:
            self.config["refresh_interval"] = refresh_interval
        if refresh_vc is not None:
            self.config["refresh_vc"] = refresh_vc
        template = self._get_template("adapters.sql")
        rel = self._make_relation("dynamic_table")
        result = template.module.clickzetta__replace_dynamic_table_as(rel, "select 1")
        return _norm(result)

    def test_replace_with_interval_only(self):
        sql = self._run_replace(refresh_interval="5 MINUTE")
        self.assertIn("create or replace dynamic table", sql)
        self.assertIn("refresh interval 5 minute", sql)
        self.assertNotIn("vcluster", sql)

    def test_replace_with_interval_and_vc(self):
        sql = self._run_replace(refresh_interval="10 MINUTE", refresh_vc="default")
        self.assertIn("create or replace dynamic table", sql)
        self.assertIn("refresh interval 10 minute", sql)
        self.assertIn("vcluster default", sql)

    def test_replace_without_interval(self):
        sql = self._run_replace()
        self.assertIn("create or replace dynamic table", sql)
        self.assertNotIn("refresh interval", sql)

    def test_replace_relation_name_included(self):
        sql = self._run_replace(refresh_interval="1 MINUTE")
        self.assertIn("ws.s.t", sql)


class TestQueryCommentMacro(MacroTestBase):
    """Tests for clickzetta__query_comment — JSON metadata injection."""

    def _run_query_comment(self, node=None):
        template = self._get_template("adapters.sql", {
            "dbt_version": "1.8.0",
            "target": {"name": "dev", "profile_name": "my_project"},
            "tojson": __import__("json").dumps,
        })
        result = template.module.clickzetta__query_comment(node)
        import json
        return json.loads(result.strip())

    def test_comment_contains_app_field(self):
        data = self._run_query_comment()
        self.assertEqual(data["app"], "dbt")

    def test_comment_contains_dbt_version(self):
        data = self._run_query_comment()
        self.assertEqual(data["dbt_version"], "1.8.0")

    def test_comment_contains_target_name(self):
        data = self._run_query_comment()
        self.assertEqual(data["target_name"], "dev")

    def test_comment_with_model_node(self):
        node = mock.Mock()
        node.unique_id = "model.my_project.orders"
        node.name = "orders"
        node.resource_type = "model"
        node.config = mock.Mock()
        node.config.get = lambda k, default=None: "table" if k == "materialized" else default
        data = self._run_query_comment(node)
        self.assertEqual(data["node_id"], "model.my_project.orders")
        self.assertEqual(data["node_name"], "orders")
        self.assertEqual(data["materialized"], "table")

    def test_comment_with_none_node(self):
        # node=None should still produce valid JSON with app field
        data = self._run_query_comment(node=None)
        self.assertEqual(data["app"], "dbt")
        self.assertNotIn("node_id", data)

    def test_comment_is_valid_json(self):
        import json
        template = self._get_template("adapters.sql", {
            "dbt_version": "1.8.0",
            "target": {"name": "prod", "profile_name": "proj"},
            "tojson": json.dumps,
        })
        result = template.module.clickzetta__query_comment(None)
        # Must not raise
        parsed = json.loads(result.strip())
        self.assertIsInstance(parsed, dict)


class TestQueryTagCredentials(unittest.TestCase):
    """Tests for query_tag field in ClickZettaCredentials."""

    def _make_credentials(self, **kwargs):
        from dbt.adapters.clickzetta.connections import ClickZettaCredentials
        defaults = dict(
            workspace="ws",
            instance="inst",
            service="svc",
            username="user",
            password="pass",
            schema="public",
            vcluster="default",
        )
        defaults.update(kwargs)
        return ClickZettaCredentials(**defaults)

    def test_query_tag_defaults_to_none(self):
        creds = self._make_credentials()
        self.assertIsNone(creds.query_tag)

    def test_query_tag_can_be_set(self):
        creds = self._make_credentials(query_tag="dbt_prod")
        self.assertEqual(creds.query_tag, "dbt_prod")

    def test_query_tag_in_connection_keys(self):
        creds = self._make_credentials()
        self.assertIn("query_tag", creds._connection_keys())

    def test_query_tag_with_special_chars(self):
        # Single quotes in tag must be handled (escaped in SET statement)
        creds = self._make_credentials(query_tag="dbt's tag")
        self.assertEqual(creds.query_tag, "dbt's tag")


if __name__ == "__main__":
    unittest.main()
