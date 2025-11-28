# Transaction Model

**Location:** `backend/src/models/transaction.rs`

Represents a payment between two agents with complete lifecycle tracking, dual priority system, and split transaction support.

---

## Overview

A Transaction represents a payment order from one agent (sender) to another (receiver). Each transaction tracks:
- Original and remaining amounts (i64 cents)
- Arrival and deadline timing
- Internal priority (0-10) for bank decisions
- RTGS priority (Urgent/Normal) for settlement queue
- Status lifecycle (Pending → Settled or Overdue)
- Parent/child relationships for split transactions

---

## Struct Definition

**Location:** `transaction.rs:162-239`

```rust
pub struct Transaction {
    id: String,                              // UUID identifier
    sender_id: String,                       // Sending agent
    receiver_id: String,                     // Receiving agent
    amount: i64,                             // Original amount (immutable)
    remaining_amount: i64,                   // Unsettled portion
    arrival_tick: usize,                     // When entered system
    deadline_tick: usize,                    // Latest settlement time
    priority: u8,                            // Internal priority (0-10)
    original_priority: u8,                   // Pre-escalation priority
    status: TransactionStatus,               // Current lifecycle state
    parent_id: Option<String>,               // For split transactions
    rtgs_priority: Option<RtgsPriority>,     // Queue 2 priority (when submitted)
    rtgs_submission_tick: Option<usize>,     // Queue 2 entry time
    declared_rtgs_priority: Option<RtgsPriority>, // Bank's declared preference
}
```

---

## Fields

### `id`

**Type:** `String`
**Location:** `transaction.rs:165`

Unique transaction identifier (UUID v4).

**Generation:**
```rust
id: uuid::Uuid::new_v4().to_string()
```

**Example:** `"550e8400-e29b-41d4-a716-446655440000"`

---

### `sender_id`

**Type:** `String`
**Location:** `transaction.rs:168`

Agent ID of the payment sender.

**Constraints:**
- Must reference existing agent in simulation
- Sender's balance will be debited on settlement

---

### `receiver_id`

**Type:** `String`
**Location:** `transaction.rs:171`

Agent ID of the payment receiver.

**Constraints:**
- Must reference existing agent in simulation
- Cannot equal `sender_id` (no self-payments)
- Receiver's balance will be credited on settlement

---

### `amount`

**Type:** `i64` (cents)
**Location:** `transaction.rs:174`

Original transaction amount (immutable).

**CRITICAL:** Always integer cents, never float.

**Constraints:**
- Must be positive (`amount > 0`)
- Set at construction, never changes

**Example:**
- `100000` = $1,000.00
- `5000000` = $50,000.00

---

### `remaining_amount`

**Type:** `i64` (cents)
**Location:** `transaction.rs:177`

Amount still to be settled.

**Initial Value:** Same as `amount`

**Updates:**
- Decreases when transaction settles
- Reaches 0 when fully settled
- For split transactions: parent's remaining decreases as children settle

**Invariant:** `0 <= remaining_amount <= amount`

---

### `arrival_tick`

**Type:** `usize`
**Location:** `transaction.rs:180`

Tick when transaction entered the system.

**Usage:**
- Used for delay cost calculations
- Used for settlement timing metrics
- Deadline is always after arrival

---

### `deadline_tick`

**Type:** `usize`
**Location:** `transaction.rs:183`

Tick by which transaction must settle.

**Constraints:**
- `deadline_tick > arrival_tick`
- Capped at episode end tick (Issue #6 fix)

**Boundary Semantics:**
- `current_tick <= deadline_tick`: Valid (not past deadline)
- `current_tick > deadline_tick`: Past deadline (overdue)

---

### `priority`

**Type:** `u8` (0-10)
**Location:** `transaction.rs:187`
**Default:** `5`

Internal bank priority for Queue 1 ordering.

**Range:** 0 (lowest) to 10 (highest)

**Usage:**
- Used by cash manager policies
- Can be modified by policies during Queue 1 processing
- Escalation may boost priority as deadline approaches

**Capped:** Values > 10 are capped to 10

---

### `original_priority`

**Type:** `u8` (0-10)
**Location:** `transaction.rs:191`

Priority before any escalation or modification.

**Usage:**
- Preserved for reference
- Escalation boost calculated from this value
- Set equal to `priority` at construction

---

### `status`

**Type:** `TransactionStatus`
**Location:** `transaction.rs:194`
**Default:** `Pending`

Current lifecycle state.

See [TransactionStatus](#transactionstatus-enum) for details.

---

### `parent_id`

**Type:** `Option<String>`
**Location:** `transaction.rs:205`
**Default:** `None`

Parent transaction ID for split transactions.

**Values:**
- `None`: Regular (non-split) transaction
- `Some(id)`: Child of split transaction with given parent ID

**Related:**
- See [Split Transactions](#split-transactions)
- Created by `new_split()` constructor

---

### `rtgs_priority`

**Type:** `Option<RtgsPriority>`
**Location:** `transaction.rs:218`
**Default:** `None`

RTGS priority assigned when submitted to Queue 2.

**Values:**
- `None`: Not yet submitted to RTGS
- `Some(priority)`: Submitted with this priority

**Set By:** `set_rtgs_priority()` when entering Queue 2
**Cleared By:** `clear_rtgs_priority()` when withdrawn from Queue 2

---

### `rtgs_submission_tick`

**Type:** `Option<usize>`
**Location:** `transaction.rs:228`
**Default:** `None`

Tick when transaction was submitted to Queue 2.

**Usage:**
- Used for FIFO ordering within same RTGS priority band
- Earlier submission tick = processed first

---

### `declared_rtgs_priority`

**Type:** `Option<RtgsPriority>`
**Location:** `transaction.rs:238`
**Default:** `None`

Bank's preferred RTGS priority for when transaction is submitted.

**Values:**
- `None`: Use default Normal priority
- `Some(priority)`: Use this priority when entering Queue 2

**Set By:** `submit_transaction_with_rtgs_priority()` on Orchestrator

---

## Enums

### `TransactionStatus`

**Location:** `transaction.rs:102-127`

```rust
pub enum TransactionStatus {
    /// Waiting to be settled
    Pending,

    /// Partially settled (split transactions only)
    PartiallySettled {
        first_settlement_tick: usize,
    },

    /// Fully settled
    Settled {
        tick: usize,
    },

    /// Past deadline but still settleable
    Overdue {
        missed_deadline_tick: usize,
    },
}
```

**State Transitions:**
```
Pending → Settled (full settlement)
Pending → PartiallySettled (partial settlement)
Pending → Overdue (deadline missed)

PartiallySettled → Settled (remaining settled)
PartiallySettled → Overdue (deadline missed)

Overdue → Settled (settled after deadline)
```

---

### `RtgsPriority`

**Location:** `transaction.rs:53-64`

```rust
pub enum RtgsPriority {
    HighlyUrgent = 0,  // Central bank/CLS only
    Urgent = 1,        // Time-critical, may incur fees
    Normal = 2,        // Standard (default)
}
```

**Ordering:**
- Lower numeric value = higher priority
- `HighlyUrgent < Urgent < Normal`

**Usage:**
- Determines processing order in Queue 2
- Within same priority: FIFO by submission tick

---

### `TransactionError`

**Location:** `transaction.rs:130-146`

```rust
pub enum TransactionError {
    IndivisibleTransaction,
    AmountExceedsRemaining { amount: i64, remaining: i64 },
    AlreadySettled,
    TransactionDropped,
    InvalidAmount,
}
```

---

## Constructors

### `Transaction::new()`

**Location:** `transaction.rs:266-295`

Create a new transaction.

```rust
pub fn new(
    sender_id: String,
    receiver_id: String,
    amount: i64,
    arrival_tick: usize,
    deadline_tick: usize,
) -> Self
```

**Panics:**
- If `amount <= 0`
- If `deadline_tick <= arrival_tick`

**Defaults:**
- `id`: UUID v4
- `priority`: 5
- `status`: Pending
- `parent_id`: None
- `rtgs_priority`: None

**Example:**
```rust
let tx = Transaction::new(
    "BANK_A".to_string(),
    "BANK_B".to_string(),
    100000,  // $1,000.00
    10,      // arrival tick
    50,      // deadline tick
);
```

---

### `Transaction::new_split()`

**Location:** `transaction.rs:339-369`

Create a child transaction from a split parent.

```rust
pub fn new_split(
    sender_id: String,
    receiver_id: String,
    amount: i64,
    arrival_tick: usize,
    deadline_tick: usize,
    parent_id: String,
) -> Self
```

**Same constraints as `new()`, plus:**
- `parent_id` links to parent transaction

**Example:**
```rust
// Split parent into two children
let child1 = Transaction::new_split(
    parent.sender_id().to_string(),
    parent.receiver_id().to_string(),
    50000,  // Half of parent
    parent.arrival_tick(),
    parent.deadline_tick(),
    parent.id().to_string(),
);
```

---

### `with_priority()` Builder

**Location:** `transaction.rs:489-494`

Set priority using builder pattern.

```rust
let tx = Transaction::new(...)
    .with_priority(8);  // High priority
```

---

### `from_snapshot()` / `from_snapshot_with_rtgs()`

**Location:** `transaction.rs:406-473`

Restore transaction from checkpoint with all fields preserved.

---

## Key Methods

### Getters

| Method | Return Type | Description |
|--------|-------------|-------------|
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
| `declared_rtgs_priority()` | `Option<RtgsPriority>` | Bank's preference |

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

#### `settle(amount, tick)`

**Location:** `transaction.rs:724-751`

Settle transaction (full settlement only).

```rust
pub fn settle(&mut self, amount: i64, tick: usize) -> Result<(), TransactionError>
```

**Requirements:**
- `amount > 0`
- `amount == remaining_amount` (must settle full remaining)
- Not already settled

**Effects:**
- `remaining_amount = 0`
- `status = Settled { tick }`

---

#### `mark_overdue(tick)`

**Location:** `transaction.rs:853-867`

Mark transaction as overdue (idempotent).

```rust
pub fn mark_overdue(&mut self, tick: usize) -> Result<(), TransactionError>
```

**Requirements:**
- Not already settled

**Effects:**
- `status = Overdue { missed_deadline_tick: tick }`

**Idempotent:** Calling multiple times preserves original tick.

---

#### `set_priority(priority)`

**Location:** `transaction.rs:896-898`

Update internal priority.

```rust
pub fn set_priority(&mut self, priority: u8)
```

**Effects:**
- `priority = min(priority, 10)` (capped)

---

#### `set_rtgs_priority(priority, tick)`

**Location:** `transaction.rs:629-632`

Set RTGS priority when entering Queue 2.

```rust
pub fn set_rtgs_priority(&mut self, priority: RtgsPriority, tick: usize)
```

**Effects:**
- `rtgs_priority = Some(priority)`
- `rtgs_submission_tick = Some(tick)`

---

#### `clear_rtgs_priority()`

**Location:** `transaction.rs:638-641`

Clear RTGS priority when withdrawn from Queue 2.

```rust
pub fn clear_rtgs_priority(&mut self)
```

**Effects:**
- `rtgs_priority = None`
- `rtgs_submission_tick = None`

---

## Transaction Lifecycle

```
┌─────────────────────────────────────────────────────────────────┐
│                    Transaction Lifecycle                        │
└─────────────────────────────────────────────────────────────────┘

1. CREATION (ArrivalGenerator or CustomTransactionArrival)
   └─ Transaction::new() → Status: Pending
      └─ Added to SimulationState.transactions
      └─ Sender.queue_outgoing(tx_id) → In Queue 1

2. QUEUE 1 (Agent Internal Queue)
   └─ Cash manager policy evaluates
   └─ Options:
      ├─ PolicyHold: Remain in Queue 1
      ├─ PolicySubmit: Release to Queue 2
      ├─ PolicySplit: Split into children
      └─ PolicyDrop: (deprecated - cannot drop)

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
   └─ tx.mark_overdue(tick) → Status: Overdue { missed_deadline_tick }
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

- **Purpose:** Bank's view of payment importance
- **Where Used:** Queue 1 ordering
- **Modifiable:** Yes, by policies
- **Escalation:** Boosted as deadline approaches

### RTGS Priority (Urgent/Normal)

- **Purpose:** Declared to central settlement system
- **Where Used:** Queue 2 ordering
- **Modifiable:** Only via withdraw/resubmit
- **Cost:** Urgent may incur higher fees

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

## Related Types

- [Agent](agent.md) - Agent model
- [SimulationState](simulation-state.md) - State management
- [ArrivalGenerator](../03-generators/arrival-generator.md) - Transaction generation
- [Settlement Engine](../05-settlement/rtgs-engine.md) - Settlement processing

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

*Last Updated: 2025-11-28*
