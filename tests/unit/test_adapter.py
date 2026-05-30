import unittest
from unittest import mock
import multiprocessing

import dbt.flags as flags
from dbt.exceptions import DbtRuntimeError
from agate import Row
from dbt.adapters.clickzetta import ClickZettaAdapter, ClickZettaRelation
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

    def test_parse_relation(self):
        self.maxDiff = None
        rel_type = ClickZettaRelation.get_relation_type.Table

        relation = ClickZettaRelation.create(
            schema="dbt", identifier="dbt_able", type=rel_type
        )
        assert relation.database is None

        plain_rows = [
            ("col1", "decimal(19,0)"),
            (
                "col2",
                "string",
            ),
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
        self.assertEqual(
            rows[0].to_column_dict(omit_none=False),
            {
                "table_database": None,
                "table_schema": relation.schema,
                "table_name": relation.name,
                "column": "col1",
                "dtype": "decimal(19,0)",
                "numeric_scale": None,
                "numeric_precision": None,
                "char_size": None,
            },
        )

        self.assertEqual(
            rows[1].to_column_dict(omit_none=False),
            {
                "table_database": None,
                "table_schema": relation.schema,
                "table_name": relation.name,
                "column": "col2",
                "dtype": "string",
                "numeric_scale": None,
                "numeric_precision": None,
                "char_size": None,
            },
        )

        self.assertEqual(
            rows[2].to_column_dict(omit_none=False),
            {
                "table_database": None,
                "table_schema": relation.schema,
                "table_name": relation.name,
                "column": "dt",
                "dtype": "date",
                "numeric_scale": None,
                "numeric_precision": None,
                "char_size": None,
            },
        )

        self.assertEqual(
            rows[3].to_column_dict(omit_none=False),
            {
                "table_database": None,
                "table_schema": relation.schema,
                "table_name": relation.name,
                "column": "col3",
                "dtype": "string",
                "numeric_scale": None,
                "numeric_precision": None,
                "char_size": None,
            },
        )

        self.assertEqual(
            rows[8].to_column_dict(omit_none=False),
            {
                "table_database": None,
                "table_schema": relation.schema,
                "table_name": relation.name,
                "column": "col8",
                "dtype": "timestamp",
                "numeric_scale": None,
                "numeric_precision": None,
                "char_size": None,
            },
        )

    def test_relation_with_database(self):
        config = self._get_target_http(self.project_cfg)
        adapter = ClickZettaAdapter(config, MP_CONTEXT)
        # workspace maps to database; render() includes it as workspace.schema.table
        rel = adapter.Relation.create(schema="dbt", identifier="dbt_table_1")
        self.assertEqual(rel.render(), "dbt.dbt_table_1")
        rel_with_db = adapter.Relation.create(database="db", schema="dbt", identifier="dbt_table_1")
        # render should include database (workspace) prefix
        self.assertIn("db.", rel_with_db.render())
        self.assertEqual(rel_with_db.render(), "db.dbt.dbt_table_1")

    def test_relation_type_consistency(self):
        from dbt.adapters.clickzetta.relation import ClickZettaRelationType
        # All relation types used in list_relations_without_caching must be
        # ClickZettaRelationType enum members, not plain strings or classproperty values
        for t in [
            ClickZettaRelationType.Table,
            ClickZettaRelationType.View,
            ClickZettaRelationType.DynamicTable,
            ClickZettaRelationType.MaterializedView,
            ClickZettaRelationType.Stream,
        ]:
            rel = ClickZettaRelation.create(schema="s", identifier="t", type=t)
            self.assertEqual(rel.type, t)
            # type comparison must work both ways (StrEnum)
            self.assertEqual(rel.type, str(t))

    def test_generate_database_name_macro_logic(self):
        # generate_database_name is a Jinja macro; test its Python-equivalent logic:
        # - returns custom_database_name when provided
        # - falls back to target.database (workspace) when not provided
        def generate_database_name(custom_database_name, target_database):
            if custom_database_name is not None:
                return custom_database_name.strip()
            return target_database.strip()

        self.assertEqual(generate_database_name(None, "quick_start"), "quick_start")
        self.assertEqual(generate_database_name("my_workspace", "quick_start"), "my_workspace")
        self.assertEqual(generate_database_name("  padded  ", "quick_start"), "padded")
