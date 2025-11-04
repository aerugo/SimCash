# Schema Migration Fix - Column Mismatch Issue

**Date**: 2025-11-04
**Issue**: Database column mismatch error when running simulations with persistence
**Status**: ✅ Fixed

## Problem Description

When running a simulation with persistence enabled, users encountered the following error:

```
✗ Error: Binder Error: table transactions has 21 columns but 22 values were supplied
```

This occurred when:
1. An existing database had an older schema (missing the `overdue_since_tick` column)
2. Schema validation detected the missing column
3. The system attempted to re-initialize the schema
4. The re-initialization used `CREATE TABLE IF NOT EXISTS`, which doesn't modify existing tables
5. Transaction writes failed because the Rust FFI returned 22 columns but the table only had 21

## Root Cause

The `initialize_schema()` method in [connection.py](api/payment_simulator/persistence/connection.py) used `CREATE TABLE IF NOT EXISTS`, which is safe for idempotent operations but cannot update existing tables with schema changes.

When schema validation failed, the CLI called `initialize_schema()` again, but since the table already existed, the DDL statements had no effect, leaving the old schema in place.

## Solution

Following TDD principles, we:

1. **Wrote failing tests** ([test_schema_migration.py](api/tests/integration/test_schema_migration.py)) that reproduced the issue
2. **Implemented the fix** by:
   - Adding a `force_recreate` parameter to `initialize_schema()`
   - Creating a `_drop_all_tables()` helper method to drop tables before recreating
   - Updating the CLI to use `force_recreate=True` when validation fails
3. **Verified all tests pass** and the original issue is resolved

## Changes Made

### 1. connection.py

Added `force_recreate` parameter to `initialize_schema()`:

```python
def initialize_schema(self, force_recreate: bool = False):
    """Initialize database schema from Pydantic models.

    Args:
        force_recreate: If True, drop existing tables before recreating them.
                      Use this when schema validation fails and tables need to be updated.
    """
    if force_recreate:
        print("  Dropping existing tables...")
        self._drop_all_tables()

    # Generate and execute DDL...
```

Added `_drop_all_tables()` helper method:

```python
def _drop_all_tables(self):
    """Drop all tables managed by this system.

    Drops tables in reverse dependency order to avoid foreign key violations.
    """
    tables_to_drop = [
        "tick_queue_snapshots",
        "tick_agent_states",
        "policy_decisions",
        # ... all managed tables
    ]

    for table_name in tables_to_drop:
        self.conn.execute(f"DROP TABLE IF EXISTS {table_name}")
```

### 2. run.py (CLI)

Updated schema re-initialization to use `force_recreate=True`:

```python
if not db_manager.validate_schema(quiet=quiet):
    log_info("Schema incomplete, re-initializing...", quiet)
    db_manager.initialize_schema(force_recreate=True)  # Added force_recreate=True
```

### 3. test_schema_migration.py

Created comprehensive tests covering:
- Column mismatch error reproduction
- Schema validation detection of missing columns
- Schema re-initialization after validation failure

## Testing

All tests pass:

```bash
$ pytest tests/integration/test_schema_migration.py -v
============================= test session starts ==============================
tests/integration/test_schema_migration.py::TestSchemaMigration::test_schema_column_mismatch_on_write PASSED
tests/integration/test_schema_migration.py::TestSchemaMigration::test_schema_validation_detects_missing_column PASSED
tests/integration/test_schema_migration.py::TestSchemaMigration::test_schema_reinitialization_after_validation_failure PASSED
============================== 3 passed in 0.67s ===============================
```

End-to-end CLI test also succeeds:

```bash
$ uv run payment-sim run --config ../examples/configs/5_agent_lsm_collateral_scenario.yaml --persist
✓ Simulation completed successfully
```

## Impact

- **User Experience**: No more manual database deletion required when schema changes
- **Development**: Easier schema evolution during development
- **Safety**: Tables are only dropped when validation explicitly fails
- **Backward Compatibility**: Existing code using `initialize_schema()` without parameters continues to work

## Future Considerations

While this fix resolves the immediate issue, consider implementing:

1. **Proper migrations**: Instead of dropping tables, use ALTER TABLE statements to preserve data
2. **Backup before drop**: Automatically backup data before dropping tables
3. **Incremental migration system**: Track schema version and apply incremental changes

For now, the current fix is appropriate for development and early testing phases where data loss is acceptable.

## Related Files

- [api/payment_simulator/persistence/connection.py](api/payment_simulator/persistence/connection.py) - DatabaseManager implementation
- [api/payment_simulator/cli/commands/run.py](api/payment_simulator/cli/commands/run.py) - CLI command implementation
- [api/tests/integration/test_schema_migration.py](api/tests/integration/test_schema_migration.py) - Test suite
- [api/payment_simulator/persistence/models.py](api/payment_simulator/persistence/models.py) - Schema definitions

## Verification Checklist

- [x] Tests written following TDD principles
- [x] All tests pass
- [x] Original issue reproduced in test
- [x] Fix resolves the issue
- [x] End-to-end CLI test successful
- [x] No regression in existing functionality
- [x] Documentation updated
