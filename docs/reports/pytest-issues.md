# Pytest Issues Report

**Generated:** 2025-12-11
**Test Results Summary:**
- **Passed:** 2297
- **Failed:** 26
- **Skipped:** 104
- **XPassed:** 1
- **Warnings:** 7

---

## Failed Tests (26 total)

### Category 1: FileNotFoundError - Wrong Policy Path (25 tests)

**Root Cause:** Tests are looking for policy files in `backend/policies/` but the actual location is `simulator/policies/`.

**Affected Files:**

| File | Line | Wrong Path |
|------|------|------------|
| `test_policy_scenario_complex_policies.py` | 40 | `backend/policies/{policy_name}.json` |
| `test_lsm_metric_fix.py` | 25 | `backend/policies/liquidity_splitting.json` |
| `test_settlement_rate_fix_verification.py` | 25 | `backend/policies/liquidity_splitting.json` |
| `test_validate_policy_cli.py` | 297 | `backend/policies/fifo.json` |
| `test_validate_policy_cli.py` | 304 | `backend/policies/liquidity_splitting.json` |
| `test_smart_splitter_investigation.py` | 32, 157 | `backend/policies/smart_splitter.json` |

**Correct Path Pattern:**
```python
# WRONG (causes failures)
policy_path = Path(__file__).parent.parent.parent.parent / "backend" / "policies" / f"{policy_name}.json"

# CORRECT (use simulator directory)
policy_path = Path(__file__).parent.parent.parent.parent / "simulator" / "policies" / f"{policy_name}.json"
```

**Missing Policies Referenced:**
- `liquidity_splitting.json`
- `goliath_national_bank.json`
- `cautious_liquidity_preserver.json`
- `balanced_cost_optimizer.json`
- `smart_splitter.json`
- `aggressive_market_maker.json`
- `fifo.json`

**Fix Required:** Update path from `backend/policies` to `simulator/policies` in the 5 affected test files.

### Category 2: Assertion Failure (1 test)

**Test:** `test_trace_goliath_national_bank.py::TestGoliathEODRush::test_eod_without_buffer_holds`

**Location:** `api/tests/integration/test_trace_goliath_national_bank.py:162`

**Expected:** `settlement_rate <= 0.1` (should hold transaction)
**Actual:** `settlement_rate = 1.0` (transaction was released)

**Description:** The test verifies that at EOD rush (tick 95/100) with insufficient buffer, the GoliathNationalBank policy should HOLD the transaction. Instead, it released it.

**Possible Causes:**
1. Buffer calculation logic in the policy may have changed
2. Test amounts ($40k balance, $30k payment) may be too small relative to $50M buffer parameter
3. Policy may have fallback logic that releases under certain conditions

**Investigation Needed:** Review GoliathNationalBank policy's EOD rush branch and buffer check logic.

---

## Skipped Tests (104 total)

### Category 1: Castro Module Not Available (~13 tests)

Tests designed to run in Castro's separate virtual environment. These are expected to skip in the main API test environment.

**Files:**
- `test_run_id_core.py` - 2 tests
- `test_context_builder_core.py` - 3 tests
- `test_state_provider_core.py` - 4 tests
- `test_experiment_repository.py` - 2 tests
- `test_optimization_core.py` - 1 test
- `test_verbose_core.py` - 1 test
- `test_experiment_runner_core.py` - 1 test
- `test_llm_client_core.py` - 1 test

**Status:** Expected behavior - these tests should be run from Castro's environment.

### Category 2: DataService Not Yet Implemented (~19 tests)

**File:** `test_data_service.py`

Tests for a DataService module that hasn't been implemented yet. All tests skip with "DataService not yet implemented".

**Status:** Future implementation required.

### Category 3: Config Files Not Found (~12 tests)

Tests that skip when specific YAML config files are missing.

**Missing Config Files:**
- `comprehensive_feature_showcase_ultra_stressed.yaml`
- `5_agent_lsm_collateral_scenario.yaml`
- `three_day_realistic_crisis_scenario.yaml`

**Files with these skips:**
- `test_determinism_gold_standard.py`
- `test_ten_day_crisis_scenario.py`
- `test_split_parent_investigation.py`
- `test_settlement_rate_debug.py`
- `test_collateral_crisis_scenario.py`
- `test_cli_event_filters.py`
- `test_output_equivalence.py` (multiple tests)
- `test_diagnostic_dashboard_e2e.py`

**Available Configs in `examples/configs/`:**
- `test_minimal_eod.yaml`
- `test_near_deadline.yaml`
- `target2_lsm_features_test.yaml`
- `test_priority_escalation.yaml`
- `bis_liquidity_delay_tradeoff.yaml`
- `target2_crisis_25day.yaml`
- `target2_crisis_25day_bad_policy.yaml`
- `suboptimal_policies_10day.yaml`
- `suboptimal_policies_25day.yaml`
- `crisis_resolution_10day.yaml`
- `advanced_policy_crisis.yaml`

**Status:** Either create missing configs or update tests to use existing configs.

### Category 4: API Output Strategy Not Implemented (~18 tests)

**File:** `test_api_output_strategy.py`

Tests for output strategies (JSON, WebSocket, Null) that haven't been implemented yet.

**Skipped Features:**
- `JSONOutputStrategy`
- `WebSocketOutputStrategy`
- `NullOutputStrategy`
- General protocol implementations

**Status:** Future implementation required.

### Category 5: State Provider Factory Not Implemented (~14 tests)

**File:** `test_api_state_provider_factory.py`

Tests for a factory pattern that hasn't been implemented yet.

**Status:** Future implementation required.

### Category 6: YAML Loader json_path Support (~4 tests)

**File:** `test_collateral_crisis_scenario.py`

Tests skipped because YAML loader doesn't support `json_path` policies yet.

**Status:** Feature enhancement required.

### Category 7: Runner Migration Feature Flag (~2 tests)

**File:** `test_runner_migration.py`

Tests waiting for a feature flag to be added.

**Status:** Feature flag implementation required.

### Category 8: Enriched Events Not Implemented (~4 tests)

**File:** `test_replay_identity_gold_standard.py`

Tests requiring full implementation of enriched events.

**Status:** Feature implementation required.

### Category 9: TransactionReprioritized Action (~2 tests)

**File:** `test_prioritization_replay_identity.py`

Tests for `TransactionReprioritized` action that requires FromJson policy with Reprioritize action.

**Status:** Future enhancement.

### Category 10: Runtime Condition Skips (~16+ tests)

Tests that skip based on runtime conditions (e.g., no LSM events occurred, no settlements, etc.):

- "No LSM bilateral offsets occurred"
- "No RTGS settlements occurred"
- "No settlements occurred"
- "No arrivals generated"
- "No queued transactions"
- "No near-deadline section found"
- "No credit utilization found"
- "No CostAccrual events"
- "Database locked"

**Status:** These are expected - tests skip when scenarios don't produce the data they need to verify.

### Category 11: Miscellaneous (~8 tests)

Other specific skips:

| Test | Reason |
|------|--------|
| `test_three_day_realistic_crisis_scenario_event_counts` | Expects 48 events but only 44 generated |
| `test_split_transaction_settlement_rate` | API changed - `get_all_transactions()` removed |
| `test_collateral_posts_events_for_all_agent_trees` | No policies have collateral trees implemented |
| `test_drops_transactions_when_deadline_reached` | System marks overdue instead of dropping |
| `test_state_register_persistence` (2 tests) | Not implemented yet - awaiting full integration |

---

## XPassed Test (1)

An unexpectedly passing test - a test marked with `xfail` that now passes. This typically indicates a bug was fixed or the test conditions changed.

**Action:** Review and remove the `xfail` marker if the test should now pass consistently.

---

## Warnings (7)

Standard pytest warnings, typically deprecation warnings or collection warnings. Review pytest output for specific details.

---

## Recommended Actions

### Immediate (Fix Failing Tests)

1. **Fix policy path issue (25 tests):**
   ```bash
   # Files to update:
   # - api/tests/integration/test_policy_scenario_complex_policies.py
   # - api/tests/integration/test_lsm_metric_fix.py
   # - api/tests/integration/test_settlement_rate_fix_verification.py
   # - api/tests/unit/test_validate_policy_cli.py
   # - api/tests/integration/test_smart_splitter_investigation.py

   # Change: "backend" -> "simulator"
   ```

2. **Investigate test_eod_without_buffer_holds:**
   - Review GoliathNationalBank policy logic
   - Check if buffer parameters match test expectations
   - Consider if test amounts need scaling

### Short-term (Reduce Skipped Tests)

3. **Create missing config files or update tests:**
   - `comprehensive_feature_showcase_ultra_stressed.yaml`
   - `5_agent_lsm_collateral_scenario.yaml`
   - `three_day_realistic_crisis_scenario.yaml`

4. **Review XPassed test and update marker**

### Long-term (Feature Implementation)

5. **Implement DataService** (19 tests blocked)
6. **Implement API OutputStrategies** (18 tests blocked)
7. **Implement StateProviderFactory** (14 tests blocked)
8. **Add YAML loader json_path support** (4 tests blocked)
9. **Add runner migration feature flag** (2 tests blocked)
10. **Complete enriched events implementation** (4 tests blocked)

---

## Test Health Summary

| Category | Count | Status |
|----------|-------|--------|
| Passing | 2297 | Healthy |
| Failed - Path Issue | 25 | **Fix Required** |
| Failed - Assertion | 1 | **Investigation Required** |
| Skipped - Castro | ~13 | Expected (different env) |
| Skipped - Not Implemented | ~55 | Feature backlog |
| Skipped - Missing Config | ~12 | Create configs or update tests |
| Skipped - Runtime | ~16+ | Expected behavior |
| XPassed | 1 | Review and update |

**Overall Assessment:** The test suite is fundamentally healthy. The 25 path-related failures are a simple fix (wrong directory name). The remaining issues are primarily due to features not yet implemented or tests designed for a different environment.
