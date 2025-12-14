# System Overview

**Version**: 1.0
**Last Updated**: 2025-11-28

---

## Purpose

SimCash simulates high-value payment operations between banks, modeling how cash managers strategically time and fund outgoing payments during the business day. It implements real-world RTGS (Real-Time Gross Settlement) systems like TARGET2, where banks balance competing pressures:

- Minimizing liquidity costs
- Meeting payment deadlines
- Avoiding gridlock
- Maintaining system throughput

---

## Design Philosophy

### Why Rust + Python?

SimCash uses a hybrid architecture that combines the strengths of both languages:

```mermaid
flowchart TB
    subgraph "Python Layer"
        direction TB
        P1[Configuration<br/>Pydantic validation]
        P2[API/CLI<br/>User interfaces]
        P3[Persistence<br/>DuckDB integration]
        P4[Analysis<br/>Polars DataFrames]
    end

    subgraph "Rust Layer"
        direction TB
        R1[Tick Loop<br/>High-frequency execution]
        R2[Settlement<br/>RTGS + LSM algorithms]
        R3[RNG<br/>Deterministic randomness]
        R4[Events<br/>Audit trail generation]
    end

    P1 -->|"Validated Config"| FFI
    P2 -->|"Commands"| FFI
    FFI -->|"PyO3"| R1
    R1 --> R2
    R1 --> R3
    R1 --> R4
    R4 -->|"Events"| FFI
    FFI -->|"Results"| P3
    FFI -->|"Data"| P4

    style P1 fill:#3776ab,color:#fff
    style P2 fill:#3776ab,color:#fff
    style P3 fill:#3776ab,color:#fff
    style P4 fill:#3776ab,color:#fff
    style R1 fill:#dea584,color:#000
    style R2 fill:#dea584,color:#000
    style R3 fill:#dea584,color:#000
    style R4 fill:#dea584,color:#000
```

| Language | Responsibility | Rationale |
|----------|---------------|-----------|
| **Rust** | Simulation engine | Performance-critical tick loop (1000+ ticks/sec), deterministic execution, memory safety |
| **Python** | Orchestration | Developer ergonomics, rich ecosystem (Pydantic, FastAPI, Polars), rapid iteration |

### Core Principles

1. **Rust Owns State** - Python only receives snapshots, never mutable references
2. **Python Orchestrates** - Configuration, API, lifecycle management live in Python
3. **FFI is Thin** - Minimal, stable API surface with simple types

---

## Three-Tier Architecture

```mermaid
flowchart TB
    subgraph Tier1["Tier 1: Presentation"]
        CLI["CLI Tool<br/>(Typer)"]
        API["REST API<br/>(FastAPI)"]
        WS["WebSocket<br/>(Future)"]
    end

    subgraph Tier2["Tier 2: Business Logic"]
        direction TB
        Config["Config Validation<br/>(Pydantic)"]
        Exec["Execution Engine<br/>(SimulationRunner)"]
        Provider["StateProvider<br/>(Abstraction)"]
    end

    subgraph Tier3["Tier 3: Core Engine"]
        direction TB
        Orch["Orchestrator"]
        Settle["Settlement<br/>(RTGS + LSM)"]
        Policy["Policy<br/>(Decision Trees)"]
        Events["Event Log"]
    end

    subgraph Data["Data Layer"]
        DB[(DuckDB)]
    end

    CLI --> Config
    API --> Config
    Config --> Exec
    Exec --> Provider
    Provider -->|"FFI"| Orch
    Provider -->|"SQL"| DB
    Orch --> Settle
    Orch --> Policy
    Orch --> Events
    Events -->|"Persist"| DB

    style Tier1 fill:#e1f5fe
    style Tier2 fill:#fff3e0
    style Tier3 fill:#fce4ec
```

### Tier 1: Presentation Layer

| Component | Technology | Purpose |
|-----------|------------|---------|
| CLI Tool | Python/Typer | `payment-sim run`, `replay`, `checkpoint`, `db` commands |
| REST API | Python/FastAPI | Programmatic simulation control |
| WebSocket | Future | Real-time streaming for UI |

### Tier 2: Business Logic Layer

| Component | Purpose | Key Pattern |
|-----------|---------|-------------|
| Config Validation | Validate YAML against Pydantic schemas | Fail-fast validation |
| Execution Engine | Template Method for simulation modes | `SimulationRunner` + `OutputStrategy` |
| StateProvider | Abstract data access (live vs replay) | Protocol pattern |

### Tier 3: Core Engine (Rust)

| Component | Lines of Code | Purpose |
|-----------|---------------|---------|
| Orchestrator | ~2,000 | Main tick loop, coordinates all components |
| Settlement | ~1,500 | RTGS immediate + LSM optimization |
| Policy | ~4,880 | Decision tree evaluation |
| Events | ~800 | 50+ event types, audit trail |

---

## Component Interaction

### Run Command Flow

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant CLI as CLI (Python)
    participant Config as Config Layer
    participant Runner as SimulationRunner
    participant FFI as FFI Bridge
    participant Rust as Rust Engine
    participant DB as DuckDB

    User->>CLI: payment-sim run config.yaml
    CLI->>Config: load_config(path)
    Config->>Config: Pydantic validation
    Config-->>CLI: SimulationConfig

    CLI->>FFI: Orchestrator.new(config_dict)
    FFI->>Rust: Create Orchestrator
    Rust-->>FFI: PyOrchestrator

    CLI->>Runner: SimulationRunner(orch, config)

    loop For each tick
        Runner->>FFI: orch.tick()
        FFI->>Rust: Execute tick loop
        Rust->>Rust: Arrivals → Policy → RTGS → LSM → Costs
        Rust-->>FFI: TickResult
        FFI-->>Runner: Dict[str, Any]
        Runner->>Runner: OutputStrategy.on_tick_complete()
        Runner->>DB: Persist events (if enabled)
    end

    Runner-->>CLI: Final stats
    CLI-->>User: JSON output
```

### Replay Command Flow

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant CLI as CLI (Python)
    participant Provider as DatabaseStateProvider
    participant Display as display_tick_verbose_output
    participant DB as DuckDB

    User->>CLI: payment-sim replay --simulation-id sim-abc123
    CLI->>DB: Load simulation config
    DB-->>CLI: SimulationConfig

    CLI->>Provider: DatabaseStateProvider(conn, sim_id)

    loop For each tick in range
        CLI->>DB: get_simulation_events(tick)
        DB-->>CLI: Events list
        CLI->>Display: display_tick_verbose_output(provider, events)
        Display->>Provider: get_agent_balance(), get_queue()...
        Provider->>DB: SQL queries
        DB-->>Provider: Results
        Display-->>CLI: Formatted output
    end

    Note over Display: Same function used for both<br/>live execution and replay!
```

---

## Key Architectural Decisions

### ADR-1: Money Representation

**Decision**: All monetary values are `i64` (signed 64-bit integers) representing cents.

**Rationale**:
- Floating-point arithmetic introduces rounding errors that compound over millions of transactions
- Financial systems demand exact arithmetic
- Integer operations are faster and deterministic

**Consequence**:
```rust
// CORRECT
let amount: i64 = 100000; // $1,000.00 in cents

// FORBIDDEN
let amount: f64 = 1000.00; // NO FLOATS FOR MONEY
```

### ADR-2: Deterministic Execution

**Decision**: All randomness via seeded xorshift64* RNG with explicit seed persistence.

**Rationale**:
- Simulation must be perfectly reproducible for debugging
- Research validation requires identical results
- Compliance auditing needs audit trails

**Consequence**:
```rust
// After each RNG call, new seed MUST be persisted
let (value, new_seed) = rng.next_u64(current_seed);
state.rng_seed = new_seed; // CRITICAL
```

### ADR-3: Two-Queue Architecture

**Decision**: Separate Queue 1 (internal bank queue) from Queue 2 (RTGS central queue).

**Rationale**:
- Captures reality that banks choose when to submit (Queue 1)
- Settlement depends on liquidity availability (Queue 2)
- Delay costs apply only to Queue 1 (policy choice, not liquidity constraint)

```mermaid
flowchart LR
    subgraph Bank["Bank (Agent)"]
        Q1["Queue 1<br/>Internal Queue"]
    end

    subgraph RTGS["Central RTGS"]
        Q2["Queue 2<br/>Settlement Queue"]
    end

    Arrival[/"Transaction<br/>Arrival"/] --> Q1
    Q1 -->|"Policy Decision:<br/>Submit"| Q2
    Q2 -->|"Sufficient<br/>Liquidity"| Settled((Settled))
    Q2 -->|"Insufficient<br/>Liquidity"| Q2
    Q2 -->|"LSM<br/>Offset"| Settled

    style Q1 fill:#bbdefb
    style Q2 fill:#c8e6c9
```

### ADR-4: StateProvider Pattern

**Decision**: Abstract data access behind a protocol to ensure replay identity.

**Rationale**:
- Same display code must work for both live execution and replay
- `run --verbose` output must be byte-for-byte identical to `replay --verbose`
- Enables future data sources (external APIs, etc.)

**Consequence**:
```mermaid
flowchart TB
    Display["display_tick_verbose_output()"]

    Display --> Provider{StateProvider<br/>Protocol}

    Provider --> Live["OrchestratorStateProvider<br/>(FFI calls)"]
    Provider --> Replay["DatabaseStateProvider<br/>(SQL queries)"]

    Live --> Result[/"Identical Output"/]
    Replay --> Result
```

### ADR-5: Event-Sourced Persistence

**Decision**: All simulation activity recorded as immutable events in `simulation_events` table.

**Rationale**:
- Complete audit trail for analysis
- Single source of truth for replay
- Events are self-contained (no external lookups needed)

**Consequence**:
- Events include ALL data needed for display (not just IDs)
- No legacy tables or manual reconstruction
- Replay queries only `simulation_events`

---

## System Invariants

These properties MUST hold at all times:

### INV-1: Balance Conservation

```
sum(all_agent_balances) == sum(initial_balances) + sum(external_transfers)
```

Settlement moves money between agents but never creates or destroys it.

### INV-2: Determinism

```
seed + config → identical_execution_trace
```

Given the same seed and configuration, the simulation produces byte-for-byte identical results.

### INV-3: Queue Validity

```
∀ tx_id ∈ rtgs_queue: transactions.contains(tx_id)
```

All transaction IDs in Queue 2 reference existing transactions.

### INV-4: Atomicity

```
settlement(tx) ∈ {complete_success, complete_failure}
```

Settlement is all-or-nothing. Partial settlement only via explicit splitting.

### INV-5: Event Completeness

```
∀ event ∈ event_log: event.contains(all_display_fields)
```

Events are self-contained with all data needed for display.

---

## Data Flow Architecture

### Configuration Flow

```mermaid
flowchart LR
    YAML["YAML File"] --> Loader["YAML Loader<br/>(PyYAML)"]
    Loader --> Pydantic["Pydantic<br/>Validation"]
    Pydantic --> Dict["Python Dict"]
    Dict --> FFI["FFI Bridge"]
    FFI --> Rust["Rust Structs"]

    style YAML fill:#fff3e0
    style Pydantic fill:#e8f5e9
    style FFI fill:#fce4ec
    style Rust fill:#dea584
```

### Event Flow

```mermaid
flowchart LR
    Rust["Rust Engine"] --> Event["Event<br/>Enum"]
    Event --> Serialize["FFI<br/>Serialization"]
    Serialize --> Dict["Python Dict"]
    Dict --> Writer["Event<br/>Writer"]
    Writer --> DB[(DuckDB<br/>simulation_events)]

    DB --> Query["Query<br/>Interface"]
    Query --> Display["Display<br/>Function"]

    style Rust fill:#dea584
    style DB fill:#e3f2fd
```

### State Query Flow

```mermaid
flowchart TB
    subgraph LiveMode["Live Execution"]
        Code1["Display Code"] --> Provider1["OrchestratorStateProvider"]
        Provider1 --> FFI1["FFI Call"]
        FFI1 --> Rust1["Rust State"]
    end

    subgraph ReplayMode["Replay Execution"]
        Code2["Display Code"] --> Provider2["DatabaseStateProvider"]
        Provider2 --> SQL["SQL Query"]
        SQL --> DB[(DuckDB)]
    end

    Note["Same display_tick_verbose_output()<br/>function used in both modes"]
```

---

## Performance Characteristics

| Metric | Target | Achieved |
|--------|--------|----------|
| Tick throughput | 1,000/sec | 1,200+/sec |
| LSM cycle detection | <1ms | ~0.5ms typical |
| FFI overhead | Minimal | ~10μs per call |
| Event serialization | Fast | ~1μs per event |

### Bottleneck Analysis

```mermaid
pie title Typical Tick Time Distribution
    "RTGS Processing" : 35
    "LSM Optimization" : 25
    "Policy Evaluation" : 20
    "Event Generation" : 10
    "FFI Overhead" : 5
    "Other" : 5
```

---

## Security Boundaries

```mermaid
flowchart TB
    subgraph Trusted["Trusted Zone"]
        Rust["Rust Engine"]
        Python["Python Layer"]
        DB[(DuckDB)]
    end

    subgraph Validated["Validation Boundary"]
        Config["Config Input"]
        API["API Input"]
    end

    Config -->|"Pydantic"| Python
    API -->|"Pydantic"| Python
    Python -->|"Type Safe"| Rust
    Python --> DB
    Rust --> Python

    style Trusted fill:#e8f5e9
    style Validated fill:#fff3e0
```

- **Config Validation**: All YAML input validated against Pydantic schemas
- **API Validation**: All HTTP input validated before processing
- **FFI Type Safety**: PyO3 ensures type correctness at boundary
- **No External Network**: Simulation engine has no network access

---

## Future Architecture

```mermaid
flowchart TB
    subgraph Current["Current (v1.0)"]
        CLI1["CLI"]
        API1["REST API"]
        Engine1["Rust Engine"]
        DB1[(DuckDB)]
    end

    subgraph Future["Future (v2.0)"]
        CLI2["CLI"]
        API2["REST API"]
        WS["WebSocket<br/>Streaming"]
        Engine2["Rust Engine"]
        LLM["LLM Manager<br/>(Async)"]
        DB2[(DuckDB)]
        Redis["Redis<br/>(State Cache)"]
    end

    CLI2 --> Engine2
    API2 --> Engine2
    WS --> Engine2
    LLM --> Engine2
    Engine2 --> DB2
    Engine2 --> Redis
```

### Planned Enhancements

1. **Phase 11**: BIS AI Cash Management compatibility
2. **Phase 12**: LLM Manager with shadow replay validation
3. **Phase 13**: Multi-rail support (RTGS + DNS)
4. **Phase 14**: Enhanced shock scenarios
5. **Phase 15**: Production readiness (WebSocket, frontend)

---

## Related Documents

- [02-rust-core-engine.md](./02-rust-core-engine.md) - Rust module details
- [03-python-api-layer.md](./03-python-api-layer.md) - Python layer details
- [04-ffi-boundary.md](./04-ffi-boundary.md) - Integration patterns
- [11-tick-loop-anatomy.md](./11-tick-loop-anatomy.md) - Execution flow

---

*Next: [02-rust-core-engine.md](./02-rust-core-engine.md) - Deep dive into the Rust backend*
