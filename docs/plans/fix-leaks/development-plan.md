# Fix Payment Agent Information Leakage - Development Plan

**Status**: In Progress
**Created**: 2025-12-17
**Branch**: claude/fix-payment-agent-leakage-OCT0n

## Summary

Fix critical information leakage vulnerabilities in the LLM-based payment policy optimization system where agents can see other agents' balance information, transaction details, and cost breakdowns that should be isolated.

## Critical Invariants to Respect

- **INV-1**: Money is ALWAYS i64 - All amounts in events and cost breakdowns are integer cents
- **INV-5**: Replay Identity - Event structure changes must not break replay (we're only changing formatting, not event content)

### NEW Invariant to Introduce

- **NEW INV-10**: Agent Isolation - An LLM optimizing for Agent X may ONLY see:
  - Outgoing transactions FROM Agent X
  - Incoming liquidity events TO Agent X (amount only, no sender balance)
  - Agent X's own policy and state changes
  - Agent X's own cost breakdown (not system-wide aggregate)

## Current State Analysis

### Problem Statement

During policy optimization, agent LLM prompts receive information that violates agent isolation:

1. **Balance Leakage**: `context_builder.py._format_settlement_event()` shows sender's balance to receivers
2. **LSM Event Exposure**: Bilateral/cycle events expose counterparty amounts and net positions
3. **Cost Aggregation**: Cost breakdown aggregates ALL agents' costs, not per-agent

### Root Cause

Two different event formatters exist with inconsistent behavior:
- `event_filter.py._format_single_event()` - Correctly hides sender balance from receivers
- `context_builder.py._format_settlement_event()` - LEAKS sender balance unconditionally

### Files to Modify

| File | Current State | Planned Changes |
|------|---------------|-----------------|
| `api/payment_simulator/ai_cash_mgmt/bootstrap/context_builder.py` | Shows sender balance to all viewers | Add sender check before showing balance; sanitize LSM event details |
| `api/payment_simulator/experiments/runner/optimization.py` | Aggregates system-wide costs | Extract per-agent cost breakdown |
| `api/tests/ai_cash_mgmt/unit/test_prompt_agent_isolation.py` | Tests basic filtering | Add tests for balance/LSM/cost leakage |

## Solution Design

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Event Flow to LLM Prompts                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Rust Events → EnrichedEvaluationResult.event_trace                 │
│                           │                                         │
│                           ▼                                         │
│           ┌───────────────────────────────────┐                     │
│           │ filter_events_for_agent()         │ ← FILTER (exists)   │
│           │ (decides WHICH events to include) │                     │
│           └───────────────────────────────────┘                     │
│                           │                                         │
│                           ▼                                         │
│           ┌───────────────────────────────────┐                     │
│           │ _format_settlement_event()        │ ← SANITIZE (FIX!)   │
│           │ (decides WHAT fields to show)     │                     │
│           └───────────────────────────────────┘                     │
│                           │                                         │
│                           ▼                                         │
│                    LLM Prompt                                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **Fix in context_builder.py, not event structure**: The events contain correct data for audit trails; we only sanitize what's shown to LLMs
2. **Per-agent cost breakdown**: Use existing `per_agent_costs` field in EnrichedEvaluationResult instead of aggregating all
3. **LSM event sanitization**: Show only information relevant to the viewing agent's position

## Phase Overview

| Phase | Description | TDD Focus | Estimated Tests |
|-------|-------------|-----------|-----------------|
| 1 | Fix RtgsImmediateSettlement balance leakage | Verify receiver cannot see sender balance | 3 tests |
| 2 | Sanitize LSM event details | Verify counterparty-specific data hidden | 4 tests |
| 3 | Fix cost breakdown isolation | Verify per-agent costs, not system-wide | 2 tests |

## Phase 1: Fix Balance Leakage

**Goal**: Ensure receivers of RTGS settlements cannot see sender's balance change

### Deliverables
1. Failing tests proving balance leakage exists
2. Fix in `context_builder.py._format_settlement_event()`
3. Passing tests confirming fix

### TDD Approach
1. Write failing test: receiver sees sender balance (currently fails - leakage exists)
2. Modify `_format_settlement_event()` to check if agent is sender before showing balance
3. Verify test passes

### Success Criteria
- [ ] Test proves receiver CANNOT see sender_balance_before/after
- [ ] Test proves sender CAN still see their own balance
- [ ] All existing tests still pass

## Phase 2: Sanitize LSM Events

**Goal**: LSM events only show information relevant to the viewing agent

### Deliverables
1. Failing tests for LSM information exposure
2. Modified `_format_event_details()` for LSM events
3. Passing tests

### TDD Approach
1. Write tests proving bilateral/cycle events expose counterparty data
2. Add agent-aware formatting for `LsmBilateralOffset` and `LsmCycleSettlement`
3. Verify sanitized output

### Success Criteria
- [ ] Bilateral offset shows only viewing agent's position
- [ ] Cycle settlement shows only total saved, not all net_positions
- [ ] Agent participation is visible but amounts are agent-specific

## Phase 3: Cost Breakdown Isolation

**Goal**: Cost breakdown shows only the target agent's costs, not system-wide aggregate

### Deliverables
1. Failing test for system-wide cost aggregation
2. Fix in `optimization.py` to use per-agent costs
3. Passing tests

### TDD Approach
1. Write test that cost_breakdown reflects agent-specific costs
2. Modify cost aggregation to use `per_agent_costs` from EnrichedEvaluationResult
3. Verify isolation

### Success Criteria
- [ ] Agent's cost breakdown reflects only their costs
- [ ] Different agents get different cost breakdowns from same simulation

## Testing Strategy

### Unit Tests
- `test_balance_not_leaked_to_receiver` - Receiver sees settlement amount but not sender balance
- `test_balance_visible_to_sender` - Sender sees their own balance change
- `test_lsm_bilateral_hides_counterparty_amount` - Only own side visible
- `test_lsm_cycle_hides_net_positions` - Net positions not exposed
- `test_cost_breakdown_per_agent` - Costs are agent-specific

### Integration Tests
- Full optimization loop with multi-agent scenario verifying isolation

### Identity/Invariant Tests
- New tests in `test_prompt_agent_isolation.py` enforcing INV-10 (Agent Isolation)

## Documentation Updates

After implementation is complete, update the following:

- [ ] `docs/reference/patterns-and-conventions.md` - Add INV-10: Agent Isolation invariant
- [ ] Update `api/CLAUDE.md` if needed for agent isolation guidance

## Progress Tracking

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1 | Complete | Balance leakage fix - sender check added |
| Phase 2 | Complete | LSM event sanitization - bilateral/cycle formatters added |
| Phase 3 | Complete | Cost breakdown isolation - already working via per_agent_costs |
