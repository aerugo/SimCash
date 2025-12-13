# ScheduledSettlementEvent Implementation Plan

**Created**: 2025-12-13
**Status**: Ready for implementation
**Purpose**: Enable bootstrap evaluation to use real orchestration engine with exact settlement timing

---

## Problem Statement

Bootstrap evaluation needs incoming liquidity ("beats") to arrive at exactly the tick they settled in the original simulation.

Current approach uses `DirectTransferEvent` which:
- Bypasses the transaction/settlement engine
- Is just a direct balance adjustment
- Doesn't go through RTGS

We need a mechanism that:
- Goes through the real RTGS engine
- Settles at EXACTLY the specified tick
- Produces real settlement events

---

## Solution: ScheduledSettlementEvent

A new scenario event type that atomically creates and settles a transaction at a specified tick.

### Lifecycle

```
Tick 0 to T-1:  [event waiting in scenario queue]

Tick T:         Event fires →
                1. Transaction created (SOURCE → TARGET)
                2. Immediately submitted to RTGS
                3. SOURCE has funds → settles instantly
                4. Emit: RtgsImmediateSettlement
                5. TARGET balance += amount
```

No transaction exists before tick T. Clean, atomic semantics.

---

## Implementation Phases

### Phase 1: Rust - Add ScheduledSettlementEvent

**File**: `simulator/src/models/scenario_event.rs` (or wherever scenario events are defined)

Add new variant:
```rust
pub enum ScenarioEvent {
    // ... existing variants ...

    /// Settlement that occurs at exactly the scheduled tick.
    /// Used by bootstrap evaluation to inject liquidity "beats".
    ScheduledSettlement {
        from_agent: String,
        to_agent: String,
        amount: i64,
        // Note: schedule.tick IS the settlement tick
    },
}
```

**File**: `simulator/src/orchestrator/engine.rs`

Handle the new event type in scenario event processing:
```rust
ScenarioEvent::ScheduledSettlement { from_agent, to_agent, amount } => {
    // Create transaction
    let tx = Transaction::new(
        from_agent.clone(),
        to_agent.clone(),
        amount,
        current_tick,  // arrival = now
        current_tick,  // deadline = now (immediate)
        0,             // priority
    );

    // Settle immediately via RTGS
    // (sender is SOURCE with infinite liquidity, so always succeeds)
    self.settle_transaction_rtgs(&tx)?;
}
```

### Phase 2: Rust - FFI Serialization

**File**: `simulator/src/ffi/types.rs`

Add parsing for the new event type from Python dict:
```rust
"ScheduledSettlement" => {
    ScenarioEvent::ScheduledSettlement {
        from_agent: get_string(dict, "from_agent")?,
        to_agent: get_string(dict, "to_agent")?,
        amount: get_i64(dict, "amount")?,
    }
}
```

### Phase 3: Python - Schema Definition

**File**: `api/payment_simulator/config/schemas.py`

Add new event class:
```python
class ScheduledSettlementEvent(BaseModel):
    """Settlement that occurs at exactly the scheduled tick.

    Used by bootstrap evaluation to inject liquidity "beats" -
    incoming settlements that must arrive at a specific tick.

    Unlike DirectTransferEvent, this goes through the real RTGS engine
    and produces normal settlement events.
    """

    from_agent: str = Field(..., description="Sending agent ID")
    to_agent: str = Field(..., description="Receiving agent ID")
    amount: int = Field(..., description="Amount in cents (integer)", gt=0)
    schedule: OneTimeSchedule = Field(..., description="When settlement occurs")

    def to_ffi_dict(self) -> dict[str, Any]:
        return {
            "event_type": "ScheduledSettlement",
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "amount": self.amount,
            "schedule": self.schedule.model_dump(),
        }
```

Update `ScenarioEvent` union type to include new event.

### Phase 4: Python - Update SandboxConfigBuilder

**File**: `api/payment_simulator/ai_cash_mgmt/bootstrap/sandbox_config.py`

Replace `DirectTransferEvent` with `ScheduledSettlementEvent`:

```python
def _incoming_to_settlement(
    self, tx: RemappedTransaction, agent_id: str
) -> ScheduledSettlementEvent:
    """Convert incoming settlement to scheduled settlement event.

    The settlement occurs at exactly settlement_tick (the "beat"),
    going through the real RTGS engine.
    """
    tick = tx.settlement_tick if tx.settlement_tick is not None else 0

    return ScheduledSettlementEvent(
        from_agent="SOURCE",
        to_agent=agent_id,
        amount=tx.amount,
        schedule=OneTimeSchedule(tick=tick),
    )
```

Update `_build_scenario_events` to use new method.

---

## Testing Strategy

### Unit Tests (Rust)

```rust
#[test]
fn test_scheduled_settlement_settles_at_exact_tick() {
    // Setup: ScheduledSettlement at tick 5
    // Run ticks 0-4: verify no balance change
    // Run tick 5: verify balance changed, settlement event emitted
}

#[test]
fn test_scheduled_settlement_produces_rtgs_event() {
    // Verify RtgsImmediateSettlement event is emitted
}
```

### Integration Tests (Python)

```python
def test_scheduled_settlement_timing():
    """Verify settlement occurs at exactly the scheduled tick."""
    config = create_config_with_scheduled_settlement(tick=5, amount=10000)
    orch = Orchestrator.new(config)

    for t in range(5):
        orch.tick()
        balance = orch.get_agent_balance("TARGET")
        assert balance == 0, f"Balance should be 0 before tick 5, got {balance} at tick {t}"

    orch.tick()  # tick 5
    balance = orch.get_agent_balance("TARGET")
    assert balance == 10000, "Balance should be 10000 after tick 5"

def test_scheduled_settlement_emits_event():
    """Verify normal settlement event is produced."""
    # Run simulation, check events include RtgsImmediateSettlement
```

### Bootstrap Evaluation Test

```python
def test_bootstrap_uses_scheduled_settlement():
    """Verify bootstrap evaluation uses ScheduledSettlementEvent."""
    # Create bootstrap sample with incoming settlement at tick 5
    # Build sandbox config
    # Verify scenario_events contains ScheduledSettlementEvent
```

---

## Files Changed Summary

| File | Change |
|------|--------|
| `simulator/src/models/scenario_event.rs` | Add `ScheduledSettlement` variant |
| `simulator/src/orchestrator/engine.rs` | Handle new event in processing |
| `simulator/src/ffi/types.rs` | Parse new event from Python |
| `api/payment_simulator/config/schemas.py` | Add `ScheduledSettlementEvent` class |
| `api/payment_simulator/ai_cash_mgmt/bootstrap/sandbox_config.py` | Use new event type |
| `simulator/tests/` | Unit tests |
| `api/tests/integration/` | Integration tests |

---

## Success Criteria

- [ ] ScheduledSettlement settles at exactly the specified tick
- [ ] Normal `RtgsImmediateSettlement` event is emitted
- [ ] Bootstrap evaluation uses ScheduledSettlementEvent for incoming beats
- [ ] All existing tests pass
- [ ] New tests cover timing and event emission

---

## Notes

- SOURCE agent still has infinite liquidity (no change)
- SINK agent unchanged (still receives outgoing payments)
- Only incoming liquidity mechanism changes (DirectTransfer → ScheduledSettlement)
- This ensures bootstrap evaluation uses the same RTGS engine as main simulation
