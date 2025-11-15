# Replay Identity Architectural Fix - Implementation Plan

**Date:** 2025-11-15
**Status:** In Progress
**Goal:** Ensure replay output is byte-for-byte identical to run output (modulo timing)

---

## Executive Summary

This plan implements a holistic architectural fix to ENSURE run/replay identity. The key insight is that replay must be a **pure playback** of persisted events, never reconstructing or recalculating.

**Core Strategy:**
1. **StateProvider Pattern** - Unify display code for run and replay
2. **Event Enrichment** - Persist ALL display data in events
3. **Scope Separation** - Separate display range from metrics scope
4. **Zero Recalculation** - Replay only displays persisted data

---

## Phase 1: Unified Display via StateProvider Pattern (CURRENT)

**Goal:** Single display function serves both run and replay modes.

### Current State
- ✅ `StateProvider` protocol exists (`state_provider.py`)
- ✅ `OrchestratorStateProvider` wraps live FFI
- ✅ `DatabaseStateProvider` wraps database queries
- ❌ Display code still has dual paths (run.py vs replay.py)

### Implementation

**Step 1.1: Audit Display Code**
```bash
# Find all display functions
grep -r "def display_" api/payment_simulator/cli/
grep -r "def log_" api/payment_simulator/cli/
```

**Step 1.2: Move Display Logic to Unified Module**
```
api/payment_simulator/cli/display/
├── verbose_output.py       # Main verbose display logic
├── json_output.py          # JSON serialization
├── agent_stats.py          # Agent financial stats
└── tick_summary.py         # Per-tick summaries
```

**Step 1.3: Refactor Display Functions**
Change signature from:
```python
def display_settlements(orch: Orchestrator, tick: int):
    settlements = orch.get_settled_transactions(tick)  # ❌ Direct FFI
```

To:
```python
def display_settlements(provider: StateProvider, tick: int):
    settlements = provider.get_settled_transactions(tick)  # ✅ Abstracted
```

**Step 1.4: Update run.py and replay.py**
```python
# run.py
from payment_simulator.cli.display import display_tick_verbose_output
provider = OrchestratorStateProvider(orchestrator)
display_tick_verbose_output(provider, tick, events)

# replay.py  
from payment_simulator.cli.display import display_tick_verbose_output
provider = DatabaseStateProvider(db_manager, simulation_id)
display_tick_verbose_output(provider, tick, events)
```

**Success Criteria:**
- [ ] All display functions take `StateProvider` parameter
- [ ] No direct `orchestrator.` or `db_manager.` calls in display code
- [ ] run.py and replay.py call identical display functions

---

## Phase 2: Fix Metrics Scope Confusion

**Goal:** Separate "tick range to display" from "simulation scope for metrics".

### Current Issue
Replay queries events for tick 299-299 but tries to show:
- Total transactions across full simulation (shows 6 instead of 549)
- EOD metrics for full day (shows 0 unsettled instead of 110)

### Implementation

**Step 2.1: Add Simulation Metadata to StateProvider**
```python
class StateProvider(Protocol):
    def get_simulation_metadata(self) -> Dict:
        """Get full simulation scope (start/end ticks, total days)."""
        ...
    
    def get_tick_range(self) -> Tuple[int, int]:
        """Get currently displayed tick range (for replay filtering)."""
        ...
```

**Step 2.2: Query Full Simulation for Metrics**
```python
def display_json_summary(provider: StateProvider):
    metadata = provider.get_simulation_metadata()
    
    # ALWAYS query full simulation for metrics, not just display range
    metrics = provider.get_metrics(
        from_tick=0,
        to_tick=metadata['total_ticks']  # ✅ Full scope
    )
```

**Step 2.3: Fix EOD Metrics**
```python
def display_eod_summary(provider: StateProvider, day: int):
    # Query full day range, not just current tick
    day_start = day * provider.get_ticks_per_day()
    day_end = (day + 1) * provider.get_ticks_per_day()
    
    stats = provider.get_day_statistics(
        from_tick=day_start,
        to_tick=day_end  # ✅ Full day scope
    )
```

**Success Criteria:**
- [ ] JSON metrics show full simulation totals in both run and replay
- [ ] EOD summary shows full day statistics, not just displayed tick
- [ ] Replay with `--from-tick 299 --to-tick 299` still shows correct totals

---

## Phase 3: Event Enrichment - Persist Display Data

**Goal:** Events contain ALL fields needed for display, no reconstruction required.

### Current Issues
- LSM events missing TX IDs (shows blank in replay)
- Cannot distinguish RTGS from Queue2 settlements
- Overdue costs recalculated instead of persisted

### Implementation

**Step 3.1: Enrich LSM Events**
```rust
// backend/src/models/event.rs
pub enum Event {
    LsmBilateralOffset {
        tick: usize,
        agent_a: String,
        agent_b: String,
        tx_id_a: String,  // ← Add TX IDs
        tx_id_b: String,  // ← Add TX IDs
        amount_a: i64,
        amount_b: i64,
        net_saved: i64,
    },
}
```

**Step 3.2: Enrich Settlement Events**
```rust
pub enum Event {
    RtgsImmediateSettlement {
        tick: usize,
        tx_id: String,
        sender: String,
        receiver: String,
        amount: i64,
        balance_before: i64,  // ← Add for display
        balance_after: i64,   // ← Add for display
    },
    Queue2LiquidityRelease {
        tick: usize,
        tx_id: String,
        sender: String,
        receiver: String,
        amount: i64,
        queued_ticks: usize,      // ← Add
        release_reason: String,   // ← Add
    },
}
```

**Step 3.3: Persist Calculated Costs**
```rust
pub enum Event {
    TransactionWentOverdue {
        tick: usize,
        tx_id: String,
        sender: String,
        receiver: String,
        amount: i64,
        deadline: usize,
        ticks_late: usize,
        deadline_penalty: i64,        // ← Persist calculated value
        cumulative_delay_cost: i64,   // ← Persist, don't recalculate
    },
}
```

**Success Criteria:**
- [ ] LSM events show TX IDs in replay
- [ ] Settlement detail blocks appear in replay
- [ ] Overdue costs identical between run and replay

---

## Phase 4: Eliminate Recalculation in Replay

**Goal:** Replay displays persisted event data only, never recalculates.

### Current Issues
- Overdue delay costs recalculated with wrong formula (replay: $14,250 vs run: $231.78)
- Credit utilization recalculated (replay: 98% vs run: 171%)

### Implementation

**Step 4.1: Add Cost Summary Events**
```rust
pub enum Event {
    CostAccrualSummary {
        tick: usize,
        total_tick_cost: i64,
        per_agent: Vec<AgentCostBreakdown>,
    },
}

pub struct AgentCostBreakdown {
    agent_id: String,
    liquidity_cost: i64,
    delay_cost: i64,
    penalty_cost: i64,
    total_cost: i64,
}
```

**Step 4.2: Persist Agent State Snapshots**
```rust
pub enum Event {
    AgentStateSnapshot {
        tick: usize,
        agent_id: String,
        balance: i64,
        credit_limit: i64,
        credit_used: i64,
        credit_utilization_pct: f64,  // ← Persist calculated value
        queue1_size: usize,
        queue2_size: usize,
    },
}
```

**Step 4.3: Display from Persisted Values Only**
```python
def display_overdue_transactions(provider: StateProvider, tick: int):
    overdues = provider.get_overdue_transactions(tick)
    
    for tx in overdues:
        # ✅ Use persisted values from event
        delay_cost = tx['cumulative_delay_cost']  # NOT recalculated
        penalty = tx['deadline_penalty']          # NOT recalculated
        
        console.print(f"Overdue: {tx['ticks_late']} ticks")
        console.print(f"Penalty ${penalty/100:.2f} + Delay ${delay_cost/100:.2f}")
```

**Success Criteria:**
- [ ] All costs identical between run and replay
- [ ] Credit utilization % identical
- [ ] No recalculation logic in replay.py

---

## Phase 5: Comprehensive Testing

**Goal:** Ensure replay identity is tested and maintained.

### Test Strategy

**Level 1: Unit Tests (Event Enrichment)**
```python
# tests/unit/test_event_enrichment.py
def test_lsm_bilateral_event_has_tx_ids():
    """LSM bilateral offset events must include TX IDs."""
    event = Event.LsmBilateralOffset(...)
    assert 'tx_id_a' in event
    assert 'tx_id_b' in event
```

**Level 2: Integration Tests (StateProvider Contract)**
```python
# tests/integration/test_state_provider_contract.py
def test_both_providers_return_same_data():
    """OrchestratorStateProvider and DatabaseStateProvider must return identical data."""
    # Run simulation
    orch = Orchestrator.new(config)
    orch.tick()
    
    # Get data from both providers
    orch_provider = OrchestratorStateProvider(orch)
    db_provider = DatabaseStateProvider(db, sim_id)
    
    assert orch_provider.get_balance("BANK_A") == db_provider.get_balance("BANK_A")
```

**Level 3: E2E Tests (Full Replay Identity)**
```python
# tests/integration/test_replay_identity_comprehensive_v2.py
def test_run_replay_byte_identical():
    """Run and replay outputs must be byte-for-byte identical (modulo timing)."""
    # Run simulation
    run_output = run_simulation(config, persist=True)
    
    # Replay full simulation
    replay_output = replay_simulation(db, sim_id)
    
    # Normalize (remove timing)
    assert normalize(run_output) == normalize(replay_output)
```

**Success Criteria:**
- [ ] All 13 discrepancies have failing tests
- [ ] All tests pass after fixes
- [ ] CI/CD enforces replay identity

---

## Implementation Roadmap

### Week 1: Foundation
- [x] Document discrepancies (breaking_replay_identity.md)
- [ ] Write failing tests for all 13 discrepancies
- [ ] Implement Phase 1 (StateProvider pattern)

### Week 2: Core Fixes
- [ ] Implement Phase 2 (Metrics scope)
- [ ] Implement Phase 3 (Event enrichment)
- [ ] Fix high-priority discrepancies (#2, #5, #7)

### Week 3: Completion
- [ ] Implement Phase 4 (Eliminate recalculation)
- [ ] Fix medium-priority discrepancies (#3, #4, #8)
- [ ] All tests passing

### Week 4: Validation
- [ ] Fix low-priority discrepancies (#1, #10, #11, #12, #13)
- [ ] Full regression testing
- [ ] Documentation updates

---

## Success Metrics

### Technical
- ✅ All 13 discrepancies resolved
- ✅ `diff <(run) <(replay)` shows only timing differences
- ✅ Zero recalculation in replay code
- ✅ All display code uses StateProvider

### Quality
- ✅ 100% of replay tests passing
- ✅ No TODO/FIXME comments related to replay
- ✅ CI/CD enforces replay identity
- ✅ Documentation updated

---

## Risk Mitigation

### Risk: Breaking Existing Functionality
**Mitigation:** Comprehensive test coverage before refactoring

### Risk: Performance Degradation
**Mitigation:** Event enrichment happens at generation time (one-time cost)

### Risk: Database Schema Changes
**Mitigation:** Use JSON columns for flexible event data (already implemented)

---

## References

- Discrepancy Catalog: `docs/plans/breaking_replay_identity.md`
- StateProvider Protocol: `api/payment_simulator/cli/execution/state_provider.py`
- CLAUDE.md: Replay Identity section
- Gold Standard Tests: `api/tests/integration/test_replay_identity_gold_standard.py`

---

**Next Action:** Begin Phase 1 implementation - refactor display code to use StateProvider.
