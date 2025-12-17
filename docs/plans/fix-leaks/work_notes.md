# Fix Payment Agent Information Leakage - Work Notes

**Project**: Fix critical information leakage in LLM payment policy optimization
**Started**: 2025-12-17
**Branch**: claude/fix-payment-agent-leakage-OCT0n

---

## Session Log

### 2025-12-17 - Initial Investigation and Planning

**Context Review Completed**:
- Read `docs/reference/patterns-and-conventions.md` - identified applicable invariants: INV-1 (money as i64), INV-5 (replay identity)
- Read `api/payment_simulator/ai_cash_mgmt/prompts/event_filter.py` - understood correct filtering behavior
- Read `api/payment_simulator/ai_cash_mgmt/bootstrap/context_builder.py` - found balance leakage bug
- Read `api/payment_simulator/experiments/runner/optimization.py` - found cost aggregation issue
- Read `api/tests/ai_cash_mgmt/unit/test_prompt_agent_isolation.py` - understood existing tests

**Applicable Invariants**:
- INV-1: All costs and amounts remain integer cents
- INV-5: Event structure unchanged; only formatting changes

**Key Insights**:
1. Two different formatters exist with inconsistent behavior:
   - `event_filter.py._format_single_event()` - Correctly hides sender balance from receivers
   - `context_builder.py._format_settlement_event()` - LEAKS sender balance unconditionally
2. LSM events expose counterparty transaction amounts and net positions
3. Cost breakdown aggregates system-wide, not per-agent

**Confirmed Leakage via Testing**:
```python
# Receiver BANK_A sees sender BANK_B's balance change:
[tick 1] RtgsImmediateSettlement: tx_id=tx_b_pays_a, amount=$500.00
  Balance: $10,000.00 → $9,500.00  ← BANK_B's balance LEAKED!
```

**Completed**:
- [x] Investigated leakage vectors
- [x] Confirmed balance leakage with test script
- [x] Confirmed LSM event exposure
- [x] Created development plan
- [x] Created work notes

**Next Steps**:
1. ~~Create phase 1 plan (balance leakage)~~ DONE
2. ~~Write failing tests proving leakage~~ DONE
3. ~~Fix `_format_settlement_event()` to check agent_id~~ DONE
4. ~~Verify tests pass~~ DONE

---

## Phase Progress

### Phase 1: Fix Balance Leakage
**Status**: Complete
**Started**: 2025-12-17
**Completed**: 2025-12-17

#### Results
- Added TDD tests proving balance leakage exists (3 tests)
- Fixed `_format_settlement_event()` to check `sender == self._agent_id` before showing balance
- All 3 tests now pass

#### Files Modified
- `api/payment_simulator/ai_cash_mgmt/bootstrap/context_builder.py` - Added sender check
- `api/tests/ai_cash_mgmt/unit/test_prompt_agent_isolation.py` - Added 3 balance isolation tests

### Phase 2: LSM Event Sanitization
**Status**: Complete
**Started**: 2025-12-17
**Completed**: 2025-12-17

#### Results
- Added TDD tests for LSM event leakage (4 tests)
- Added `_format_lsm_bilateral()` - shows only viewing agent's position
- Added `_format_lsm_cycle()` - shows participation and total, hides individual amounts/positions
- All 4 tests pass

#### Files Modified
- `api/payment_simulator/ai_cash_mgmt/bootstrap/context_builder.py` - Added LSM formatters
- `api/tests/ai_cash_mgmt/unit/test_prompt_agent_isolation.py` - Added 4 LSM sanitization tests

### Phase 3: Cost Breakdown Isolation
**Status**: Complete (already working)
**Started**: 2025-12-17
**Completed**: 2025-12-17

#### Results
- Added TDD tests for cost isolation (2 tests)
- Tests revealed cost isolation already works via `per_agent_costs` field
- No code changes needed - `_get_agent_cost()` method already uses per-agent costs

---

## Key Decisions

### Decision 1: Fix Formatting, Not Event Structure
**Rationale**: Events contain balance data for legitimate audit trail purposes. The fix should be in the LLM-facing formatter, not the event structure itself. This preserves replay identity and audit capabilities.

### Decision 2: Consolidate on Agent-Aware Formatting
**Rationale**: `event_filter.py` already has correct agent-aware formatting. We should apply the same pattern to `context_builder.py` to ensure consistency.

---

## Issues Encountered

(None yet - will be updated during implementation)

---

## Files Modified

### To Create
- `docs/plans/fix-leaks/development-plan.md` - Development plan
- `docs/plans/fix-leaks/work_notes.md` - This file
- `docs/plans/fix-leaks/phases/phase_1.md` - Balance leakage fix plan
- `docs/plans/fix-leaks/phases/phase_2.md` - LSM sanitization plan
- `docs/plans/fix-leaks/phases/phase_3.md` - Cost isolation plan

### To Modify
- `api/payment_simulator/ai_cash_mgmt/bootstrap/context_builder.py` - Fix balance/LSM leakage
- `api/payment_simulator/experiments/runner/optimization.py` - Fix cost aggregation
- `api/tests/ai_cash_mgmt/unit/test_prompt_agent_isolation.py` - Add leakage tests

---

## Documentation Updates Required

### patterns-and-conventions.md Changes
- [ ] Add INV-10: Agent Isolation invariant

### Other Documentation
- [ ] Update api/CLAUDE.md if needed
