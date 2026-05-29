import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch, PropertyMock


class TestAddQueryBindingSubstitution(unittest.TestCase):
    """
    Tests for the Python-side binding substitution in ClickZettaConnectionManager.add_query.

    Bindings are substituted on the Python side (sql % tuple) because the ClickZetta
    cursor does not support parameterized queries. Each binding type must be rendered
    as a valid SQL literal.
    """

    def _substitute(self, sql, bindings):
        """
        Replicate the substitution logic from add_query so we can test it in isolation
        without needing a real database connection.
        """
        cast_bindings = []
        for binding in bindings:
            if binding is None:
                cast_bindings.append("NULL")
            elif isinstance(binding, bool):
                cast_bindings.append("true" if binding else "false")
            elif isinstance(binding, (int, float)):
                cast_bindings.append(str(binding))
            else:
                escaped = str(binding).replace("'", "''")
                cast_bindings.append(f"'{escaped}'")
        return sql % tuple(cast_bindings)

    # --- None ---

    def test_none_becomes_null(self):
        result = self._substitute("insert into t values (%s)", [None])
        self.assertEqual(result, "insert into t values (NULL)")

    # --- bool (must be checked before int) ---

    def test_true_becomes_true(self):
        result = self._substitute("insert into t values (%s)", [True])
        self.assertEqual(result, "insert into t values (true)")

    def test_false_becomes_false(self):
        result = self._substitute("insert into t values (%s)", [False])
        self.assertEqual(result, "insert into t values (false)")

    def test_bool_not_treated_as_int(self):
        # bool is a subclass of int in Python; True must not become 1
        result = self._substitute("insert into t values (%s, %s)", [True, False])
        self.assertIn("true", result)
        self.assertIn("false", result)
        self.assertNotIn("'1'", result)
        self.assertNotIn("'0'", result)

    # --- numeric ---

    def test_int_is_bare_literal(self):
        result = self._substitute("insert into t values (%s)", [42])
        self.assertEqual(result, "insert into t values (42)")

    def test_negative_int(self):
        result = self._substitute("insert into t values (%s)", [-7])
        self.assertEqual(result, "insert into t values (-7)")

    def test_float_is_bare_literal(self):
        result = self._substitute("insert into t values (%s)", [3.14])
        self.assertEqual(result, "insert into t values (3.14)")

    def test_zero_int(self):
        result = self._substitute("insert into t values (%s)", [0])
        self.assertEqual(result, "insert into t values (0)")

    # --- string ---

    def test_plain_string(self):
        result = self._substitute("insert into t values (%s)", ["hello"])
        self.assertEqual(result, "insert into t values ('hello')")

    def test_string_with_single_quote(self):
        # "kevin's" must become 'kevin''s' (SQL standard escaping)
        result = self._substitute("insert into t values (%s)", ["kevin's"])
        self.assertEqual(result, "insert into t values ('kevin''s')")

    def test_string_with_multiple_single_quotes(self):
        result = self._substitute("insert into t values (%s)", ["it's a dog's life"])
        self.assertEqual(result, "insert into t values ('it''s a dog''s life')")

    def test_string_with_percent(self):
        # "50% off" — % must be escaped to %% before Python format substitution,
        # then %% becomes % in the final SQL
        result = self._substitute("insert into t values (%s)", ["50% off"])
        self.assertEqual(result, "insert into t values ('50% off')")

    def test_string_with_percent_and_quote(self):
        result = self._substitute("insert into t values (%s)", ["it's 50% done"])
        self.assertEqual(result, "insert into t values ('it''s 50% done')")

    def test_empty_string(self):
        result = self._substitute("insert into t values (%s)", [""])
        self.assertEqual(result, "insert into t values ('')")

    # --- Decimal (goes through string path) ---

    def test_decimal_is_quoted_string(self):
        # Decimal is not a subclass of int/float, so it becomes a quoted string.
        # cast('123.45' as decimal(10,2)) is valid in ClickZetta.
        result = self._substitute("insert into t values (%s)", [Decimal("123.45")])
        self.assertEqual(result, "insert into t values ('123.45')")

    # --- multiple bindings ---

    def test_multiple_mixed_bindings(self):
        result = self._substitute(
            "insert into t values (%s, %s, %s, %s, %s)",
            ["alice", 1, True, None, "it's fine"],
        )
        self.assertEqual(
            result,
            "insert into t values ('alice', 1, true, NULL, 'it''s fine')",
        )


if __name__ == "__main__":
    unittest.main()
