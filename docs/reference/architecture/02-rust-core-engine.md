# Rust Core Engine

**Version**: 1.0
**Last Updated**: 2025-11-28

---

## Overview

The Rust core engine is the performance-critical heart of SimCash, implementing the simulation tick loop, settlement algorithms, and policy evaluation. It comprises **19,445 lines of code** across **31 files** organized into **8 core modules**.

---

## Module Architecture

```mermaid
flowchart TB
    subgraph lib["lib.rs (Entry Point)"]
        PyModule["PyO3 Module<br/>Exports"]
    end

    subgraph core["core/"]
        TimeManager["TimeManager<br/>time.rs"]
    end

    subgraph models["models/"]
        Agent["Agent<br/>agent.rs"]
        Transaction["Transaction<br/>transaction.rs"]
        State["SimulationState<br/>state.rs"]
        Event["Event<br/>event.rs"]
        Collateral["CollateralEvent<br/>collateral_event.rs"]
        QueueIndex["AgentQueueIndex<br/>queue_index.rs"]
    end

    subgraph orchestrator["orchestrator/"]
        Engine["Orchestrator<br/>engine.rs"]
        Checkpoint["Checkpoint<br/>checkpoint.rs"]
    end

    subgraph settlement["settlement/"]
        RTGS["RTGS<br/>rtgs.rs"]
        LSM["LSM<br/>lsm.rs"]
        Graph["Graph<br/>lsm/graph.rs"]
        PairIndex["PairIndex<br/>lsm/pair_index.rs"]
    end

    subgraph rng["rng/"]
        RngManager["RngManager<br/>xorshift.rs"]
    end

    subgraph policy["policy/"]
        PolicyTrait["CashManagerPolicy"]
        subgraph tree["tree/"]
            TreeTypes["types.rs"]
            TreeContext["context.rs"]
            TreeInterp["interpreter.rs"]
            TreeExec["executor.rs"]
            TreeFactory["factory.rs"]
            TreeValid["validation.rs"]
        end
    end

    subgraph arrivals["arrivals/"]
        ArrivalGen["ArrivalGenerator<br/>mod.rs"]
    end

    subgraph events["events/"]
        ScenarioEvent["ScenarioEvent<br/>types.rs"]
        EventHandler["EventHandler<br/>handler.rs"]
    end

    subgraph ffi["ffi/"]
        PyOrch["PyOrchestrator<br/>orchestrator.rs"]
        FFITypes["Type Conversions<br/>types.rs"]
    end

    PyModule --> PyOrch
    PyOrch --> Engine
    Engine --> State
    Engine --> TimeManager
    Engine --> RngManager
    Engine --> PolicyTrait
    Engine --> RTGS
    Engine --> LSM
    Engine --> ArrivalGen
    Engine --> EventHandler
    State --> Agent
    State --> Transaction
    State --> Event
    LSM --> Graph
    LSM --> PairIndex
    PolicyTrait --> tree

    style lib fill:#fff3e0
    style models fill:#e3f2fd
    style orchestrator fill:#fce4ec
    style settlement fill:#e8f5e9
    style policy fill:#f3e5f5
```

---

## Module Dependency Graph

```mermaid
flowchart LR
    lib --> ffi
    lib --> orchestrator
    lib --> models
    lib --> rng
    lib --> core
    lib --> arrivals

    ffi --> orchestrator
    ffi --> models

    orchestrator --> settlement
    orchestrator --> policy
    orchestrator --> arrivals
    orchestrator --> events
    orchestrator --> models
    orchestrator --> rng
    orchestrator --> core

    settlement --> models

    policy --> models
    policy --> orchestrator

    arrivals --> models
    arrivals --> rng

    events --> models

    style lib fill:#fff3e0
    style ffi fill:#ffcdd2
    style orchestrator fill:#fce4ec
    style models fill:#e3f2fd
    style settlement fill:#e8f5e9
    style policy fill:#f3e5f5
    style rng fill:#fff9c4
    style arrivals fill:#b2dfdb
    style events fill:#d1c4e9
```

---

## 1. Core Module (`core/`)

### Purpose
Time management and initialization utilities.

### Files

| File | Lines | Purpose |
|------|-------|---------|
| `mod.rs` | ~20 | Module re-exports |
| `time.rs` | ~100 | TimeManager struct |

### TimeManager

**Source**: `simulator/src/core/time.rs`

```rust
pub struct TimeManager {
    current_tick: usize,     // Total ticks elapsed
    ticks_per_day: usize,    // Ticks per business day
}
```

```mermaid
classDiagram
    class TimeManager {
        -current_tick: usize
        -ticks_per_day: usize
        +new(ticks_per_day) TimeManager
        +from_state(ticks_per_day, num_days, current_tick, current_day) TimeManager
        +advance_tick()
        +current_tick() usize
        +current_day() usize
        +tick_within_day() usize
        +is_last_tick_of_day() bool
        +ticks_until_eod() usize
    }
```

**Key Methods**:

| Method | Returns | Description |
|--------|---------|-------------|
| `advance_tick()` | `()` | Increment current tick |
| `current_tick()` | `usize` | Total ticks since start |
| `current_day()` | `usize` | Current business day (0-indexed) |
| `tick_within_day()` | `usize` | Tick within current day |
| `is_last_tick_of_day()` | `bool` | True if at day boundary |
| `ticks_until_eod()` | `usize` | Ticks remaining in day |

---

## 2. Models Module (`models/`)

### Purpose
Core domain types: Agent, Transaction, SimulationState, Events.

### Files

| File | Lines | Purpose |
|------|-------|---------|
| `mod.rs` | ~50 | Module re-exports |
| `agent.rs` | ~500 | Agent (bank) struct |
| `transaction.rs` | ~400 | Transaction struct |
| `state.rs` | ~300 | SimulationState container |
| `event.rs` | ~800 | Event enum (50+ variants) |
| `collateral_event.rs` | ~100 | CollateralEvent struct |
| `queue_index.rs` | ~150 | O(1) queue lookup |

### Class Relationships

```mermaid
classDiagram
    class SimulationState {
        -agents: BTreeMap~String, Agent~
        -transactions: BTreeMap~String, Transaction~
        -rtgs_queue: Vec~String~
        -event_log: EventLog
        -queue2_index: AgentQueueIndex
        +get_agent(id) Agent
        +get_transaction(id) Transaction
        +add_transaction(tx)
        +enqueue_rtgs(tx_id)
        +dequeue_rtgs(tx_id)
    }

    class Agent {
        -id: String
        -balance: i64
        -outgoing_queue: Vec~String~
        -posted_collateral: i64
        -release_budget_remaining: i64
        -state_registers: HashMap
        +balance() i64
        +debit(amount)
        +credit(amount)
        +can_pay(amount) bool
        +available_liquidity() i64
    }

    class Transaction {
        -id: String
        -sender_id: String
        -receiver_id: String
        -amount: i64
        -remaining_amount: i64
        -status: TransactionStatus
        -priority: u8
        -rtgs_priority: RtgsPriority
        +is_fully_settled() bool
        +settle(amount, tick)
        +mark_overdue(tick)
    }

    class EventLog {
        -events: Vec~Event~
        +add_event(event)
        +get_events_at_tick(tick) Vec~Event~
        +all_events() Vec~Event~
    }

    SimulationState "1" --> "*" Agent : contains
    SimulationState "1" --> "*" Transaction : contains
    SimulationState "1" --> "1" EventLog : contains
    Agent "1" --> "*" Transaction : sends
    Agent "1" --> "*" Transaction : receives
```

### Agent Fields (Key Subset)

**Source**: `simulator/src/models/agent.rs`

| Field | Type | Purpose |
|-------|------|---------|
| `id` | `String` | Unique identifier (e.g., "BANK_A") |
| `balance` | `i64` | Central bank balance (cents) |
| `outgoing_queue` | `Vec<String>` | Queue 1 (internal) |
| `posted_collateral` | `i64` | Secured collateral |
| `unsecured_cap` | `i64` | Overdraft limit |
| `release_budget_remaining` | `i64` | Budget this tick |
| `bilateral_limits` | `HashMap<String, i64>` | T2 LSM limits |
| `state_registers` | `HashMap<String, f64>` | Policy memory |

### Transaction Status

```mermaid
stateDiagram-v2
    [*] --> Pending: Created
    Pending --> PartiallySettled: Partial settle
    Pending --> Settled: Full settle
    Pending --> Overdue: Deadline passed
    PartiallySettled --> Settled: Remaining settled
    Overdue --> Settled: Late settlement

    note right of Pending: In Queue 1 or Queue 2
    note right of Overdue: Delay multiplier applied
```

---

## 3. Orchestrator Module (`orchestrator/`)

### Purpose
Main simulation loop and state coordination.

### Files

| File | Lines | Purpose |
|------|-------|---------|
| `mod.rs` | ~50 | Module re-exports |
| `engine.rs` | ~2000 | Orchestrator struct, tick loop |
| `checkpoint.rs` | ~200 | State serialization |

### Orchestrator Structure

**Source**: `simulator/src/orchestrator/engine.rs`

```mermaid
classDiagram
    class Orchestrator {
        -state: SimulationState
        -rng: RngManager
        -time: TimeManager
        -policies: HashMap~String, Policy~
        -arrival_generators: HashMap~String, ArrivalGenerator~
        -scenario_handler: ScenarioEventHandler
        -config: OrchestratorConfig
        -daily_metrics: DailyMetrics
        +new(config) Orchestrator
        +tick() TickResult
        +current_tick() usize
        +current_day() usize
        +get_agent_balance(id) i64
        +get_tick_events(tick) Vec~Event~
        +checkpoint(path)
        +restore(path) Orchestrator
    }

    class OrchestratorConfig {
        +ticks_per_day: usize
        +num_days: usize
        +rng_seed: u64
        +agent_configs: Vec~AgentConfig~
        +cost_rates: CostRates
        +lsm_config: LsmConfig
        +queue1_ordering: Queue1Ordering
        +priority_mode: bool
    }

    class TickResult {
        +tick: usize
        +day: usize
        +num_arrivals: usize
        +num_settlements: usize
        +queue2_size: usize
        +total_costs: i64
        +events: Vec~Event~
    }

    Orchestrator --> OrchestratorConfig
    Orchestrator --> TickResult
```

### Tick Loop

See [11-tick-loop-anatomy.md](./11-tick-loop-anatomy.md) for detailed breakdown.

```mermaid
flowchart TB
    Start(["tick called"]) --> AdvanceTime["1. Advance Time"]
    AdvanceTime --> CheckEOD{"2. Check EOD?"}
    CheckEOD -->|Yes| ProcessEOD["Process EOD"]
    CheckEOD -->|No| Arrivals
    ProcessEOD --> ResetDay["Reset daily state"]
    ResetDay --> Arrivals

    Arrivals["3. Generate Arrivals"] --> EDO["4. Entry Disposition<br/>Offsetting"]
    EDO --> PolicyLoop["5. For Each Agent"]

    subgraph PolicyEval["Policy Evaluation"]
        PolicyLoop --> EvalPolicy["Evaluate Policy"]
        EvalPolicy --> ExecuteDecisions["Execute Decisions<br/>Submit/Hold/Split"]
    end

    ExecuteDecisions --> RTGS["6. RTGS Processing"]
    RTGS --> LSMOpt["7. LSM Optimization"]
    LSMOpt --> Costs["8. Cost Accrual"]
    Costs --> Cleanup["9. Drop Expired"]
    Cleanup --> Events["10. Log Events"]
    Events --> Return(["Return TickResult"])
```

---

## 4. Settlement Module (`settlement/`)

### Purpose
RTGS settlement and LSM optimization algorithms.

### Files

| File | Lines | Purpose |
|------|-------|---------|
| `mod.rs` | ~100 | Module re-exports |
| `rtgs.rs` | ~400 | RTGS settlement |
| `lsm.rs` | ~600 | LSM algorithms |
| `lsm/graph.rs` | ~300 | Cycle detection graph |
| `lsm/pair_index.rs` | ~200 | Bilateral pair indexing |

### RTGS Settlement Flow

**Source**: `simulator/src/settlement/rtgs.rs`

```mermaid
flowchart TB
    Submit["submit_transaction()"] --> Check{"Transaction<br/>settled?"}
    Check -->|Yes| Error["Error:<br/>AlreadySettled"]
    Check -->|No| Liquidity{"sender.can_pay<br/>(amount)?"}

    Liquidity -->|Yes| Debit["Debit sender"]
    Debit --> Credit["Credit receiver"]
    Credit --> Mark["Mark settled"]
    Mark --> Event["Emit<br/>RtgsImmediateSettlement"]
    Event --> Success([SettledImmediately])

    Liquidity -->|No| Queue["Add to Queue 2"]
    Queue --> QueueEvent["Emit<br/>QueuedRtgs"]
    QueueEvent --> Queued([Queued])
```

### LSM Algorithm Sequence

**Source**: `simulator/src/settlement/lsm.rs`

```mermaid
flowchart LR
    subgraph Algorithm1["Algorithm 1: FIFO"]
        FIFO["Process queue<br/>in order"]
    end

    subgraph Algorithm2["Algorithm 2: Bilateral"]
        Bilateral["Find A↔B pairs<br/>Net offset"]
    end

    subgraph Algorithm3["Algorithm 3: Multilateral"]
        Multi["Detect cycles<br/>A→B→C→A"]
    end

    Queue2["Queue 2"] --> Algorithm1
    Algorithm1 -->|"Unsettled"| Algorithm2
    Algorithm2 -->|"Unsettled"| Algorithm3
    Algorithm3 -->|"Still unsettled"| Remain["Remain in queue"]

    Algorithm1 -->|"Settled"| Done1([Settled])
    Algorithm2 -->|"Settled"| Done2([Settled])
    Algorithm3 -->|"Settled"| Done3([Settled])
```

### Bilateral Offset

```mermaid
flowchart LR
    subgraph Before["Before Offset"]
        A1["Bank A"] -->|"$100"| B1["Bank B"]
        B1 -->|"$80"| A1
    end

    subgraph After["After Offset"]
        A2["Bank A"] -->|"$20 net"| B2["Bank B"]
    end

    Before --> Process["bilateral_offset()"]
    Process --> After

    Note["Settled with $20 liquidity<br/>instead of $180"]
```

### Cycle Detection

```mermaid
flowchart LR
    subgraph Cycle["Detected Cycle"]
        A["Bank A"] -->|"$100"| B["Bank B"]
        B -->|"$120"| C["Bank C"]
        C -->|"$80"| A
    end

    subgraph Settlement["Net Positions"]
        AP["A: +$20"]
        BP["B: -$20"]
        CP["C: $0"]
    end

    Cycle --> Detect["detect_cycles()"]
    Detect --> Settlement
    Settlement --> Settle["settle_cycle()"]
    Settle --> Done["Max outflow: $20<br/>(not $300 gross)"]
```

---

## 5. RNG Module (`rng/`)

### Purpose
Deterministic random number generation for reproducible simulations.

### Files

| File | Lines | Purpose |
|------|-------|---------|
| `mod.rs` | ~20 | Module re-exports |
| `xorshift.rs` | ~200 | RngManager implementation |

### RngManager

**Source**: `simulator/src/rng/xorshift.rs`

```mermaid
classDiagram
    class RngManager {
        -state: u64
        +new(seed: u64) RngManager
        +next() u64
        +range(min: i64, max: i64) i64
        +next_f64() f64
        +poisson(lambda: f64) u32
        +normal(mean: i64, std_dev: i64) i64
        +lognormal(mean: f64, std_dev: f64) i64
        +get_state() u64
    }
```

**Algorithm**: xorshift64*

```rust
fn next(&mut self) -> u64 {
    self.state ^= self.state >> 12;
    self.state ^= self.state << 25;
    self.state ^= self.state >> 27;
    self.state.wrapping_mul(0x2545F4914F6CDD1D)
}
```

**Key Property**: Passes TestU01's BigCrush statistical tests.

**Determinism Guarantee**:
```rust
// CRITICAL: Always persist state after each call
let (value, new_seed) = rng.next();
state.rng_seed = new_seed; // Must update!
```

---

## 6. Policy Module (`policy/`)

### Purpose
Decision tree policies for cash management.

### Files

| File | Lines | Purpose |
|------|-------|---------|
| `mod.rs` | ~100 | Trait definition, re-exports |
| `tree/mod.rs` | ~50 | Tree module entry |
| `tree/types.rs` | ~400 | DecisionTreeDef, TreeNode |
| `tree/context.rs` | ~800 | EvalContext (50+ fields) |
| `tree/interpreter.rs` | ~600 | Expression evaluation |
| `tree/executor.rs` | ~400 | TreePolicy execution |
| `tree/factory.rs` | ~200 | Policy creation |
| `tree/validation.rs` | ~300 | Safety validation |

### Policy Trait

**Source**: `simulator/src/policy/mod.rs`

```mermaid
classDiagram
    class CashManagerPolicy {
        <<interface>>
        +evaluate_queue(agent, state, tick, cost_rates, ticks_per_day, eod_rush_threshold) Vec~ReleaseDecision~
        +as_any_mut() &mut dyn Any
    }

    class TreePolicy {
        -payment_tree: DecisionTreeDef
        -bank_tree: Option~DecisionTreeDef~
        -strategic_collateral_tree: Option~DecisionTreeDef~
        -end_of_tick_collateral_tree: Option~DecisionTreeDef~
        +evaluate_queue(...) Vec~ReleaseDecision~
    }

    class FifoPolicy {
        +evaluate_queue(...) Vec~ReleaseDecision~
    }

    class DeadlinePolicy {
        -urgency_threshold: usize
        +evaluate_queue(...) Vec~ReleaseDecision~
    }

    CashManagerPolicy <|.. TreePolicy
    CashManagerPolicy <|.. FifoPolicy
    CashManagerPolicy <|.. DeadlinePolicy
```

### Release Decision Types

```mermaid
classDiagram
    class ReleaseDecision {
        <<enumeration>>
        SubmitFull
        SubmitPartial
        Hold
        Reprioritize
        Drop
    }

    class SubmitFull {
        +tx_id: String
        +priority_override: Option~u8~
        +target_tick: Option~usize~
    }

    class SubmitPartial {
        +tx_id: String
        +num_splits: usize
    }

    class Hold {
        +tx_id: String
        +reason: HoldReason
    }

    class Reprioritize {
        +tx_id: String
        +new_priority: u8
    }

    ReleaseDecision --> SubmitFull
    ReleaseDecision --> SubmitPartial
    ReleaseDecision --> Hold
    ReleaseDecision --> Reprioritize
```

### Decision Tree Evaluation

```mermaid
flowchart TB
    Start["evaluate_queue()"] --> BuildCtx["Build EvalContext<br/>(50+ fields)"]
    BuildCtx --> BankTree{"bank_tree<br/>defined?"}

    BankTree -->|Yes| EvalBank["Evaluate bank_tree"]
    EvalBank --> ApplyBank["Apply bank actions<br/>(SetBudget, SetState)"]
    BankTree -->|No| CollateralTree
    ApplyBank --> CollateralTree

    CollateralTree{"collateral_tree<br/>defined?"} -->|Yes| EvalColl["Evaluate collateral_tree"]
    CollateralTree -->|No| PaymentLoop
    EvalColl --> ApplyColl["Apply collateral actions<br/>(Post, Withdraw)"]
    ApplyColl --> PaymentLoop

    PaymentLoop["For each tx in queue"] --> EvalPayment["Evaluate payment_tree"]
    EvalPayment --> Decision{"Decision?"}

    Decision -->|Submit| AddSubmit["Add SubmitFull/Partial"]
    Decision -->|Hold| AddHold["Add Hold"]
    Decision -->|Drop| AddDrop["Add Drop"]

    AddSubmit --> Next{"More txs?"}
    AddHold --> Next
    AddDrop --> Next
    Next -->|Yes| PaymentLoop
    Next -->|No| Return["Return decisions"]
```

---

## 7. Arrivals Module (`arrivals/`)

### Purpose
Transaction generation with configurable distributions.

### Files

| File | Lines | Purpose |
|------|-------|---------|
| `mod.rs` | ~800 | ArrivalGenerator, distributions |

### Arrival Configuration

**Source**: `simulator/src/arrivals/mod.rs`

```mermaid
classDiagram
    class ArrivalConfig {
        +rate_per_tick: f64
        +amount_distribution: AmountDistribution
        +counterparty_weights: HashMap~String, f64~
        +deadline_range: (usize, usize)
        +priority_distribution: PriorityDistribution
        +divisible: bool
    }

    class AmountDistribution {
        <<enumeration>>
        Uniform
        Normal
        LogNormal
        Exponential
    }

    class PriorityDistribution {
        <<enumeration>>
        Fixed
        Categorical
        Uniform
    }

    class ArrivalBandsConfig {
        +urgent: Option~ArrivalBandConfig~
        +normal: Option~ArrivalBandConfig~
        +low: Option~ArrivalBandConfig~
    }

    ArrivalConfig --> AmountDistribution
    ArrivalConfig --> PriorityDistribution
```

### Arrival Generation Flow

```mermaid
flowchart TB
    Tick["tick()"] --> ForAgent["For each agent"]
    ForAgent --> Config{"Has<br/>ArrivalConfig?"}

    Config -->|No| Skip["Skip"]
    Config -->|Yes| Poisson["Sample Poisson(λ)"]

    Poisson --> Count["N arrivals"]
    Count --> ForN["For i in 0..N"]

    ForN --> Amount["Sample amount<br/>(distribution)"]
    Amount --> Receiver["Sample receiver<br/>(weights)"]
    Receiver --> Deadline["Sample deadline<br/>(range)"]
    Deadline --> Priority["Sample priority<br/>(distribution)"]
    Priority --> CreateTx["Create Transaction"]
    CreateTx --> Queue["Add to Queue 1"]
    Queue --> Event["Emit Arrival event"]
    Event --> ForN

    Skip --> NextAgent["Next agent"]
    Event --> NextAgent
```

---

## 8. Events Module (`events/`)

### Purpose
Scenario event handling for external interventions.

### Files

| File | Lines | Purpose |
|------|-------|---------|
| `mod.rs` | ~20 | Module re-exports |
| `types.rs` | ~400 | ScenarioEvent enum |
| `handler.rs` | ~400 | ScenarioEventHandler |

### Scenario Event Types

**Source**: `simulator/src/events/types.rs`

```mermaid
classDiagram
    class ScenarioEvent {
        <<enumeration>>
        DirectTransfer
        CustomTransactionArrival
        CollateralAdjustment
        GlobalArrivalRateChange
        AgentArrivalRateChange
        CounterpartyWeightChange
        DeadlineWindowChange
        DeadlineCapChange
    }

    class EventSchedule {
        <<enumeration>>
        OneTime
        Recurring
    }

    class ScheduledEvent {
        +event: ScenarioEvent
        +schedule: EventSchedule
    }

    ScheduledEvent --> ScenarioEvent
    ScheduledEvent --> EventSchedule
```

---

## 9. FFI Module (`ffi/`)

### Purpose
PyO3 bindings for Python interoperability.

### Files

| File | Lines | Purpose |
|------|-------|---------|
| `mod.rs` | ~50 | Module re-exports |
| `orchestrator.rs` | ~600 | PyOrchestrator wrapper |
| `types.rs` | ~500 | Type conversions |

See [04-ffi-boundary.md](./04-ffi-boundary.md) for detailed FFI patterns.

### PyOrchestrator

**Source**: `simulator/src/ffi/orchestrator.rs`

```mermaid
classDiagram
    class PyOrchestrator {
        -inner: Orchestrator
        +new(config: PyDict) PyResult~Self~
        +tick() PyResult~PyObject~
        +current_tick() usize
        +current_day() usize
        +get_agent_balance(agent_id: str) PyResult~i64~
        +get_tick_events(tick: usize) PyResult~PyObject~
        +get_all_events() PyResult~PyObject~
        +checkpoint(path: str) PyResult~()~
        +restore(path: str) PyResult~Self~
    }
```

---

## Error Handling

### Error Types

```mermaid
classDiagram
    class SimulationError {
        <<enumeration>>
        AgentNotFound
        TransactionNotFound
        InsufficientLiquidity
        InvalidConfiguration
        SettlementFailed
        CheckpointFailed
    }

    class SettlementError {
        <<enumeration>>
        InsufficientLiquidity
        AlreadySettled
        InvalidTransaction
        AtomicityViolation
    }

    class AgentError {
        <<enumeration>>
        InsufficientBalance
        InvalidOperation
        CollateralError
    }
```

### Error Propagation

```mermaid
flowchart LR
    Rust["Rust Error"] --> PyO3["PyO3 Conversion"]
    PyO3 --> Python["Python Exception"]

    subgraph Rust
        SimErr["SimulationError"]
        SettleErr["SettlementError"]
    end

    subgraph Python
        PyErr["PyErr"]
        ValueError["ValueError"]
    end

    SimErr --> PyErr
    SettleErr --> ValueError
```

---

## Performance Characteristics

### Algorithmic Complexity

| Operation | Time | Space |
|-----------|------|-------|
| Agent lookup | O(log n) | O(1) |
| Transaction lookup | O(log n) | O(1) |
| RTGS settle | O(1) | O(1) |
| Bilateral offset | O(n²) | O(n) |
| Cycle detection | O(V + E) | O(V + E) |
| Policy evaluation | O(d × q) | O(q) |

Where: n = agents, d = tree depth, q = queue size, V = vertices, E = edges

### Memory Layout

```mermaid
flowchart TB
    subgraph Orchestrator["Orchestrator (~2KB base)"]
        State["SimulationState"]
        Time["TimeManager (24B)"]
        RNG["RngManager (8B)"]
        Config["OrchestratorConfig"]
    end

    subgraph SimState["SimulationState (~N KB)"]
        Agents["BTreeMap<String, Agent>"]
        Txs["BTreeMap<String, Transaction>"]
        Queue["Vec<String> (Queue 2)"]
        Events["Vec<Event>"]
    end

    subgraph AgentMem["Agent (~500B each)"]
        AgentFields["Core fields"]
        AgentQueue["outgoing_queue"]
        AgentMaps["HashMap fields"]
    end

    State --> SimState
    SimState --> AgentMem
```

---

## Testing Strategy

### Test Organization

```
simulator/tests/
├── integration/
│   ├── test_determinism.rs
│   ├── test_settlement.rs
│   ├── test_lsm.rs
│   └── test_policy.rs
└── unit/
    ├── test_agent.rs
    ├── test_transaction.rs
    └── test_rng.rs
```

### Test Commands

```bash
# Run all Rust tests (must use --no-default-features)
cd simulator
cargo test --no-default-features

# Run specific test
cargo test --no-default-features test_determinism

# Run with output
cargo test --no-default-features -- --nocapture
```

---

## Related Documents

- [05-domain-models.md](./05-domain-models.md) - Detailed model documentation
- [06-settlement-engines.md](./06-settlement-engines.md) - Settlement algorithms
- [07-policy-system.md](./07-policy-system.md) - Policy DSL details
- [08-event-system.md](./08-event-system.md) - Event types catalog

---

*Next: [03-python-api-layer.md](./03-python-api-layer.md) - Python layer architecture*
