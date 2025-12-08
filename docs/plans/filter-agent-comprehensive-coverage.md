# Feature Request: Comprehensive Bank-Centric Event Filtering

## Summary

Enhance `--filter-agent BANK_A` to provide a complete view of all events relevant to a specific bank's perspective, including:
1. All events for transactions where the bank is the **sender**
2. Settlement events where the bank is the **receiver** (incoming liquidity)
3. New "incoming liquidity" notification for settlements received

## Motivation

When debugging or analyzing a specific bank's behavior, operators need to see:
- Everything that happens to transactions the bank sends (full lifecycle)
- When the bank receives money (but not the sender's internal decisions about that transaction)

Currently, `--filter-agent` has significant gaps that make bank-centric analysis incomplete.

## Current State: Gaps in `--filter-agent`

### Problem 1: Inconsistent Field Names

The filter checks `agent_id` and `sender_id`, but several events use different field names:

```python
# Current filter logic (filters.py:95)
event_agent = event.get("agent_id") or event.get("sender_id")
```

**Events using `sender` (not `sender_id`) - MISSED:**
- `RtgsImmediateSettlement` → uses `sender`
- `RtgsSubmission` → uses `sender`
- `RtgsWithdrawal` → uses `sender`
- `RtgsResubmission` → uses `sender`

**Events using different structures - MISSED:**
- `LsmBilateralOffset` → uses `agent_a`, `agent_b`
- `LsmCycleSettlement` → uses `agents` (array)

### Problem 2: No Receiver Filtering

The filter never checks `receiver_id` or `receiver` fields. A bank cannot see when it receives incoming payments.

### Problem 3: No Incoming Liquidity Notification

When BANK_B settles a payment to BANK_A, BANK_A's verbose output shows nothing about incoming liquidity.

## Proposed Solution

### Part 1: Fix Sender Field Matching

Update the filter to check all sender-related fields:

```python
def _get_event_agents(event: dict) -> set[str]:
    """Extract all agent IDs involved in an event."""
    agents = set()

    # Standard fields
    if agent_id := event.get("agent_id"):
        agents.add(agent_id)
    if sender_id := event.get("sender_id"):
        agents.add(sender_id)
    if sender := event.get("sender"):
        agents.add(sender)

    # LSM bilateral
    if agent_a := event.get("agent_a"):
        agents.add(agent_a)
    if agent_b := event.get("agent_b"):
        agents.add(agent_b)

    # LSM cycle
    if agents_list := event.get("agents"):
        agents.update(agents_list)

    return agents
```

### Part 2: Receiver Filtering for Settlements Only

Add receiver matching **only for settlement events**:

```python
SETTLEMENT_EVENT_TYPES = {
    "RtgsImmediateSettlement",
    "Queue2LiquidityRelease",
    "LsmBilateralOffset",
    "LsmCycleSettlement",
    "OverdueTransactionSettled",
}

def matches(self, event: dict, tick: int) -> bool:
    # ... existing logic ...

    if self.agent_id is not None:
        event_agents = self._get_event_agents(event)

        # Check if agent is sender/actor
        if self.agent_id in event_agents:
            return True  # Continue to other filters

        # For settlements only: also match if agent is receiver
        if event.get("event_type") in SETTLEMENT_EVENT_TYPES:
            receiver = event.get("receiver_id") or event.get("receiver")
            if receiver == self.agent_id:
                return True  # Continue to other filters

        # Agent not involved
        return False
```

**Rationale:** A bank wants to see:
- ✅ Arrivals it sends
- ✅ Policy decisions it makes
- ✅ Settlements of its outgoing transactions
- ✅ Settlements where it **receives** money
- ❌ NOT: Other banks' policy decisions about payments coming to it
- ❌ NOT: Arrivals at other banks destined for it

### Part 3: Incoming Liquidity Notification

Add a new display message when showing settlements where the filtered bank is receiver:

**Example Output:**
```
┌─ Tick 42 ─────────────────────────────────────────────────────────┐
│ SETTLEMENTS                                                        │
├────────────────────────────────────────────────────────────────────┤
│ RTGS Immediate: tx_00000123 BANK_B → BANK_A $10,000.00            │
│   ↳ 💰 BANK_A liquidity will increase by $10,000.00 next tick     │
│                                                                    │
│ LSM Bilateral: BANK_C ↔ BANK_A offset $5,000.00                   │
│   ↳ 💰 BANK_A net liquidity change: +$2,500.00 next tick          │
└────────────────────────────────────────────────────────────────────┘
```

**Implementation in `display.py`:**

```python
def _format_settlement_with_incoming(
    event: dict,
    filter_agent: str | None
) -> list[str]:
    """Format settlement event, adding incoming liquidity note if receiver matches filter."""
    lines = [_format_settlement_line(event)]

    if filter_agent is None:
        return lines

    receiver = event.get("receiver_id") or event.get("receiver")
    if receiver == filter_agent:
        amount = event.get("amount", 0)
        lines.append(
            f"  ↳ {filter_agent} liquidity will increase by "
            f"${amount/100:,.2f} next tick"
        )

    return lines
```

For LSM events, calculate net position change:

```python
def _calculate_lsm_net_change(event: dict, agent_id: str) -> int:
    """Calculate net liquidity change for an agent in LSM settlement."""
    if event.get("event_type") == "LsmBilateralOffset":
        if event.get("agent_a") == agent_id:
            return event.get("amount_b", 0) - event.get("amount_a", 0)
        elif event.get("agent_b") == agent_id:
            return event.get("amount_a", 0) - event.get("amount_b", 0)

    elif event.get("event_type") == "LsmCycleSettlement":
        agents = event.get("agents", [])
        net_positions = event.get("net_positions", [])
        if agent_id in agents:
            idx = agents.index(agent_id)
            # Net position is negative of liquidity change
            return -net_positions[idx] if idx < len(net_positions) else 0

    return 0
```

## Event Field Reference

For implementation, here are all the agent-related fields across event types:

| Event Type | Sender Fields | Receiver Fields |
|------------|---------------|-----------------|
| `Arrival` | `sender_id` | `receiver_id` |
| `PolicySubmit/Hold/Drop/Split` | `agent_id` | - |
| `TransactionReprioritized` | `agent_id` | - |
| `PriorityEscalated` | `sender_id` | - |
| `QueuedRtgs` | `sender_id` | - |
| `RtgsImmediateSettlement` | `sender` | `receiver` |
| `RtgsSubmission` | `sender` | `receiver` |
| `RtgsWithdrawal` | `sender` | - |
| `RtgsResubmission` | `sender` | - |
| `Queue2LiquidityRelease` | `sender` | `receiver` |
| `LsmBilateralOffset` | `agent_a`, `agent_b` | (both are sender+receiver) |
| `LsmCycleSettlement` | `agents` (array) | (all are sender+receiver) |
| `TransactionWentOverdue` | `sender_id` | `receiver_id` |
| `OverdueTransactionSettled` | `sender_id` | `receiver_id` |
| `CostAccrual` | `agent_id` | - |
| `Collateral*` | `agent_id` | - |
| `StateRegisterSet` | `agent_id` | - |
| `BankBudgetSet` | `agent_id` | - |

## Testing Requirements

### Unit Tests

```python
def test_filter_matches_sender_field_variants():
    """Filter matches events using 'sender' (not just 'sender_id')."""
    f = EventFilter(agent_id="BANK_A")

    # Should match: uses 'sender'
    assert f.matches({"event_type": "RtgsImmediateSettlement", "sender": "BANK_A"}, tick=1)

    # Should match: uses 'sender_id'
    assert f.matches({"event_type": "Arrival", "sender_id": "BANK_A"}, tick=1)


def test_filter_matches_lsm_agents():
    """Filter matches LSM events using agent_a/agent_b/agents."""
    f = EventFilter(agent_id="BANK_A")

    # Bilateral
    assert f.matches({
        "event_type": "LsmBilateralOffset",
        "agent_a": "BANK_A",
        "agent_b": "BANK_B"
    }, tick=1)

    assert f.matches({
        "event_type": "LsmBilateralOffset",
        "agent_a": "BANK_B",
        "agent_b": "BANK_A"
    }, tick=1)

    # Cycle
    assert f.matches({
        "event_type": "LsmCycleSettlement",
        "agents": ["BANK_B", "BANK_A", "BANK_C"]
    }, tick=1)


def test_filter_matches_receiver_for_settlements_only():
    """Filter matches receiver only for settlement events."""
    f = EventFilter(agent_id="BANK_A")

    # Should match: settlement where BANK_A receives
    assert f.matches({
        "event_type": "RtgsImmediateSettlement",
        "sender": "BANK_B",
        "receiver": "BANK_A"
    }, tick=1)

    # Should NOT match: arrival where BANK_A is receiver (not settlement)
    assert not f.matches({
        "event_type": "Arrival",
        "sender_id": "BANK_B",
        "receiver_id": "BANK_A"
    }, tick=1)

    # Should NOT match: policy event for tx going to BANK_A
    assert not f.matches({
        "event_type": "PolicySubmit",
        "agent_id": "BANK_B",
        "receiver_id": "BANK_A"  # Even if this field existed
    }, tick=1)
```

### Integration Tests

```python
def test_filter_agent_shows_complete_outbound_lifecycle():
    """--filter-agent shows all events for outbound transactions."""
    # Setup: BANK_A sends tx that goes through queue, then LSM
    orch = create_orchestrator_with_queued_lsm_scenario()

    events = []
    for tick in range(100):
        orch.tick()
        tick_events = orch.get_tick_events(tick)
        events.extend([e for e in tick_events if filter.matches(e, tick)])

    # Verify complete lifecycle captured
    event_types = [e["event_type"] for e in events]
    assert "Arrival" in event_types
    assert "PolicySubmit" in event_types
    assert "RtgsSubmission" in event_types  # Was missing before!
    assert "LsmBilateralOffset" in event_types  # Was missing before!


def test_filter_agent_shows_incoming_settlements():
    """--filter-agent shows settlements where bank receives money."""
    # Setup: BANK_B sends to BANK_A
    orch = create_orchestrator_with_incoming_payment()

    # Filter for BANK_A
    filter = EventFilter(agent_id="BANK_A")

    events = collect_filtered_events(orch, filter)

    # Should see the settlement (BANK_A receives)
    settlements = [e for e in events if e["event_type"] == "RtgsImmediateSettlement"]
    assert len(settlements) == 1
    assert settlements[0]["receiver"] == "BANK_A"

    # Should NOT see the arrival (BANK_B's event)
    arrivals = [e for e in events if e["event_type"] == "Arrival"]
    assert len(arrivals) == 0  # Arrival is BANK_B's event
```

## Implementation Checklist

- [ ] Update `EventFilter._get_event_agents()` to extract all agent fields
- [ ] Add `SETTLEMENT_EVENT_TYPES` constant
- [ ] Update `EventFilter.matches()` to include receiver for settlements
- [ ] Add incoming liquidity display helper functions
- [ ] Update `display_tick_verbose_output()` to show incoming liquidity
- [ ] Pass `filter_agent` through display call chain
- [ ] Add unit tests for field matching
- [ ] Add integration tests for complete lifecycle
- [ ] Update CLI documentation
- [ ] Update `docs/reference/cli/filtering.md`

## Future Considerations

### Optional: Separate `--filter-sender` and `--filter-receiver`

For more granular control, could add:
- `--filter-sender BANK_A` - only events where BANK_A sends
- `--filter-receiver BANK_A` - only events where BANK_A receives
- `--filter-agent BANK_A` - both (current behavior after fix)

### Optional: Normalize Field Names in Rust

Long-term, consider normalizing all sender fields to `sender_id` in Rust event definitions. This would require a migration but simplify Python logic.

## References

- Current filter implementation: `api/payment_simulator/cli/filters.py`
- Event definitions: `simulator/src/models/event.rs`
- Display logic: `api/payment_simulator/cli/execution/display.py`
- CLI flags: `api/payment_simulator/cli/commands/run.py:422-461`
