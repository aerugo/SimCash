# Optimizer Prompt Improvements - Work Notes

## Session: 2025-12-13

### Initial Analysis Complete

Identified three issues from audit output review:

1. **Agent Isolation Violation** (CRITICAL)
   - `filter_events_for_agent()` exists in `event_filter.py` but is NEVER called
   - `events` parameter accepted by `PolicyOptimizer.optimize()` but completely ignored
   - BANK_A can see BANK_B's outgoing transactions - this invalidates optimization results

2. **Poor Event Formatting**
   - Current: `RtgsImmediateSettlement: tx_id=..., amount=$40.90`
   - CLI uses: Rich formatted output with emojis, tables, grouping by tick

3. **Section Hierarchy Wrong**
   - Initial simulation nested inside `<best_seed_output>` tags
   - Should be the most prominent section, not buried

### Phase 1: Agent Isolation (TDD) - COMPLETE ✅

#### Step 1: Write Failing Tests

Created `api/tests/ai_cash_mgmt/unit/test_prompt_agent_isolation.py` with 11 tests:
- `TestEnrichedBootstrapContextBuilderIsolation` (4 tests)
- `TestSingleAgentContextIsolation` (2 tests)
- `TestOptimizationPromptIsolation` (2 tests)
- `TestRtgsSettlementIsolation` (1 test)
- `TestLSMEventIsolation` (2 tests)

All tests initially FAILED as expected, detecting:
- BANK_B's outgoing tx leaked to BANK_A
- BANK_B's policy decisions leaked
- BANK_C<->BANK_D LSM bilateral leaked
- BANK_D-E-F LSM cycle leaked

#### Step 2: Implement Fix

**File: `api/payment_simulator/ai_cash_mgmt/bootstrap/context_builder.py`**
- Modified `format_event_trace_for_llm()` to call `filter_events_for_agent()`
- Convert BootstrapEvent objects to dicts for filtering
- Use index-based matching to preserve original event objects

**File: `api/payment_simulator/ai_cash_mgmt/optimization/policy_optimizer.py`**
- Added import for `filter_events_for_agent` and `format_filtered_output`
- Modified `optimize()` to filter raw events when passed via `events` parameter
- Creates `effective_best_seed_output` from filtered events

#### Step 3: Verify All Tests Pass

All 25 tests pass:
- 11 new agent isolation tests
- 14 existing optimizer prompt integration tests

---

### Phase 2: Section Hierarchy (TDD) - COMPLETE ✅

#### Step 1: Write Failing Tests

Created `api/tests/ai_cash_mgmt/unit/test_prompt_section_hierarchy.py` with 8 tests:
- `TestInitialSimulationSection` (3 tests)
- `TestBootstrapSampleLabeling` (2 tests)
- `TestContextTypesUpdated` (2 tests)
- `TestSectionNumbering` (1 test)

All tests initially FAILED as expected.

#### Step 2: Implement Fix

**File: `api/payment_simulator/ai_cash_mgmt/prompts/context_types.py`**
- Added `initial_simulation_output` field to `SingleAgentContext`

**File: `api/payment_simulator/ai_cash_mgmt/prompts/single_agent_context.py`**
- Added `initial_simulation_output` parameter to `build_single_agent_context()`
- Created new `_build_initial_simulation_section()` method for Section 4
- Renamed `_build_simulation_output_section()` to `_build_bootstrap_samples_section()` (Section 5)
- Updated section numbering (1-8) in Table of Contents and headers
- Bootstrap samples now clearly labeled as such

#### Step 3: Verify All Tests Pass

All 33 tests pass:
- 11 agent isolation tests
- 8 new section hierarchy tests
- 14 existing optimizer prompt integration tests

---

### Phase 3: Event Formatting (TDD) - COMPLETE ✅

#### Step 1: Write Failing Tests

Created `api/tests/ai_cash_mgmt/unit/test_event_formatting.py` with 6 tests:
- `TestCurrencyFormatting` (2 tests) - Already passing
- `TestTickGrouping` (1 test) - Already passing
- `TestSettlementBalanceChanges` (1 test) - FAILED as expected
- `TestVisualMarkers` (2 tests) - Already passing

Only balance change display needed fixing.

#### Step 2: Implement Fix

**File: `api/payment_simulator/ai_cash_mgmt/bootstrap/context_builder.py`**
- Added `_format_settlement_event()` method to show balance changes
- Format: `Balance: $5,000.00 → $4,000.00` for settlements with balance info

#### Step 3: Verify All Tests Pass

All 39 tests pass:
- 11 agent isolation tests
- 8 section hierarchy tests
- 6 event formatting tests
- 14 existing optimizer prompt integration tests

---

## ALL PHASES COMPLETE ✅

Summary of changes:
1. **Agent Isolation (CRITICAL)**: Fixed event filtering to prevent cross-agent data leakage
2. **Section Hierarchy**: Added separate initial simulation section, renamed bootstrap samples
3. **Event Formatting**: Added balance change display for settlement events

---

## Progress Log

| Time | Action | Result |
|------|--------|--------|
| Start | Created development plan | `docs/plans/optimizer_prompt/development_plan.md` |
| | Created work notes | This file |
| | Phase 1: Write failing tests | 11 tests written, all fail as expected |
| | Phase 1: Implement fix | Modified `context_builder.py` and `policy_optimizer.py` |
| | Phase 1: Verify tests pass | All 25 tests pass ✅ |
| | Phase 2: Write failing tests | 8 tests written in `test_prompt_section_hierarchy.py` |
| | Phase 2: Implement fix | Modified `context_types.py` and `single_agent_context.py` |
| | Phase 2: Verify tests pass | All 33 tests pass ✅ |
| | Phase 3: Write failing tests | 6 tests written in `test_event_formatting.py` |
| | Phase 3: Implement fix | Modified `context_builder.py` to show balance changes |
| | Phase 3: Verify tests pass | All 39 tests pass ✅ |
