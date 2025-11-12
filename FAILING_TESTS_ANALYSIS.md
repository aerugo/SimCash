# Test Failure Analysis

## Summary
- **Total Failures**: 29 failed, 13 errors
- **Total Passing**: 725 passed
- **Skipped**: 28 skipped

## Failure Categories

### Category 1: Environment/Path Issues (16 failures)

#### 1.1 Hardcoded CWD Path (5 failures)
**Root Cause**: Tests use hardcoded `cwd='/home/user/SimCash/api'` but actual path is `/Users/hugi/GitRepos/cashman/api`

**Affected Tests**:
- `test_run_replay_identity.py::TestRunReplayIdentity::test_full_tick_output_identity`
- `test_scenario_events_replay_identity.py::test_direct_transfer_replay_identity`
- `test_scenario_events_replay_identity.py::test_multiple_scenario_events_replay_identity`
- `test_scenario_events_replay_identity.py::test_repeating_scenario_event_replay_identity`
- `test_scenario_replay_cli.py::test_scenario_events_replay_identity_simple`

**Fix Strategy**: Use `Path(__file__).parent.parent` to dynamically find project root

#### 1.2 Missing Config Files (11 failures)
**Root Cause**: Tests reference config files in `/Users/hugi/GitRepos/cashman/examples/configs/` but directory structure is different

**Affected Tests**:
- `test_cli_event_filters.py` (13 errors) - needs `12_bank_4_policy_comparison.yaml`
- `test_settlement_rate_debug.py::test_settlement_rate_debug` - needs `5_agent_lsm_collateral_scenario.yaml`
- `test_split_parent_investigation.py::test_split_parent_investigation` - needs `5_agent_lsm_collateral_scenario.yaml`
- `test_ten_day_crisis_scenario.py` (5 failures) - needs `three_day_realistic_crisis_scenario.yaml`

**Fix Strategy**: Either create inline configs or skip tests with clear skip messages

---

### Category 2: API/Method Changes (4 failures)

#### 2.1 inject_transaction() Removed (2 failures)
**Root Cause**: Method renamed/removed, should use `submit_transaction()`

**Affected Tests**:
- `test_queue2_events.py::test_queue2_settlement_generates_distinct_event`
- `test_queue2_events.py::test_settlement_event_still_emitted`

**Fix Strategy**: Replace with `submit_transaction()`

#### 2.2 get_all_transactions() Doesn't Exist (1 failure)
**Root Cause**: Method doesn't exist on Orchestrator

**Affected Tests**:
- `test_split_transaction_settlement_rate.py::test_settlement_rate_bug_with_split_transactions`

**Fix Strategy**: Use alternative API or skip test if feature is deprecated

#### 2.3 DatabaseManager API Change (1 failure)
**Root Cause**: `get_simulation_events()` expects connection object, not DatabaseManager

**Affected Tests**:
- `test_queue1_amounts.py::test_queue1_display_amounts_match_sum`

**Fix Strategy**: Pass `db_manager.get_connection()` instead of `db_manager`

---

### Category 3: Schema/Validation Issues (3 failures)

#### 3.1 Scenario Event Schema Changes
**Root Cause**: Pydantic schemas have changed, tests use old schema structure

**Affected Tests**:
- `test_scenario_event_schemas.py::test_counterparty_weight_change_validation`
- `test_scenario_event_schemas.py::test_deadline_window_change_validation`
- `test_scenario_event_schemas.py::test_all_event_types_to_ffi`

**Errors**:
```
CounterpartyWeightChangeEvent: expects 'counterparty' and 'new_weight' fields, tests use 'new_weights'
DeadlineWindowChangeEvent: expects multipliers, tests use 'new_deadline_range'
```

**Fix Strategy**: Update tests to match new schema definitions

---

### Category 4: Mock Setup Issues (5 failures)

#### 4.1 Mock Not Subscriptable
**Root Cause**: `orch.get_system_metrics()` mock returns Mock object instead of dict

**Affected Tests**:
- `test_simulation_runner.py::TestSimulationRunner::test_runner_calls_lifecycle_hooks_in_order`
- `test_simulation_runner.py::TestSimulationRunner::test_runner_detects_eod_correctly`
- `test_simulation_runner.py::TestSimulationRunner::test_runner_calls_persistence_hooks`
- `test_simulation_runner.py::TestSimulationRunner::test_runner_tracks_statistics_correctly`
- `test_simulation_runner.py::TestSimulationRunner::test_runner_applies_event_filter`

**Error**: `TypeError: 'Mock' object is not subscriptable` at line:
```python
day_arrivals = corrected_metrics["total_arrivals"] - self.previous_cumulative_arrivals
```

**Fix Strategy**: Add `orch.get_system_metrics.return_value = {...}` to mock setup

---

### Category 5: Logic/Calculation Issues (5 failures)

#### 5.1 Determinism Broken (1 failure - CRITICAL)
**Root Cause**: Same seed producing different results

**Affected Tests**:
- `test_determinism.py::test_same_seed_same_results`

**Error**:
```
AssertionError: assert [{'num_arriva... 5, ...}, ...] == [{'num_arriva... 5, ...}, ...]
At index 1 diff: {'tick': 1, 'num_arrivals': 1, ...
```

**Fix Strategy**: INVESTIGATE - This is a critical invariant violation!

#### 5.2 Credit Utilization Calculation Wrong (1 failure)
**Root Cause**: Credit utilization shows 0% instead of expected 60%

**Affected Tests**:
- `test_output_unified.py::TestUnifiedLogAgentState::test_log_agent_state_with_credit_utilization`

**Expected**: `60%` (balance=$200k, credit_limit=$500k → used $300k = 60%)
**Actual**: `0%`

**Fix Strategy**: Check credit calculation logic in `log_agent_state()`

#### 5.3 No Arrivals Generated (2 failures)
**Root Cause**: Arrival generation not working in tests

**Affected Tests**:
- `test_deadline_capping.py::test_deadline_offset_respects_episode_boundary`
- `test_deadline_capping.py::test_deadlines_reasonable_within_episode`

**Error**: `AssertionError: Should have generated arrivals`

**Fix Strategy**: Check if arrival config is correctly passed to Orchestrator

#### 5.4 Float Formatting (1 failure - TRIVIAL)
**Root Cause**: Settlement rate returns `0.0` instead of `0`

**Affected Tests**:
- `test_cli.py::TestAIIntegration::test_jq_compatibility`

**Fix Strategy**: Update assertion to accept `0.0` or format output

---

## Fix Priority

### Priority 1: Quick Wins (Low Risk)
1. ✅ Fix hardcoded paths (5 tests)
2. ✅ Fix float formatting (1 test)
3. ✅ Fix mock setup (5 tests)
4. ✅ Fix API method calls (3 tests)

### Priority 2: Schema Updates (Medium Risk)
5. ✅ Update scenario event schemas (3 tests)

### Priority 3: Missing Configs (Medium Risk)
6. ✅ Skip or create inline configs (11 tests)

### Priority 4: Logic Investigation (High Risk)
7. 🔴 **CRITICAL**: Investigate determinism failure
8. ⚠️ Investigate credit calculation
9. ⚠️ Investigate arrival generation

---

## Implementation Plan

1. Start with Category 1.1 (paths) - straightforward fixes
2. Fix Category 4 (mocks) - add proper return values
3. Fix Category 2 (API changes) - update method calls
4. Fix Category 3 (schemas) - update to new schema
5. Fix Category 1.2 (configs) - skip with messages
6. Fix Category 5.4 (formatting) - trivial change
7. **INVESTIGATE** Category 5.1 (determinism) - requires deep dive
8. **INVESTIGATE** Category 5.2 & 5.3 (logic issues)
