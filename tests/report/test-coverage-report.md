# dbt-clickzetta Test Coverage Report

**Date**: 2026-05-30
**Version**: 1.7.5
**Test environment**: ClickZetta Lakehouse, instance f8866243, workspace quick_start

---

## Summary

| Suite | Tests | Passed | Failed | xfailed | Notes |
|---|---|---|---|---|---|
| Unit tests | 93 | 93 | 0 | 0 | No connection required |
| Functional tests | 32 | 32 | 0 | 0 | Requires Lakehouse connection |
| **Total** | **125** | **125** | **0** | **0** | |

All 125 tests pass. One test (`TestIncrementalDeleteInsertCorrectness`) was previously marked `xfail` due to a multi-statement execution bug; the bug has been fixed and the test now passes.

---

## Unit Tests (`tests/unit/`)

### test_adapter.py
- Adapter initialization and connection parameter validation

### test_column.py
- Column type parsing and mapping
- `safe_cast` macro behavior (plain types, NOT NULL removal, NULL values, TIMESTAMP_LTZ)

### test_connections.py
- Connection string construction
- Incremental strategy validation

### test_macros.py
- Drop relation SQL generation (view, dynamic_table, materialized_view, stream, table)
- Rename relation SQL generation
- Merge key SQL generation (single key, composite key, incremental_predicates)
- Index SQL generation (bloomfilter, inverted, vector)

### test_macros_extended.py
- Extended macro coverage including dynamic_table and materialized_view handling

---

## Functional Tests (`tests/functional/`)

### test_basic.py — Core materializations

| Test | What it verifies |
|---|---|
| `TestSimpleMaterializations` | table, view, incremental, snapshot — basic dbt adapter compliance |
| `TestIncremental` | merge strategy — standard dbt incremental behavior |
| `TestIncrementalAppend` | append strategy — standard dbt incremental behavior |
| `TestIncrementalInsertOverwrite` | insert_overwrite strategy — partition overwrite semantics |
| `TestGenericTests` | not_null, unique, relationships, accepted_values |
| `TestSingularTests` | Custom SQL tests |
| `TestEphemeral` | Ephemeral materialization (CTE-based, no physical table) |
| `TestEmpty` | Empty model handling |
| `TestSnapshotTimestamp` | SCD Type 2 — timestamp strategy |
| `TestSnapshotCheckCols` | SCD Type 2 — check_cols strategy |
| `TestAdapterMethods` | Adapter utility methods |

### test_data_correctness.py — Incremental strategy correctness

| Test | Strategy | What it verifies |
|---|---|---|
| `TestIncrementalMergeCorrectness` | merge | Upsert: existing rows updated, new rows inserted, unaffected rows preserved |
| `TestIncrementalAppendCorrectness` | append | Duplicate insert behavior on second run |
| `TestInsertOverwriteCorrectness` | insert_overwrite | Partition overwrite: only target partition replaced, other partitions preserved |
| `TestIncrementalDeleteInsertCorrectness` | delete+insert | DELETE then INSERT as two separate statements (see Bug Fix section) |
| `TestCompositeKeyMergeCorrectness` | merge (composite key) | `unique_key=['user_id', 'event_date']` — correct upsert on composite primary key |
| `TestWindowFunctionCorrectness` | — | ROW_NUMBER, SUM OVER, RANK, LAG window functions |
| `TestNullHandlingCorrectness` | — | NULL in JOIN, aggregation, and filter conditions |
| `TestTypeConversionCorrectness` | — | STRING→TIMESTAMP, DECIMAL precision, BOOLEAN casting |
| `TestPartitionedTableCorrectness` | — | Partition pruning, cross-partition aggregation |
| `TestDateMacroCorrectness` | — | dateadd, datediff, date_trunc macros |
| `TestSchemaChangeCorrectness` | — | `on_schema_change='sync_all_columns'` — new column auto-sync |
| `TestIncrementalPredicatesCorrectness` | — | `incremental_predicates` filter applied on second run |

### test_dynamic_table.py — Dynamic table (declarative incremental)

| Test | What it verifies |
|---|---|
| `TestDynamicTable` | Create, auto-refresh on create (initialize=ON_CREATE), full_refresh rebuild, no-op on second run |
| `TestDynamicTableWithPartition` | Partitioned dynamic table — correct partition data after create |
| `TestDynamicTableUpstreamChange` | **Core feature**: upstream INSERT/UPDATE/DELETE reflected after manual REFRESH |
| `TestDynamicTablePipeline` | DT-on-DT cascade: upstream DT → downstream aggregation DT, cascade refresh correct |
| `TestMaterializedView` | Create, data correctness (computed columns), full_refresh |

### test_grants.py — Access control

| Test | What it verifies |
|---|---|
| `TestGrantsTable::test_grants_applied` | `grants={'select': ['workspace_analyst']}` applied to table after run |
| `TestGrantsTable::test_grants_revoked_on_change` | Grants revoked when config changes to empty grants |
| `TestGrantsView::test_grants_applied_view` | `grants={'select': ['workspace_analyst']}` applied to view after run |

---

## Bug Fixes Discovered During Testing

### 1. `delete+insert` strategy — INSERT silently dropped (FIXED)

**Root cause**: ClickZetta does not support multi-statement execution in a single API call. The `delete+insert` strategy generated `DELETE ...; INSERT ...` as one string, causing only the DELETE to execute. The INSERT was silently dropped, leaving the target table empty after each incremental run.

**Fix**: `incremental.sql` now detects `delete+insert` strategy and executes DELETE (as `statement('main')`) and INSERT (as `statement('main_insert')`) as two separate calls. Two helper macros added to `strategies.sql`: `get_delete_insert_delete_sql` and `get_delete_insert_insert_sql`.

**Files changed**:
- `dbt/include/clickzetta/macros/materializations/incremental/incremental.sql`
- `dbt/include/clickzetta/macros/materializations/incremental/strategies.sql`

### 2. `test_grants.py` — Hardcoded schema and removed API (FIXED)

**Root cause**: Tests used hardcoded schema `dbt_test` instead of the dynamic test schema, and called `project.update_config()` which was removed in dbt 1.8.

**Fix**: Replaced `dbt_test` with `project.test_schema` / `project.database`, and replaced `update_config()` with `write_file()` to directly overwrite the model file.

**Files changed**:
- `tests/functional/test_grants.py`

---

## Known Limitations

### Dynamic table: `decimal` aggregation in DT-on-DT (Lakehouse bug CZLH-66000)

When a dynamic table aggregates (`SUM`, `AVG`) a `decimal` column from another dynamic table, the Lakehouse optimizer throws `bad integral cast decimal(20,2) to i`. This is a platform-level optimizer bug.

**Workaround**: Use `int` or `bigint` columns in the source dynamic table when the downstream DT needs to aggregate them. The `TestDynamicTablePipeline` test uses `int amount` to avoid this.

**Status**: Reported. Pending fix from Lakehouse platform team.

---

## Coverage Gaps (not yet tested)

| Area | Gap | Priority |
|---|---|---|
| Dynamic table | `refresh_interval='DOWNSTREAM'` mode end-to-end | Medium |
| Dynamic table | `refresh_vc` parameter validation | Low |
| Incremental | Lookback window pattern (`>= max - interval N days`) | Medium |
| Snapshot | Multi-field simultaneous change in `check` strategy | Low (noted in CLAUDE.md) |
| Grants | Multi-role grants | Low |
