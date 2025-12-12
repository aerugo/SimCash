# Transaction Model

> Runtime representation of a payment between two agents

Represents a payment order from one agent (sender) to another (receiver) with complete lifecycle tracking, dual priority system, and split transaction support.

---

## Overview

A Transaction tracks:
- Original and remaining amounts (i64 cents)
- Arrival and deadline timing
- Internal priority (0-10) for bank decisions
- RTGS priority (Urgent/Normal) for settlement queue
- Status lifecycle (Pending → Settled or Overdue)
- Parent/child relationships for split transactions

---

## State Fields

### Core Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | `String` | Unique transaction identifier (UUID v4) |
| `sender_id` | `String` | Sending agent ID (balance debited on settlement) |
| `receiver_id` | `String` | Receiving agent ID (balance credited on settlement) |
| `amount` | `i64` (cents) | Original transaction amount (immutable, must be positive) |
| `remaining_amount` | `i64` (cents) | Unsettled portion (decreases as settlement occurs) |

**CRITICAL:** Amount is always integer cents (INV-1).

### Timing Fields

| Field | Type | Description |
|-------|------|-------------|
| `arrival_tick` | `usize` | Tick when transaction entered the system |
| `deadline_tick` | `usize` | Latest settlement tick (past = overdue) |

**Deadline Semantics:**
- `current_tick <= deadline_tick`: Valid (not past deadline)
- `current_tick > deadline_tick`: Past deadline (overdue)

### Priority Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `priority` | `u8` | 5 | Internal priority (0-10, capped) for Queue 1 ordering |
| `original_priority` | `u8` | 5 | Priority before escalation (preserved for reference) |
| `rtgs_priority` | `Option<RtgsPriority>` | None | Queue 2 priority (set when submitted to RTGS) |
| `rtgs_submission_tick` | `Option<usize>` | None | Tick when entered Queue 2 (for FIFO ordering) |
| `declared_rtgs_priority` | `Option<RtgsPriority>` | None | Bank's preferred RTGS priority |

### Status Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | `TransactionStatus` | Pending | Current lifecycle state |
| `parent_id` | `Option<String>` | None | Parent ID for split transactions |

---

## Enums

### TransactionStatus

| Variant | Description |
|---------|-------------|
| `Pending` | Waiting to be settled |
| `PartiallySettled { first_settlement_tick }` | Partially settled (split transactions only) |
| `Settled { tick }` | Fully settled |
| `Overdue { missed_deadline_tick }` | Past deadline but still settleable |

**State Transitions:**

```
Pending → Settled (full settlement)
Pending → PartiallySettled (partial settlement)
Pending → Overdue (deadline missed)

PartiallySettled → Settled (remaining settled)
PartiallySettled → Overdue (deadline missed)

Overdue → Settled (settled after deadline)
```

### RtgsPriority

| Variant | Value | Description |
|---------|-------|-------------|
| `HighlyUrgent` | 0 | Central bank/CLS only |
| `Urgent` | 1 | Time-critical, may incur fees |
| `Normal` | 2 | Standard (default) |

**Ordering:** Lower value = higher priority. Within same priority: FIFO by submission tick.

### TransactionError

| Variant | Description |
|---------|-------------|
| `IndivisibleTransaction` | Cannot split this transaction |
| `AmountExceedsRemaining { amount, remaining }` | Settlement exceeds remaining |
| `AlreadySettled` | Transaction already settled |
| `TransactionDropped` | Transaction was dropped |
| `InvalidAmount` | Invalid amount value |

---

## Key Methods

### Constructors

| Method | Description |
|--------|-------------|
| `Transaction::new(sender_id, receiver_id, amount, arrival_tick, deadline_tick)` | Create new transaction |
| `Transaction::new_split(..., parent_id)` | Create child from split parent |
| `.with_priority(priority)` | Builder: set priority |
| `from_snapshot(...)` | Restore from checkpoint |

**Constructor Constraints:**
- `amount > 0`
- `deadline_tick > arrival_tick`

### Getters

| Method | Returns | Description |
|--------|---------|-------------|
| `id()` | `&str` | Transaction ID |
| `sender_id()` | `&str` | Sender agent ID |
| `receiver_id()` | `&str` | Receiver agent ID |
| `amount()` | `i64` | Original amount |
| `remaining_amount()` | `i64` | Unsettled amount |
| `settled_amount()` | `i64` | `amount - remaining_amount` |
| `arrival_tick()` | `usize` | Arrival tick |
| `deadline_tick()` | `usize` | Deadline tick |
| `priority()` | `u8` | Current priority |
| `original_priority()` | `u8` | Pre-escalation priority |
| `status()` | `&TransactionStatus` | Current status |
| `parent_id()` | `Option<&str>` | Parent ID if split |
| `rtgs_priority()` | `Option<RtgsPriority>` | Queue 2 priority |
| `rtgs_submission_tick()` | `Option<usize>` | Queue 2 entry time |

### Status Queries

| Method | Description |
|--------|-------------|
| `is_pending()` | Status is Pending |
| `is_fully_settled()` | `remaining_amount == 0` |
| `is_past_deadline(tick)` | `tick > deadline_tick` |
| `is_overdue()` | Status is Overdue |
| `overdue_since_tick()` | Tick when became overdue |
| `is_split()` | Has parent_id |

### Mutations

| Method | Description |
|--------|-------------|
| `settle(amount, tick)` | Settle transaction (requires `amount == remaining_amount`) |
| `mark_overdue(tick)` | Mark as overdue (idempotent) |
| `set_priority(priority)` | Update priority (capped at 10) |
| `set_rtgs_priority(priority, tick)` | Set Queue 2 priority and submission tick |
| `clear_rtgs_priority()` | Clear Queue 2 priority when withdrawn |

---

## Transaction Lifecycle

```
1. CREATION (ArrivalGenerator or CustomTransactionArrival)
   └─ Transaction::new() → Status: Pending
      └─ Added to SimulationState.transactions
      └─ Sender.queue_outgoing(tx_id) → In Queue 1

2. QUEUE 1 (Agent Internal Queue)
   └─ Cash manager policy evaluates
   └─ Options:
      ├─ PolicyHold: Remain in Queue 1
      ├─ PolicySubmit: Release to Queue 2
      └─ PolicySplit: Split into children

3. QUEUE 2 (RTGS Central Queue)
   └─ tx.set_rtgs_priority(priority, tick)
   └─ Settlement attempts each tick
   └─ Options:
      ├─ RtgsImmediateSettlement: If liquidity available
      ├─ Queue2LiquidityRelease: Later when liquidity arrives
      ├─ LsmBilateralOffset: Found offsetting payment
      ├─ LsmCycleSettlement: Part of cycle
      └─ Overdue: If current_tick > deadline_tick

4. SETTLEMENT
   └─ tx.settle(amount, tick) → Status: Settled { tick }
   └─ sender.debit(amount)
   └─ receiver.credit(amount)
   └─ Remove from RTGS queue

5. OVERDUE (if deadline missed)
   └─ tx.mark_overdue(tick) → Status: Overdue
   └─ Remains in queue, still settleable
   └─ Escalated costs apply (5x delay multiplier)
   └─ Eventually settles (all obligations must clear)
```

---

## Split Transactions

When a policy splits a large transaction:

1. **Parent** remains in system with original `amount`
2. **Children** created via `new_split()` with `parent_id`
3. As children settle:
   - Parent's `remaining_amount` decreases
   - When all children settle, parent marked settled
4. **Cost tracking**: Split friction cost charged once per split

**Example:**
```
Parent: $10,000 → Split into 4 children

├─ Child 1: $2,500 → Settles tick 10
├─ Child 2: $2,500 → Settles tick 15
├─ Child 3: $2,500 → Settles tick 20
└─ Child 4: $2,500 → Settles tick 25

Parent Timeline:
- Tick 10: remaining = $7,500
- Tick 15: remaining = $5,000
- Tick 20: remaining = $2,500
- Tick 25: remaining = $0, status = Settled
```

---

## Dual Priority System

SimCash implements a TARGET2-style dual priority system:

### Internal Priority (0-10)

| Aspect | Description |
|--------|-------------|
| **Purpose** | Bank's view of payment importance |
| **Where Used** | Queue 1 ordering |
| **Modifiable** | Yes, by policies |
| **Escalation** | Boosted as deadline approaches |

### RTGS Priority (Urgent/Normal)

| Aspect | Description |
|--------|-------------|
| **Purpose** | Declared to central settlement system |
| **Where Used** | Queue 2 ordering |
| **Modifiable** | Only via withdraw/resubmit |
| **Cost** | Urgent may incur higher fees |

### Relationship

```
Queue 1 Processing (internal priority):
- Policies use internal priority (0-10)
- May reprioritize based on conditions
- High internal priority → release early

Queue 2 Processing (RTGS priority):
- System uses RTGS priority (Urgent/Normal)
- Fixed once submitted (unless withdrawn)
- Urgent processed before Normal
```

---

## Related Events

| Event | When Emitted |
|-------|-------------|
| `Arrival` | Transaction created |
| `PolicySubmit` | Released to Queue 2 |
| `RtgsImmediateSettlement` | Immediate settlement |
| `Queue2LiquidityRelease` | Queued tx settles |
| `LsmBilateralOffset` | Bilateral netting |
| `LsmCycleSettlement` | Cycle settlement |
| `TransactionWentOverdue` | Deadline missed |
| `OverdueTransactionSettled` | Overdue tx settles |

---

## See Also

- [Agent Model](agent.md) - Agent runtime model
- [Architecture: Domain Models](../../architecture/05-domain-models.md) - High-level overview
- [Scenario Configuration](../../scenario/index.md) - YAML configuration

---

*Last Updated: 2025-12-12*
