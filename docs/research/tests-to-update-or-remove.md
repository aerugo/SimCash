# Tests to Update or Remove for credit_limit Deprecation

**Last Updated**: 2025-11-15
**Related**: `deprecate-backwards-compatibility-guide.md`, `deprecation-checklist.md`

---

## Overview

This document catalogs all tests that reference `credit_limit` and categorizes them by the action required during the deprecation process.

**Total files found**: 102 test files reference `credit_limit`

**Categories**:
1. **UPDATE**: Tests that use `credit_limit` in fixtures (mechanical rename to `unsecured_cap`)
2. **REMOVE**: Tests specifically testing backwards compatibility logic (delete entirely)
3. **KEEP**: Tests that are unrelated to credit_limit backwards compatibility (no changes needed)

---

## Tests to REMOVE (Delete Entirely)

These tests specifically verify backwards compatibility logic that will be removed.

### Rust Tests (Backend)

#### 1. `backend/tests/test_release_flags.rs`
**Lines**: 284-300

**Test Name**: `test_release_backward_compatible_construction`

**Purpose**: Tests that `ReleaseDecision` enum can be constructed with omitted optional fields (backwards compatibility for policy release flags)

**Action**: **KEEP** - This is testing policy decision backwards compatibility, NOT credit_limit/unsecured_cap backwards compatibility.

**Rationale**: Different feature domain. This test should remain.

---

#### 2. `backend/tests/test_lsm_t2_compliant.rs`
**Lines**: 95-xxx

**Test Name**: `test_cycle_equal_amounts_backward_compatible`

**Purpose**: Tests that LSM handles equal-value cycles consistently with pre-T2 implementation

**Action**: **KEEP** - This is testing LSM algorithm backwards compatibility, NOT credit_limit.

**Rationale**: Different feature domain. This test verifies LSM correctness.

---

#### 3. `backend/tests/test_bank_budgets.rs`
**Line**: 522

**Comment**: `// Test that policy without bank_tree is still valid (backward compatibility)`

**Action**: **KEEP** - This is testing policy tree backwards compatibility, NOT credit_limit.

---

### Python Tests (API)

#### 4. `api/tests/integration/test_config_json_persistence.py`
**Lines**: 183-223

**Test Name**: `test_backwards_compatibility_without_config_json`

**Purpose**: Tests that old database records without the `config_json` field still work

**Action**: **KEEP** - This is testing database schema backwards compatibility, NOT credit_limit.

**Rationale**: Different feature. Database migrations are separate from config schema migrations.

---

#### 5. `api/tests/test_cli.py`
**Line**: 219

**Test Name**: `test_jq_compatibility`

**Purpose**: Tests JSON output compatibility with `jq` command-line tool

**Action**: **KEEP** - This is testing CLI output format, NOT credit_limit.

---

### Summary of Tests to REMOVE

**Count**: 0

**Finding**: There are NO tests specifically testing credit_limit → unsecured_cap backwards compatibility logic.

**Implication**: The backwards compatibility code was added without corresponding tests! This is a risk, but also makes deprecation simpler (no tests to remove).

---

## Tests to UPDATE (Mechanical Refactoring)

These tests use `credit_limit` in configuration fixtures and need mechanical updates to use `unsecured_cap` instead.

### High-Priority Updates (Core Functionality Tests)

#### 1. `api/tests/integration/test_credit_limit_enforcement.py`
**Lines**: All (entire file)

**Purpose**: Tests that credit limits are enforced (RTGS, LSM bilateral, LSM multilateral)

**Action**: **UPDATE** - Rename all `credit_limit` to `unsecured_cap` in configs

**Reason**: This tests the feature (overdraft enforcement), not backwards compatibility

**Example Change**:
```python
# BEFORE
"credit_limit": 500000,

# AFTER
"unsecured_cap": 500000,
```

**Impact**: 4 test methods, ~20 occurrences of `credit_limit`

---

#### 2. `api/tests/unit/test_persistence_credit_limit.py`
**Lines**: All (entire file)

**Purpose**: Tests that credit limits are persisted for replay

**Action**: **UPDATE AND RENAME FILE**

**Changes Required**:
1. Rename file: `test_persistence_credit_limit.py` → `test_persistence_unsecured_cap.py`
2. Update all `credit_limit` → `unsecured_cap` in code
3. Update docstrings
4. Update method names: `get_agent_credit_limit` → `get_agent_unsecured_cap`

**Example**:
```python
# BEFORE
assert "credit_limit" in bank_a_state
assert bank_a_state["credit_limit"] == 500000

# AFTER
assert "unsecured_cap" in bank_a_state
assert bank_a_state["unsecured_cap"] == 500000
```

**Impact**: 2 test classes, ~15 occurrences

---

### Rust Backend Tests (All Need UPDATE)

**Files**: 30 Rust test files

**Action**: For each file, update test fixtures:

```rust
// BEFORE
let config = AgentConfig {
    id: "BANK_A".to_string(),
    opening_balance: 1_000_000,
    credit_limit: 200_000,
    unsecured_cap: None,
    // ...
};

// AFTER
let config = AgentConfig {
    id: "BANK_A".to_string(),
    opening_balance: 1_000_000,
    unsecured_cap: 200_000,  // No longer Option<i64>
    // ...
};
```

**Automation**:
```bash
cd backend

# Step 1: Replace in test files
find tests/ -name "*.rs" -exec sed -i 's/credit_limit: \([0-9]*\),/unsecured_cap: \1,/g' {} \;

# Step 2: Remove unsecured_cap: None lines (if credit_limit was set)
# This requires manual review as sed doesn't handle multi-line well

# Step 3: Verify compilation
cargo test --no-default-features --no-run
```

**Manual Review Required**: Yes - ensure no semantic changes

---

### Python API/Integration Tests (All Need UPDATE)

**Files**: 68 Python test files

**Action**: For each file, update config dicts:

```python
# BEFORE
"credit_limit": 200000,

# AFTER
"unsecured_cap": 200000,
```

**Automation**:
```bash
cd api

# Step 1: Replace in test files
find tests/ -name "*.py" -exec sed -i 's/"credit_limit": /"unsecured_cap": /g' {} \;

# Step 2: Verify tests pass
uv run pytest tests/
```

**Manual Review Required**: Yes - verify no semantic changes

---

## Detailed File-by-File Breakdown

### Rust Backend Tests (30 files)

| File | Occurrences | Action | Notes |
|------|-------------|--------|-------|
| `test_agent.rs` | ~10 | UPDATE | Core agent tests |
| `test_orchestrator_integration.rs` | ~15 | UPDATE | Integration tests |
| `test_rtgs_settlement.rs` | ~5 | UPDATE | RTGS tests |
| `test_lsm.rs` | ~8 | UPDATE | LSM tests |
| `test_collateral_edge_cases.rs` | ~12 | UPDATE | Collateral tests |
| `test_checkpoint.rs` | ~6 | UPDATE | Checkpoint tests |
| `test_overdraft_regime.rs` | ~20 | UPDATE | Critical - overdraft tests |
| `test_policy_*` (8 files) | ~30 | UPDATE | Policy engine tests |
| Others (18 files) | ~50 | UPDATE | Various integration tests |

**Total Rust Test Updates**: ~156 occurrences across 30 files

---

### Python Integration Tests (68 files)

| Category | Files | Action | Notes |
|----------|-------|--------|-------|
| FFI tests | 6 | UPDATE | `api/tests/ffi/test_*.py` |
| CLI tests | 3 | UPDATE | `api/tests/cli/test_*.py` |
| Integration tests | 50 | UPDATE | `api/tests/integration/test_*.py` |
| E2E tests | 3 | UPDATE | `api/tests/e2e/test_*.py` |
| Unit tests | 6 | UPDATE | `api/tests/unit/test_*.py` |

**Total Python Test Updates**: ~200+ occurrences across 68 files

---

## Tests That Need Special Attention

### 1. Snapshot/Checkpoint Tests

**Files**:
- `backend/tests/test_checkpoint.rs`
- `api/tests/ffi/test_checkpoint.py`
- `api/tests/cli/test_checkpoint_cli.py`
- `api/tests/e2e/test_checkpoint_integration.py`
- `api/tests/integration/test_checkpoint_persistence.py`

**Issue**: These tests may rely on serialized checkpoint data that includes `credit_limit` field.

**Action**:
1. Update config fixtures to use `unsecured_cap`
2. Verify checkpoint serialization excludes `credit_limit`
3. Test that old checkpoints with `credit_limit` fail gracefully with clear error message

**Example Test to Add**:
```python
def test_old_checkpoint_with_credit_limit_rejected():
    """Verify that checkpoints from before deprecation are rejected."""
    # Create a mock checkpoint with credit_limit field
    old_checkpoint = {..., "credit_limit": 500000}

    with pytest.raises(ValueError, match="credit_limit.*no longer supported"):
        restore_from_checkpoint(old_checkpoint)
```

---

### 2. Replay Identity Tests

**Files**:
- `api/tests/integration/test_replay_identity*.py` (6 files)
- `api/tests/integration/test_run_replay_*.py` (3 files)

**Issue**: These tests verify run/replay output identity. If credit_limit is referenced in verbose output, these tests may fail during migration.

**Action**:
1. Update config fixtures to use `unsecured_cap`
2. Verify that replay still produces identical output
3. Update any expected output strings that reference "credit limit"

---

### 3. Persistence Tests

**Files**:
- `api/tests/integration/test_*_persistence.py` (15 files)
- `api/tests/unit/test_persistence_credit_limit.py`

**Issue**: Tests verify database persistence. Schema changes may affect these.

**Action**:
1. Update fixtures
2. Verify database schema doesn't store `credit_limit` (only `unsecured_cap`)
3. Test that queries for agent overdraft capacity use correct field name

---

### 4. Verbose Output Tests

**Files**:
- `backend/tests/test_verbose_cli_ffi.rs`
- Any tests checking CLI output strings

**Issue**: Verbose output may contain "credit limit" terminology

**Action**:
1. Update expected output strings: "Credit Limit" → "Unsecured Cap"
2. Verify display formatters use new terminology

---

## Automated Update Strategy

### Phase 1: Automated Search & Replace

```bash
#!/bin/bash
# Script: update_tests_credit_limit.sh

set -e

echo "=== Phase 1: Automated Search & Replace ==="

# Rust tests
echo "Updating Rust test configs..."
cd backend/tests
find . -name "*.rs" -exec sed -i 's/credit_limit: \([0-9_]*\)/unsecured_cap: \1/g' {} \;

# Python tests
echo "Updating Python test configs..."
cd ../../api/tests
find . -name "*.py" -exec sed -i 's/"credit_limit": /"unsecured_cap": /g' {} \;

echo "✓ Automated updates complete"
echo ""
echo "Next steps:"
echo "1. Run: cd backend && cargo test --no-default-features"
echo "2. Run: cd api && uv run pytest"
echo "3. Manually review and fix any failures"
```

### Phase 2: Manual Review Checklist

For each failing test:
- [ ] Is it a compilation error? → Update struct field access
- [ ] Is it a config parsing error? → Update config fixture
- [ ] Is it an assertion failure? → Update expected values
- [ ] Is it a serialization error? → Update FFI/database code
- [ ] Is it a backwards compatibility test? → Delete the test

---

## Validation Commands

### After all updates, verify:

```bash
# 1. No credit_limit references in test configs (except comments)
git grep '"credit_limit"' -- 'api/tests/**/*.py' | grep -v '#'  # Should be empty
git grep 'credit_limit:' -- 'backend/tests/**/*.rs' | grep -v '//'  # Should be empty

# 2. All unsecured_cap references are present
git grep 'unsecured_cap' -- 'api/tests/**/*.py' | wc -l  # Should be ~200+
git grep 'unsecured_cap' -- 'backend/tests/**/*.rs' | wc -l  # Should be ~150+

# 3. All tests pass
cd backend && cargo test --no-default-features
cd api && uv run pytest
```

---

## Estimated Effort

| Task | Files | Occurrences | Time Estimate |
|------|-------|-------------|---------------|
| Automated search/replace | 98 | ~400 | 30 minutes |
| Manual review & fixes | 98 | ~50 failures | 3-4 hours |
| Snapshot/checkpoint updates | 5 | ~20 | 1 hour |
| Replay identity verification | 9 | ~30 | 1 hour |
| Persistence test updates | 16 | ~40 | 1-2 hours |
| Verbose output updates | 2 | ~5 | 30 minutes |
| Final validation | All | All | 1 hour |

**Total**: 8-10 hours

---

## Success Criteria

- [ ] All Rust tests pass: `cargo test --no-default-features`
- [ ] All Python tests pass: `uv run pytest`
- [ ] No `credit_limit` in test configs (except comments)
- [ ] Replay identity tests still pass
- [ ] Checkpoint tests handle old format gracefully
- [ ] Persistence tests use `unsecured_cap` field
- [ ] Verbose output uses new terminology

---

## Rollback Strategy

If test updates introduce bugs:

```bash
# Revert all test changes
git checkout HEAD -- backend/tests/
git checkout HEAD -- api/tests/

# Or revert individual files
git checkout HEAD -- backend/tests/test_specific_file.rs
```

---

## Notes

### Finding 1: No Dedicated Backwards Compatibility Tests
The search revealed **zero tests** specifically verifying the credit_limit → unsecured_cap backwards compatibility logic. This means:
- ✅ **Good**: No tests to delete during deprecation
- ❌ **Bad**: Backwards compatibility was never explicitly tested
- ⚠️ **Implication**: May have already had bugs in backwards compatibility logic

### Finding 2: Most Tests Are Mechanical Updates
~95% of test changes are simple search/replace operations:
- `"credit_limit": 500000` → `"unsecured_cap": 500000`
- `credit_limit: 200_000` → `unsecured_cap: 200_000`

This can be largely automated with careful sed/awk scripts.

### Finding 3: High Test Coverage of Feature
The 102 test files using `credit_limit` demonstrate strong test coverage of the overdraft feature itself. These tests should continue to work after renaming the field.

---

## Appendix: Full File List

### Rust Backend Tests (30 files)
```
backend/src/policy/tree/tests/test_phase_9_5_integration.rs
backend/tests/test_checkpoint.rs
backend/tests/test_event_emission.rs
backend/tests/test_agent.rs
backend/tests/test_overdraft_regime.rs
backend/tests/test_orchestrator_integration.rs
backend/tests/test_policy_deadline_scenarios.rs
backend/tests/test_collateral_event_tracking.rs
backend/tests/test_verbose_cli_ffi.rs
backend/tests/test_rtgs_settlement.rs
backend/tests/test_policy_liquidity_scenarios.rs
backend/tests/test_counterparty_fields.rs
backend/tests/test_lsm_awareness_fields.rs
backend/tests/test_collateral_edge_cases.rs
backend/tests/test_lsm_t2_compliant.rs
backend/tests/test_policy_json_integration.rs
backend/tests/test_transaction_splitting.rs
backend/tests/test_math_helpers.rs
backend/tests/test_throughput_progress_fields.rs
backend/tests/test_collateral_timer_invariants.rs
backend/tests/test_cost_accrual.rs
backend/tests/orchestrator_scenario_events_test.rs
backend/tests/test_public_signal_fields.rs
backend/tests/test_bps_conversion.rs
backend/tests/test_lsm.rs
backend/tests/test_lsm_cycle_detection.rs
backend/tests/test_ffi_scenario_events.rs
backend/tests/test_policy_fifo_scenarios.rs
backend/tests/test_three_bank_policies.rs
backend/tests/test_agent_collateral_math.rs
backend/tests/test_policy_stress.rs
backend/tests/scenario_events_test.rs
backend/tests/test_orchestrator_collateral_integration.rs
```

### Python Tests (68 files)
```
api/tests/ffi/test_transaction_submission.py
api/tests/ffi/test_tick_execution.py
api/tests/ffi/test_orchestrator_creation.py
api/tests/ffi/test_checkpoint.py
api/tests/ffi/test_determinism.py
api/tests/ffi/test_state_queries.py
api/tests/cli/test_run_command.py
api/tests/cli/test_checkpoint_cli.py
api/tests/integration/test_api_transactions.py
api/tests/integration/test_agent_arrival_rate_change.py
api/tests/integration/test_policy_scenario_complex_policies.py
api/tests/integration/test_replay_identity_gold_standard.py
api/tests/integration/test_state_provider_contract.py
api/tests/integration/test_collateral_headroom.py
api/tests/integration/test_api_simulations.py
api/tests/integration/test_decision_path_tracking.py
api/tests/integration/test_budget_display.py
api/tests/integration/test_settlement_count_fix.py
api/tests/integration/test_policy_scenario_comparative.py
api/tests/integration/test_replay_identity.py
api/tests/integration/test_collateral_crisis_scenario.py
api/tests/integration/test_counterparty_weight_change.py
api/tests/integration/test_settlement_rate_fix_verification.py
api/tests/integration/test_lsm_event_completeness.py
api/tests/integration/test_credit_limit_enforcement.py
api/tests/integration/test_phase1_api_enhancements.py
api/tests/integration/test_diagnostic_endpoints.py
api/tests/integration/test_event_persistence.py
api/tests/integration/test_transaction_persistence.py
api/tests/integration/test_determinism_gold_standard.py
api/tests/integration/test_replay_output_determinism.py
api/tests/integration/test_query_interface.py
api/tests/integration/test_scenario_events_ffi.py
api/tests/integration/test_global_arrival_rate_change.py
api/tests/integration/test_replay_identity_comprehensive_v2.py
api/tests/integration/test_overdue_transactions.py
api/tests/integration/test_run_replay_identity.py
api/tests/integration/test_run_replay_byte_identical.py
api/tests/integration/test_queue_persistence.py
api/tests/integration/test_collateral_policy_event_persistence.py
api/tests/integration/test_lsm_metric_fix.py
api/tests/integration/test_config_json_persistence.py
api/tests/integration/test_scenario_events_persistence.py
api/tests/integration/test_overdue_verbose_e2e.py
api/tests/integration/test_settlement_rate_debug.py
api/tests/integration/test_overdue_replay_identity.py
api/tests/integration/test_policy_snapshot_persistence.py
api/tests/integration/test_split_transaction_settlement_rate.py
api/tests/integration/test_new_runner_integration.py
api/tests/integration/test_runner_migration.py
api/tests/integration/test_queries.py
api/tests/integration/test_lsm_activation.py
api/tests/integration/test_scenario_events_replay_identity.py
api/tests/integration/test_collateral_event_persistence.py
api/tests/integration/test_lsm_event_logging.py
api/tests/integration/test_collateral_withdrawal_invariants.py
api/tests/integration/test_simulation_metadata_persistence.py
api/tests/integration/test_overdue_debug.py
api/tests/integration/test_scenario_events_edge_cases.py
api/tests/integration/test_agent_metrics.py
api/tests/integration/test_policy_engine_unit.py
api/tests/integration/test_overdue_ffi_methods.py
api/tests/integration/test_policy_snapshots.py
api/tests/integration/test_diagnostic_api_config_json.py
api/tests/integration/test_settlement_classification.py
api/tests/integration/test_cost_api.py
api/tests/integration/test_deadline_window_change.py
api/tests/integration/test_agent_metrics_persistence.py
api/tests/integration/test_collateral_timer_auto_withdrawal.py
api/tests/integration/test_transaction_status_heuristic_bug.py
api/tests/integration/test_lsm_cycle_persistence.py
api/tests/integration/test_smart_splitter_investigation.py
api/tests/integration/test_performance_diagnostics.py
api/tests/integration/test_checkpoint_persistence.py
api/tests/integration/test_scenario_replay_cli.py
api/tests/integration/test_custom_transaction_arrival.py
api/tests/integration/test_split_parent_investigation.py
api/tests/integration/test_cost_ffi.py
api/tests/integration/test_trace_goliath_national_bank.py
api/tests/integration/test_event_timeline_api.py
api/tests/e2e/test_checkpoint_integration.py
api/tests/e2e/test_checkpoint_api.py
api/tests/test_cli.py
api/tests/unit/test_deadline_capping.py
api/tests/unit/test_persistence_credit_limit.py
api/tests/unit/test_queue2_events.py
api/tests/unit/test_simulation_record_config_json.py
api/tests/unit/test_output_unified.py
api/tests/unit/test_database_schema.py
api/tests/unit/test_scenario_event_schemas.py
api/tests/unit/test_config.py
api/tests/unit/test_queue2_settlement_events.py
api/tests/unit/test_state_provider.py
```

---

**Last Updated**: 2025-11-15
**Next Steps**: Execute automated updates, then manual review
**See Also**: `deprecate-backwards-compatibility-guide.md`, `deprecation-checklist.md`
