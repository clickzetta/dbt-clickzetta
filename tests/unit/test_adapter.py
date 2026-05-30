import unittest
from unittest import mock
import multiprocessing

import agate
import dbt.flags as flags
from dbt.exceptions import DbtRuntimeError
from agate import Row
from dbt.adapters.clickzetta import ClickZettaAdapter, ClickZettaRelation
from dbt.adapters.clickzetta.relation import ClickZettaRelationType
from .utils import config_from_parts_or_dicts
import sqlparse

MP_CONTEXT = multiprocessing.get_context("spawn")


class TestClickZettaAdapter(unittest.TestCase):
    def setUp(self):
        flags.STRICT_MODE = False

        self.project_cfg = {
            "name": "X",
            "version": "0.0.1",
            "profile": "test",
            "project-root": "/tmp/dbt/does-not-exist",
            "quoting": {
                "identifier": False,
                "schema": False,
            },
            "config-version": 2,
        }

    def _get_target_http(self, project):
        return config_from_parts_or_dicts(
            project,
            {
                "outputs": {
                    "test": {
                        "type": "clickzetta",
                        "service": "cn-shanghai-alicloud.api.clickzetta.com",
                        "workspace": "test_workspace",
                        "instance": "test_instance",
                        "vcluster": "default_ap",
                        "username": "test_user",
                        "schema": "dbt",
                        "password": "test_password",
                        "split_size": 8 * 1024 * 1024,
                    }
                },
                "target": "test",
            },
        )

    def _make_relation(self, rel_type, database="ws", schema="s", identifier="t"):
        return ClickZettaRelation.create(
            database=database, schema=schema, identifier=identifier, type=rel_type
        )

    # --- parse_describe_extended ---

    def test_parse_relation(self):
        self.maxDiff = None
        rel_type = ClickZettaRelation.get_relation_type.Table

        relation = ClickZettaRelation.create(
            schema="dbt", identifier="dbt_able", type=rel_type
        )
        assert relation.database is None

        plain_rows = [
            ("col1", "decimal(19,0)"),
            ("col2", "string"),
            ("dt", "date"),
            ("col3", "string"),
            ("col4", "int32"),
            ("col5", "int64"),
            ("col6", "float32"),
            ("col7", "bool"),
            ("col8", "timestamp"),
            ("col9", "varchar(30)"),
            ("col10", "char(23)"),
        ]

        input_cols = [Row(keys=["column_name", "data_type"], values=r) for r in plain_rows]

        config = self._get_target_http(self.project_cfg)
        rows = ClickZettaAdapter(config, MP_CONTEXT).parse_describe_extended(relation, input_cols)
        self.assertEqual(len(rows), 11)
        self.assertEqual(rows[0].to_column_dict(omit_none=False)["column"], "col1")
        self.assertEqual(rows[0].to_column_dict(omit_none=False)["dtype"], "decimal(19,0)")
        self.assertEqual(rows[8].to_column_dict(omit_none=False)["column"], "col8")
        self.assertEqual(rows[8].to_column_dict(omit_none=False)["dtype"], "timestamp")

    def test_parse_relation_filters_system_columns(self):
        """parse_describe_extended filters __ prefixed stream system columns."""
        relation = ClickZettaRelation.create(schema="s", identifier="t")
        rows_with_system = [
            ("__change_type", "string not null"),
            ("__commit_version", "bigint"),
            ("id", "bigint"),
            ("name", "string"),
        ]
        input_cols = [Row(keys=["column_name", "data_type"], values=r) for r in rows_with_system]
        config = self._get_target_http(self.project_cfg)
        result = ClickZettaAdapter(config, MP_CONTEXT).parse_describe_extended(relation, input_cols)
        col_names = [r.column for r in result]
        self.assertNotIn("__change_type", col_names)
        self.assertNotIn("__commit_version", col_names)
        self.assertIn("id", col_names)
        self.assertIn("name", col_names)

    # --- relation rendering ---

    def test_relation_with_database(self):
        config = self._get_target_http(self.project_cfg)
        adapter = ClickZettaAdapter(config, MP_CONTEXT)
        rel = adapter.Relation.create(schema="dbt", identifier="dbt_table_1")
        self.assertEqual(rel.render(), "dbt.dbt_table_1")
        rel_with_db = adapter.Relation.create(database="db", schema="dbt", identifier="dbt_table_1")
        self.assertIn("db.", rel_with_db.render())
        self.assertEqual(rel_with_db.render(), "db.dbt.dbt_table_1")

    # --- relation type consistency ---

    def test_relation_type_consistency(self):
        for t in [
            ClickZettaRelationType.Table,
            ClickZettaRelationType.View,
            ClickZettaRelationType.DynamicTable,
            ClickZettaRelationType.MaterializedView,
            ClickZettaRelationType.Stream,
        ]:
            rel = ClickZettaRelation.create(schema="s", identifier="t", type=t)
            self.assertEqual(rel.type, t)
            self.assertEqual(rel.type, str(t))

    # --- generate_database_name ---

    def test_generate_database_name_macro_logic(self):
        def generate_database_name(custom_database_name, target_database):
            if custom_database_name is not None:
                return custom_database_name.strip()
            return target_database.strip()

        self.assertEqual(generate_database_name(None, "quick_start"), "quick_start")
        self.assertEqual(generate_database_name("my_workspace", "quick_start"), "my_workspace")
        self.assertEqual(generate_database_name("  padded  ", "quick_start"), "padded")

    # --- get_columns_in_relation ---

    def test_get_columns_in_relation_stream_returns_empty(self):
        """get_columns_in_relation returns [] for stream relations (system columns filtered)."""
        config = self._get_target_http(self.project_cfg)
        adapter = ClickZettaAdapter(config, MP_CONTEXT)
        stream_rel = self._make_relation(ClickZettaRelationType.Stream)
        result = adapter.get_columns_in_relation(stream_rel)
        self.assertEqual(result, [])

    # --- standardize_grants_dict ---

    def _make_grants_table(self, rows):
        col_names = [
            "granted_type", "privilege", "conditions", "granted_on", "object_name",
            "granted_to", "grantee_name", "grantor_name", "grant_option", "granted_time"
        ]
        return agate.Table(rows, col_names)

    def test_standardize_grants_dict_direct_grants_only(self):
        """Only PRIVILEGE grants are included; OBJECT_HIERARCHY grants are excluded."""
        config = self._get_target_http(self.project_cfg)
        adapter = ClickZettaAdapter(config, MP_CONTEXT)
        table = self._make_grants_table([
            ["PRIVILEGE", "SELECT TABLE", "", "TABLE", "t", "ROLE", "ws.analyst", "", False, ""],
            ["OBJECT_HIERARCHY", "SELECT TABLE", "", "TABLE", "t", "ROLE", "ws.admin", "", False, ""],
        ])
        result = adapter.standardize_grants_dict(table)
        self.assertIn("select", result)
        self.assertEqual(result["select"], ["analyst"])
        # admin from OBJECT_HIERARCHY should not appear
        self.assertNotIn("admin", result.get("select", []))

    def test_standardize_grants_dict_privilege_normalization(self):
        """'SELECT TABLE' normalizes to 'select'; 'INSERT TABLE' to 'insert'."""
        config = self._get_target_http(self.project_cfg)
        adapter = ClickZettaAdapter(config, MP_CONTEXT)
        table = self._make_grants_table([
            ["PRIVILEGE", "SELECT TABLE", "", "TABLE", "t", "ROLE", "ws.r1", "", False, ""],
            ["PRIVILEGE", "INSERT TABLE", "", "TABLE", "t", "ROLE", "ws.r2", "", False, ""],
        ])
        result = adapter.standardize_grants_dict(table)
        self.assertIn("select", result)
        self.assertIn("insert", result)
        self.assertNotIn("SELECT TABLE", result)

    def test_standardize_grants_dict_strips_workspace_prefix(self):
        """'ws.my_role' grantee becomes 'my_role'."""
        config = self._get_target_http(self.project_cfg)
        adapter = ClickZettaAdapter(config, MP_CONTEXT)
        table = self._make_grants_table([
            ["PRIVILEGE", "SELECT TABLE", "", "TABLE", "t", "ROLE", "quick_start.analyst", "", False, ""],
        ])
        result = adapter.standardize_grants_dict(table)
        self.assertEqual(result["select"], ["analyst"])

    def test_standardize_grants_dict_user_prefix(self):
        """USER grantees get 'user:' prefix; ROLE grantees do not."""
        config = self._get_target_http(self.project_cfg)
        adapter = ClickZettaAdapter(config, MP_CONTEXT)
        table = self._make_grants_table([
            ["PRIVILEGE", "SELECT TABLE", "", "TABLE", "t", "ROLE", "ws.my_role", "", False, ""],
            ["PRIVILEGE", "SELECT TABLE", "", "TABLE", "t", "USER", "ws.alice", "", False, ""],
        ])
        result = adapter.standardize_grants_dict(table)
        grantees = result["select"]
        self.assertIn("my_role", grantees)
        self.assertIn("user:alice", grantees)
        self.assertNotIn("user:my_role", grantees)
        self.assertNotIn("alice", grantees)

    def test_standardize_grants_dict_empty_table(self):
        """Empty grants table returns empty dict."""
        config = self._get_target_http(self.project_cfg)
        adapter = ClickZettaAdapter(config, MP_CONTEXT)
        table = self._make_grants_table([])
        result = adapter.standardize_grants_dict(table)
        self.assertEqual(result, {})

