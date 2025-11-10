# Scenario Events: Remaining Implementation Plan

## Status: Phase 14-15 Completion

**Date**: 2025-11-10
**Current State**: 2/7 event types fully implemented
**Goal**: Complete implementation of remaining 4 event types

---

## ✅ Completed Event Types

### 1. CustomTransactionArrival
- ✅ Rust enum variant
- ✅ FFI parsing
- ✅ Pydantic schema
- ✅ Rust handler implementation (Orchestrator level)
- ✅ Event logging
- ✅ Display logic
- ✅ 5 comprehensive tests

### 2. CollateralAdjustment
- ✅ Rust enum variant
- ✅ FFI parsing
- ✅ Pydantic schema
- ✅ Rust handler implementation
- ✅ Event logging
- ✅ Display logic (implicit in collateral changes)
- ✅ Tested via integration

### 3. DirectTransfer (Pre-existing)
- ✅ Fully implemented and working

---

## ⚠️ Remaining Event Types (Priority Order)

### Priority 1: AgentArrivalRateChange
**Rationale**: Simpler state mutation, no cross-agent dependencies

**Status**:
- ✅ Rust enum variant defined
- ✅ FFI parsing implemented
- ✅ Pydantic schema defined
- ❌ Handler implementation (returns "not yet implemented")

**Implementation Scope**:
```rust
ScenarioEvent::AgentArrivalRateChange { agent, multiplier } => {
    // 1. Validate agent exists
    // 2. Get current ArrivalConfig
    // 3. Multiply rate_per_tick by multiplier
    // 4. Update agent's ArrivalConfig
    // 5. Log event
}
```

**Edge Cases**:
- Multiplier of 0 (Python schema requires > 0, but test 0.001)
- Very large multipliers (cap at 100×?)
- Negative multipliers (schema prevents)

**Testing Strategy** (TDD):
1. Test: Change single agent rate by 2×
2. Test: Change rate by 0.5× (halve)
3. Test: Change rate by 0.001 (near-halt)
4. Test: Verify other agents unaffected
5. Test: Multiple changes to same agent (multiplicative)
6. Test: Event logging verification

### Priority 2: GlobalArrivalRateChange
**Rationale**: Similar to AgentArrivalRateChange but affects all agents

**Status**:
- ✅ Rust enum variant defined
- ✅ FFI parsing implemented
- ✅ Pydantic schema defined
- ❌ Handler implementation

**Implementation Scope**:
```rust
ScenarioEvent::GlobalArrivalRateChange { multiplier } => {
    // 1. Iterate over all agents
    // 2. For each agent with ArrivalConfig:
    //    a. Get current rate_per_tick
    //    b. Multiply by multiplier
    //    c. Update ArrivalConfig
    // 3. Log event
}
```

**Edge Cases**:
- Agents without ArrivalConfig (skip gracefully)
- Agents with rate_per_tick = 0 (leave as 0)
- Very large multipliers

**Testing Strategy** (TDD):
1. Test: Double all agent rates (2×)
2. Test: Halve all agent rates (0.5×)
3. Test: Verify all agents affected equally
4. Test: Agent with rate=0 remains 0
5. Test: Event logging with agent count
6. Test: Multiple global changes (multiplicative effect)

### Priority 3: DeadlineWindowChange
**Rationale**: Affects future arrivals only, no immediate state impact

**Status**:
- ✅ Rust enum variant defined
- ✅ FFI parsing implemented
- ✅ Pydantic schema defined
- ❌ Handler implementation

**Implementation Scope**:
```rust
ScenarioEvent::DeadlineWindowChange { agent, new_deadline_range } => {
    // 1. Validate agent exists
    // 2. Validate new_deadline_range is [min, max] with min < max
    // 3. Get agent's ArrivalConfig
    // 4. Update deadline_range field
    // 5. Log event
}
```

**Edge Cases**:
- Invalid range (min >= max) - Python schema validates
- Very tight windows ([1, 2])
- Very wide windows ([100, 500])

**Testing Strategy** (TDD):
1. Test: Change deadline window to tighter range
2. Test: Change deadline window to wider range
3. Test: Verify future arrivals use new deadlines
4. Test: Verify existing transactions unaffected
5. Test: Event logging verification
6. Test: Multiple changes to same agent (last wins)

### Priority 4: CounterpartyWeightChange
**Rationale**: Most complex, involves weight redistribution logic

**Status**:
- ✅ Rust enum variant defined
- ✅ FFI parsing implemented
- ✅ Pydantic schema defined (corrected to single counterparty)
- ❌ Handler implementation

**Implementation Scope**:
```rust
ScenarioEvent::CounterpartyWeightChange {
    agent,
    counterparty,
    new_weight,
    auto_balance_others,
} => {
    // 1. Validate agent and counterparty exist
    // 2. Get agent's ArrivalConfig
    // 3. Get current counterparty_weights HashMap
    // 4. Update weight for specified counterparty
    // 5. If auto_balance_others:
    //    a. Calculate remaining weight: 1.0 - new_weight
    //    b. Get other counterparties
    //    c. Redistribute remaining weight proportionally
    // 6. Validate weights sum to ~1.0
    // 7. Update ArrivalConfig
    // 8. Log event
}
```

**Edge Cases**:
- Counterparty not in current weights (add new entry)
- new_weight = 0 (remove counterparty)
- new_weight = 1.0 (all transactions to one counterparty)
- auto_balance_others with only 1 other counterparty
- Weights don't sum to 1.0 due to floating point

**Testing Strategy** (TDD):
1. Test: Change existing counterparty weight
2. Test: Add new counterparty with auto_balance
3. Test: Set weight to 0 (effective removal)
4. Test: Set weight to 1.0 with auto_balance
5. Test: Verify weights sum to ~1.0
6. Test: Multiple changes (cumulative effect)
7. Test: Event logging verification

---

## Implementation Order (TDD Workflow)

### Phase 1: AgentArrivalRateChange (2-3 hours)

**Step 1: Write Failing Tests** (RED)
```python
# File: api/tests/integration/test_agent_arrival_rate_change.py

def test_agent_arrival_rate_change_doubles_rate():
    """Test doubling a specific agent's arrival rate."""
    config = {
        "ticks_per_day": 20,
        "num_days": 1,
        "rng_seed": 42,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1000000,
                "credit_limit": 500000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 0.5,  # Start: 0.5
                    # ... other fields
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 1000000,
                "credit_limit": 500000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 0.5,  # Should remain 0.5
                    # ... other fields
                },
            },
        ],
        "scenario_events": [
            {
                "type": "AgentArrivalRateChange",
                "agent": "BANK_A",
                "multiplier": 2.0,  # Double BANK_A only
                "schedule": "OneTime",
                "tick": 5,
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Tick 0-4: Original rates
    for _ in range(5):
        orch.tick()

    # Tick 5: Event executes
    orch.tick()

    # Tick 6-19: New rates
    for _ in range(14):
        orch.tick()

    # Measure arrivals in each period
    # Period 1 (ticks 0-4): BANK_A ~2.5 arrivals (5 * 0.5)
    # Period 2 (ticks 6-19): BANK_A ~14 arrivals (14 * 1.0)
    # BANK_B should have ~10 arrivals total (20 * 0.5)

    events = orch.get_all_events()

    # Count arrivals per agent per period
    # ... assertions

    assert rate_change_worked
```

**Step 2: Implement Handler** (GREEN)
```rust
// File: backend/src/events/handler.rs

ScenarioEvent::AgentArrivalRateChange { agent, multiplier } => {
    execute_agent_arrival_rate_change(state, tick, agent, *multiplier)
}

fn execute_agent_arrival_rate_change(
    state: &mut SimulationState,
    tick: usize,
    agent: &str,
    multiplier: f64,
) -> Result<(), String> {
    // Get agent
    let agent_obj = state
        .get_agent_mut(agent)
        .ok_or_else(|| format!("Agent not found: {}", agent))?;

    // Get arrival config
    let arrival_config = agent_obj
        .arrival_config_mut()
        .ok_or_else(|| format!("Agent {} has no arrival config", agent))?;

    // Update rate
    let old_rate = arrival_config.rate_per_tick;
    let new_rate = old_rate * multiplier;
    arrival_config.rate_per_tick = new_rate;

    // Log event
    log_scenario_event(state, tick, "agent_arrival_rate_change", &json!({
        "agent": agent,
        "multiplier": multiplier,
        "old_rate": old_rate,
        "new_rate": new_rate,
    }));

    Ok(())
}
```

**Step 3: Run Tests** - Should pass

**Step 4: Write More Tests** - Edge cases

**Step 5: Refactor** - If needed

### Phase 2: GlobalArrivalRateChange (1-2 hours)

Similar TDD workflow, simpler implementation (iterate all agents).

### Phase 3: DeadlineWindowChange (2-3 hours)

Similar TDD workflow, needs verification that future arrivals use new range.

### Phase 4: CounterpartyWeightChange (3-4 hours)

Most complex, needs careful testing of weight redistribution logic.

---

## Testing Checklist

For each event type, verify:

- [ ] Basic functionality (event executes)
- [ ] State change occurs correctly
- [ ] Other agents/state unaffected (isolation)
- [ ] Multiple events cumulative
- [ ] Event logging complete
- [ ] Replay identity maintained
- [ ] Display logic works (if applicable)
- [ ] Edge cases handled
- [ ] Integration with ten_day_crisis_scenario.yaml

---

## Replay Identity Requirements

Each event must:

1. **Log complete details** to `simulation_events` table
2. **Include all parameters** in details JSON
3. **Log state before/after** (old_value, new_value)
4. **Work identically** in replay mode

Example event log:
```json
{
  "tick": 205,
  "event_type": "ScenarioEventExecuted",
  "scenario_event_type": "agent_arrival_rate_change",
  "details": {
    "agent": "REGIONAL_TRUST",
    "multiplier": 0.001,
    "old_rate": 0.475,
    "new_rate": 0.000475
  }
}
```

---

## Success Criteria

**Phase Complete When**:

1. ✅ All 4 event types have handlers implemented
2. ✅ All tests passing (≥15 new tests)
3. ✅ ten_day_crisis_scenario.yaml runs successfully (all 500 ticks)
4. ✅ Replay identity verified
5. ✅ Display logic added for new events
6. ✅ Documentation updated (remove ⚠️ warnings)

**Estimated Timeline**: 8-12 hours total

---

## Display Logic Requirements

Add to `api/payment_simulator/cli/output.py`:

```python
def log_scenario_events(events, quiet=False):
    # ... existing code ...

    elif scenario_type == "agent_arrival_rate_change":
        agent = details.get("agent", "?")
        multiplier = details.get("multiplier", 1.0)
        old_rate = details.get("old_rate", 0)
        new_rate = details.get("new_rate", 0)
        console.print(f"   • [yellow]AgentArrivalRateChange:[/yellow] {agent} rate: {old_rate:.3f} → {new_rate:.3f} ({multiplier}×)")

    elif scenario_type == "global_arrival_rate_change":
        multiplier = details.get("multiplier", 1.0)
        agent_count = details.get("agent_count", 0)
        console.print(f"   • [magenta]GlobalArrivalRateChange:[/magenta] All {agent_count} agents × {multiplier}")

    elif scenario_type == "deadline_window_change":
        agent = details.get("agent", "?")
        old_range = details.get("old_range", [])
        new_range = details.get("new_range", [])
        console.print(f"   • [blue]DeadlineWindowChange:[/blue] {agent} deadlines: {old_range} → {new_range}")

    elif scenario_type == "counterparty_weight_change":
        agent = details.get("agent", "?")
        counterparty = details.get("counterparty", "?")
        old_weight = details.get("old_weight", 0)
        new_weight = details.get("new_weight", 0)
        console.print(f"   • [cyan]CounterpartyWeightChange:[/cyan] {agent} → {counterparty}: {old_weight:.2f} → {new_weight:.2f}")
```

---

## Risk Mitigation

**Risk 1**: ArrivalConfig access patterns unclear
**Mitigation**: Review existing code in `backend/src/models/agent.rs`

**Risk 2**: Weight redistribution floating point errors
**Mitigation**: Use epsilon comparison, normalize weights after redistribution

**Risk 3**: Replay identity breaks
**Mitigation**: Write replay tests for each event type

**Risk 4**: Performance impact
**Mitigation**: Keep handlers simple, avoid expensive operations

---

## Next Steps

1. Create `test_agent_arrival_rate_change.py` (TDD RED)
2. Implement handler in Rust (TDD GREEN)
3. Run tests, iterate
4. Repeat for remaining 3 event types
5. Integration test with ten_day_crisis_scenario.yaml
6. Update documentation
7. Commit and push

---

## Related Files

**Rust**:
- `backend/src/events/types.rs` - Event enum
- `backend/src/events/handler.rs` - Handler implementation
- `backend/src/models/agent.rs` - ArrivalConfig access
- `backend/src/ffi/types.rs` - FFI parsing (already done)

**Python**:
- `api/payment_simulator/config/schemas.py` - Pydantic schemas (already done)
- `api/payment_simulator/cli/output.py` - Display logic
- `api/tests/integration/test_*_event.py` - Test files

**Documentation**:
- `README.md` - Update to remove ⚠️ warnings
- `examples/scenario_events.md` - Update status
- `examples/configs/ten_day_crisis_scenario.yaml` - Update header

---

*Plan created: 2025-11-10*
*Next update: After Phase 1 completion*
