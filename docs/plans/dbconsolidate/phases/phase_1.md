# Phase 1: Delete Dead Code (Castro Audit Tables)

**Status**: ✅ Complete
**Completed**: 2025-12-14
**Estimated Effort**: Small
**Risk Level**: Low (dead code removal)

---

## Goal

Remove unused Castro audit tables and their associated code. These tables are defined but never written to by the experiment framework.

## Dead Code Inventory

### Tables to Remove

| Table | Location | Why Dead |
|-------|----------|----------|
| `llm_interaction_log` | `ai_cash_mgmt/persistence/repository.py` | Experiments use `experiment_events` instead |
| `policy_diffs` | `ai_cash_mgmt/persistence/repository.py` | Never written to |
| `iteration_context` | `ai_cash_mgmt/persistence/repository.py` | Never written to |

### Models to Remove

| Model | Location |
|-------|----------|
| `LLMInteractionRecord` | `ai_cash_mgmt/persistence/models.py` |
| `PolicyDiffRecord` | `ai_cash_mgmt/persistence/models.py` |
| `IterationContextRecord` | `ai_cash_mgmt/persistence/models.py` |

### Repository Methods to Remove

From `GameRepository` in `ai_cash_mgmt/persistence/repository.py`:

```
# LLM Interaction methods
save_llm_interaction()
get_llm_interactions()
get_failed_parsing_attempts()
_row_to_llm_interaction()

# Policy Diff methods
save_policy_diff()
get_policy_diffs()
get_parameter_trajectory()
_row_to_policy_diff()

# Iteration Context methods
save_iteration_context()
get_iteration_contexts()
_row_to_iteration_context()
```

### Tests to Remove/Update

| Test File | Action |
|-----------|--------|
| `tests/ai_cash_mgmt/integration/test_database_integration.py` | Remove dead code tests |
| `tests/ai_cash_mgmt/unit/test_game_config.py` | Check for audit table refs |
| `tests/integration/test_castro_audit_trail_persistence.py` | Delete file |
| `tests/unit/test_castro_audit_trail_models.py` | Delete file |

### Migration File to Delete

- `api/migrations/004_add_audit_tables.sql`

---

## TDD Approach

### Step 1: Write Verification Tests (RED)

Before deleting anything, write tests that verify the dead code is truly unused:

```python
# tests/unit/test_dead_code_verification.py

def test_experiment_does_not_use_llm_interaction_log():
    """Verify experiments don't write to llm_interaction_log table."""
    # Run a minimal experiment
    # Check llm_interaction_log table is empty
    # This test should PASS (confirming code is dead)

def test_experiment_does_not_use_policy_diffs():
    """Verify experiments don't write to policy_diffs table."""
    pass

def test_experiment_does_not_use_iteration_context():
    """Verify experiments don't write to iteration_context table."""
    pass

def test_llm_interactions_stored_in_experiment_events():
    """Verify LLM interactions ARE stored in experiment_events."""
    # Run experiment that triggers LLM
    # Check experiment_events has llm_interaction events
    pass
```

### Step 2: Delete Dead Models

1. Remove from `ai_cash_mgmt/persistence/models.py`:
   - `LLMInteractionRecord` class
   - `PolicyDiffRecord` class
   - `IterationContextRecord` class

2. Run tests to ensure no imports break

### Step 3: Delete Dead Repository Methods

1. Remove from `ai_cash_mgmt/persistence/repository.py`:
   - Table creation in `initialize_schema()`
   - All methods listed above
   - Index creation for dead tables

2. Run tests

### Step 4: Delete Dead Test Files

1. Delete `tests/integration/test_castro_audit_trail_persistence.py`
2. Delete `tests/unit/test_castro_audit_trail_models.py`
3. Update any other test files with references

### Step 5: Delete Migration File

1. Delete `api/migrations/004_add_audit_tables.sql`
2. Verify migration system still works

### Step 6: Final Verification (GREEN)

Run full test suite:
```bash
cd api
.venv/bin/python -m pytest
.venv/bin/python -m mypy payment_simulator/
.venv/bin/python -m ruff check payment_simulator/
```

---

## Sub-Phase Checklist

- [x] **1.1** Write verification tests confirming dead code
- [x] **1.2** Delete `LLMInteractionRecord`, `PolicyDiffRecord`, `IterationContextRecord` models
- [x] **1.3** Delete repository methods for dead tables
- [x] **1.4** Delete table creation SQL from `initialize_schema()`
- [x] **1.5** Delete test files for dead code
- [x] **1.6** Delete migration file `004_add_audit_tables.sql`
- [x] **1.7** Run full test suite
- [x] **1.8** Run mypy and ruff
- [x] **1.9** Update work_notes.md with completion

---

## Rollback Plan

If issues are discovered:
1. Revert commits
2. Re-add dead code
3. Investigate why code appeared dead but isn't

---

## Files Changed Summary

| File | Change |
|------|--------|
| `ai_cash_mgmt/persistence/models.py` | Remove 3 model classes (~120 lines) |
| `ai_cash_mgmt/persistence/repository.py` | Remove table creation + methods (~300 lines) |
| `migrations/004_add_audit_tables.sql` | Delete file |
| `tests/integration/test_castro_audit_trail_persistence.py` | Delete file |
| `tests/unit/test_castro_audit_trail_models.py` | Delete file |
| `tests/unit/test_dead_code_verification.py` | New file (verification) |

---

## Acceptance Criteria

- [x] All dead tables removed from schema
- [x] All dead models removed
- [x] All dead repository methods removed
- [x] No import errors
- [x] All existing tests pass (database integration tests: 12/12)
- [x] mypy passes
- [x] ruff passes
- [ ] Experiments still run correctly (manual verification) - skipped, will verify in Phase 5
