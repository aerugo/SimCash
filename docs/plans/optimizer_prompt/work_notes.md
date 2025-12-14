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

## Progress Log

| Time | Action | Result |
|------|--------|--------|
| Start | Created development plan | `docs/plans/optimizer_prompt/development_plan.md` |
| | Created work notes | This file |
| | Phase 1: Write failing tests | 11 tests written, all fail as expected |
| | Phase 1: Implement fix | Modified `context_builder.py` and `policy_optimizer.py` |
| | Phase 1: Verify tests pass | All 25 tests pass ✅ |
