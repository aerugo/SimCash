# Phase 3.3-4.5 Remaining Issues Fix Plan

**Date:** 2025-11-13
**Status:** In Progress
**Approach:** Strict TDD - Write failing tests first, then fix until tests pass

## Issues Identified

### 1. State Register Duplicate Key Constraint ⚠️ HIGH PRIORITY

**Problem:**
```
Constraint Error: Duplicate key "simulation_id: sim-13639ba5, tick: 199, agent_id: REGIONAL_TRUST, register_key: bank_state_mode" violates primary key constraint.
```

**Root Cause:**
- Policy tree executes `SetState(bank_state_mode, 1.0)` during bank-level evaluation
- EOD reset logic executes `SetState(bank_state_mode, 0.0)` in same tick
- Both try to insert same PK into `agent_state_registers` table

**Impact:** Simulation crashes at ~tick 199 when EOD coincides with policy mode change

**Solution Options:**
1. **Option A (Recommended)**: Store only final register value per tick
   - Rust collects all SetState/AddState operations during tick
   - At EOD batch write, compute final value for each register
   - Insert only one row per (simulation_id, tick, agent_id, register_key)

2. **Option B**: Add sequence number to PK
   - Schema: `PRIMARY KEY (simulation_id, tick, agent_id, register_key, sequence)`
   - Allows multiple updates per tick
   - More complex queries to get final value

3. **Option C**: Execute EOD reset at tick N+1
   - Shifts timing, breaks semantic meaning of "end of day"

**Chosen Solution:** Option A - Store only final values

**TDD Approach:**
1. Write test that creates policy with multiple SetState operations in same tick
2. Run test, verify it fails with duplicate key error
3. Modify persistence layer to batch and merge state register operations
4. Run test, verify it passes
5. Verify advanced crisis scenario completes without error

---

### 2. Collateral Events Not Persisted ⚠️ HIGH PRIORITY

**Problem:**
- `PostCollateral` and `WithdrawCollateral` actions execute successfully
- Verbose output shows "💰 Collateral Activity"
- BUT: No events in `simulation_events` table with collateral-related event_types
- Legacy `collateral_events` table is empty

**Root Cause:**
- Collateral actions may not be generating events
- OR events are generated but not serialized across FFI
- OR events are serialized but event_type doesn't match expected values

**Impact:**
- Replay cannot show collateral activity
- Database queries can't analyze collateral usage
- Timers can't be persisted/replayed

**TDD Approach:**
1. Write test that posts collateral and queries simulation_events
2. Run test, verify no collateral events found (RED)
3. Trace code path: Rust action → Event generation → FFI serialization → DB persistence
4. Fix missing event generation/serialization
5. Run test, verify events appear in database (GREEN)
6. Refactor for clarity

---

### 3. Budget Operations Not Displayed ⚠️ MEDIUM PRIORITY

**Problem:**
- `SetReleaseBudget` actions execute and persist to database
- Database shows: `{"max_value": 8750000, "focus_counterparties": null, ...}`
- BUT: Verbose output doesn't show any "Budget Set" or similar messages

**Root Cause:**
- No display function for budget events in `api/payment_simulator/cli/output.py`
- `display_tick_verbose_output()` doesn't call any budget logging function

**Impact:**
- Users can't see adaptive budget management in action
- Reduced visibility into Phase 3.3 feature

**TDD Approach:**
1. Write test that captures verbose output and checks for budget message
2. Run test, verify no budget output (RED)
3. Add `log_budget_operations()` function to output.py
4. Add call to `display_tick_verbose_output()`
5. Run test, verify budget operations appear (GREEN)

---

### 4. Collateral Timer Auto-Withdrawal ⚠️ HIGH PRIORITY

**Problem:**
- Policies specify `auto_withdraw_after_ticks` parameter
- No evidence of automatic withdrawals in verbose output
- Feature may not be implemented at all

**Root Cause:** Unknown - need to investigate if feature exists in Rust

**TDD Approach:**
1. Write test that posts collateral with timer, advances N ticks, checks for withdrawal
2. Run test, determine if feature exists
3. If RED (doesn't exist): Implement in Rust core
4. If RED (exists but broken): Fix implementation
5. Run test, verify auto-withdrawal occurs (GREEN)

---

## Implementation Order (TDD)

### Phase 1: Critical Fixes (Blocking Simulation Completion)

1. **Issue #1: State Register Duplicate Key**
   - Priority: HIGHEST (blocks simulation completion)
   - Complexity: MEDIUM (persistence layer change)
   - Test file: `api/tests/integration/test_state_register_persistence.py`

2. **Issue #2: Collateral Event Persistence**
   - Priority: HIGH (blocks replay feature)
   - Complexity: HIGH (full stack tracing required)
   - Test file: `api/tests/integration/test_collateral_event_persistence.py`

### Phase 2: Feature Completion

3. **Issue #4: Collateral Timer Auto-Withdrawal**
   - Priority: HIGH (Phase 3.4 incomplete without it)
   - Complexity: HIGH (may require Rust implementation)
   - Test file: `api/tests/integration/test_collateral_timers.py`

4. **Issue #3: Budget Operation Display**
   - Priority: MEDIUM (feature works, just not visible)
   - Complexity: LOW (Python display only)
   - Test file: `api/tests/integration/test_budget_display.py`

---

## Detailed Implementation Steps

### Step 1: Fix State Register Duplicate Key

**Test First (TDD Red):**

```python
# api/tests/integration/test_state_register_persistence.py

def test_multiple_state_updates_same_tick_stores_final_value():
    """Test that multiple SetState operations in same tick store only final value."""

    # Create policy that sets mode twice in same tick
    config = {
        "seed": 42,
        "ticks_per_day": 10,
        "agents": [
            {
                "id": "TEST_BANK",
                "opening_balance": 100000,
                "policy_id": "test_multi_state_update",
            }
        ],
        "policies": {
            "test_multi_state_update": {
                "version": "1.0",
                "bank_tree": {
                    "type": "sequence",
                    "children": [
                        {
                            "type": "action",
                            "action": "SetState",
                            "parameters": {
                                "key": {"value": "test_counter"},
                                "value": {"value": 1.0},
                                "reason": {"value": "first_update"}
                            }
                        },
                        {
                            "type": "action",
                            "action": "SetState",
                            "parameters": {
                                "key": {"value": "test_counter"},
                                "value": {"value": 5.0},
                                "reason": {"value": "second_update"}
                            }
                        }
                    ]
                }
            }
        }
    }

    orch = Orchestrator.new(config)
    persistence = create_test_persistence()

    # Run one tick
    orch.tick()

    # Persist events
    events = orch.get_tick_events(0)
    write_events_batch(persistence.conn, "test-sim", events)

    # Query database - should have only ONE row for test_counter at tick 0
    result = persistence.conn.execute("""
        SELECT register_value, COUNT(*)
        FROM agent_state_registers
        WHERE agent_id = 'TEST_BANK'
        AND register_key = 'test_counter'
        AND tick = 0
        GROUP BY register_value
    """).fetchall()

    # Should NOT fail with duplicate key error
    assert len(result) == 1, "Should have exactly one row for register at tick 0"
    assert result[0][0] == 5.0, "Should store final value (5.0, not 1.0)"
```

**Implementation:**

1. Modify `api/payment_simulator/persistence/event_writer.py`
2. Add `_merge_state_register_events()` helper function
3. Modify `write_events_batch()` to call merger before DB insert

**Test After (TDD Green):** Run test, verify it passes

---

### Step 2: Fix Collateral Event Persistence

**Test First (TDD Red):**

```python
# api/tests/integration/test_collateral_event_persistence.py

def test_collateral_events_persisted_to_database():
    """Test that PostCollateral and WithdrawCollateral generate persisted events."""

    config = create_collateral_test_config()
    orch = Orchestrator.new(config)
    persistence = create_test_persistence()

    # Run ticks until collateral is posted
    for _ in range(10):
        orch.tick()

    # Get all events
    all_events = orch.get_all_events()

    # Filter collateral events
    collateral_events = [
        e for e in all_events
        if e.get('event_type') in ['CollateralPosted', 'CollateralWithdrawn', 'PostCollateral', 'WithdrawCollateral']
    ]

    assert len(collateral_events) > 0, "Should have collateral events in orchestrator"

    # Persist to database
    write_events_batch(persistence.conn, "test-sim", all_events)

    # Query database
    db_collateral_events = persistence.conn.execute("""
        SELECT event_type, details
        FROM simulation_events
        WHERE event_type IN ('CollateralPosted', 'CollateralWithdrawn', 'PostCollateral', 'WithdrawCollateral')
    """).fetchall()

    assert len(db_collateral_events) > 0, "Collateral events should be persisted"
    assert len(db_collateral_events) == len(collateral_events), "All collateral events should persist"
```

**Investigation Steps:**

1. Check if `Event::CollateralPosted` exists in Rust
2. Check if collateral actions generate events
3. Check FFI serialization in `backend/src/ffi/orchestrator.rs`
4. Check event writer filtering

**Implementation:** TBD based on investigation findings

---

### Step 3: Implement Collateral Timer Auto-Withdrawal

**Test First (TDD Red):**

```python
# api/tests/integration/test_collateral_timers.py

def test_collateral_auto_withdrawal_after_timer():
    """Test that collateral with auto_withdraw_after_ticks withdraws automatically."""

    config = {
        "seed": 42,
        "ticks_per_day": 50,
        "agents": [{"id": "TEST_BANK", "opening_balance": 1000000, "policy_id": "timer_test"}],
        "policies": {
            "timer_test": {
                "version": "1.0",
                "bank_tree": {
                    "type": "condition",
                    "condition": {"op": "==", "left": {"field": "tick"}, "right": {"value": 0.0}},
                    "on_true": {
                        "type": "action",
                        "action": "PostCollateral",
                        "parameters": {
                            "amount": {"value": 100000.0},
                            "reason": {"value": "test_timer"},
                            "auto_withdraw_after_ticks": {"value": 10.0}
                        }
                    },
                    "on_false": {"type": "action", "action": "Hold"}
                }
            }
        }
    }

    orch = Orchestrator.new(config)

    # Tick 0: Post collateral
    orch.tick()
    collateral_tick_0 = orch.get_agent_posted_collateral("TEST_BANK")
    assert collateral_tick_0 == 100000, "Should have posted collateral"

    # Ticks 1-9: Still posted
    for tick in range(1, 10):
        orch.tick()
        collateral = orch.get_agent_posted_collateral("TEST_BANK")
        assert collateral == 100000, f"Tick {tick}: Collateral should still be posted"

    # Tick 10: Should auto-withdraw
    orch.tick()
    collateral_tick_10 = orch.get_agent_posted_collateral("TEST_BANK")
    assert collateral_tick_10 == 0, "Tick 10: Collateral should be auto-withdrawn"

    # Check for withdrawal event
    events = orch.get_tick_events(10)
    withdrawal_events = [e for e in events if 'withdraw' in e.get('event_type', '').lower()]
    assert len(withdrawal_events) > 0, "Should have withdrawal event at tick 10"
```

**Implementation:** TBD based on investigation

---

### Step 4: Implement Budget Operation Display

**Test First (TDD Red):**

```python
# api/tests/integration/test_budget_display.py

def test_budget_operations_displayed_in_verbose_output():
    """Test that SetReleaseBudget operations appear in verbose output."""

    config = create_budget_test_config()
    orch = Orchestrator.new(config)

    # Capture verbose output
    from io import StringIO
    import sys

    captured_output = StringIO()
    sys.stdout = captured_output

    # Run with verbose display
    display_tick_verbose_output(
        provider=OrchestratorStateProvider(orch),
        events=orch.get_tick_events(0),
        tick_num=0,
        agent_ids=["TEST_BANK"],
        prev_balances={},
        num_arrivals=0,
        num_settlements=0,
        num_lsm_releases=0
    )

    sys.stdout = sys.__stdout__
    output = captured_output.getvalue()

    # Check for budget-related output
    assert "Budget" in output or "Release Budget" in output, "Should display budget operations"
    assert "max_value" in output.lower() or "budget" in output.lower(), "Should show budget details"
```

**Implementation:**

1. Add `log_budget_operations()` to `api/payment_simulator/cli/output.py`
2. Call it from `display_tick_verbose_output()` after policy decisions
3. Format budget events with clear visual indicator

---

## Success Criteria

### Phase 1 Complete When:
- [ ] Advanced crisis scenario runs to completion (300 ticks) without crashes
- [ ] No duplicate key constraint errors
- [ ] Collateral events appear in simulation_events table
- [ ] All TDD tests pass

### Phase 2 Complete When:
- [ ] Collateral timers auto-withdraw after specified ticks
- [ ] Budget operations visible in verbose output
- [ ] All TDD tests pass
- [ ] Replay identity maintained (run vs replay output identical)

### Full Success When:
- [ ] All Phase 3.3, 3.4, and 4.5 features working and visible
- [ ] All tests pass
- [ ] Documentation updated
- [ ] No known bugs or regressions

---

## Testing Strategy

### Unit Tests
- Individual event merging logic
- Individual display functions
- Timer countdown logic

### Integration Tests (TDD)
- End-to-end state register persistence
- End-to-end collateral event persistence
- End-to-end timer functionality
- End-to-end budget display

### Validation Tests
- Advanced crisis scenario runs to completion
- Replay identity maintained
- All features visible and working

---

## Rollback Plan

If any fix causes regressions:
1. Revert specific commit
2. Run full test suite
3. Re-approach with different strategy
4. Maintain TDD discipline throughout

---

## Timeline Estimate

- Issue #1 (State Register): 1-2 hours
- Issue #2 (Collateral Persistence): 2-3 hours (investigation + fix)
- Issue #4 (Collateral Timers): 3-4 hours (may require Rust implementation)
- Issue #3 (Budget Display): 0.5-1 hour
- **Total**: 6.5-10 hours

---

**End of Plan**
