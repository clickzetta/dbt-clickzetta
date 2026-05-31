import unittest
from unittest import mock
import re
import os
from jinja2 import Environment, FileSystemLoader


class TestClickZettaMacros(unittest.TestCase):
    def setUp(self):
        project_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        self.jinja_env = Environment(
            loader=FileSystemLoader(project_path + "/dbt/include/clickzetta/macros"),
            extensions=[
                "jinja2.ext.do",
            ],
        )

        self.config = {}
        self.default_context = {
            "validation": mock.Mock(),
            "model": mock.Mock(),
            "exceptions": mock.Mock(),
            "config": mock.Mock(),
            "adapter": mock.Mock(),
            "return": lambda r: r,
        }
        self.default_context["config"].get = lambda key, default=None, **kwargs: self.config.get(
            key, default
        )

    def __get_template(self, template_filename):
        return self.jinja_env.get_template(template_filename, globals=self.default_context)

    def __run_macro(self, template, name, temporary, relation, sql):
        self.default_context["model"].alias = relation

        def dispatch(macro_name, macro_namespace=None, packages=None):
            return getattr(template.module, f"clickzetta__{macro_name}")

        self.default_context["adapter"].dispatch = dispatch

        value = getattr(template.module, name)(temporary, relation, sql)
        return re.sub(r"\s\s+", " ", value)

    def __run_macro_dynamic_table(self, template, name, relation, sql):
        self.default_context["model"].alias = relation

        def dispatch(macro_name, macro_namespace=None, packages=None):
            return getattr(template.module, f"clickzetta__{macro_name}")

        self.default_context["adapter"].dispatch = dispatch

        value = getattr(template.module, name)(relation, sql)
        return re.sub(r"\s\s+", " ", value)

    def test_macros_load(self):
        self.jinja_env.get_template("adapters.sql")

    def test_macros_create_table_as(self):
        template = self.__get_template("adapters.sql")
        sql = self.__run_macro(
            template, "clickzetta__create_table_as", False, "my_table", "select 1"
        ).strip()

        self.assertEqual(sql, "create table my_table as select 1")

    def test_macros_create_table_as_partition(self):
        template = self.__get_template("adapters.sql")

        self.config["partition_by"] = "partition_1"
        sql = self.__run_macro(
            template, "clickzetta__create_table_as", False, "my_table", "select 1"
        ).strip()
        self.assertEqual(sql, "create table my_table partitioned by (partition_1) as select 1")

    def test_macros_create_table_as_partitions(self):
        template = self.__get_template("adapters.sql")

        self.config["partition_by"] = ["partition_1", "partition_2"]
        sql = self.__run_macro(
            template, "clickzetta__create_table_as", False, "my_table", "select 1"
        ).strip()
        self.assertEqual(
            sql, "create table my_table partitioned by (partition_1,partition_2) as select 1"
        )

    def test_macros_create_table_as_cluster(self):
        template = self.__get_template("adapters.sql")

        self.config["clustered_by"] = "cluster_1"
        self.config["buckets"] = "1"
        sql = self.__run_macro(
            template, "clickzetta__create_table_as", False, "my_table", "select 1"
        ).strip()
        self.assertEqual(
            sql, "create table my_table clustered by (cluster_1) into 1 buckets as select 1"
        )

    def test_macros_create_table_as_clusters(self):
        template = self.__get_template("adapters.sql")

        self.config["clustered_by"] = ["cluster_1", "cluster_2"]
        self.config["buckets"] = "1"
        sql = self.__run_macro(
            template, "clickzetta__create_table_as", False, "my_table", "select 1"
        ).strip()
        self.assertEqual(
            sql,
            "create table my_table clustered by (cluster_1,cluster_2) into 1 buckets as select 1",
        )

    def test_macros_create_table_as_location(self):
        template = self.__get_template("adapters.sql")

        self.config["location_root"] = "/mnt/root"
        sql = self.__run_macro(
            template, "clickzetta__create_table_as", False, "my_table", "select 1"
        ).strip()
        self.assertEqual(sql, "create table my_table location '/mnt/root/my_table' as select 1")

    def test_macros_create_table_as_comment(self):
        template = self.__get_template("adapters.sql")

        self.config["persist_docs"] = {"relation": True}
        self.default_context["model"].description = "Description Test"
        sql = self.__run_macro(
            template, "clickzetta__create_table_as", False, "my_table", "select 1"
        ).strip()
        self.assertEqual(sql, "create table my_table comment 'Description Test' as select 1")

    def test_macros_create_table_as_all(self):
        template = self.__get_template("adapters.sql")

        self.config["location_root"] = "/mnt/root"
        self.config["partition_by"] = ["partition_1", "partition_2"]
        self.config["clustered_by"] = ["cluster_1", "cluster_2"]
        self.config["buckets"] = "1"
        self.config["persist_docs"] = {"relation": True}
        self.default_context["model"].description = "Description Test"

        sql = self.__run_macro(
            template, "clickzetta__create_table_as", False, "my_table", "select 1"
        ).strip()
        self.assertEqual(
            sql,
            "create table my_table partitioned by (partition_1,partition_2) clustered by (cluster_1,cluster_2) into 1 buckets location '/mnt/root/my_table' comment 'Description Test' as select 1",
        )

        self.config["buckets"] = "2"
        self.config["clustered_by"] = ["cluster_3", "cluster_4"]
        sql = self.__run_macro(
            template, "clickzetta__create_table_as", False, "my_table", "select 1"
        ).strip()
        self.assertEqual(
            sql,
            "create table my_table partitioned by (partition_1,partition_2) clustered by (cluster_3,cluster_4) into 2 buckets location '/mnt/root/my_table' comment 'Description Test' as select 1",
        )

    def test_macros_create_dynamic_table_as_(self):
        template = self.__get_template("adapters.sql")
        sql = self.__run_macro_dynamic_table(
            template, "clickzetta__create_dynamic_table_as", "my_dynamic_table", "select 1"
        ).strip()

        self.assertEqual(sql, "create dynamic table my_dynamic_table as select 1")

    def test_macros_create_dynamic_table_as_partition(self):
        template = self.__get_template("adapters.sql")
        self.config["partition_by"] = "partition_1"
        sql = self.__run_macro_dynamic_table(
            template, "clickzetta__create_dynamic_table_as", "my_dynamic_table", "select 1"
        ).strip()

        self.assertEqual(sql, "create dynamic table my_dynamic_table partitioned by (partition_1) as select 1")

    def test_macros_create_dynamic_table_as_partitions(self):
        template = self.__get_template("adapters.sql")
        self.config["partition_by"] = ["partition_1", "partition_2"]
        sql = self.__run_macro_dynamic_table(
            template, "clickzetta__create_dynamic_table_as", "my_dynamic_table", "select 1"
        ).strip()

        self.assertEqual(sql, "create dynamic table my_dynamic_table partitioned by (partition_1,partition_2) "
                              "as select 1")

    def test_macros_create_dynamic_table_as_cluster(self):
        template = self.__get_template("adapters.sql")
        self.config["clustered_by"] = "cluster_1"
        self.config["buckets"] = "1"
        sql = self.__run_macro_dynamic_table(
            template, "clickzetta__create_dynamic_table_as", "my_dynamic_table", "select 1"
        ).strip()

        self.assertEqual(sql, "create dynamic table my_dynamic_table clustered by (cluster_1) into 1 buckets "
                              "as select 1")

    def test_macros_create_dynamic_table_as_clusters(self):
        template = self.__get_template("adapters.sql")
        self.config["clustered_by"] = ["cluster_1", "cluster_2"]
        self.config["buckets"] = "1"
        sql = self.__run_macro_dynamic_table(
            template, "clickzetta__create_dynamic_table_as", "my_dynamic_table", "select 1"
        ).strip()

        self.assertEqual(sql, "create dynamic table my_dynamic_table clustered by (cluster_1,cluster_2) into 1 buckets "
                              "as select 1")

    def test_macros_create_dynamic_table_as_refresh(self):
        template = self.__get_template("adapters.sql")
        self.config["refresh_interval"] = '3 minutes'
        sql = self.__run_macro_dynamic_table(
            template, "clickzetta__create_dynamic_table_as", "my_dynamic_table", "select 1"
        ).strip()

        self.assertEqual(sql, "create dynamic table my_dynamic_table refresh interval 3 minutes as select 1")

    def test_macros_create_dynamic_table_as_refresh_with_vc(self):
        template = self.__get_template("adapters.sql")
        self.config["refresh_interval"] = '5 MINUTE'
        self.config["refresh_vc"] = 'default'
        sql = self.__run_macro_dynamic_table(
            template, "clickzetta__create_dynamic_table_as", "my_dynamic_table", "select 1"
        ).strip()

        self.assertEqual(sql, "create dynamic table my_dynamic_table refresh interval 5 MINUTE vcluster default as select 1")

    def test_macros_create_dynamic_table_as_all(self):
        template = self.__get_template("adapters.sql")

        self.config["partition_by"] = ["partition_1", "partition_2"]
        self.config["clustered_by"] = ["cluster_1", "cluster_2"]
        self.config["buckets"] = "1"
        self.config["persist_docs"] = {"relation": True}
        self.config["refresh_interval"] = '3 minutes'
        self.default_context["model"].description = "Description Test"
        sql = self.__run_macro_dynamic_table(
            template, "clickzetta__create_dynamic_table_as", "my_dynamic_table", "select 1"
        ).strip()
        self.assertEqual(
            sql,
            "create dynamic table my_dynamic_table partitioned by (partition_1,partition_2) clustered by (cluster_1,"
            "cluster_2) into 1 buckets refresh interval 3 minutes as select 1",
        )
        self.config["buckets"] = "2"
        self.config["clustered_by"] = ["cluster_3", "cluster_4"]
        sql = self.__run_macro_dynamic_table(
            template, "clickzetta__create_dynamic_table_as", "my_dynamic_table", "select 1"
        ).strip()
        self.assertEqual(
            sql,
            "create dynamic table my_dynamic_table partitioned by (partition_1,partition_2) clustered by (cluster_3,"
            "cluster_4) into 2 buckets refresh interval 3 minutes as select 1",
        )

    # ── replace_dynamic_table_as (full_refresh path) ──────────────────────────

    def test_macros_replace_dynamic_table_as_minimal(self):
        """full_refresh with no config → CREATE OR REPLACE DYNAMIC TABLE ... AS ..."""
        template = self.__get_template("adapters.sql")
        sql = self.__run_macro_dynamic_table(
            template, "clickzetta__replace_dynamic_table_as", "my_dynamic_table", "select 1"
        ).strip()
        self.assertEqual(sql, "create or replace dynamic table my_dynamic_table as select 1")

    def test_macros_replace_dynamic_table_as_refresh(self):
        """full_refresh with refresh_interval + refresh_vc → correct REFRESH INTERVAL vcluster clause."""
        template = self.__get_template("adapters.sql")
        self.config["refresh_interval"] = "5 MINUTE"
        self.config["refresh_vc"] = "default"
        sql = self.__run_macro_dynamic_table(
            template, "clickzetta__replace_dynamic_table_as", "my_dynamic_table", "select 1"
        ).strip()
        self.assertEqual(
            sql,
            "create or replace dynamic table my_dynamic_table refresh interval 5 MINUTE vcluster default as select 1"
        )

    def test_macros_replace_dynamic_table_as_with_partition(self):
        """full_refresh preserves partition and refresh config."""
        template = self.__get_template("adapters.sql")
        self.config["partition_by"] = ["ds"]
        self.config["refresh_interval"] = "10 MINUTE"
        self.config["refresh_vc"] = "default"
        sql = self.__run_macro_dynamic_table(
            template, "clickzetta__replace_dynamic_table_as", "my_dynamic_table", "select 1"
        ).strip()
        self.assertEqual(
            sql,
            "create or replace dynamic table my_dynamic_table partitioned by (ds) "
            "refresh interval 10 MINUTE vcluster default as select 1"
        )

    def test_macros_replace_dynamic_table_as_target_lag(self):
        """full_refresh with target_lag config emits TARGET_LAG clause."""
        template = self.__get_template("adapters.sql")
        self.config["target_lag"] = "1 minute"
        sql = self.__run_macro_dynamic_table(
            template, "clickzetta__replace_dynamic_table_as", "my_dynamic_table", "select 1"
        ).strip()
        self.assertIn("TARGET_LAG '1 minute'", sql)
        self.assertIn("create or replace dynamic table", sql)
