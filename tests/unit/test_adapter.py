import unittest
from unittest import mock

import dbt.flags as flags
from dbt.exceptions import DbtRuntimeError
from agate import Row
from dbt.adapters.clickzetta import ClickZettaAdapter, ClickZettaRelation
from .utils import config_from_parts_or_dicts


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
                        "base_url": "https://dev-api.zettadecision.com",
                        "workspace": "system_smoke",
                        "instance_name": "clickzetta",
                        "vc_name": "vcz_gp_daily",
                        "user_name": "cz_lh_smoke_test",
                        "schema": "dbt",
                        "password": "Abc123456",
                    }
                },
                "target": "test",
            },
        )

    def test_http_connection(self):
        config = self._get_target_http(self.project_cfg)
        adapter = ClickZettaAdapter(config)

        connection = adapter.acquire_connection("dummy")
        connection.handle  # trigger lazy-load

        self.assertEqual(connection.state, "open")
        self.assertIsNotNone(connection.handle)
        self.assertEqual(connection.credentials.workspace, "system_smoke")
        self.assertEqual(connection.credentials.instance_name, "clickzetta")
        self.assertEqual(connection.credentials.vc_name, "vcz_gp_daily")
        self.assertEqual(connection.credentials.password, "Abc123456")
        self.assertEqual(connection.credentials.base_url, "https://dev-api.zettadecision.com")
        self.assertEqual(connection.credentials.user_name, "cz_lh_smoke_test")
        self.assertEqual(connection.credentials.schema, "dbt")
        self.assertIsNone(connection.credentials.database)


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

        input_cols = [Row(keys=["col_name", "data_type"], values=r) for r in plain_rows]

        config = self._get_target_http(self.project_cfg)
        rows = ClickZettaAdapter(config).parse_describe_extended(relation, input_cols)
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
        adapter = ClickZettaAdapter(config)
        # fine
        adapter.Relation.create(schema="dbt", identifier="dbt_table_1")
        with self.assertRaises(DbtRuntimeError):
            # not fine - database set
            adapter.Relation.create(database="db", schema="dbt", identifier="dbt_table_1")
