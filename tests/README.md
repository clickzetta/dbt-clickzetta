# dbt-clickzetta Test Suite

## Structure

```
tests/
├── unit/                        # Unit tests — no database connection required
│   ├── test_adapter.py          # Adapter Python methods
│   ├── test_column.py           # ClickZettaColumn type system
│   ├── test_connections.py      # Connection binding substitution
│   ├── test_macros.py           # Core Jinja macros (create_table_as, dynamic_table)
│   └── test_macros_extended.py  # Extended macro tests (drop/rename, indexes, strategies)
└── functional/                  # Functional tests — require a real ClickZetta connection
    ├── test_basic.py
    ├── test_data_correctness.py
    └── test_dynamic_table.py
```

## Running Tests

### Unit tests (no connection needed)

```bash
pip install pytest
pytest tests/unit/
```

### Functional tests (requires connection)

Functional tests run against the `examples/` dbt project. Set up a connection first:

```bash
cp examples/profiles.yml.example examples/profiles.yml
# Fill in your ClickZetta credentials
```

Then run the full examples pipeline:

```bash
cd examples
dbt seed --profiles-dir . --full-refresh
dbt run --profiles-dir .
dbt snapshot --profiles-dir .   # required for assert_snapshot_integrity
dbt test --profiles-dir .
```

## Unit Test Coverage

| File | What It Tests |
|---|---|
| `test_adapter.py` | `parse_describe_extended`, `get_columns_in_relation` (stream guard), `standardize_grants_dict`, relation rendering, type consistency |
| `test_column.py` | `is_integer`, `is_float`, `is_string`, `translate_type` (PostgreSQL/MySQL alias mapping) |
| `test_connections.py` | Python-side binding substitution: None→NULL, bool, int/float, string escaping (single quotes, %) |
| `test_macros.py` | `create_table_as` (partition, cluster, location, comment), `create_dynamic_table_as` |
| `test_macros_extended.py` | `drop_relation` (all types + None), `rename_relation` (all types + error cases), `safe_cast` (not null stripping), `get_delete_insert_sql`, `create_indexes` (bloomfilter/inverted/vector) |

## Writing New Tests

### Unit tests for Python methods

Add to `test_adapter.py`. Use `_get_target_http()` to build a config, then instantiate `ClickZettaAdapter(config, MP_CONTEXT)`.

### Unit tests for Jinja macros

Add to `test_macros_extended.py`. Use `MacroTestBase` which provides:

- `self._get_template(filename)` — loads a macro file with a mock context
- `self._make_relation(rel_type, database, schema, identifier)` — creates a mock relation
- `_make_statement_capturer(list)` — captures SQL from `{% call statement %}` blocks via Jinja's `caller()` mechanism

Example:

```python
def test_my_macro(self):
    captured = []
    template = self._get_template("adapters.sql", {
        "statement": _make_statement_capturer(captured)
    })
    rel = self._make_relation("table")
    template.module.clickzetta__my_macro(rel)
    self.assertIn("expected sql fragment", " ".join(captured))
```

### Functional tests

The `examples/` project is the functional test suite. Add new models, seeds, or singular tests there. The full pipeline (seed → run → snapshot → test) must pass with 0 errors.

## Known Limitations

- **Snapshot integrity test** (`assert_snapshot_integrity`) requires a two-round seed+snapshot setup to produce historical records. See `examples/README.md` for the manual steps.
- **`orders_clone_timetravel`** is disabled by default (`enabled=false`) — it requires the source table to have existed for ≥1 hour. See `examples/README.md` for how to run it manually.
- **`workspace_analyst` role** must exist in your ClickZetta workspace for `assert_grants_regional_revenue` to pass. Override with `--vars '{"grant_role": "your_role"}'`.
