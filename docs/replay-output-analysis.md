# Replay Output Discrepancy Analysis

## Problem Statement
Currently, replay of persisted simulations does not produce **identical** verbose output compared to original live execution. This violates the requirement for deterministic reproducibility.

## Root Causes

### 1. Different Output Functions Called

**Live Execution** (`VerboseModeOutput.on_tick_complete`):
- `log_agent_queues_detailed(orch, agent_id, balance, balance_change)`
- `log_cost_breakdown(orch, agent_ids)`

**Replay** (`replay.py`):
- `log_agent_state_from_db(mock_orch, agent_id, state_data, queue_data)`
- `log_cost_breakdown_from_db(agent_states)`

**Impact**: Even with identical data, different functions format output differently.

### 2. Missing Output Sections in Replay

**Present in Live, Missing in Replay:**
- SECTION 3.5: Queued RTGS transactions (`log_queued_rtgs`)
- SECTION 6.5: Cost accrual events (`log_cost_accrual_events`)

**Impact**: Replay output is incomplete compared to live execution.

### 3. MockOrchestrator Lacks Methods

Live execution calls these Orchestrator methods:
- `get_agent_credit_limit(agent_id)` - returns i64
- `get_agent_queue1_contents(agent_id)` - returns list[str]
- `get_rtgs_queue_contents()` - returns list[str]
- `get_agent_collateral_posted(agent_id)` - returns i64
- `get_agent_accumulated_costs(agent_id)` - returns dict
- `get_queue1_size(agent_id)` - returns int

MockOrchestrator only has:
- `get_transaction_details(tx_id)` - returns dict | None

**Impact**: Replay cannot display queue details, credit utilization, collateral, etc.

### 4. Conditional Display Logic Differs

**Live Execution** (lines 156-159 in strategies.py):
```python
if balance_change != 0 or queue1_size > 0 or agent_in_rtgs:
    log_agent_queues_detailed(orch, agent_id, current_balance, balance_change)
```
Shows agent state only if there's activity.

**Replay** (lines 761-764 in replay.py):
```python
for agent_id, state in states_by_agent.items():
    agent_queues = queue_snapshots.get(agent_id, {})
    log_agent_state_from_db(mock_orch, agent_id, state, agent_queues)
```
Shows ALL agents unconditionally (if `has_full_replay` is True).

**Impact**: Replay may show agents with no activity, creating extra output.

### 5. Cost Field Name Mismatch

**Live execution** (`log_cost_breakdown`):
```python
costs.get("deadline_penalty", 0)  # Line 751
```

**Replay** (`log_cost_breakdown_from_db`):
```python
state.get("penalty_cost", 0)  # Line 1098
```

**Impact**: If field names don't match in database, costs won't display correctly.

### 6. Event Reconstruction vs Direct Access

**Live execution**: Calls orchestrator methods to get current state
**Replay**: Reconstructs events from database records

Different code paths mean different potential for bugs/inconsistencies.

---

## Proposed Solution: Unified Output System

### Design Principles

1. **Single Source of Truth**: One set of output functions for both live and replay
2. **Data Interface**: Define a common interface that both Orchestrator and database provide
3. **Complete Persistence**: Persist ALL data needed for identical output
4. **Section Parity**: Replay must have exact same sections as live execution

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Unified Output Functions (output.py)                   │
│  - log_transaction_arrivals()                           │
│  - log_settlement_details()                             │
│  - log_agent_state()  ← UNIFIED, not two versions      │
│  - log_cost_breakdown() ← UNIFIED, not two versions     │
│  - ... all other functions                              │
└─────────────────────────────┬───────────────────────────┘
                              │
                ┌─────────────┴──────────────┐
                │                            │
       ┌────────▼─────────┐        ┌────────▼─────────┐
       │  Live Execution  │        │  Replay Mode     │
       │                  │        │                  │
       │  Data Provider:  │        │  Data Provider:  │
       │  Orchestrator    │        │  DatabaseView    │
       │  (FFI calls)     │        │  (DB queries)    │
       └──────────────────┘        └──────────────────┘
```

### Implementation Plan

#### Step 1: Define Data Provider Protocol

Create `StateProvider` protocol with methods:
- `get_transaction_details(tx_id) -> dict | None`
- `get_agent_balance(agent_id) -> i64`
- `get_agent_credit_limit(agent_id) -> i64`
- `get_agent_queue1_contents(agent_id) -> list[str]`
- `get_rtgs_queue_contents() -> list[str]`
- `get_agent_collateral_posted(agent_id) -> i64`
- `get_agent_accumulated_costs(agent_id) -> dict`
- `get_queue1_size(agent_id) -> int`

#### Step 2: Implement StateProvider for Live Execution

```python
class OrchestratorStateProvider:
    """Wraps Orchestrator to implement StateProvider protocol."""

    def __init__(self, orch: Orchestrator):
        self.orch = orch

    def get_transaction_details(self, tx_id: str) -> dict | None:
        return self.orch.get_transaction_details(tx_id)

    # ... implement all other methods as thin wrappers
```

#### Step 3: Implement StateProvider for Replay

```python
class DatabaseStateProvider:
    """Provides state from database for replay."""

    def __init__(self, conn, simulation_id: str, tick: int,
                 tx_cache: dict, agent_states: dict, queue_snapshots: dict):
        self.conn = conn
        self.simulation_id = simulation_id
        self.tick = tick
        self.tx_cache = tx_cache
        self.agent_states = agent_states
        self.queue_snapshots = queue_snapshots

    def get_transaction_details(self, tx_id: str) -> dict | None:
        # Use tx_cache (already built)
        return self.tx_cache.get(tx_id)

    def get_agent_balance(self, agent_id: str) -> int:
        return self.agent_states[agent_id]["balance"]

    # ... implement all methods from database state
```

#### Step 4: Unify Output Functions

Replace duplicate functions with single implementation:

**BEFORE**:
- `log_agent_queues_detailed(orch, ...)` - for live
- `log_agent_state_from_db(mock_orch, ...)` - for replay

**AFTER**:
- `log_agent_state(provider: StateProvider, agent_id, ...)` - for both

Same for:
- `log_cost_breakdown()` and `log_cost_breakdown_from_db()` → unified `log_cost_breakdown()`

#### Step 5: Expand Database Persistence

**New tables needed**:

1. **`tick_agent_states`** (EXPAND existing table):
   - Add: `credit_limit` (i64)
   - Add: `collateral_posted` (i64)

2. **`tick_queue_snapshots`** (EXPAND existing table):
   - Add: `rtgs_queue` (JSON array of tx_ids)

3. **`cost_accrual_events`** (NEW table):
   ```sql
   CREATE TABLE cost_accrual_events (
       event_id VARCHAR PRIMARY KEY,
       simulation_id VARCHAR NOT NULL,
       tick INTEGER NOT NULL,
       agent_id VARCHAR NOT NULL,
       cost_type VARCHAR NOT NULL,  -- "liquidity", "delay", "collateral", "penalty", "split"
       amount INTEGER NOT NULL,
       details VARCHAR,  -- JSON for extra context
       created_at TIMESTAMP NOT NULL
   );
   ```

4. **`queued_rtgs_events`** (already in simulation_events, but verify):
   - Ensure QueuedRtgs events are persisted with full details

#### Step 6: Update Event Persistence

In `PersistenceManager`, ensure these events are captured:
- QueuedRtgs (with reason)
- CostAccrual (new event type)

#### Step 7: Update Replay Logic

Replace conditional `has_full_replay` checks with:
- Always show all sections (matching live execution)
- If data missing, show placeholder or error message
- Never silently skip sections

#### Step 8: Add Determinism Test

```python
def test_replay_output_identical():
    """Verify replay produces byte-for-byte identical output to live execution."""

    # Run simulation with verbose output captured
    live_output = run_simulation_capture_output(config, verbose=True)

    # Replay from database
    replay_output = replay_simulation_capture_output(sim_id, verbose=True)

    # Compare line by line
    live_lines = live_output.splitlines()
    replay_lines = replay_output.splitlines()

    assert len(live_lines) == len(replay_lines), f"Line count differs: {len(live_lines)} vs {len(replay_lines)}"

    for i, (live_line, replay_line) in enumerate(zip(live_lines, replay_lines)):
        assert live_line == replay_line, f"Line {i} differs:\nLive:   {live_line}\nReplay: {replay_line}"
```

---

## Robustness for Future Features

### Problem
As new features are added (e.g., new cost types, new queues), output can diverge again.

### Solution: Contract Testing

1. **Define Output Contract**:
   - Document every section in verbose output
   - Document exact format of each line
   - Version the output format

2. **Automatic Verification**:
   - Every simulation run stores a hash of verbose output
   - Replay must produce same hash
   - CI fails if hashes don't match

3. **Schema Migrations**:
   - When adding new event types or state fields:
     - Update StateProvider protocol
     - Update both OrchestratorStateProvider and DatabaseStateProvider
     - Add database migration
     - Update output functions
   - Use type checking to ensure both providers implement all methods

4. **Single Execution Path**:
   - Live execution and replay should use SAME output strategy class
   - Only difference: data source (Orchestrator vs Database)
   - Eliminates possibility of logic divergence

---

## Implementation Checklist

### Phase 1: Foundation
- [ ] Create `StateProvider` protocol
- [ ] Implement `OrchestratorStateProvider`
- [ ] Implement `DatabaseStateProvider`
- [ ] Add database schema migrations

### Phase 2: Unify Output
- [ ] Merge `log_agent_queues_detailed` + `log_agent_state_from_db` → `log_agent_state`
- [ ] Merge `log_cost_breakdown` + `log_cost_breakdown_from_db` → `log_cost_breakdown`
- [ ] Add `log_queued_rtgs` to replay
- [ ] Add `log_cost_accrual_events` to replay

### Phase 3: Persistence
- [ ] Expand `tick_agent_states` table
- [ ] Expand `tick_queue_snapshots` table
- [ ] Create `cost_accrual_events` table
- [ ] Update persistence manager to capture all data

### Phase 4: Replay Logic
- [ ] Remove `has_full_replay` conditional logic
- [ ] Use unified output functions
- [ ] Match section order exactly to live execution

### Phase 5: Testing
- [ ] Write determinism test (output comparison)
- [ ] Test with multiple scenarios
- [ ] Verify across different config options

### Phase 6: Documentation
- [ ] Document output format versioning
- [ ] Add migration guide for future features
- [ ] Update CLAUDE.md with StateProvider pattern

---

## Expected Outcome

After implementation:
1. ✅ Replay output is **byte-for-byte identical** to live execution
2. ✅ No conditional sections (all or nothing)
3. ✅ Single code path for output formatting
4. ✅ Type-safe guarantee that live and replay use same interface
5. ✅ Automated tests verify determinism
6. ✅ Future features forced to maintain parity

## Timeline Estimate

- Phase 1: 2-3 hours
- Phase 2: 3-4 hours
- Phase 3: 2-3 hours
- Phase 4: 1-2 hours
- Phase 5: 2-3 hours
- Phase 6: 1 hour

**Total: ~12-16 hours**
