# dbt-clickzetta Test Suite

## Overview

There are three layers of testing. **All three must pass before releasing a new version.**

| Layer | What | Requires connection |
|---|---|---|
| Unit tests | Python methods + Jinja macro SQL generation | No |
| Functional tests | dbt-core adapter test suite | Yes |
| Examples project | End-to-end integration: all adapter features | Yes |

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
    ├── test_basic.py            # dbt-core base test suite (materializations, incremental, snapshots)
    ├── test_data_correctness.py # Data correctness: merge, append, insert_overwrite, NULL handling
    ├── test_dynamic_table.py    # Dynamic table materialization
    └── test_grants.py           # Grants / RBAC

examples/                        # Integration test project (separate from pytest)
```

## Running Tests

### 1. Unit tests (no connection needed)

```bash
pip install pytest
pytest tests/unit/
# Expected: 92 passed
```

### 2. Functional tests (requires connection)

Functional tests use dbt-core's pytest adapter test framework. Set environment variables:

```bash
export CLICKZETTA_TEST_SERVICE=cn-shanghai-alicloud.api.clickzetta.com
export CLICKZETTA_TEST_INSTANCE=your_instance
export CLICKZETTA_TEST_WORKSPACE=your_workspace
export CLICKZETTA_TEST_USERNAME=your_username
export CLICKZETTA_TEST_PASSWORD=your_password
export CLICKZETTA_TEST_VCLUSTER=default_ap
export CLICKZETTA_TEST_SCHEMA=dbt_test

pytest tests/functional/
```

### 3. Examples project — integration test (requires connection)

The `examples/` project exercises every adapter feature end-to-end with real data.
This is the primary integration test and **must pass before any release**.

```bash
cd examples
cp profiles.yml.example profiles.yml   # fill in credentials once

# Full test run (run in this order):
dbt seed --profiles-dir . --full-refresh   # load test data
dbt run --profiles-dir .                   # build all models (14 models)
dbt snapshot --profiles-dir .              # build snapshots
dbt test --profiles-dir .                  # run all tests
# Expected: 49 passed, 0 errors
```

**What it covers:** table/view/incremental/snapshot/dynamic_table/materialized_view
materializations, all incremental strategies (merge/append/insert_overwrite/delete+insert),
indexes (bloomfilter/inverted/vector), VCluster switching, persist_docs, grants, clone,
Table Stream as source, seed via COPY INTO.

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

Add to `test_adapter.py`. Use `_get_target_http()` to build a config, then instantiate
`ClickZettaAdapter(config, MP_CONTEXT)`.

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

## Known Limitations

- **Snapshot integrity test** (`assert_snapshot_integrity`) requires a two-round seed+snapshot
  setup to produce historical records. See `examples/README.md` for the manual steps.
- **`orders_clone_timetravel`** is disabled by default (`enabled=false`) — it requires the
  source table to have existed for ≥1 hour. See `examples/README.md` for how to run it manually.
- **`workspace_analyst` role** must exist in your ClickZetta workspace for
  `assert_grants_regional_revenue` to pass. Override with `--vars '{"grant_role": "your_role"}'`.
