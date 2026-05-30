import unittest
from dbt.adapters.clickzetta.column import ClickZettaColumn


class TestClickZettaColumnTypes(unittest.TestCase):
    """Tests for ClickZettaColumn type classification and alias translation."""

    def _col(self, dtype):
        return ClickZettaColumn(column="c", dtype=dtype)

    # --- is_integer ---

    def test_is_integer_canonical_names(self):
        for t in ["tinyint", "smallint", "int", "bigint"]:
            with self.subTest(dtype=t):
                self.assertTrue(self._col(t).is_integer(), f"{t} should be integer")

    def test_is_integer_canonical_names_uppercase(self):
        for t in ["TINYINT", "SMALLINT", "INT", "BIGINT"]:
            with self.subTest(dtype=t):
                self.assertTrue(self._col(t).is_integer())

    def test_is_integer_legacy_arrow_names(self):
        # Legacy Arrow/ClickHouse internal names kept for backwards compatibility
        for t in ["int8", "int16", "int32", "int64"]:
            with self.subTest(dtype=t):
                self.assertTrue(self._col(t).is_integer())

    def test_is_integer_false_for_non_integers(self):
        for t in ["float", "double", "string", "boolean", "decimal(10,2)", "timestamp"]:
            with self.subTest(dtype=t):
                self.assertFalse(self._col(t).is_integer())

    # --- is_float ---

    def test_is_float_canonical_names(self):
        for t in ["float", "double"]:
            with self.subTest(dtype=t):
                self.assertTrue(self._col(t).is_float())

    def test_is_float_canonical_names_uppercase(self):
        for t in ["FLOAT", "DOUBLE"]:
            with self.subTest(dtype=t):
                self.assertTrue(self._col(t).is_float())

    def test_is_float_legacy_arrow_names(self):
        for t in ["float32", "float64"]:
            with self.subTest(dtype=t):
                self.assertTrue(self._col(t).is_float())

    def test_is_float_false_for_non_floats(self):
        for t in ["int", "bigint", "string", "boolean", "decimal(10,2)"]:
            with self.subTest(dtype=t):
                self.assertFalse(self._col(t).is_float())

    # --- is_string ---

    def test_is_string(self):
        for t in ["string", "varchar", "char"]:
            with self.subTest(dtype=t):
                self.assertTrue(self._col(t).is_string())

    def test_is_string_false(self):
        for t in ["int", "float", "boolean", "timestamp"]:
            with self.subTest(dtype=t):
                self.assertFalse(self._col(t).is_string())

    # --- translate_type (alias mapping) ---

    def test_translate_postgresql_numeric_aliases(self):
        cases = {
            "float8": "double",
            "float4": "float",
            "int2": "smallint",
            "int4": "int",
            "int8": "bigint",
            "integer": "int",
            "numeric": "decimal",
            "real": "float",
        }
        for alias, expected in cases.items():
            with self.subTest(alias=alias):
                self.assertEqual(ClickZettaColumn.translate_type(alias), expected)

    def test_translate_postgresql_string_aliases(self):
        self.assertEqual(ClickZettaColumn.translate_type("text"), "string")
        self.assertEqual(ClickZettaColumn.translate_type("character varying"), "varchar")

    def test_translate_postgresql_bool_alias(self):
        self.assertEqual(ClickZettaColumn.translate_type("bool"), "boolean")

    def test_translate_timestamp_aliases(self):
        self.assertEqual(ClickZettaColumn.translate_type("timestamptz"), "timestamp_ltz")
        self.assertEqual(ClickZettaColumn.translate_type("timestamp with time zone"), "timestamp_ltz")
        self.assertEqual(ClickZettaColumn.translate_type("timestamp without time zone"), "timestamp_ntz")
        self.assertEqual(ClickZettaColumn.translate_type("datetime"), "timestamp_ntz")

    def test_translate_unknown_type_passthrough(self):
        # Unknown types pass through unchanged
        self.assertEqual(ClickZettaColumn.translate_type("vector(float, 128)"), "vector(float, 128)")
        self.assertEqual(ClickZettaColumn.translate_type("decimal(10,2)"), "decimal(10,2)")
        self.assertEqual(ClickZettaColumn.translate_type("varchar(255)"), "varchar(255)")

    def test_translate_case_insensitive(self):
        self.assertEqual(ClickZettaColumn.translate_type("FLOAT8"), "double")
        self.assertEqual(ClickZettaColumn.translate_type("Bool"), "boolean")

    def test_translate_strips_length_for_alias_lookup(self):
        # "integer(10)" base is "integer" → maps to "int"
        self.assertEqual(ClickZettaColumn.translate_type("integer(10)"), "int")


class TestClickZettaColumnRelationType(unittest.TestCase):
    """Tests for ClickZettaRelationType enum consistency."""

    def test_relation_type_values(self):
        from dbt.adapters.clickzetta.relation import ClickZettaRelationType
        self.assertEqual(str(ClickZettaRelationType.Table), "table")
        self.assertEqual(str(ClickZettaRelationType.View), "view")
        self.assertEqual(str(ClickZettaRelationType.DynamicTable), "dynamic_table")
        self.assertEqual(str(ClickZettaRelationType.MaterializedView), "materialized_view")
        self.assertEqual(str(ClickZettaRelationType.Stream), "stream")

    def test_relation_type_comparison(self):
        from dbt.adapters.clickzetta.relation import ClickZettaRelationType
        # Enum members should compare equal to their string values (StrEnum)
        self.assertEqual(ClickZettaRelationType.Table, "table")
        self.assertEqual(ClickZettaRelationType.Stream, "stream")
        self.assertEqual(ClickZettaRelationType.DynamicTable, "dynamic_table")


if __name__ == "__main__":
    unittest.main()
