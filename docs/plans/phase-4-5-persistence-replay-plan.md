# Phase 4.5: State Register Persistence & Replay Implementation Plan

## Overview

Complete persistence and replay support for state registers to ensure full replay identity.

**CRITICAL**: Replay output MUST be byte-for-byte identical to run output (modulo timing).

## Architecture

```
Run Mode:     Agent.state_registers → StateRegisterSet event → DB (2 tables)
              ↓
Replay Mode:  DB simulation_events → StateProvider → Display
```

## Implementation Tasks

### Task 1: Database Schema (Python)

**File**: `api/payment_simulator/persistence/schema.py`

Add `agent_state_registers` table for efficient querying:

```sql
CREATE TABLE IF NOT EXISTS agent_state_registers (
    simulation_id TEXT NOT NULL,
    tick INTEGER NOT NULL,
    agent_id TEXT NOT NULL,
    register_key TEXT NOT NULL,
    register_value REAL NOT NULL,
    PRIMARY KEY (simulation_id, tick, agent_id, register_key)
);

CREATE INDEX IF NOT EXISTS idx_agent_state_tick
ON agent_state_registers(simulation_id, agent_id, tick);
```

**Testing**: Write test that creates DB and verifies schema exists.

### Task 2: Event Persistence (Python)

**File**: `api/payment_simulator/persistence/persistence.py`

Extend `EventWriter` to persist StateRegisterSet events to BOTH tables:
1. `simulation_events` (for replay via StateProvider)
2. `agent_state_registers` (for efficient queries)

**Testing**: Write test that persists StateRegisterSet event and verifies both tables updated.

### Task 3: StateProvider Integration (Python)

**File**: `api/payment_simulator/cli/execution/state_provider.py`

Add `get_agent_state_registers()` method to `DatabaseStateProvider`:

```python
def get_agent_state_registers(self, agent_id: str, tick: int) -> Dict[str, float]:
    """Get all state registers for an agent at a specific tick.

    Returns most recent value for each register up to and including tick.
    """
    # Query agent_state_registers table
    # Return dict of register_key -> value
```

**Testing**: Write test that stores registers in DB, then retrieves via StateProvider.

### Task 4: Display Support (Python)

**File**: `api/payment_simulator/cli/display/verbose_output.py`

Add display function for StateRegisterSet events:

```python
def log_state_register_set(event: Dict):
    """Display state register changes."""
    console.print(f"[cyan]State Register:[/cyan] {event['agent_id']}")
    console.print(f"  Key: {event['register_key']}")
    console.print(f"  Old: {event['old_value']:.2f} → New: {event['new_value']:.2f}")
    if event.get('reason'):
        console.print(f"  Reason: {event['reason']}")
```

Integrate into `display_tick_verbose_output()`.

**Testing**: Write test that captures display output and verifies formatting.

### Task 5: Replay Identity Test (Python)

**File**: `api/tests/integration/test_replay_identity_gold_standard.py`

Add comprehensive test:

```python
def test_state_register_events_have_all_fields():
    """Verify StateRegisterSet events contain all required fields."""
    config = create_state_register_test_scenario()
    orch = Orchestrator.new(config)

    for _ in range(10):
        orch.tick()

    events = orch.get_all_events()
    state_events = [e for e in events if e['event_type'] == 'StateRegisterSet']

    assert len(state_events) > 0

    for event in state_events:
        assert 'tick' in event
        assert 'agent_id' in event
        assert 'register_key' in event
        assert 'old_value' in event
        assert 'new_value' in event
        assert 'reason' in event
        assert event['register_key'].startswith('bank_state_')

def test_state_register_replay_identity():
    """Verify state registers replay identically."""
    config = create_state_register_policy_config()

    # Run mode
    run_output = run_with_persistence(config, ticks=20, db_path="test.db")

    # Replay mode
    replay_output = replay_from_db("test.db", ticks=20)

    # Compare (should be identical)
    assert_outputs_identical(run_output, replay_output)
```

**Testing**: TDD - write test first, then implement persistence to make it pass.

## Implementation Order (TDD)

1. ✅ **Rust Backend Complete** (already done)
   - Agent storage
   - Event emission
   - Orchestrator integration
   - FFI serialization

2. **Task 1: Database Schema** (30 min)
   - Write test for schema creation
   - Implement schema in `schema.py`
   - Verify test passes

3. **Task 2: Event Persistence** (45 min)
   - Write test for double-write (both tables)
   - Implement EventWriter extension
   - Verify test passes

4. **Task 3: StateProvider** (45 min)
   - Write test for register retrieval
   - Implement get_agent_state_registers()
   - Verify test passes

5. **Task 4: Display Support** (30 min)
   - Write test for display formatting
   - Implement log_state_register_set()
   - Integrate into display_tick_verbose_output()
   - Verify test passes

6. **Task 5: Replay Identity** (60 min)
   - Write replay identity test (FIRST - TDD!)
   - Run test (should fail initially)
   - Fix any issues
   - Verify test passes

## Success Criteria

- [ ] `agent_state_registers` table created automatically
- [ ] StateRegisterSet events persist to both tables
- [ ] StateProvider can retrieve registers from DB
- [ ] Display shows register changes in verbose mode
- [ ] Replay output identical to run output
- [ ] All existing tests still pass
- [ ] New integration tests pass

## Key Design Decisions

**Why Two Tables?**
1. `simulation_events`: Single source of truth, used by StateProvider
2. `agent_state_registers`: Efficient querying (indexed by agent/tick)

**Why NOT Legacy Pattern?**
- Old approach: Separate tables + manual reconstruction
- New approach: Events are self-contained, StateProvider abstracts access
- Result: Simpler, less fragile, automatic replay identity

## Estimated Time

- Database Schema: 30 min
- Event Persistence: 45 min
- StateProvider: 45 min
- Display: 30 min
- Replay Identity Tests: 60 min
- **Total: ~3.5 hours**

## Files to Modify

**Python Side:**
- `api/payment_simulator/persistence/schema.py` (add table)
- `api/payment_simulator/persistence/persistence.py` (EventWriter)
- `api/payment_simulator/cli/execution/state_provider.py` (get_agent_state_registers)
- `api/payment_simulator/cli/display/verbose_output.py` (display function)
- `api/tests/integration/test_replay_identity_gold_standard.py` (tests)

**No Rust Changes Needed** - Rust side is complete!
