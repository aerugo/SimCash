# Unified Replay Architecture - Implementation Ready

**Status:** ✅ Planning Complete, Ready for Implementation
**Date:** 2025-11-09
**Estimated Effort:** 27-37 hours (3-5 days)

## Quick Start

You're about to complete the transition to a unified replay architecture. Everything is planned, documented, and ready to go.

### What's Been Done ✅

1. **Comprehensive Plan** ([`docs/plans/unified-replay-architecture-completion.md`](plans/unified-replay-architecture-completion.md))
   - 8-phase implementation roadmap
   - Detailed technical specifications
   - Risk assessment and mitigation strategies

2. **Gold Standard Test Suite** ([`api/tests/integration/test_replay_identity_gold_standard.py`](../api/tests/integration/test_replay_identity_gold_standard.py))
   - 14 TDD tests defining success criteria
   - Event enrichment tests
   - FFI serialization tests
   - Replay integrity tests
   - Regression tests for known bugs

3. **Complete Documentation**
   - Updated `CLAUDE.md` with mandatory workflows
   - Implementation guide with examples
   - Troubleshooting playbook
   - Testing checklist

### What Needs To Be Done

Follow the 8-phase plan in order. Each phase builds on the previous one.

## Phase-by-Phase Implementation

### Phase 1: Baseline (5 minutes)

Run the test suite to see current state:

```bash
cd /Users/hugi/GitRepos/cashman/api
.venv/bin/pytest tests/integration/test_replay_identity_gold_standard.py -v
```

**Expected:** Most tests skipped (scenarios don't trigger events) or failing (enriched fields don't exist).

**This is correct** - you're doing TDD!

### Phase 2: Enrich Rust Event Types (6-8 hours)

**Goal:** Add ALL display fields to Event enum variants.

**Files to modify:**
- `backend/src/models/event.rs` - Expand Event enum
- `backend/src/settlement/lsm.rs` - Populate LSM events
- `backend/src/orchestrator/engine.rs` - Populate collateral events

**Key changes:**

```rust
// backend/src/models/event.rs

pub enum Event {
    // ... existing variants ...

    LsmBilateralOffset {
        tick: i64,
        agent_a: String,       // NEW
        agent_b: String,       // NEW
        amount_a: i64,         // NEW
        amount_b: i64,         // NEW
        tx_ids: Vec<String>,
    },

    LsmCycleSettlement {
        tick: i64,
        agents: Vec<String>,           // NEW
        tx_amounts: Vec<i64>,          // NEW
        total_value: i64,              // NEW
        net_positions: Vec<i64>,       // NEW
        max_net_outflow: i64,          // NEW
        max_net_outflow_agent: String, // NEW
        tx_ids: Vec<String>,
    },

    CollateralPosted {
        tick: i64,
        agent_id: String,
        amount: i64,
        new_total: i64,       // NEW
        trigger: String,      // NEW
    },

    CollateralReleased {
        tick: i64,
        agent_id: String,
        amount: i64,
        new_total: i64,       // NEW
        trigger: String,      // NEW
    },
}
```

**Test:**
```bash
cd backend
cargo test --no-default-features
```

**Success criteria:** Rust tests pass, Event types compile.

### Phase 3: Update FFI Layer (3-4 hours)

**Goal:** Serialize ALL new fields across FFI boundary.

**Files to modify:**
- `backend/src/ffi/orchestrator.rs`

**Key changes:**

In `get_tick_events()` and `get_all_events()`, update event serialization:

```rust
Event::LsmBilateralOffset { tick, agent_a, agent_b, amount_a, amount_b, tx_ids } => {
    let mut dict = HashMap::new();
    dict.insert("event_type".to_string(), "lsm_bilateral_offset".into());
    dict.insert("tick".to_string(), tick.into());
    dict.insert("agent_a".to_string(), agent_a.into());
    dict.insert("agent_b".to_string(), agent_b.into());
    dict.insert("amount_a".to_string(), amount_a.into());  // NEW
    dict.insert("amount_b".to_string(), amount_b.into());  // NEW
    dict.insert("tx_ids".to_string(), tx_ids.into());
    dict
}

// Similar for other events...
```

**Test:**
```bash
cd api
.venv/bin/pytest tests/integration/test_replay_identity_gold_standard.py::TestFFIEventSerialization -v
```

**Success criteria:** FFI tests pass, all fields cross the boundary.

### Phase 4: Verify Persistence (2-3 hours)

**Goal:** Ensure `simulation_events` table stores complete enriched events.

**Files to check:**
- `api/payment_simulator/cli/execution/persistence.py`

**What to do:** The `EventWriter` should already handle this automatically. Verify by:

1. Running a simulation with persistence:
```bash
cd api
.venv/bin/payment-sim run --config sim_config_simple_example.yaml --persist test_output.db
```

2. Checking the database:
```bash
sqlite3 test_output.db "SELECT event_type, details FROM simulation_events LIMIT 5;"
```

3. Verify JSON `details` column contains all enriched fields.

**Test:**
```bash
.venv/bin/pytest tests/integration/test_replay_identity_gold_standard.py::TestPersistenceCompleteness -v
```

**Success criteria:** All event fields persist correctly to database.

### Phase 5: Simplify Replay Logic (3-4 hours)

**Goal:** Remove ALL legacy queries and manual reconstruction.

**Files to modify:**
- `api/payment_simulator/cli/commands/replay.py`

**What to remove:**

1. Delete calls to:
   - `get_lsm_cycles_by_tick()`
   - `get_collateral_events_by_tick()`

2. Delete reconstruction functions:
   - `_reconstruct_lsm_events()`
   - `_reconstruct_collateral_events()`

3. Update main loop:

```python
# BEFORE
for tick in range(tick_start, tick_end + 1):
    raw_events = get_simulation_events(sim_id, tick=tick)
    lsm_cycles = get_lsm_cycles_by_tick(sim_id, tick)  # ❌ REMOVE
    collateral = get_collateral_events_by_tick(sim_id, tick)  # ❌ REMOVE
    events = _reconstruct_lsm_events(lsm_cycles)  # ❌ REMOVE
    # ...

# AFTER
for tick in range(tick_start, tick_end + 1):
    result = get_simulation_events(conn, sim_id, tick=tick)
    events = result['events']  # ✅ ONLY SOURCE

    if verbose:
        display_tick_verbose_output(provider, tick, events)
```

**Test:**
```bash
.venv/bin/pytest tests/integration/test_replay_identity_gold_standard.py::TestReplayWithoutReconstruction -v
```

**Success criteria:** Code inspection tests pass (no legacy queries or reconstruction).

### Phase 6: Remove Legacy Infrastructure (2-3 hours)

**Goal:** Clean up redundant tables and code.

**Files to modify:**
- `api/payment_simulator/cli/commands/run.py`
- `api/payment_simulator/persistence/queries.py`
- `api/payment_simulator/persistence/models.py`

**What to do:**

1. **Remove legacy table writes** in `run.py`:
```python
# In _persist_day_data(), DELETE:
if lsm_cycles:
    cursor.executemany("""...""", lsm_cycles)  # ❌ DELETE

if collateral_events:
    cursor.executemany("""...""", collateral_events)  # ❌ DELETE
```

2. **Deprecate legacy queries** in `queries.py`:
```python
@deprecated("Use get_simulation_events() instead")
def get_lsm_cycles_by_tick(...):
    ...
```

3. **Create migration** to drop tables (optional):
```sql
-- migrations/003_remove_legacy_tables.sql
DROP TABLE IF EXISTS lsm_cycles;
-- Keep collateral_events if diagnostic UI uses it
```

**Test:**
```bash
# Verify no code references legacy queries
grep -r "get_lsm_cycles_by_tick\|get_collateral_events_by_tick" api/payment_simulator/cli/commands/
# Should find ZERO results
```

**Success criteria:** No legacy table writes, legacy queries deprecated.

### Phase 7: Documentation Updates (ALREADY DONE ✅)

This phase is complete! Documentation has been updated:

- ✅ `CLAUDE.md` - Comprehensive replay identity guidelines
- ✅ `docs/replay-unified-architecture-implementation.md` - Implementation guide
- ✅ `docs/plans/unified-replay-architecture-completion.md` - Detailed plan

### Phase 8: Validation (3-4 hours)

**Goal:** Verify complete replay identity.

**Tests to run:**

1. **All replay tests:**
```bash
cd api
.venv/bin/pytest tests/integration/test_replay*.py -v
```

2. **Gold standard tests:**
```bash
.venv/bin/pytest tests/integration/test_replay_identity_gold_standard.py -v
```

3. **Manual end-to-end test:**
```bash
# Run with persistence
.venv/bin/payment-sim run --config sim_config_simple_example.yaml --persist output.db --verbose > run_output.txt

# Replay
.venv/bin/payment-sim replay output.db --verbose > replay_output.txt

# Compare (should be identical)
diff <(grep -v "Duration:" run_output.txt) <(grep -v "Duration:" replay_output.txt)
# Expected: NO OUTPUT (files identical)
```

4. **Performance check:**
```bash
# Benchmark replay (should not be slower)
time .venv/bin/payment-sim replay output.db
```

**Success criteria:**
- ✅ All tests pass
- ✅ Manual diff shows no differences
- ✅ No performance regression
- ✅ Code review confirms no legacy queries

## Success Checklist

Mark complete when:

- [ ] All `test_replay_identity_gold_standard.py` tests pass
- [ ] Manual diff test shows identical output
- [ ] No legacy tables exist or are queried
- [ ] No manual reconstruction logic in `replay.py`
- [ ] `replay.py` only calls `get_simulation_events()`
- [ ] FFI serializes all event fields
- [ ] All Rust tests pass
- [ ] All Python integration tests pass
- [ ] Documentation is accurate
- [ ] Code review complete

## If You Get Stuck

### Common Issues

**"Event doesn't have field X"**
- Add field to Event enum in `backend/src/models/event.rs`
- Add FFI serialization in `backend/src/ffi/orchestrator.rs`

**"Test is skipped"**
- Test scenario didn't trigger the event
- This is OK during development
- Adjust scenario or test will pass when real usage triggers it

**"Replay differs from run"**
- Check if replay queries legacy tables (it shouldn't)
- Check if event has all required fields
- Use `grep -r "get_lsm_cycles_by_tick" api/` to find legacy queries

**"Build fails"**
- After Rust changes: `cd api && uv sync --extra dev --reinstall-package payment-simulator`
- Run Rust tests: `cd backend && cargo test --no-default-features`

### Getting Help

1. **Read the docs:**
   - `CLAUDE.md` section on "Critical Invariant: Replay Identity"
   - `docs/replay-unified-architecture-implementation.md`

2. **Check test output:**
   - Tests are designed to guide you
   - Read assertion messages carefully

3. **Inspect events:**
```python
# In Python test
events = orch.get_tick_events(orch.current_tick())
import json
print(json.dumps(events[0], indent=2))
```

## Key Principles to Remember

1. **Single Source of Truth:** `simulation_events` table is the ONLY source for replay.

2. **Rich Events at Source:** Events must contain ALL display data when created in Rust.

3. **No Manual Reconstruction:** Python never reconstructs data - events are already complete.

4. **StateProvider Abstraction:** Display code never touches Rust/DB directly.

## Timeline

Conservative estimate: **27-37 hours** total

- Phase 2 (Rust enrichment): 6-8 hours
- Phase 3 (FFI): 3-4 hours
- Phase 4 (Persistence): 2-3 hours
- Phase 5 (Replay simplification): 3-4 hours
- Phase 6 (Legacy removal): 2-3 hours
- Phase 7 (Documentation): 4-5 hours (DONE ✅)
- Phase 8 (Validation): 3-4 hours

**Actual effort likely:** 3-5 focused workdays

## Next Action

Start with Phase 2:

```bash
# 1. Open the Rust event model
code backend/src/models/event.rs

# 2. Add enriched fields to Event variants
#    Reference: docs/plans/unified-replay-architecture-completion.md Phase 2

# 3. Update event generation sites
code backend/src/settlement/lsm.rs
code backend/src/orchestrator/engine.rs

# 4. Test
cd backend
cargo test --no-default-features
```

Good luck! The groundwork is all laid. Now it's just following the plan.

---

**Questions?** All answers are in the documentation. Start with `CLAUDE.md`.

**Blocked?** Check the troubleshooting section in this doc or `CLAUDE.md`.

**Ready to code?** Phase 2 awaits. Let's ship this! 🚀
