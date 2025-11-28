# Event Filtering

The CLI supports filtering events during verbose and event-stream output modes. This document describes the filtering options, syntax, and behavior.

## Overview

Event filtering allows you to focus on specific events during simulation execution or replay. Filters are applied using AND logic - all specified filters must match for an event to be displayed.

## Requirements

Filters require one of these output modes:

- `--verbose` - Verbose mode
- `--event-stream` - Event stream mode

Using filters without these modes produces an error:

```
Error: Event filters (--filter-*) require either --verbose or --event-stream mode
```

## Filter Options

| Option | Description | Example |
|--------|-------------|---------|
| `--filter-event-type` | Filter by event type(s) | `Arrival,Settlement` |
| `--filter-agent` | Filter by agent ID | `BANK_A` |
| `--filter-tx` | Filter by transaction ID | `tx-abc123` |
| `--filter-tick-range` | Filter by tick range | `50-100` |

---

## Event Type Filter

Filter events by their type.

### Syntax

```bash
--filter-event-type TYPE1,TYPE2,...
```

Multiple types are comma-separated (no spaces).

### Available Event Types

| Event Type | Description |
|------------|-------------|
| `Arrival` | Transaction arrival |
| `RtgsImmediateSettlement` | RTGS immediate settlement |
| `Queue2LiquidityRelease` | Queue-2 liquidity release |
| `LsmBilateralOffset` | LSM bilateral (2-agent) offset |
| `LsmCycleSettlement` | LSM multi-agent cycle |
| `TransactionWentOverdue` | Transaction exceeded deadline |
| `CostAccrual` | Continuous cost accrual |
| `PolicySubmit` | Policy decision: submit |
| `PolicyHold` | Policy decision: hold |
| `PolicyDrop` | Policy decision: drop |
| `PolicySplit` | Policy decision: split |
| `CollateralPost` | Collateral posting |
| `CollateralWithdraw` | Collateral withdrawal |
| `EndOfDay` | End-of-day marker |
| `ScenarioEventExecuted` | Scenario event triggered |
| `StateRegisterSet` | State register update |
| `BankBudgetSet` | Bank budget set |
| `QueuedRtgs` | Transaction queued for RTGS |

### Examples

```bash
# Only arrivals
payment-sim run --config cfg.yaml --verbose --filter-event-type Arrival

# Arrivals and settlements
payment-sim run --config cfg.yaml --verbose --filter-event-type Arrival,RtgsImmediateSettlement

# All LSM events
payment-sim run --config cfg.yaml --verbose --filter-event-type LsmBilateralOffset,LsmCycleSettlement

# Policy decisions only
payment-sim run --config cfg.yaml --verbose --filter-event-type PolicySubmit,PolicyHold,PolicyDrop,PolicySplit
```

---

## Agent Filter

Filter events by agent ID. Matches both `agent_id` and `sender_id` fields.

### Syntax

```bash
--filter-agent AGENT_ID
```

### Field Matching

The filter checks:

1. `agent_id` field (for policy events, cost events)
2. `sender_id` field (for transaction events)

### Examples

```bash
# All events for BANK_A
payment-sim run --config cfg.yaml --verbose --filter-agent BANK_A

# Combined with event type
payment-sim run --config cfg.yaml --verbose \
  --filter-agent BANK_A \
  --filter-event-type Arrival,Settlement
```

---

## Transaction Filter

Filter events by transaction ID.

### Syntax

```bash
--filter-tx TRANSACTION_ID
```

### Examples

```bash
# Track specific transaction
payment-sim run --config cfg.yaml --verbose --filter-tx tx-abc123

# Combine with tick range
payment-sim run --config cfg.yaml --verbose \
  --filter-tx tx-abc123 \
  --filter-tick-range 0-50
```

---

## Tick Range Filter

Filter events by tick number.

### Syntax

```bash
--filter-tick-range MIN-MAX
--filter-tick-range MIN-
--filter-tick-range -MAX
```

### Formats

| Format | Meaning |
|--------|---------|
| `10-50` | Ticks 10 through 50 (inclusive) |
| `10-` | Tick 10 onwards (no upper limit) |
| `-50` | Up to tick 50 (no lower limit) |

### Examples

```bash
# Specific range
payment-sim run --config cfg.yaml --verbose --filter-tick-range 50-100

# From tick 100 onwards
payment-sim run --config cfg.yaml --verbose --filter-tick-range 100-

# Up to tick 50
payment-sim run --config cfg.yaml --verbose --filter-tick-range -50

# Single tick (effectively)
payment-sim run --config cfg.yaml --verbose --filter-tick-range 42-42
```

---

## Combining Filters

Filters use **AND logic** - all specified filters must match.

### Examples

```bash
# Arrivals for BANK_A in ticks 0-50
payment-sim run --config cfg.yaml --verbose \
  --filter-event-type Arrival \
  --filter-agent BANK_A \
  --filter-tick-range 0-50

# Settlements and LSM for specific transaction
payment-sim run --config cfg.yaml --verbose \
  --filter-event-type RtgsImmediateSettlement,LsmBilateralOffset,LsmCycleSettlement \
  --filter-tx tx-abc123

# All cost events for BANK_B after tick 100
payment-sim run --config cfg.yaml --verbose \
  --filter-event-type CostAccrual \
  --filter-agent BANK_B \
  --filter-tick-range 100-
```

### Filter Logic

```
event_matches = (
    (event_types is None OR event.type IN event_types)
    AND (agent_id is None OR event.agent_id == agent_id OR event.sender_id == agent_id)
    AND (tx_id is None OR event.tx_id == tx_id)
    AND (tick_min is None OR tick >= tick_min)
    AND (tick_max is None OR tick <= tick_max)
)
```

---

## Use Cases

### Debugging a Specific Agent

```bash
# See all activity for one bank
payment-sim run --config crisis.yaml --verbose --filter-agent TROUBLED_BANK
```

### Tracking a Transaction

```bash
# Follow a transaction through the system
payment-sim run --config scenario.yaml --verbose --filter-tx tx-large-payment

# Shows: arrival → policy decision → settlement (or queue)
```

### Analyzing Tick Range

```bash
# Investigate issue at tick 150
payment-sim run --config scenario.yaml --verbose --filter-tick-range 145-155
```

### Monitoring LSM Activity

```bash
# See only LSM events
payment-sim run --config scenario.yaml --verbose \
  --filter-event-type LsmBilateralOffset,LsmCycleSettlement
```

### Cost Analysis

```bash
# Cost events for specific agent
payment-sim run --config scenario.yaml --verbose \
  --filter-event-type CostAccrual \
  --filter-agent BANK_A
```

### End-of-Day Focus

```bash
# See EOD events (typically at ticks 99, 199, 299 for 100 ticks/day)
payment-sim run --config scenario.yaml --verbose \
  --filter-event-type EndOfDay
```

---

## Replay Filtering

Filters work with the replay command as well:

```bash
# Replay specific agent's activity
payment-sim replay --simulation-id sim-abc123 --verbose \
  --filter-agent BANK_A \
  --filter-tick-range 0-50
```

Note: Replay tick range is controlled by `--from-tick` and `--to-tick` options, which are separate from the filter. The replay range determines what ticks are processed; the filter determines what events are displayed.

---

## Event Stream Filtering

In event-stream mode, filters affect which JSON lines are output:

```bash
# Only LSM events as JSONL
payment-sim run --config scenario.yaml --event-stream \
  --filter-event-type LsmBilateralOffset,LsmCycleSettlement

# Pipe to processor
payment-sim run --config scenario.yaml --event-stream \
  --filter-agent BANK_A | ./process_bank_events.py
```

---

## Troubleshooting

### No Events Displayed

If no events are displayed:

1. Check event type spelling (case-sensitive)
2. Verify agent ID exists in simulation
3. Check tick range is within simulation bounds
4. Remember: filters use AND logic

### Error: Filters Require Mode

```
Error: Event filters (--filter-*) require either --verbose or --event-stream mode
```

**Solution**: Add `--verbose` or `--event-stream` to your command.

### Empty Event Type List

An empty `--filter-event-type` (just the flag with no value) matches no events:

```bash
# Matches nothing!
payment-sim run --config cfg.yaml --verbose --filter-event-type ""
```

---

## Implementation Details

**File**: `api/payment_simulator/cli/filters.py`

The `EventFilter` class implements filtering logic:

```python
class EventFilter:
    def __init__(
        self,
        event_types: list[str] | None = None,
        agent_id: str | None = None,
        tx_id: str | None = None,
        tick_min: int | None = None,
        tick_max: int | None = None,
    ):
        ...

    def matches(self, event: dict, tick: int) -> bool:
        # AND logic across all filters
        ...
```

---

## Related Documentation

- [Output Modes](output-modes.md) - Verbose and event-stream modes
- [run Command](commands/run.md) - Full run command reference
- [replay Command](commands/replay.md) - Replay command reference
