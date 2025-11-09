# Unified Replay Architecture - Implementation Summary

**Status:** Planning Complete, Implementation Ready
**Date:** 2025-11-09
**Priority:** P0 (Critical)

## Overview

This document summarizes the work completed and provides a roadmap for finishing the transition to a unified replay architecture where all simulation events replay with perfect fidelity to the original run.

## What Has Been Done

### 1. Comprehensive Plan Document ✅

**File:** [`docs/plans/unified-replay-architecture-completion.md`](plans/unified-replay-architecture-completion.md)

This document provides:
- Detailed architectural analysis
- Root cause analysis of current replay bugs
- Phase-by-phase implementation plan (8 phases)
- Success criteria
- Risk assessment
- Timeline estimate (27-37 hours)

**Key Insight:** The fundamental issue is that `run` and `replay` use different data sources. The solution is to make `simulation_events` the single source of truth.

### 2. Gold Standard Test Suite ✅

**File:** [`api/tests/integration/test_replay_identity_gold_standard.py`](../api/tests/integration/test_replay_identity_gold_standard.py)

This TDD test suite defines success criteria for complete replay identity:

#### Test Classes

**`TestEventEnrichment`**
- `test_lsm_bilateral_offset_has_all_fields()`: Verifies bilateral offsets contain `agent_a`, `agent_b`, `amount_a`, `amount_b`
- `test_lsm_cycle_settlement_has_all_fields()`: Verifies cycles contain `agents`, `tx_amounts`, `net_positions`, `max_net_outflow`, etc.
- `test_collateral_posted_has_all_fields()`: Verifies collateral events contain `amount`, `new_total`, `trigger`
- `test_transaction_became_overdue_has_all_fields()`: Verifies overdue events have complete data

**`TestFFIEventSerialization`**
- `test_ffi_serializes_lsm_bilateral_completely()`: Verifies FFI doesn't drop fields across Rust→Python boundary

**`TestPersistenceCompleteness`**
- `test_simulation_events_table_stores_enriched_lsm_events()`: Verifies database stores ALL event fields

**`TestReplayWithoutReconstruction`**
- `test_replay_does_not_query_lsm_cycles_table()`: Code inspection test - ensures no legacy queries
- `test_replay_does_not_have_reconstruction_functions()`: Code inspection test - ensures no manual reconstruction

**`TestEndToEndReplayIdentity`**
- Gold standard integration tests (currently skipped - will pass once implementation complete)

**`TestRegressionBugs`**
- `test_bilateral_offset_agent_count_bug_fixed()`: Guards against len(agents)==3 vs len(agents)==2 bug
- `test_event_field_name_consistency()`: Guards against `deadline` vs `deadline_tick` inconsistencies

#### Running the Tests

```bash
# Run all gold standard tests
cd api
.venv/bin/pytest tests/integration/test_replay_identity_gold_standard.py -v

# Run specific test class
.venv/bin/pytest tests/integration/test_replay_identity_gold_standard.py::TestEventEnrichment -v

# Run with verbose output
.venv/bin/pytest tests/integration/test_replay_identity_gold_standard.py -v -s
```

**Current State:** Most tests are skipped or would fail because enriched events are not yet implemented. This is expected and correct for TDD.

### 3. Architectural Foundation ✅

The project already has solid foundations:
- `StateProvider` protocol exists
- `display_tick_verbose_output()` shared display function exists
- `simulation_events` table exists
- `EventWriter` persistence exists

**What's Missing:** Event data isn't rich enough, and replay still queries legacy tables.

## Implementation Roadmap

Follow the [detailed plan](plans/unified-replay-architecture-completion.md) in order. Here's the high-level flow:

### Phase 1: Run Tests Baseline (Current State)

```bash
cd api
.venv/bin/pytest tests/integration/test_replay_identity_gold_standard.py -v
```

**Expected:** Most tests skipped (scenarios don't trigger events) or failing (enriched fields don't exist yet).

### Phase 2: Enrich Rust Event Types

**Files to modify:**
- `backend/src/models/event.rs`
- `backend/src/settlement/lsm.rs`
- `backend/src/orchestrator/engine.rs`

**Action:** Add missing fields to `Event` enum variants:

```rust
LsmBilateralOffset {
    tick: i64,
    agent_a: String,       // NEW
    agent_b: String,       // NEW
    amount_a: i64,         // NEW: Amount flowing A→B
    amount_b: i64,         // NEW: Amount flowing B→A
    tx_ids: Vec<String>,
},
```

**Test:** Run Rust tests to verify Event types compile and are populated.

### Phase 3: Update FFI Layer

**Files to modify:**
- `backend/src/ffi/orchestrator.rs`

**Action:** Update `get_tick_events()` and `get_all_events()` to serialize ALL new fields to Python dicts.

**Test:** Run FFI tests to verify serialization:

```bash
cd api
.venv/bin/pytest tests/integration/test_replay_identity_gold_standard.py::TestFFIEventSerialization -v
```

### Phase 4: Verify Persistence

**Files to check:**
- `api/payment_simulator/cli/execution/persistence.py`

**Action:** Verify `EventWriter` correctly stores enriched events to `simulation_events.details` JSON column.

**Test:** Run persistence tests:

```bash
.venv/bin/pytest tests/integration/test_replay_identity_gold_standard.py::TestPersistenceCompleteness -v
```

### Phase 5: Simplify Replay Logic

**Files to modify:**
- `api/payment_simulator/cli/commands/replay.py`

**Action:**
1. Remove calls to `get_lsm_cycles_by_tick()` and `get_collateral_events_by_tick()`
2. Delete `_reconstruct_lsm_events()` and `_reconstruct_collateral_events()` functions
3. Source ALL events from `get_simulation_events()`

**Test:** Run replay tests:

```bash
.venv/bin/pytest tests/integration/test_replay_identity_gold_standard.py::TestReplayWithoutReconstruction -v
```

### Phase 6: Remove Legacy Infrastructure

**Files to modify:**
- `api/payment_simulator/cli/commands/run.py` (remove legacy table writes)
- `api/payment_simulator/persistence/queries.py` (deprecate legacy queries)

**Action:** Create database migration to drop `lsm_cycles` table.

### Phase 7: Update Documentation

**Files to modify:**
- `CLAUDE.md` (add replay identity maintenance section)
- `api/CLAUDE.md` (add replay implementation notes)
- `docs/replay-architecture.md` (create comprehensive guide)

### Phase 8: Validation

**Action:** Run full test suite:

```bash
# All replay tests
.venv/bin/pytest tests/integration/test_replay*.py -v

# Gold standard tests
.venv/bin/pytest tests/integration/test_replay_identity_gold_standard.py -v

# Manual validation
payment-sim run --config test.yaml --persist output.db --verbose > run.txt
payment-sim replay output.db --verbose > replay.txt
diff <(grep -v "Duration:" run.txt) <(grep -v "Duration:" replay.txt)
# Should output nothing - files identical
```

## Success Criteria

Implementation is complete when:

1. ✅ All tests in `test_replay_identity_gold_standard.py` pass
2. ✅ Manual diff test shows identical output (run vs replay)
3. ✅ No legacy tables exist (`lsm_cycles`, `collateral_events`)
4. ✅ No manual reconstruction logic exists in `replay.py`
5. ✅ `replay.py` only queries `simulation_events` table
6. ✅ Documentation is complete
7. ✅ No performance regression

## Key Design Principles

### 1. Single Source of Truth

**Rule:** `simulation_events` table is the ONLY source for replay.

```
Run Mode:    Rust → FFI → Display
Replay Mode: Database → Display

Both paths must produce identical results.
```

### 2. Rich Events at Source

**Rule:** Events must contain ALL display data when created in Rust.

❌ **Bad:**
```rust
Event::LsmCycleSettlement {
    tx_ids: vec!["tx1", "tx2"],  // Insufficient!
}
```

✅ **Good:**
```rust
Event::LsmCycleSettlement {
    agents: vec!["A", "B", "C"],
    tx_amounts: vec![1000, 2000, 3000],
    net_positions: vec![500, -200, -300],
    max_net_outflow: 500,
    max_net_outflow_agent: "A".to_string(),
    tx_ids: vec!["tx1", "tx2", "tx3"],
}
```

### 3. No Manual Reconstruction

**Rule:** Python never reconstructs data - events are already complete.

❌ **Bad:**
```python
# replay.py
lsm_cycles = get_lsm_cycles_by_tick(tick)
events = _reconstruct_lsm_events(lsm_cycles)  # Manual work!
```

✅ **Good:**
```python
# replay.py
events = get_simulation_events(sim_id, tick=tick)  # Already complete!
display_tick_verbose_output(provider, tick, events)
```

### 4. StateProvider Abstraction

**Rule:** Display code never touches Rust/DB directly.

❌ **Bad:**
```python
def display_lsm_cycle(orch: Orchestrator):  # Couples to Rust!
    cycles = orch.get_lsm_cycles()
```

✅ **Good:**
```python
def display_lsm_cycle(provider: StateProvider):  # Abstract!
    cycles = provider.get_lsm_cycles()
```

## Troubleshooting Common Issues

### "Event field 'X' missing"

**Cause:** FFI not serializing field.

**Fix:** Add field to dict in `backend/src/ffi/orchestrator.rs`:

```rust
dict.insert("X".to_string(), event.X.into());
```

### "Replay output differs from run"

**Cause:** Replay using legacy table instead of `simulation_events`.

**Fix:** Check `replay.py` - should ONLY call `get_simulation_events()`.

### "Test skipped: No [event type] occurred"

**Cause:** Test scenario didn't trigger the event.

**Fix:** This is OK during development. Adjust test scenario if needed, or test passes when real scenarios trigger it.

### "Event has wrong structure"

**Cause:** Rust Event variant doesn't match expected structure.

**Fix:** Update Event enum in `backend/src/models/event.rs`.

## Next Steps

To resume implementation, start with Phase 2 (Enrich Rust Event Types):

```bash
# 1. Read the plan
cat docs/plans/unified-replay-architecture-completion.md

# 2. Open Rust event model
code backend/src/models/event.rs

# 3. Add enriched fields to Event variants

# 4. Run tests to verify
cd backend
cargo test --no-default-features

# 5. Continue through phases 3-8
```

## Additional Resources

- **Detailed Plan:** [`docs/plans/unified-replay-architecture-completion.md`](plans/unified-replay-architecture-completion.md)
- **Gold Standard Tests:** [`api/tests/integration/test_replay_identity_gold_standard.py`](../api/tests/integration/test_replay_identity_gold_standard.py)
- **Existing Replay Tests:** [`api/tests/integration/test_replay_output_determinism.py`](../api/tests/integration/test_replay_output_determinism.py)
- **StateProvider Protocol:** [`api/payment_simulator/cli/execution/state_provider.py`](../api/payment_simulator/cli/execution/state_provider.py)
- **Replay Command:** [`api/payment_simulator/cli/commands/replay.py`](../api/payment_simulator/cli/commands/replay.py)

## References

- Original architectural report (provided in initial conversation)
- CLAUDE.md replay identity invariant documentation
- StateProvider pattern documentation

---

*This document serves as the bridge between planning and implementation. All planning is complete; implementation can now proceed following the TDD approach.*
