# Domain Models

**Version**: 1.0
**Last Updated**: 2025-11-28

---

## Overview

SimCash's domain model consists of four core entities: **Agent** (banks), **Transaction** (payments), **SimulationState** (container), and **TimeManager** (temporal tracking).

---

## Entity Relationships

```mermaid
erDiagram
    SimulationState ||--o{ Agent : contains
    SimulationState ||--o{ Transaction : contains
    SimulationState ||--|| EventLog : contains
    SimulationState ||--|| AgentQueueIndex : contains

    Agent ||--o{ Transaction : sends
    Agent ||--o{ Transaction : receives
    Agent ||--o{ Transaction : queues_in_Q1

    Transaction ||--o| Transaction : parent_of

    EventLog ||--o{ Event : contains
```

---

## 1. Agent (Bank)

**Source**: `simulator/src/models/agent.rs`

Represents a participating bank with settlement account, queues, and policy state.

### Agent Structure

```mermaid
classDiagram
    class Agent {
        +id: String
        +balance: i64
        +outgoing_queue: Vec~String~
        +incoming_expected: Vec~String~
        +posted_collateral: i64
        +unsecured_cap: i64
        +liquidity_buffer: i64
        +collateral_haircut: f64
        +release_budget_remaining: i64
        +state_registers: HashMap~String, f64~
        +bilateral_limits: HashMap~String, i64~
        +multilateral_limit: Option~i64~
        +new(id, balance) Agent
        +balance() i64
        +debit(amount) Result
        +credit(amount)
        +can_pay(amount) bool
        +available_liquidity() i64
        +queue_outgoing(tx_id)
        +dequeue_outgoing(tx_id)
        +post_collateral(amount, reason, tick)
        +withdraw_collateral(amount, tick)
    }
```

### Field Reference

#### Identity & Core State

| Field | Type | Description |
|-------|------|-------------|
| `id` | `String` | Unique identifier (e.g., "BANK_A") |
| `balance` | `i64` | Central bank balance in cents |

#### Queue Management

| Field | Type | Description |
|-------|------|-------------|
| `outgoing_queue` | `Vec<String>` | Queue 1: Transaction IDs awaiting release |
| `incoming_expected` | `Vec<String>` | Expected incoming transaction IDs |
| `last_decision_tick` | `Option<usize>` | Last policy evaluation tick |

#### Liquidity Management

| Field | Type | Description |
|-------|------|-------------|
| `liquidity_buffer` | `i64` | Target minimum balance |
| `posted_collateral` | `i64` | Secured collateral amount |
| `collateral_haircut` | `f64` | Discount rate (e.g., 0.02 = 2%) |
| `unsecured_cap` | `i64` | Maximum unsecured overdraft |
| `allocated_liquidity` | `i64` | External pool allocation |

#### Budget Control

| Field | Type | Description |
|-------|------|-------------|
| `release_budget_max` | `Option<i64>` | Max release per tick |
| `release_budget_remaining` | `i64` | Remaining budget this tick |
| `release_budget_focus_counterparties` | `Option<Vec<String>>` | Allowed receivers |
| `release_budget_per_counterparty_limit` | `Option<i64>` | Max per counterparty |
| `release_budget_per_counterparty_usage` | `HashMap<String, i64>` | Usage tracking |

#### TARGET2 LSM Limits

| Field | Type | Description |
|-------|------|-------------|
| `bilateral_limits` | `HashMap<String, i64>` | Per-counterparty outflow caps |
| `multilateral_limit` | `Option<i64>` | Total outflow cap |
| `bilateral_outflows` | `HashMap<String, i64>` | Current day outflows |
| `total_outflow` | `i64` | Total outflow this day |

#### Policy State

| Field | Type | Description |
|-------|------|-------------|
| `state_registers` | `HashMap<String, f64>` | Policy memory (max 10 registers) |

### Key Methods

#### Balance Operations

```mermaid
flowchart LR
    subgraph Debit["debit(amount)"]
        CheckBal{"balance >= amount?"}
        CheckBal -->|Yes| SubBal["balance -= amount"]
        CheckBal -->|No| Error["InsufficientBalance"]
    end

    subgraph Credit["credit(amount)"]
        AddBal["balance += amount"]
    end

    subgraph CanPay["can_pay(amount)"]
        Calc["balance + credit_limit >= amount"]
    end
```

#### Liquidity Calculation

```rust
pub fn available_liquidity(&self) -> i64 {
    let credit_headroom = self.credit_limit();
    self.balance + credit_headroom
}

pub fn credit_limit(&self) -> i64 {
    let collateral_credit = (self.posted_collateral as f64 * (1.0 - self.collateral_haircut)) as i64;
    self.unsecured_cap + collateral_credit
}
```

---

## 2. Transaction

**Source**: `simulator/src/models/transaction.rs`

Represents a payment instruction with lifecycle tracking.

### Transaction Structure

```mermaid
classDiagram
    class Transaction {
        +id: String
        +sender_id: String
        +receiver_id: String
        +amount: i64
        +remaining_amount: i64
        +arrival_tick: usize
        +deadline_tick: usize
        +priority: u8
        +original_priority: u8
        +rtgs_priority: Option~RtgsPriority~
        +status: TransactionStatus
        +parent_id: Option~String~
        +divisible: bool
        +new(...) Transaction
        +is_fully_settled() bool
        +is_overdue() bool
        +remaining_amount() i64
        +settle(amount, tick)
        +mark_overdue(tick)
    }

    class RtgsPriority {
        <<enumeration>>
        HighlyUrgent
        Urgent
        Normal
    }

    class TransactionStatus {
        <<enumeration>>
        Pending
        PartiallySettled
        Settled
        Overdue
    }

    Transaction --> RtgsPriority
    Transaction --> TransactionStatus
```

### Field Reference

#### Identification

| Field | Type | Description |
|-------|------|-------------|
| `id` | `String` | Unique identifier (UUID) |
| `sender_id` | `String` | Sending agent ID |
| `receiver_id` | `String` | Receiving agent ID |
| `parent_id` | `Option<String>` | Parent transaction (if split) |

#### Amount Tracking

| Field | Type | Description |
|-------|------|-------------|
| `amount` | `i64` | Original amount (cents) |
| `remaining_amount` | `i64` | Unsettled amount (cents) |

#### Temporal Properties

| Field | Type | Description |
|-------|------|-------------|
| `arrival_tick` | `usize` | System entry time |
| `deadline_tick` | `usize` | Settlement deadline |
| `rtgs_submission_tick` | `Option<usize>` | Queue 2 entry time |

#### Priority System (Dual)

| Field | Type | Description |
|-------|------|-------------|
| `priority` | `u8` | Internal priority (0-10) |
| `original_priority` | `u8` | Priority before escalation |
| `rtgs_priority` | `Option<RtgsPriority>` | Declared RTGS priority |
| `declared_rtgs_priority` | `Option<RtgsPriority>` | Intended RTGS priority |

### Transaction Status State Machine

```mermaid
stateDiagram-v2
    [*] --> Pending: Created

    Pending --> PartiallySettled: partial settle()
    Pending --> Settled: full settle()
    Pending --> Overdue: mark_overdue()

    PartiallySettled --> Settled: remaining settled
    PartiallySettled --> Overdue: deadline passed

    Overdue --> Settled: late settlement

    Settled --> [*]

    note right of Pending
        In Queue 1 or Queue 2
        Delay costs accrue (Q1 only)
    end note

    note right of Overdue
        Deadline passed
        Multiplied delay costs
        One-time penalty applied
    end note
```

### Priority Bands (TARGET2 Style)

```mermaid
flowchart TB
    subgraph Internal["Internal Priority (0-10)"]
        IP0["0-3: Low"]
        IP4["4-7: Normal"]
        IP8["8-10: Urgent"]
    end

    subgraph RTGS["RTGS Priority Bands"]
        Highly["HighlyUrgent<br/>(Central bank only)"]
        Urgent["Urgent<br/>(Time-critical)"]
        Normal["Normal<br/>(Standard)"]
    end

    IP8 -->|"Maps to"| Urgent
    IP4 -->|"Maps to"| Normal
    IP0 -->|"Maps to"| Normal
```

---

## 3. SimulationState

**Source**: `simulator/src/models/state.rs`

Container holding all simulation state.

### State Structure

```mermaid
classDiagram
    class SimulationState {
        -agents: BTreeMap~String, Agent~
        -transactions: BTreeMap~String, Transaction~
        -rtgs_queue: Vec~String~
        -event_log: EventLog
        -collateral_events: Vec~CollateralEvent~
        -lsm_cycle_events: Vec~LsmCycleEvent~
        -queue2_index: AgentQueueIndex
        +new(agents) SimulationState
        +get_agent(id) Option~&Agent~
        +get_agent_mut(id) Option~&mut Agent~
        +get_transaction(id) Option~&Transaction~
        +get_transaction_mut(id) Option~&mut Transaction~
        +add_transaction(tx)
        +num_agents() usize
        +queue_size() usize
        +enqueue_rtgs(tx_id)
        +dequeue_rtgs(tx_id)
        +rtgs_queue() &Vec~String~
        +get_event_log() &EventLog
        +add_event(event)
    }

    class AgentQueueIndex {
        -by_agent: HashMap~String, Vec~String~~
        -cached_metrics: HashMap~String, AgentQueue2Metrics~
        +rebuild(state)
        +get_agent_txs(agent_id) Vec~String~
        +get_metrics(agent_id) AgentQueue2Metrics
    }

    SimulationState --> AgentQueueIndex
```

### Queue 2 Index

The `AgentQueueIndex` provides O(1) lookup of Queue 2 transactions by agent:

```mermaid
flowchart TB
    subgraph Q2["Queue 2 (rtgs_queue)"]
        tx1["tx-001"]
        tx2["tx-002"]
        tx3["tx-003"]
        tx4["tx-004"]
    end

    subgraph Index["AgentQueueIndex"]
        A["BANK_A → [tx-001, tx-003]"]
        B["BANK_B → [tx-002, tx-004]"]
    end

    subgraph Metrics["Cached Metrics"]
        MA["BANK_A: count=2, value=$2000"]
        MB["BANK_B: count=2, value=$1500"]
    end

    Q2 --> Index
    Index --> Metrics
```

---

## 4. TimeManager

**Source**: `simulator/src/core/time.rs`

Manages simulation time progression.

### Time Structure

```mermaid
classDiagram
    class TimeManager {
        -current_tick: usize
        -ticks_per_day: usize
        +new(ticks_per_day) TimeManager
        +advance_tick()
        +current_tick() usize
        +current_day() usize
        +tick_within_day() usize
        +is_last_tick_of_day() bool
        +ticks_until_eod() usize
    }
```

### Time Calculations

```mermaid
flowchart LR
    subgraph Time["TimeManager State"]
        CT["current_tick = 250"]
        TPD["ticks_per_day = 100"]
    end

    subgraph Derived["Derived Values"]
        Day["current_day() = 2"]
        Within["tick_within_day() = 50"]
        ToEOD["ticks_until_eod() = 50"]
        IsLast["is_last_tick_of_day() = false"]
    end

    CT --> Day
    CT --> Within
    TPD --> Day
    TPD --> Within
    TPD --> ToEOD
    TPD --> IsLast
```

```rust
pub fn current_day(&self) -> usize {
    self.current_tick / self.ticks_per_day
}

pub fn tick_within_day(&self) -> usize {
    self.current_tick % self.ticks_per_day
}

pub fn is_last_tick_of_day(&self) -> bool {
    self.tick_within_day() == self.ticks_per_day - 1
}

pub fn ticks_until_eod(&self) -> usize {
    self.ticks_per_day - self.tick_within_day() - 1
}
```

---

## 5. Supporting Types

### CollateralEvent

**Source**: `simulator/src/models/collateral_event.rs`

```mermaid
classDiagram
    class CollateralEvent {
        +agent_id: String
        +tick: usize
        +day: usize
        +action: CollateralAction
        +amount: i64
        +reason: String
        +layer: CollateralLayer
        +balance_before: i64
        +posted_collateral_before: i64
        +posted_collateral_after: i64
        +available_capacity_after: i64
    }

    class CollateralAction {
        <<enumeration>>
        Post
        Withdraw
        Hold
    }

    class CollateralLayer {
        <<enumeration>>
        Strategic
        EndOfTick
    }

    CollateralEvent --> CollateralAction
    CollateralEvent --> CollateralLayer
```

### EventLog

**Source**: `simulator/src/models/event.rs`

```mermaid
classDiagram
    class EventLog {
        -events: Vec~Event~
        +new() EventLog
        +add_event(event)
        +get_events_at_tick(tick) Vec~&Event~
        +all_events() &Vec~Event~
        +len() usize
    }
```

---

## Data Flow

### Transaction Lifecycle

```mermaid
flowchart TB
    subgraph Arrival["1. Arrival"]
        Gen["ArrivalGenerator"] --> Create["Create Transaction"]
        Create --> Q1["Add to Queue 1"]
    end

    subgraph Policy["2. Policy Decision"]
        Q1 --> Eval["Policy Evaluation"]
        Eval --> Decision{"Decision?"}
        Decision -->|Submit| Submit["Release to RTGS"]
        Decision -->|Hold| Hold["Stay in Queue 1"]
        Decision -->|Split| Split["Create Children"]
    end

    subgraph Settlement["3. Settlement"]
        Submit --> Q2["Queue 2 (RTGS)"]
        Q2 --> Settle{"Liquidity?"}
        Settle -->|Yes| Immediate["RTGS Immediate"]
        Settle -->|No| Wait["Wait in Queue"]
        Wait --> LSM["LSM Optimization"]
        LSM --> Settled["Settled"]
        Immediate --> Settled
    end

    Split --> Q1
```

### Agent State Transitions

```mermaid
flowchart TB
    subgraph BOD["Beginning of Day"]
        Init["Initialize budgets"]
        Reset["Reset daily counters"]
    end

    subgraph Tick["Each Tick"]
        Receive["Receive inflows"]
        Eval["Evaluate policy"]
        Release["Release payments"]
        Costs["Accrue costs"]
    end

    subgraph EOD["End of Day"]
        Final["Final settlements"]
        Penalty["EOD penalties"]
        Metrics["Record metrics"]
    end

    BOD --> Tick
    Tick --> Tick
    Tick --> EOD
```

---

## Invariants

### Balance Conservation

```
∀ settlement:
    sender.balance_before - amount == sender.balance_after
    receiver.balance_before + amount == receiver.balance_after
```

### Queue Validity

```
∀ tx_id ∈ agent.outgoing_queue:
    transactions.contains(tx_id) == true
    transactions[tx_id].sender_id == agent.id

∀ tx_id ∈ state.rtgs_queue:
    transactions.contains(tx_id) == true
    transactions[tx_id].status == Pending
```

### Transaction Amount

```
∀ tx:
    tx.remaining_amount <= tx.amount
    tx.remaining_amount >= 0
    tx.is_fully_settled() == (tx.remaining_amount == 0)
```

### Priority Bounds

```
∀ tx:
    0 <= tx.priority <= 10
    0 <= tx.original_priority <= 10
```

---

## Memory Layout

### Estimated Sizes

| Type | Size (approx.) | Notes |
|------|----------------|-------|
| `Agent` | ~500 bytes | Varies with queue sizes |
| `Transaction` | ~200 bytes | Fixed size |
| `Event` | ~100-500 bytes | Varies by type |
| `SimulationState` | N × Agent + M × Transaction | Linear scaling |

### Efficient Access

```mermaid
flowchart TB
    subgraph Maps["BTreeMap (Sorted)"]
        Agents["agents: BTreeMap<String, Agent>"]
        Txs["transactions: BTreeMap<String, Transaction>"]
    end

    subgraph Index["HashMap (O(1) Lookup)"]
        Q2Idx["queue2_index: HashMap<String, Vec<String>>"]
    end

    subgraph Vec["Vector (Sequential)"]
        Q2["rtgs_queue: Vec<String>"]
        Events["event_log: Vec<Event>"]
    end

    Note["BTreeMap: O(log n) lookup, sorted iteration<br/>HashMap: O(1) lookup, random order<br/>Vec: O(1) index, O(n) search"]
```

---

## Related Documents

- [02-rust-core-engine.md](./02-rust-core-engine.md) - Implementation details
- [06-settlement-engines.md](./06-settlement-engines.md) - Settlement logic
- [08-event-system.md](./08-event-system.md) - Event types

---

*Next: [06-settlement-engines.md](./06-settlement-engines.md) - Settlement algorithms*
