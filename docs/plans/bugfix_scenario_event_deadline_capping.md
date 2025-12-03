# Bug Fix: CustomTransactionArrival Does Not Respect `deadline_cap_at_eod`

## Summary

`CustomTransactionArrival` scenario events bypass the `deadline_cap_at_eod` feature. When this config flag is enabled, transaction deadlines should be capped at end-of-day, but scenario events ignore this setting entirely.

## Priority

**High** - This breaks Castro experiment alignment where same-day settlement is required.

## Current Behavior

```yaml
simulation:
  ticks_per_day: 10
deadline_cap_at_eod: true  # Should cap deadlines at EOD
scenario_events:
  - type: CustomTransactionArrival
    from_agent: A
    to_agent: B
    amount: 10000
    deadline: 50  # Offset from arrival
    schedule: { type: OneTime, tick: 0 }
```

**Result:** Transaction created with `deadline_tick = 50` (uncapped)

**Expected:** Transaction created with `deadline_tick = 10` (capped at EOD)

## Root Cause

**File:** `backend/src/orchestrator/engine.rs` lines 1496-1501

```rust
// CustomTransactionArrival: create transaction through normal arrival path
ScenarioEvent::CustomTransactionArrival { ... } => {
    // Calculate deadline: if provided, it's relative to arrival tick
    let deadline_tick = if let Some(rel_deadline) = deadline {
        tick + rel_deadline  // <-- NO CAPPING APPLIED
    } else {
        tick + (self.config.ticks_per_day / 10).max(5)
    };

    // Submit directly without deadline capping
    let tx_id = self.submit_transaction(..., deadline_tick, ...)?;
}
```

The `deadline_cap_at_eod` logic exists in `ArrivalGenerator::generate_deadline()` (lines 540-561 of `backend/src/arrivals/mod.rs`), but this is never called for scenario events.

## Proposed Fix

Apply the same capping logic used by `ArrivalGenerator` to `CustomTransactionArrival` events.

### Option A: Inline the capping logic (Simpler)

```rust
ScenarioEvent::CustomTransactionArrival {
    from_agent,
    to_agent,
    amount,
    priority,
    deadline,
    is_divisible,
} => {
    let priority = priority.unwrap_or(5);
    let is_divisible = is_divisible.unwrap_or(false);

    // Calculate raw deadline
    let raw_deadline_tick = if let Some(rel_deadline) = deadline {
        tick + rel_deadline
    } else {
        tick + (self.config.ticks_per_day / 10).max(5)
    };

    // Apply deadline_cap_at_eod if enabled
    let deadline_tick = if self.config.deadline_cap_at_eod {
        let current_day = tick / self.config.ticks_per_day;
        let day_end_tick = (current_day + 1) * self.config.ticks_per_day;
        raw_deadline_tick.min(day_end_tick)
    } else {
        raw_deadline_tick
    };

    // Also cap at episode end (existing behavior for ArrivalGenerator)
    let deadline_tick = deadline_tick.min(self.config.episode_end_tick());

    let tx_id = self.submit_transaction(
        from_agent,
        to_agent,
        *amount,
        deadline_tick,
        priority,
        is_divisible,
    )?;
    // ... rest of handler
}
```

### Option B: Extract helper function (Cleaner)

Create a shared helper function that both `ArrivalGenerator` and the scenario event handler can use:

```rust
impl OrchestratorEngine {
    /// Cap a deadline according to config settings.
    fn cap_deadline(&self, arrival_tick: usize, raw_deadline: usize) -> usize {
        // Cap at episode end
        let capped = raw_deadline.min(self.config.episode_end_tick());

        // If deadline_cap_at_eod enabled, also cap at current day's end
        if self.config.deadline_cap_at_eod {
            let current_day = arrival_tick / self.config.ticks_per_day;
            let day_end_tick = (current_day + 1) * self.config.ticks_per_day;
            capped.min(day_end_tick)
        } else {
            capped
        }
    }
}
```

## Test Cases

The following tests in `experiments/castro/tests/` currently fail and should pass after the fix:

1. **`test_deadline_cap_at_eod.py::TestDeadlineCapping::test_deadline_beyond_eod_is_capped`**
   - Scenario event with `deadline: 100`, `deadline_cap_at_eod: true`
   - Should cap to EOD (tick 9 for 10 ticks/day)

2. **`test_deadline_cap_at_eod.py::TestScenarioEventDeadlineCapping::test_custom_transaction_deadline_capped`**
   - Same as above

3. **`test_deadline_cap_at_eod.py::TestSettlementUrgency::test_same_day_settlement_enforced`**
   - Verifies transactions become overdue at EOD

4. **`test_deadline_cap_at_eod.py::TestSettlementUrgency::test_unsettled_at_eod_becomes_overdue`**
   - Verifies overdue status triggers at capped deadline

5. **`test_castro_scenario_events.py::TestDeadlineAssignment::test_deadline_capped_at_eod`**
   - Scenario event with `deadline: 50`, expects capping to EOD

### New Rust Unit Test

Add to `backend/tests/test_deadline_eod_cap.rs`:

```rust
#[test]
fn test_scenario_event_deadline_respects_eod_cap() {
    let config = OrchestratorConfig {
        ticks_per_day: 10,
        num_days: 1,
        deadline_cap_at_eod: true,
        // ... other config
    };

    let mut orch = Orchestrator::new(config);

    // Scenario event arrives at tick 0 with deadline offset 50
    // Should be capped to day_end_tick = 10
    orch.add_scenario_event(ScenarioEvent::CustomTransactionArrival {
        from_agent: "A".to_string(),
        to_agent: "B".to_string(),
        amount: 10000,
        priority: Some(5),
        deadline: Some(50),  // Way beyond EOD
        is_divisible: Some(false),
    }, 0);

    orch.tick();  // Process tick 0

    let tx = orch.get_transaction("tx_id").unwrap();
    assert_eq!(tx.deadline_tick(), 10);  // Capped at EOD
}
```

## Related Documentation

- **Feature Spec:** `docs/plans/deadline_eod_cap.md` (Section 2.10 mentions this as intended behavior)
- **Existing Implementation:** `backend/src/arrivals/mod.rs` lines 535-561
- **Castro Alignment:** This is required for experiments where all payments must settle same-day

## Additional Test Fix Required

**File:** `experiments/castro/tests/test_castro_scenario_events.py`

The test `test_explicit_deadline_used` has an incorrect assertion. The `deadline` field is documented as "ticks from arrival" (offset), not an absolute tick:

```python
# Current (WRONG):
assert arrivals[0]["deadline"] == 7

# Should be (deadline = arrival_tick + offset = 2 + 7 = 9):
assert arrivals[0]["deadline"] == 9
```

This is a test bug, not a Rust bug. The schema at line 319 of `schemas.py` clearly states:
```python
deadline: int | None = Field(None, description="Deadline in ticks from arrival")
```

## Acceptance Criteria

- [x] `CustomTransactionArrival` respects `deadline_cap_at_eod` when enabled
- [x] Deadline is capped at `(current_day + 1) * ticks_per_day - 1` (last tick OF the day)
- [x] Deadline is also capped at episode end (existing behavior)
- [x] All 5 failing Python tests pass (now 149 passing, 1 unrelated failure)
- [ ] New Rust unit test added and passing (deferred)
- [x] Test `test_explicit_deadline_used` fixed to expect correct value (9, not 7)

## Resolution (2025-12-03)

**Fixed via centralized `cap_deadline` helper function in `engine.rs`.**

The fix introduces a `cap_deadline(&self, arrival_tick, raw_deadline)` helper that:
1. Caps at episode end (`num_days * ticks_per_day`)
2. If `deadline_cap_at_eod` is enabled, caps at day end (`(current_day + 1) * ticks_per_day - 1`)
3. Ensures deadline is always at least `arrival_tick + 1` (for transactions arriving at the last tick of a day)

This helper is called from:
- `submit_transaction()`
- `submit_transaction_with_rtgs_priority()`

The `CustomTransactionArrival` handler now passes the raw deadline to `submit_transaction()`, which applies capping consistently.
