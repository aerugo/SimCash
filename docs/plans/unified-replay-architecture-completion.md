# Unified Replay Architecture Completion Plan

**Status:** In Progress
**Created:** 2025-11-09
**Owner:** Development Team
**Priority:** P0 (Critical)

## Executive Summary

This document provides a comprehensive plan to complete the transition to a unified replay architecture where all simulation events are stored in a single source of truth (`simulation_events` table) and can be replayed with perfect fidelity to the original run's verbose output.

**Goal:** Guarantee that `payment-sim replay` produces byte-for-byte identical output to the original `payment-sim run` (modulo timing information).

## Current State Analysis

### What Works ✅

1. **Unified Display Layer**: `display_tick_verbose_output()` exists and is shared by both `run` and `replay`
2. **StateProvider Abstraction**: Clean interface separating display logic from data source
3. **Core Event Persistence**: `simulation_events` table exists and captures most events
4. **Unified Execution Loop**: `SimulationRunner` and `OutputStrategy` provide consistent structure

### What's Broken ❌

1. **Hybrid Data Sourcing**: `replay` uses both `simulation_events` AND legacy tables (`lsm_cycles`, `collateral_events`)
2. **Incomplete Event Enrichment**: Rust `Event` enum lacks detailed data needed for display
3. **Manual Reconstruction Logic**: Brittle Python code manually reconstructs events from legacy tables
4. **Data Redundancy**: Same data stored in multiple places (simulation_events + specialized tables)
5. **Bug-Prone**: Recent LSM replay bug demonstrates fragility of current approach

### Root Cause

The fundamental issue is that `run` and `replay` use different data sources:
- **`run`**: FFI → Rust orchestrator → Complete real-time events
- **`replay`**: Database → Incomplete events + manual reconstruction → Display

## Architecture Goal

```
┌─────────────────────────────────────────────────────────┐
│          display_tick_verbose_output()                  │
│          (Single Source of Truth for Display)           │
└────────────────┬───────────────────────────────────────┘
                 │
         ┌───────┴────────┐
         │ StateProvider  │  ← Protocol (interface)
         │   Protocol     │
         └───────┬────────┘
                 │
    ┌────────────┴─────────────┐
    │                          │
    ▼                          ▼
┌────────────────┐      ┌──────────────────┐
│ Orchestrator   │      │ Database         │
│ StateProvider  │      │ StateProvider    │
│ (Live FFI)     │      │ (Replay)         │
└────────────────┘      └──────────────────┘
         │                      │
         │                      │
         ▼                      ▼
    Rich Events  ═══════►  simulation_events
    (FFI call)             (Single table)
```

**Golden Rule:** The `simulation_events` table is the ONLY source of truth for replay.

## Implementation Plan

### Phase 1: Test Infrastructure (TDD Foundation)

**Objective:** Establish comprehensive tests that define success criteria.

#### Task 1.1: Create Gold Standard Test Framework

**File:** `api/tests/integration/test_replay_identity_gold_standard.py`

```python
def test_replay_identity_all_event_types():
    """Gold standard: run vs replay output must be identical for ALL event types."""

    # Test each event type:
    # - TransactionArrival
    # - PolicyDecision
    # - TransactionSettlement
    # - TransactionQueued
    # - TransactionBecameOverdue
    # - LsmBilateralOffset
    # - LsmCycleSettlement
    # - CollateralPosted
    # - CollateralReleased

    # For each: verify field-by-field identity
```

#### Task 1.2: Create Event-Specific Tests

```python
def test_lsm_bilateral_replay_identity():
    """LSM bilateral offsets must replay identically."""

def test_lsm_cycle_replay_identity():
    """LSM multilateral cycles must replay identically."""

def test_collateral_replay_identity():
    """Collateral events must replay identically."""

def test_overdue_transaction_replay_identity():
    """Overdue transaction events must replay identically."""
```

#### Task 1.3: Create Regression Test Suite

```python
def test_known_lsm_bilateral_bug_fixed():
    """Regression test for the bilateral offset bug (len(agents)==3 vs len(agents)==2)."""

def test_event_field_name_consistency():
    """Verify Rust and Python use same field names (deadline vs deadline_tick)."""
```

**Deliverable:** ~10 failing tests that define success criteria

---

### Phase 2: Enrich Rust Event Types

**Objective:** Make every `Event` variant contain ALL data needed for display.

#### Task 2.1: Analyze Display Requirements

**Action:** For each event type, document what data the display functions need.

| Event Type | Display Function | Required Fields |
|------------|------------------|-----------------|
| `LsmBilateralOffset` | `log_lsm_cycle_visualization` | `agent_a`, `agent_b`, `amount_a`, `amount_b`, `tx_ids` |
| `LsmCycleSettlement` | `log_lsm_cycle_visualization` | `agents`, `tx_amounts`, `total_value`, `net_positions`, `max_net_outflow`, `max_net_outflow_agent` |
| `CollateralPosted` | `log_collateral_event` | `agent_id`, `amount`, `new_total`, `trigger` |
| `CollateralReleased` | `log_collateral_event` | `agent_id`, `amount`, `new_total`, `trigger` |

#### Task 2.2: Expand Event Enum

**File:** `backend/src/models/event.rs`

```rust
pub enum Event {
    // ... existing variants ...

    LsmBilateralOffset {
        tick: i64,
        agent_a: String,
        agent_b: String,
        amount_a: i64,  // NEW: Amount flowing A→B
        amount_b: i64,  // NEW: Amount flowing B→A
        tx_ids: Vec<String>,
    },

    LsmCycleSettlement {
        tick: i64,
        agents: Vec<String>,           // NEW: Full list of agents in cycle
        tx_amounts: Vec<i64>,          // NEW: Transaction amounts
        total_value: i64,              // NEW: Total value settled
        net_positions: Vec<i64>,       // NEW: Net positions before settlement
        max_net_outflow: i64,          // NEW: Maximum net outflow in cycle
        max_net_outflow_agent: String, // NEW: Agent with max net outflow
        tx_ids: Vec<String>,
    },

    CollateralPosted {
        tick: i64,
        agent_id: String,
        amount: i64,
        new_total: i64,       // NEW: Total collateral after posting
        trigger: String,      // NEW: What triggered the posting
    },

    CollateralReleased {
        tick: i64,
        agent_id: String,
        amount: i64,
        new_total: i64,       // NEW: Total collateral after release
        trigger: String,      // NEW: What triggered the release
    },
}
```

#### Task 2.3: Update Event Generation Sites

**Files to modify:**
- `backend/src/settlement/lsm.rs`: Populate enriched LSM events
- `backend/src/orchestrator/engine.rs`: Populate enriched collateral events

**Example for LSM:**

```rust
// In lsm.rs, when creating bilateral offset
Event::LsmBilateralOffset {
    tick,
    agent_a: cycle.agent_ids[0].clone(),
    agent_b: cycle.agent_ids[1].clone(),
    amount_a: cycle.tx_amounts[0],  // NEW
    amount_b: cycle.tx_amounts[1],  // NEW
    tx_ids: cycle.tx_ids.clone(),
}
```

#### Task 2.4: Add Rust Unit Tests

**File:** `backend/tests/test_event_enrichment.rs`

```rust
#[test]
fn test_lsm_bilateral_event_contains_all_fields() {
    // Create LSM bilateral scenario
    // Verify Event contains agent_a, agent_b, amount_a, amount_b
}

#[test]
fn test_lsm_cycle_event_contains_all_fields() {
    // Create LSM cycle scenario
    // Verify Event contains agents, tx_amounts, net_positions, etc.
}
```

**Deliverable:** Enriched Event types with comprehensive field coverage

---

### Phase 3: Update FFI Layer

**Objective:** Serialize enriched events correctly across the Rust→Python boundary.

#### Task 3.1: Update FFI Serialization

**File:** `backend/src/ffi/orchestrator.rs`

In `get_tick_events` and `get_all_events`, update event-to-dict conversion:

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

Event::LsmCycleSettlement { tick, agents, tx_amounts, total_value, net_positions,
                            max_net_outflow, max_net_outflow_agent, tx_ids } => {
    let mut dict = HashMap::new();
    dict.insert("event_type".to_string(), "lsm_cycle_settlement".into());
    dict.insert("tick".to_string(), tick.into());
    dict.insert("agents".to_string(), agents.into());                   // NEW
    dict.insert("tx_amounts".to_string(), tx_amounts.into());           // NEW
    dict.insert("total_value".to_string(), total_value.into());         // NEW
    dict.insert("net_positions".to_string(), net_positions.into());     // NEW
    dict.insert("max_net_outflow".to_string(), max_net_outflow.into()); // NEW
    dict.insert("max_net_outflow_agent".to_string(), max_net_outflow_agent.into()); // NEW
    dict.insert("tx_ids".to_string(), tx_ids.into());
    dict
}
```

#### Task 3.2: Add FFI Integration Tests

**File:** `api/tests/integration/test_ffi_event_serialization.py`

```python
def test_ffi_serializes_lsm_bilateral_with_all_fields():
    """Verify FFI returns all required fields for LSM bilateral events."""
    orch = create_test_orchestrator_with_lsm_scenario()
    orch.tick()
    events = orch.get_tick_events()

    lsm_events = [e for e in events if e['event_type'] == 'lsm_bilateral_offset']
    assert len(lsm_events) > 0

    event = lsm_events[0]
    assert 'agent_a' in event
    assert 'agent_b' in event
    assert 'amount_a' in event  # NEW
    assert 'amount_b' in event  # NEW
    assert 'tx_ids' in event
```

**Deliverable:** FFI correctly serializes all enriched event fields

---

### Phase 4: Update Persistence Layer

**Objective:** Store enriched events in `simulation_events.details` JSON column.

#### Task 4.1: Verify PersistenceManager Handles Rich Events

**File:** `api/payment_simulator/cli/execution/persistence.py`

The `EventWriter` already stores events as JSON. Verify it handles nested structures:

```python
def test_persistence_stores_nested_event_fields():
    """Verify complex event structures are correctly serialized to JSON."""
    event = {
        'event_type': 'lsm_cycle_settlement',
        'tick': 10,
        'agents': ['A', 'B', 'C'],
        'tx_amounts': [1000, 2000, 3000],
        'net_positions': [500, -200, -300],
        # ... more fields
    }

    writer.write_event(event)

    # Read back and verify all fields present
    retrieved = get_simulation_events(sim_id, tick=10)
    assert retrieved[0]['agents'] == ['A', 'B', 'C']
```

#### Task 4.2: Add Database Schema Validation

Ensure DuckDB can handle nested arrays and complex JSON:

```python
def test_duckdb_handles_complex_json():
    """Verify DuckDB correctly stores and retrieves nested JSON structures."""
```

**Deliverable:** PersistenceManager correctly stores all enriched event data

---

### Phase 5: Simplify Replay Logic

**Objective:** Remove all legacy data sources and manual reconstruction logic.

#### Task 5.1: Remove Legacy Queries from replay.py

**File:** `api/payment_simulator/cli/commands/replay.py`

**Before:**
```python
def replay_simulation(db_path, sim_id, verbose):
    # ... setup ...

    for tick in range(tick_start, tick_end + 1):
        raw_events = get_simulation_events(sim_id, tick=tick)
        lsm_cycles = get_lsm_cycles_by_tick(sim_id, tick)  # ❌ REMOVE
        collateral = get_collateral_events_by_tick(sim_id, tick)  # ❌ REMOVE

        # Manual reconstruction logic
        events = _reconstruct_lsm_events(lsm_cycles)  # ❌ REMOVE
        # ...
```

**After:**
```python
def replay_simulation(db_path, sim_id, verbose):
    # ... setup ...

    for tick in range(tick_start, tick_end + 1):
        raw_events = get_simulation_events(sim_id, tick=tick)  # ✅ ONLY SOURCE

        # Events are already in correct format - no reconstruction needed
        if verbose:
            display_tick_verbose_output(provider, tick, events)
```

#### Task 5.2: Delete Manual Reconstruction Functions

**File:** `api/payment_simulator/cli/commands/replay.py`

Delete these functions:
- `_reconstruct_lsm_events()`
- `_reconstruct_collateral_events()`

They are no longer needed because events are already enriched.

#### Task 5.3: Update DatabaseStateProvider

**File:** `api/payment_simulator/cli/execution/state_provider.py`

Ensure `DatabaseStateProvider` correctly extracts fields from the enriched events:

```python
class DatabaseStateProvider(StateProvider):
    def get_lsm_bilateral_offsets(self) -> List[Dict]:
        """Extract bilateral offsets from events (no reconstruction needed)."""
        events = [e for e in self._current_tick_events
                  if e['event_type'] == 'lsm_bilateral_offset']

        # Events already have all fields - just return them
        return events

    def get_lsm_cycles(self) -> List[Dict]:
        """Extract cycles from events (no reconstruction needed)."""
        events = [e for e in self._current_tick_events
                  if e['event_type'] == 'lsm_cycle_settlement']

        # Events already have all fields - just return them
        return events
```

**Deliverable:** Replay logic uses only `simulation_events` table

---

### Phase 6: Remove Legacy Infrastructure

**Objective:** Clean up redundant tables, queries, and persistence code.

#### Task 6.1: Remove Legacy Table Writes

**File:** `api/payment_simulator/cli/commands/run.py`

In `_persist_day_data()`, remove:
```python
# ❌ DELETE THESE BLOCKS
if lsm_cycles:
    cursor.executemany("""...""", lsm_cycles)

if collateral_events:
    cursor.executemany("""...""", collateral_events)
```

#### Task 6.2: Deprecate Legacy Query Functions

**File:** `api/payment_simulator/persistence/queries.py`

Mark as deprecated or delete:
- `get_lsm_cycles_by_tick()`
- `get_collateral_events_by_tick()`

#### Task 6.3: Create Database Migration

**File:** `api/payment_simulator/persistence/migrations/003_remove_legacy_tables.sql`

```sql
-- Drop redundant tables
DROP TABLE IF EXISTS lsm_cycles;
DROP TABLE IF EXISTS collateral_events;

-- simulation_events is now the single source of truth
```

#### Task 6.4: Update Database Schema Documentation

**File:** `api/payment_simulator/persistence/models.py`

Update docstrings to reflect new architecture:

```python
class SimulationEvent:
    """
    Single source of truth for all simulation events.

    The 'details' JSON column contains ALL data needed for display:
    - LSM events: agents, tx_amounts, net_positions, etc.
    - Collateral events: amount, new_total, trigger, etc.
    - All other events: complete field set

    IMPORTANT: When adding new event types or fields, ensure they are
    included in the Event enum in Rust and serialized via FFI.
    """
```

**Deliverable:** Clean codebase with no legacy infrastructure

---

### Phase 7: Documentation Updates

**Objective:** Ensure developers understand how to maintain replay identity.

#### Task 7.1: Update Root CLAUDE.md

**File:** `CLAUDE.md`

Add/expand section on replay identity:

```markdown
## 🎯 Critical Invariant: Replay Identity

**RULE**: `payment-sim replay` output MUST be byte-for-byte identical to
`payment-sim run` output (modulo timing information).

### The Single Source of Truth

The `simulation_events` table is the ONLY source of events for replay.

### Adding a New Event Type (Mandatory Workflow)

When adding a new event type that should appear in verbose output:

1. **Define in Rust** (`backend/src/models/event.rs`):
   ```rust
   pub enum Event {
       MyNewEvent {
           tick: i64,
           field1: String,
           field2: i64,
           // ALL fields needed for display
       },
   }
   ```

2. **Generate Event** (wherever it happens):
   ```rust
   events.push(Event::MyNewEvent {
       tick: self.current_tick,
       field1: value1,
       field2: value2,
   });
   ```

3. **Serialize via FFI** (`backend/src/ffi/orchestrator.rs`):
   ```rust
   Event::MyNewEvent { tick, field1, field2 } => {
       let mut dict = HashMap::new();
       dict.insert("event_type".to_string(), "my_new_event".into());
       dict.insert("tick".to_string(), tick.into());
       dict.insert("field1".to_string(), field1.into());
       dict.insert("field2".to_string(), field2.into());
       dict
   }
   ```

4. **Add Display Logic** (`api/payment_simulator/cli/display/verbose_output.py`):
   ```python
   def log_my_new_event(event: Dict):
       console.print(f"[cyan]My Event:[/cyan] {event['field1']} - {event['field2']}")

   # In display_tick_verbose_output:
   for event in events:
       if event['event_type'] == 'my_new_event':
           log_my_new_event(event)
   ```

5. **Write Integration Test** (`api/tests/integration/test_replay_identity.py`):
   ```python
   def test_my_new_event_replay_identity():
       """Verify MyNewEvent replays identically."""
       # Run with event, capture output
       # Replay, capture output
       # Assert outputs match
   ```

6. **Test Both Paths**:
   ```bash
   # Run and persist
   payment-sim run --config test.yaml --persist output.db --verbose

   # Replay
   payment-sim replay output.db --verbose

   # Outputs must be identical
   ```

### What NOT to Do ❌

1. **Never query specialized tables in replay logic**
   - Bad: `get_lsm_cycles_by_tick()` in `replay.py`
   - Good: All events from `get_simulation_events()`

2. **Never manually reconstruct events in Python**
   - Bad: `_reconstruct_lsm_events()` helper function
   - Good: Events already enriched in Rust

3. **Never bypass StateProvider abstraction**
   - Bad: Direct database query in display function
   - Good: Call StateProvider method

4. **Never store partial event data**
   - Bad: Event with only `tx_ids`, rest in separate table
   - Good: Event with ALL fields (agents, amounts, positions, etc.)
```

#### Task 7.2: Update API CLAUDE.md

**File:** `api/CLAUDE.md`

Add section on replay implementation:

```markdown
## Replay Architecture

The replay system is implemented using the StateProvider pattern:

- `OrchestratorStateProvider`: Live FFI calls (run mode)
- `DatabaseStateProvider`: Database queries (replay mode)

Both providers feed the same display functions, guaranteeing identical output.

### Key Files

- `cli/commands/replay.py`: Replay command implementation
- `cli/execution/state_provider.py`: StateProvider protocol and implementations
- `cli/display/verbose_output.py`: Shared display logic

### Maintaining Replay Identity

When modifying display logic:
1. Use StateProvider methods, never direct FFI/DB access
2. Test both `run` and `replay` modes
3. Verify output identity with integration tests
```

#### Task 7.3: Create Architecture Deep Dive

**File:** `docs/replay-architecture.md`

Create comprehensive documentation:

```markdown
# Replay Architecture

## Overview
## Design Principles
## Data Flow Diagrams
## Event Lifecycle
## Testing Strategy
## Troubleshooting Guide
```

**Deliverable:** Comprehensive documentation for maintaining replay identity

---

### Phase 8: Validation and Hardening

**Objective:** Verify the system meets all success criteria.

#### Task 8.1: Run Full Test Suite

```bash
# Run all tests
cd api
.venv/bin/pytest -v

# Specifically run replay identity tests
.venv/bin/pytest tests/integration/test_replay_identity*.py -v

# All tests must pass
```

#### Task 8.2: Manual Validation

```bash
# Create test scenario
payment-sim run --config test_complex.yaml --persist output.db --verbose > run_output.txt

# Replay
payment-sim replay output.db --verbose > replay_output.txt

# Compare (should be identical except timestamps)
diff <(grep -v "Duration:" run_output.txt) <(grep -v "Duration:" replay_output.txt)
# Should output nothing (files identical)
```

#### Task 8.3: Performance Validation

Ensure replay is fast (no performance regression):

```bash
# Benchmark replay
time payment-sim replay large_simulation.db

# Should be faster than or equal to original run
```

#### Task 8.4: Add Continuous Validation

**File:** `.github/workflows/replay-identity.yml`

```yaml
name: Replay Identity Check

on: [push, pull_request]

jobs:
  replay-identity:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Python
        uses: actions/setup-python@v2
      - name: Run replay identity tests
        run: |
          cd api
          uv sync --extra dev
          .venv/bin/pytest tests/integration/test_replay_identity*.py -v
```

**Deliverable:** Validated, hardened system with continuous integration

---

## Success Criteria

The transition is complete when:

1. ✅ All integration tests pass (including new replay identity tests)
2. ✅ No legacy tables (`lsm_cycles`, `collateral_events`) exist
3. ✅ No manual reconstruction logic exists in `replay.py`
4. ✅ All event types have comprehensive field coverage
5. ✅ FFI correctly serializes all event fields
6. ✅ Documentation is complete and accurate
7. ✅ Manual diff test shows identical output (run vs replay)
8. ✅ No performance regression in replay

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking existing replays | Medium | High | Provide migration script for old databases |
| FFI serialization bugs | Low | High | Comprehensive FFI tests for each event type |
| Performance regression | Low | Medium | Benchmark replay before/after |
| Incomplete event enrichment | Medium | High | Test-driven approach ensures completeness |

## Migration Path for Existing Databases

For users with existing simulation databases using legacy tables:

1. Provide migration tool to convert old format to new format
2. Document migration process in `docs/migration-guide.md`
3. Gracefully handle old databases (warn user, suggest migration)

```bash
# Migration command
payment-sim migrate-db old_database.db new_database.db
```

## Timeline Estimate

- Phase 1 (Test Infrastructure): 4-6 hours
- Phase 2 (Enrich Rust Events): 6-8 hours
- Phase 3 (Update FFI): 3-4 hours
- Phase 4 (Update Persistence): 2-3 hours
- Phase 5 (Simplify Replay): 3-4 hours
- Phase 6 (Remove Legacy): 2-3 hours
- Phase 7 (Documentation): 4-5 hours
- Phase 8 (Validation): 3-4 hours

**Total: 27-37 hours (3-5 days of focused work)**

## Conclusion

This plan provides a clear, step-by-step path to complete the unified replay architecture. By following TDD principles and maintaining strict replay identity invariants, we'll create a robust, maintainable system where replay fidelity is guaranteed by design, not by manual effort.

The key insight is: **Make events rich at the source (Rust), store them completely (database), and replay them directly (no reconstruction)**. This eliminates the entire class of reconstruction bugs and ensures perfect replay fidelity.
