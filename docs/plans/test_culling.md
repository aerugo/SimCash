# Test Suite Culling Plan

**Status:** Draft
**Created:** 2025-12-11
**Last Updated:** 2025-12-11

## Overview

The api/ test suite has grown to **2,482 tests** across **233 test files**. Many tests are likely redundant, obsolete, or debugging artifacts that no longer guard against regression. This document identifies candidates for removal to significantly speed up the test suite.

## Test Distribution Summary

| Directory | Tests | Files | Notes |
|-----------|-------|-------|-------|
| tests/integration/ | 975 | 96 | Largest category, high redundancy potential |
| tests/experiments/ | 451 | 32 | Experiment framework tests |
| tests/unit/ | 450 | 61 | Core unit tests |
| tests/ai_cash_mgmt/ | 426 | 38 | AI/Castro features |
| tests/cli/ | 59 | 5 | CLI command tests |
| tests/llm/ | 44 | 11 | LLM integration tests |
| tests/ffi/ | 35 | 5 | Rust FFI boundary tests |
| tests/e2e/ | 27 | 3 | End-to-end tests |

---

## Category 1: Debug/Investigation Tests (REMOVE)

These tests are debugging artifacts that have served their purpose. They often contain extensive `print()` statements, `pytest.fail()` for bug reproduction, or hypotheses in comments.

**Estimated Test Reduction: ~15-20 tests**

| File | Tests | Reason for Removal |
|------|-------|-------------------|
| `test_overdue_debug.py` | 1 | Debug script with print statements to understand transaction state |
| `test_settlement_rate_debug.py` | 1 | Investigation script for >100% settlement rate bug (fixed) |
| `test_smart_splitter_investigation.py` | 2 | Bug reproduction tests with `pytest.fail()` - bug has been fixed |
| `test_split_parent_investigation.py` | 1 | Investigation of split parent settlements - hypothesis documented |

### Action Items

```bash
# Files to delete
rm tests/integration/test_overdue_debug.py
rm tests/integration/test_settlement_rate_debug.py
rm tests/integration/test_smart_splitter_investigation.py
rm tests/integration/test_split_parent_investigation.py
```

---

## Category 2: Redundant Replay Identity Tests (CONSOLIDATE)

Per CLAUDE.md, `test_replay_identity_gold_standard.py` is the **authoritative test suite** for replay identity. Multiple other files test the same invariant from different angles.

**Estimated Test Reduction: ~60-70 tests**

### Keep (Authoritative)

| File | Tests | Role |
|------|-------|------|
| `test_replay_identity_gold_standard.py` | 14 | **KEEP** - Authoritative per CLAUDE.md |

### Remove or Consolidate

| File | Tests | Reason |
|------|-------|--------|
| `test_replay_identity.py` | 2 | Older basic version, covered by gold standard |
| `test_replay_identity_comprehensive.py` | 13 | Older CLI-based version |
| `test_replay_identity_comprehensive_v2.py` | 5 | Post-fix version, now covered by gold standard |
| `test_run_replay_identity.py` | 7 | Event-level tests, overlaps with gold standard |
| `test_run_replay_byte_identical.py` | 4 | SHA256 hash comparison, redundant with gold standard |
| `test_replay_output_determinism.py` | 6 | Output determinism, covered by gold standard |
| `test_replay_missing_events.py` | 5 | TDD tests for specific bugs, now fixed |

### Action Items

1. Review `test_replay_identity_gold_standard.py` to ensure complete coverage
2. Extract any unique test scenarios from files to be removed
3. Delete redundant files:

```bash
# Files to delete after verifying coverage
rm tests/integration/test_replay_identity.py
rm tests/integration/test_replay_identity_comprehensive.py
rm tests/integration/test_replay_identity_comprehensive_v2.py
rm tests/integration/test_run_replay_identity.py
rm tests/integration/test_run_replay_byte_identical.py
rm tests/integration/test_replay_output_determinism.py
rm tests/integration/test_replay_missing_events.py
```

---

## Category 3: Policy Trace Tests (EVALUATE)

These tests use the `PolicyScenarioTest` framework to trace individual transactions through policy decision trees. They're NOT debugging artifacts - they're legitimate policy validation tests.

**Recommendation: KEEP most, evaluate for consolidation**

| File | Tests | Notes |
|------|-------|-------|
| `test_trace_goliath_national_bank.py` | ~8 | Tests GoliathNationalBank policy branches |
| `test_trace_balanced_policy.py` | ~10 | Tests BalancedCostOptimizer policy branches |
| `test_trace_cautious_policy.py` | ~8 | Tests CautiousPolicyDriven branches |
| `test_trace_smart_splitter.py` | ~6 | Tests SMART_SPLITTER splitting logic |

### Considerations

- These tests provide valuable branch coverage for complex JSON policies
- They could potentially be consolidated into a single file with policy as a parameter
- Keep if policies are actively maintained; evaluate if policies are deprecated

---

## Category 4: Potentially Redundant API Tests (EVALUATE)

Multiple integration test files appear to test overlapping API functionality.

**Estimated Test Reduction: ~30-50 tests (after evaluation)**

| File | Tests | Overlap With |
|------|-------|--------------|
| `test_api_output_strategy.py` | 22 | test_api_output_consistency.py |
| `test_api_output_consistency.py` | 17 | test_api_output_strategy.py |
| `test_phase1_api_enhancements.py` | 22 | Various API tests - may be historical |
| `test_cost_api.py` | 25 | test_cost_ffi.py |
| `test_cost_ffi.py` | 16 | test_cost_api.py |

### Action Items

1. Diff the test files to identify unique vs duplicate coverage
2. Consolidate overlapping tests into single authoritative files
3. Remove historical "phase1" tests if features are now stable

---

## Category 5: Large Test Files (OPTIMIZE)

Files with 30+ tests may benefit from splitting or optimization.

| File | Tests | Lines | Notes |
|------|-------|-------|-------|
| `test_policy_engine_unit.py` | 33 | 1709 | Large but seems comprehensive |
| `test_event_filter.py` | 41 | 667 | May have redundant filter tests |
| `test_cli_commands.py` (experiments) | 37 | 609 | May overlap with other CLI tests |

---

## Category 6: Replay-Related Tests (FURTHER CONSOLIDATION)

Beyond the replay identity tests, there are additional replay-related files:

| File | Tests | Action |
|------|-------|--------|
| `test_replay_verbose_bugs.py` | 15 | **EVALUATE** - Bug regression tests, may be covered elsewhere |
| `test_replay_display_sections.py` | 3 | **EVALUATE** - Display-specific tests |
| `test_replay_eod_metrics_scope.py` | 3 | **EVALUATE** - EOD-specific tests |
| `test_replay_queue_sizes_json.py` | 2 | **EVALUATE** - Queue-specific tests |
| `test_replay_settlement_counting.py` | 2 | **EVALUATE** - Settlement counting |
| `test_filtered_replay_for_castro.py` | 10 | **KEEP** - Castro-specific filtering |
| `test_prioritization_replay_identity.py` | 8 | **EVALUATE** - Priority-specific |
| `test_overdue_replay_identity.py` | 3 | **EVALUATE** - Overdue-specific |
| `test_scenario_events_replay_identity.py` | 4 | **EVALUATE** - Scenario events |
| `test_credit_utilization_replay.py` | 2 | **EVALUATE** - Credit utilization |
| `test_scenario_replay_cli.py` | varies | **EVALUATE** - CLI replay scenarios |

**Potential reduction:** 30-40 tests if consolidated into gold standard or removed as duplicates

---

## Implementation Plan

### Phase 1: Remove Debug/Investigation Tests
**Impact:** ~5-10 tests removed
**Risk:** Very Low
**Effort:** 1 hour

1. Verify bugs referenced in investigation tests are closed
2. Delete the 4 identified investigation/debug test files
3. Run full test suite to ensure no dependencies

### Phase 2: Consolidate Replay Identity Tests
**Impact:** ~60-70 tests removed
**Risk:** Medium (ensure coverage preserved)
**Effort:** 4-6 hours

1. Create a coverage map of `test_replay_identity_gold_standard.py`
2. Review each redundant replay test file for unique scenarios
3. Add any missing scenarios to gold standard
4. Delete redundant files
5. Run full test suite

### Phase 3: Evaluate API Test Overlap
**Impact:** ~30-50 tests removed
**Risk:** Medium
**Effort:** 4-6 hours

1. Generate diff reports between similar API test files
2. Identify tests that duplicate exact same assertions
3. Choose authoritative file for each API area
4. Consolidate and remove

### Phase 4: Evaluate Remaining Replay Tests
**Impact:** ~30-40 tests removed
**Risk:** Medium
**Effort:** 4-6 hours

1. Review each remaining replay test file
2. Determine if covered by gold standard or serves unique purpose
3. Consolidate or remove as appropriate

---

## Expected Results

| Phase | Tests Removed | Cumulative Reduction |
|-------|---------------|----------------------|
| Phase 1 | 5-10 | 5-10 |
| Phase 2 | 60-70 | 65-80 |
| Phase 3 | 30-50 | 95-130 |
| Phase 4 | 30-40 | 125-170 |

**Total Expected Reduction:** 125-170 tests (5-7% of total)

### Time Savings Estimate

Assuming an average of 0.5s per test:
- Current: ~2,500 tests × 0.5s = **20+ minutes**
- After culling: ~2,350 tests × 0.5s = **~19 minutes**
- Savings: **~1-2 minutes per run**

For more significant savings, consider:
1. **Parallelization:** Use pytest-xdist for parallel execution
2. **Test markers:** Add `@pytest.mark.slow` for expensive tests
3. **Selective runs:** Create test profiles for CI vs local development

---

## Files Marked for Removal (Phase 1 Only)

The following files can be safely removed immediately:

```bash
# Debug/Investigation tests
api/tests/integration/test_overdue_debug.py
api/tests/integration/test_settlement_rate_debug.py
api/tests/integration/test_smart_splitter_investigation.py
api/tests/integration/test_split_parent_investigation.py
```

---

## Category 7: Tests Using Deprecated Settlement Event (UPDATE)

Per CLAUDE.md Breaking Changes (2025-11-16), the generic `Settlement` event has been removed. Tests using `event_type == "Settlement"` may be broken or testing deprecated behavior.

**Files with deprecated Settlement event references:**

| File | Instances | Action |
|------|-----------|--------|
| `test_state_register_display.py` | 1 | Update to use specific event types |
| `test_run_command.py` | 1 | Update filter test |
| `test_filter_agent_coverage.py` | 2 | Update filter tests |
| `test_event_timeline_api.py` | 4 | Update API filter tests |
| `test_custom_transaction_arrival.py` | 1 | Update event filtering |
| `test_split_parent_investigation.py` | 1 | **REMOVE** (already in Category 1) |
| `test_settlement_count_fix.py` | 1 | Update or remove if obsolete |
| `test_api_output_strategy.py` | 1 | Update mock data |
| `test_simulation_stats.py` | 1 | Update mock data |
| `test_simulation_runner.py` | 1 | Update mock data |
| `test_event_filter.py` | 6 | Update filter tests to use new event types |

### Action Items

1. Search and replace `Settlement` with appropriate specific event types:
   - For RTGS immediate settlements: `RtgsImmediateSettlement`
   - For queue-2 releases: `Queue2LiquidityRelease`
   - For LSM bilateral: `LsmBilateralOffset`
   - For LSM multilateral: `LsmCycleSettlement`

2. Update EventFilter tests to use new event type names

---

## Review Checklist

Before removing any test file:

- [ ] Verify the bug/feature being tested is no longer actively changing
- [ ] Check if the test scenario is covered by another test
- [ ] Search for imports of the test file
- [ ] Run full test suite after removal
- [ ] Check git blame to understand original intent

---

## Notes

- The trace tests (test_trace_*.py) look like debugging artifacts by name but are actually legitimate policy branch coverage tests using the PolicyScenarioTest framework
- The replay identity tests are the highest value targets for consolidation
- Consider adding test markers to distinguish fast vs slow tests for CI optimization
