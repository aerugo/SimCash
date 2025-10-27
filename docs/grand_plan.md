# Payment Simulator - Project Plan
## Rust Backend + Python API Architecture

> **Implementation Status (2025-10-27)**:
> - ✅ Phase 1-2 Complete: Core models (Time, RNG, Agent, Transaction)
> - ⏳ Phase 3 Planned: RTGS settlement engine (see `/docs/phase3_rtgs_analysis.md`)
> - 🎯 Phase 4+: LSM, Orchestrator, API layers

## 1) Executive Summary

### Purpose
Build a sandboxed, multi-agent simulator of high-value payment operations. The simulator demonstrates how banks (agents) time and fund outgoing payments during the business day while meeting deadlines, minimizing costs, and avoiding gridlock.

### Core Innovation
Each bank is controlled by a **decision-tree policy** (a small, auditable program) that determines payment timing and liquidity management. An **asynchronous LLM Manager service** improves the bank's policy between simulation episodes by editing the tree's code under version control. Candidate edits undergo automated validation (schema checks, property tests, Monte Carlo shadow replay) before deployment.

### Architectural Approach: Hybrid Rust-Python System

The simulator uses a **two-tier architecture** to maximize both performance and development velocity:

1. **Rust Core Backend** (`/backend`): High-performance simulation engine
   - All time-critical computation (tick loop, settlement, LSM algorithms)
   - Zero-cost abstractions and memory safety
   - Compiled to native code for maximum throughput
   - Exposed as Python extension via PyO3/Maturin

2. **Python API Layer** (`/api`): Developer-friendly middleware
   - FastAPI REST/WebSocket endpoints
   - Configuration management and validation
   - Service orchestration and lifecycle management
   - Testing infrastructure and utilities

3. **FFI Boundary**: Clean separation between layers
   - Rust exposes minimal, stable API surface
   - Python handles serialization, HTTP, and async I/O
   - Type-safe boundary via PyO3 bindings

This architecture delivers:
- **10-100x performance** improvement over pure Python (Rust orchestrator)
- **Developer ergonomics** of Python for API and tooling
- **Type safety** across the FFI boundary
- **Independent evolution** of core and API layers

### Key Architectural Principles

1. **Separation of Concerns**
   - **Rust domain**: Simulation logic, state management, deterministic computation
   - **Python domain**: HTTP handling, async coordination, configuration, testing
   - **FFI contract**: Versioned, stable interface between layers

2. **Performance-Critical in Rust**
   - Tick loop (must process thousands of ticks per second)
   - Settlement engine (immediate RTGS + LSM cycle detection)
   - RNG management (xorshift64* for determinism)
   - Memory-intensive operations (transaction queues, ledger state)

3. **Convenience in Python**
   - REST/WebSocket API endpoints (FastAPI)
   - Configuration loading and validation (Pydantic)
   - Simulation lifecycle management
   - Test fixtures and property-based testing (Hypothesis)

4. **Asynchronous Learning**
   - Simulation runs at full speed without blocking on LLM
   - LLM Managers run in separate processes/containers
   - Policy updates applied at episode boundaries (not mid-tick)
   - Monte Carlo validation samples opponent behaviors

5. **Deterministic Simulation**
   - All randomness via seeded RNG (xorshift64*)
   - Complete event log for perfect replay
   - Git-versioned policies with commit hashes

### What You Can Learn
- How rules and costs shape system behavior (early-release norms vs hoarding)
- How Liquidity-Saving Mechanisms (LSMs) reduce liquidity needs
- How throughput targets affect timing and end-of-day bunching
- What shocks (outages, fee spikes) do to queues
- Which policy structures converge or oscillate

### Audience
- Engineering teams building the simulator
- Payment operations and treasury practitioners
- Researchers interested in coordination games under liquidity constraints

---

## 2) Real-World Grounding

### Who Are the Agents?
Real-world intraday cash managers (treasury operations) who decide:
- When to release payments across rails (Fedwire/CHAPS/TARGET)
- How to fund them (overdraft, collateral, repo)
- How to prioritize client and house flows

### What Actually Moves?
**Settlement balances** (reserves at central bank or correspondent accounts). Debiting a customer account inside a bank does NOT move interbank money. The scarce resource intraday is settlement liquidity.

### How Do They Fund Payments?
- Opening balances
- Incoming payments (recycling)
- Priced overdraft or collateralized credit (10-50 bps annually)
- Intraday borrowing (repo/money markets)
- Pre-funding nostros for cross-border corridors

### Operational Realities
- **Cut-offs & windows**: Market closes, PvP/DvP cash legs, payroll deadlines
- **Throughput expectations**: Settle X% by time T (avoid end-of-day bunching)
- **Gridlock risk**: If everyone waits for inflows, nothing moves
- **Compliance holds**: Screening delays can block flows
- **Ops capacity**: Message processing limits

---

## 3) Problem Statement & Objectives

### Problem
Given stochastic arrivals of payments with deadlines and priorities, and given liquidity costs/constraints and rail rules, how should banks schedule and fund outgoing payments to minimize cost and risk while meeting obligations? How do independent policy choices interact system-wide?

### Objectives

**Agent-Level**:
- Minimize total intraday cost (liquidity + delay + fees + penalties)
- Respect credit limits and bilateral caps
- Meet hard cut-offs and throughput targets

**System-Level**:
- Maximize throughput for given liquidity usage
- Minimize delays, gridlock minutes, and end-of-day residuals
- Understand LSM efficacy and policy interactions

**Research**:
- Map regimes (priced overdraft vs collateralized credit)
- Test throughput targets and pacing incentives
- Observe policy convergence/oscillation
- Measure resilience to shocks

### Non-Goals
- Full core-banking or securities settlement replacement
- Legal/regulatory sufficiency or detailed AML modeling
- Real-time microsecond scheduling (we model discrete ticks)
- Perfect information (agents see coarse aggregates, not others' queues)

---

## 4) Key Concepts & Glossary

| Term | Definition |
|------|------------|
| **RTGS** | Real-Time Gross Settlement; payments settle individually in final funds |
| **LSM** | Liquidity-Saving Mechanism; queuing/offsetting logic that releases mutually offsetting payments |
| **Queue** | Central system holding payments awaiting sufficient liquidity |
| **Split** | Division of a divisible payment into multiple amounts (some rails disallow) |
| **Execution Attempt** | Scheduled retry for an indivisible payment (timing, not amount) |
| **Package** | Linked set of payments with shared success criteria (e.g., DvP cash legs) |
| **Bilateral Cap** | Maximum net exposure allowed between two participants |
| **Throughput** | Cumulative value settled as fraction of cumulative value arrived |
| **Peak Net Debit** | Maximum intraday shortfall of an agent's settlement account |
| **Nostro** | Account held with correspondent bank in another currency/jurisdiction |
| **RAG** | Red/Amber/Green alerting state for throughput, backlog, peak debit |
| **Headroom** | Remaining unused intraday credit capacity |
| **Episode** | Complete simulation run (one or more business days) |
| **Fire-and-forget** | Policy evaluation model where action plan is generated once at arrival |
| **Shadow replay** | Re-evaluation of past decisions with new policy using Monte Carlo sampling |
| **Guardband** | Acceptable deviation range for KPIs after policy change |
| **FFI** | Foreign Function Interface; the boundary between Rust and Python |
| **PyO3** | Rust library for creating Python bindings |
| **Maturin** | Build tool for Rust Python extensions |

---

## 5) Architecture Overview

### System Components & Layer Separation

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          PYTHON API LAYER                                │
│                        (FastAPI + Uvicorn)                               │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  REST/WebSocket Endpoints                                        │   │
│  │  - /simulations (CRUD, start/stop/reset)                        │   │
│  │  - /transactions (submit, query, statistics)                    │   │
│  │  - /settlements (bilateral ledger, LSM stats)                   │   │
│  │  - /kpis (costs, throughput, peak debit)                        │   │
│  │  - /queue (state, history)                                      │   │
│  │  - /websocket (real-time updates)                               │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                │                                         │
│  ┌─────────────────────────────▼─────────────────────────────────┐     │
│  │  Service Layer                                                  │     │
│  │  - SimulationManager (lifecycle, config validation)            │     │
│  │  - RolloutManager (A/B testing, feature flags)                 │     │
│  │  - MetricsStore (aggregation, WebSocket streaming)             │     │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                │                                         │
│  ┌─────────────────────────────▼─────────────────────────────────┐     │
│  │  Configuration & Validation                                     │     │
│  │  - Pydantic schemas (SimulationConfig, AgentConfig, etc.)      │     │
│  │  - YAML loader with environment variable substitution          │     │
│  │  - Type validation and business rules                          │     │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                │                                         │
└────────────────────────────────┼─────────────────────────────────────────┘
                                 │
                     ════════════▼══════════════
                     ║   FFI BOUNDARY (PyO3)    ║
                     ║                          ║
                     ║  - Type-safe bindings    ║
                     ║  - Minimal API surface   ║
                     ║  - Error propagation     ║
                     ║  - Zero-copy where safe  ║
                     ════════════▼══════════════
                                 │
┌────────────────────────────────┼─────────────────────────────────────────┐
│                          RUST CORE BACKEND                                │
│                   (payment_simulator_core_rs crate)                       │
│                                                                           │
│  ┌─────────────────────────────▼─────────────────────────────────┐     │
│  │  Orchestrator Engine                                            │     │
│  │  - Tick loop (advance time, process events)                    │     │
│  │  - Arrival generation (deterministic RNG)                      │     │
│  │  - Policy evaluation coordination                              │     │
│  │  - Cost accrual (liquidity, delay, penalty)                    │     │
│  │  - Event logging (structured log for replay)                   │     │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                │                                         │
│  ┌─────────────────────────────▼─────────────────────────────────┐     │
│  │  Settlement Engine                                              │     │
│  │  - Immediate RTGS settlement                                    │     │
│  │  - Balance management (opening, inflows, outflows)              │     │
│  │  - Overdraft and collateral tracking                            │     │
│  │  - Settlement failure detection                                 │     │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                │                                         │
│  ┌─────────────────────────────▼─────────────────────────────────┐     │
│  │  LSM Coordinator                                                │     │
│  │  - Bilateral netting (direct offsets)                          │     │
│  │  - Cycle detection (3-cycles, 4-cycles)                        │     │
│  │  - Batch optimization (multi-party clearing)                   │     │
│  │  - Priority-aware processing                                   │     │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                           │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │  Core Data Structures                                          │     │
│  │  - Transaction (state machine, settlement tracking)            │     │
│  │  - Agent (balances, queues, limits)                            │     │
│  │  - SystemState (global ledger, time manager)                   │     │
│  │  - RNG Manager (xorshift64*, seed persistence)                 │     │
│  └───────────────────────────────────────────────────────────────┘     │
│                                                                           │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │  Specialized Modules                                           │     │
│  │  - Arrivals (distributions, generator)                         │     │
│  │  - Costs (accrual, rates)                                      │     │
│  │  - Logging (events, levels, structured output)                 │     │
│  │  - Metrics (performance counters)                              │     │
│  └───────────────────────────────────────────────────────────────┘     │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘

              ┌──────────────────────────┐
              │   Message Queue          │
              │   (Redis/Kafka)          │
              │   [Future: LLM Updates]  │
              └──────────┬───────────────┘
                         │
              ┌──────────▼───────────┐
              │   LLM Manager        │
              │   (Separate Process) │
              │  - Receives Updates  │
              │  - Generates Patches │
              │  - Validates (MC)    │
              │  - Submits Patches   │
              └──────────────────────┘
```

### Rust Backend Modules

#### Core Module (`backend/src/core/`)
**Responsibility**: Simulation foundation and time management

**Components**:
- `initialization.rs`: System bootstrap, state construction
- `time.rs`: `TimeManager` - tick advancement, day rollover, window checks
- `mod.rs`: Module exports and core types

**Key Types**:
```rust
pub struct TimeManager {
    ticks_per_day: u32,
    current_day: u32,
    current_tick: u32,
    absolute_tick: u64,
}
```

**Why Rust**: Tight control over tick loop performance; zero-cost time calculations.

#### Orchestrator Module (`backend/src/orchestrator/`)
**Responsibility**: Main simulation loop and event coordination

**Components**:
- `engine.rs`: Tick loop, arrival generation, policy evaluation coordination
- `mod.rs`: Public API for orchestrator

**Key Operations**:
1. Advance tick
2. Generate arrivals (via RNG)
3. Evaluate policies (payment, liquidity, nostro)
4. Execute settlement attempts
5. Run LSM coordinator
6. Accrue costs
7. Log events

**Why Rust**: Orchestrator is the hottest path; runs thousands of ticks per second.

#### Settlement Module (`backend/src/settlement/`) ⏳ Phase 3
**Status**: Placeholder only. See `/docs/phase3_rtgs_analysis.md` for implementation plan.

**Responsibility**: RTGS settlement logic and central queue management

**Target Components** (Phase 3):
- `rtgs.rs`: T2-style immediate settlement + central queue
- `queue.rs`: Central RTGS queue management
- `caps.rs`: Bilateral cap enforcement (Phase 4)
- `failure.rs`: Settlement failure detection and classification
- `mod.rs`: Public settlement API

**Target Operations** (Phase 3):
- Check: `balance + credit_limit >= amount`
- If yes: debit sender, credit receiver (settlement at central bank)
- If no: add to **central RTGS queue**
- Process queue each tick (retry pending transactions)
- Drop transactions past deadline

**Why Rust**: Critical path for every transaction; memory safety prevents double-spending bugs.

#### LSM Module (`backend/src/lsm/`) 🎯 Phase 4
**Status**: Not yet implemented. Planned after Phase 3 completion.

**Responsibility**: Liquidity-Saving Mechanism (T2-style optimization)

**Target Components** (Phase 4):
- `bilateral.rs`: A↔B bilateral offsetting
- `cycle.rs`: Multi-party cycle detection (A→B→C→A)
- `coordinator.rs`: LSM orchestration, priority handling
- `mod.rs`: Public LSM API

**Target Algorithms** (Phase 4):
- Bilateral netting: O(n²) pairwise comparison
- 3-cycle detection: O(n³) but with pruning
- 4-cycle detection: O(n⁴) with early termination
- Batch optimization: Linear programming (future)

**Why Rust**: Graph algorithms are CPU-intensive; Rust's zero-cost iterators shine here.

#### Models Module (`backend/src/models/`) ✅ Phase 1-2 Complete
**Status**: Implemented. `Agent` and `Transaction` models complete.

**Components**:
- `transaction.rs`: Transaction state machine ✅ (21 tests passing)
- `agent.rs`: Agent state (balances, queues, limits) ✅ (17 tests passing)
- `state.rs`: SimulationState (placeholder, will extend in Phase 3)
- `enums.rs`: SettlementStatus, DropReason, Priority (future)
- `mod.rs`: Public model exports

**Key Invariants**:
- Transactions are immutable after creation (except settlement state) ✅
- All monetary values are i64 (cents/minor units) ✅
- State transitions are validated ✅

**Phase 3 Note**: `Agent.balance` represents bank's settlement account **at central bank**. No changes needed to Agent model for Phase 3.

**Why Rust**: Strong type system prevents invalid states; compile-time guarantees.

#### RNG Module (`backend/src/rng/`) ✅ Phase 1 Complete
**Status**: Implemented. Deterministic xorshift64* RNG complete.

**Components**:
- `xorshift.rs`: `RngManager` using xorshift64* ✅ (10 tests passing)
- `mod.rs`: Public RNG API

**Key Properties**:
- Seed persistence (state returned after each call) ✅
- Uniform, exponential, Poisson distributions ✅
- Deterministic replay (same seed → same sequence) ✅

**Why Rust**: RNG must be fast (called on every arrival); no GC pauses.

#### Core Module (`backend/src/core/`) ✅ Phase 1 Complete
**Status**: Implemented. Time management complete.

**Components**:
- `time.rs`: `TimeManager` for discrete ticks/days ✅ (6 tests passing)
- `init.rs`: State initialization (future)
- `mod.rs`: Public core API

**Why Rust**: Time management is used throughout the simulation loop.

#### Arrivals Module (`backend/src/arrivals/`) 🎯 Phase 5
**Status**: Not yet implemented. Planned for Phase 5.

**Responsibility**: Payment arrival generation

**Target Components** (Phase 5):
- `distributions.rs`: Normal, exponential, uniform distributions
- `generator.rs`: Arrival config, agent pool selection
- `mod.rs`: Public arrival API

**Target Operations** (Phase 5):
- Sample arrival time (exponential/Poisson)
- Sample amount (normal/uniform)
- Select sender/receiver from agent pool
- Assign rail, priority, deadline

**Why Rust**: High-frequency sampling; needs to be very fast.

#### Costs Module (`backend/src/costs/`) 🎯 Phase 5
**Status**: Not yet implemented. Planned for Phase 5.

**Responsibility**: Cost accrual (liquidity, delay, penalty)

**Components**:
- `accrual.rs`: Per-tick cost calculation
- `rates.rs`: Overdraft rates, collateral haircuts
- `mod.rs**: Public cost API

**Key Operations**:
- Accrue overdraft cost (peak net debit * rate * time)
- Accrue delay cost (unsettled value * time)
- Accrue penalty cost (missed deadline)

**Why Rust**: Cost calculations run every tick for every agent; needs to be efficient.

#### Logging Module (`backend/src/logging/`)
**Responsibility**: Structured event logging

**Components**:
- `events.rs`: Event types (ArrivalEvent, SettlementEvent, LSMEvent, etc.)
- `levels.rs`: Log levels (DEBUG, INFO, WARN, ERROR)
- `logger.rs`: Event logger (append-only log)
- `mod.rs`: Public logging API

**Key Properties**:
- Append-only (no overwrites)
- Structured (serializable events)
- Replay-friendly (deterministic ordering)

**Why Rust**: High-throughput logging; needs to be non-blocking.

#### Metrics Module (`backend/src/metrics/`)
**Responsibility**: Performance counters and profiling

**Components**:
- `performance.rs`: Timing, memory, throughput counters
- `mod.rs`: Public metrics API

**Key Metrics**:
- Ticks per second
- Settlements per tick
- LSM releases per tick
- Memory usage

**Why Rust**: Zero-overhead performance counters; no GC pauses.

### Python API Modules

#### Configuration (`api/config/`)
**Responsibility**: YAML loading, Pydantic validation

**Components**:
- `loader.py`: YAML parsing, environment variable substitution
- `schemas.py`: Pydantic models (SimulationConfig, AgentConfig, etc.)

**Key Features**:
- Type validation (Pydantic)
- Business rule validation (ranges, constraints)
- Default values and overrides

**Why Python**: Pydantic's ergonomics for validation; easy YAML handling.

#### Core (`api/core/`)
**Responsibility**: Python-side initialization and state management

**Components**:
- `initialization.py`: Config → Rust initialization
- `state.py`: Python wrapper for Rust SystemState

**Why Python**: Simplified config management; Python's dynamic typing for flexibility.

#### Payment Simulator API (`api/payment_simulator/`)
**Responsibility**: FastAPI application and routes

**Components**:
- `api/main.py`: FastAPI app, CORS, middleware
- `api/routes/`: REST endpoints (simulations, transactions, settlements, etc.)
- `api/services/`: Service layer (SimulationManager, etc.)
- `api/models.py`: Pydantic request/response models

**Key Endpoints**:
- POST `/simulations` - Create simulation
- POST `/simulations/{id}/start` - Start simulation
- POST `/simulations/{id}/tick` - Advance tick
- GET `/simulations/{id}/state` - Get state snapshot
- POST `/transactions` - Submit transaction
- GET `/settlements/bilateral-ledger` - Get bilateral ledger
- WS `/websocket` - Real-time updates

**Why Python**: FastAPI's async performance; easy WebSocket handling.

#### Backend Factory (`api/payment_simulator/backends/`)
**Responsibility**: FFI wrapper and backend abstraction

**Components**:
- `rust_ffi_wrapper.py`: PyO3 bindings wrapper
- `factory.py`: Backend selection (Rust vs. future alternatives)
- `protocol.py`: Abstract backend interface

**Key Responsibilities**:
- Type conversion (Python ↔ Rust)
- Error translation (Rust errors → Python exceptions)
- Lifetime management (Rust objects in Python)

**Why Python**: Flexible factory pattern; easy mocking for tests.

#### Testing (`api/tests/`)
**Responsibility**: Integration and E2E tests

**Components**:
- `unit/`: Unit tests (Python-side logic)
- `integration/`: Integration tests (FFI boundary, end-to-end flows)
- `e2e/`: Full API tests (HTTP + WebSocket)
- `performance/`: Benchmarks

**Key Test Types**:
- FFI correctness (Rust functions callable from Python)
- State conversion (Python → Rust → Python roundtrip)
- Determinism (same seed → same results)
- Performance (throughput, latency)

**Why Python**: Pytest's flexibility; Hypothesis for property-based testing.

### FFI Boundary Design

#### Type Mapping

| Python Type | Rust Type | Notes |
|-------------|-----------|-------|
| `int` | `i64` | All monetary values in cents |
| `str` | `String` | UTF-8 enforced |
| `float` | `f64` | Only for rates, not money |
| `bool` | `bool` | Direct mapping |
| `dict` | Struct | Pydantic model → Rust struct |
| `list` | `Vec<T>` | Homogeneous collections |
| `None` | `Option<T>` | Nullable types |

#### Error Handling

**Rust Side**:
```rust
pub enum SimulationError {
    InvalidConfig(String),
    SettlementFailed(String),
    InsufficientLiquidity(String),
}

impl From<SimulationError> for PyErr {
    fn from(err: SimulationError) -> PyErr {
        PyValueError::new_err(err.to_string())
    }
}
```

**Python Side**:
```python
try:
    backend.advance_tick()
except ValueError as e:
    logger.error(f"Rust error: {e}")
    raise HTTPException(status_code=400, detail=str(e))
```

#### Performance Considerations

1. **Minimize FFI crossings**: Batch operations when possible
2. **Zero-copy for large data**: Use memory views for arrays
3. **Avoid GIL contention**: Rust releases GIL during computation
4. **Lazy serialization**: Only convert data when requested by API

### Decision Type Separation (Unchanged from Original)

```rust
// Payment Decisions: Per transaction arrival (fire-and-forget)
payment_action = agent.policy.evaluate_payment(
    tx_context,      // This specific payment
    agent_state,
    public_signals
)
// Returns: PaymentAction (splits/attempts, priority)

// Liquidity Decisions: Per tick or threshold-based
if agent_state.needs_liquidity_review(tick) {
    liquidity_action = agent.policy.evaluate_liquidity(
        agent_state,
        public_signals
    )
    // Returns: LiquidityAction (collateral, overdraft target)
}

// Nostro Decisions: Per tick or threshold-based
if agent_state.needs_nostro_review(tick) {
    nostro_action = agent.policy.evaluate_nostro(
        agent_state,
        public_signals
    )
    // Returns: NostroAction (cross-rail transfers)
}
```

### Key Sequences

**1. Tick Loop (Rust Orchestrator)**
```
For each tick t:
1. Reset per-tick counters (ops capacity)
2. Generate new payment arrivals (RNG)
   - Sample arrival count (Poisson)
   - For each arrival, sample amount, sender, receiver, rail
   - Create Transaction with deadline
3. For each agent with new payments:
   - Evaluate payment policy (once per arrival, fire-and-forget)
   - Schedule execution attempts or splits
   - Store in agent's outgoing queue
4. For each agent:
   - Check if liquidity review needed
   - If yes, evaluate liquidity policy
   - Execute liquidity actions (collateral posting, overdraft adjustment)
5. Execute settlement attempts:
   - For each scheduled attempt:
     - Check balance + credit limit
     - If sufficient, settle immediately (RTGS)
     - If insufficient, add to LSM queue
6. Run LSM coordinator:
   - Bilateral netting pass
   - 3-cycle detection pass
   - 4-cycle detection pass
   - Release matched payments
7. For each agent:
   - Accrue costs (liquidity, delay)
   - Update RAG status
8. Log events (arrivals, settlements, LSM releases, costs)
9. Publish Update Pack to Python layer (if needed)
10. Check end-of-day conditions
```

**2. API Request Flow (Python → Rust → Python)**
```
1. Client sends HTTP POST to /simulations/{id}/tick
2. FastAPI route handler receives request
3. SimulationManager calls backend.advance_tick()
   ↓ (FFI crossing)
4. Rust orchestrator executes tick loop
5. Rust returns updated state (or error)
   ↑ (FFI crossing)
6. Python converts Rust state to Pydantic model
7. FastAPI serializes to JSON
8. Client receives response
```

**3. WebSocket Streaming (Python pulls from Rust)**
```
1. Client connects to /websocket
2. Python starts async loop:
   - Call backend.get_events_since(last_tick)
     ↓ (FFI crossing)
   - Rust returns event batch
     ↑ (FFI crossing)
   - Python serializes to JSON
   - Send to WebSocket
   - Sleep 100ms
   - Repeat
```

**4. Simulation Lifecycle**
```
1. POST /simulations with config
   - Python validates config (Pydantic)
   - Python calls backend.create_simulation(config)
     ↓ (FFI crossing)
   - Rust initializes SystemState
   - Rust returns simulation_id
     ↑ (FFI crossing)
   - Python stores simulation in manager

2. POST /simulations/{id}/start
   - Python calls backend.start_simulation()
   - Rust sets state to RUNNING

3. Loop: POST /simulations/{id}/tick
   - Python calls backend.advance_tick()
   - Rust executes tick loop

4. POST /simulations/{id}/stop
   - Python calls backend.stop_simulation()
   - Rust sets state to STOPPED

5. DELETE /simulations/{id}
   - Python calls backend.destroy_simulation()
   - Rust frees memory
```

---

## 6) Development Workflow

### Build System

**Rust Backend**:
```bash
# Build Rust crate
cd backend
cargo build --release

# Run Rust tests
cargo test

# Run Rust benchmarks
cargo bench

# Build Python extension
maturin build --release
```

**Python API**:
```bash
# Install in development mode (with editable Rust backend)
uv pip install -e ".[dev]"

# Run Python tests
pytest api/tests

# Run API server
uvicorn api.payment_simulator.api.main:app --reload
```

**Integrated Development**:
```bash
# Build everything and run tests
uv run maturin develop --release && uv run pytest
```

### Testing Strategy

**Rust Layer**:
- Unit tests: Test individual modules (transaction, agent, LSM)
- Integration tests: Test module interactions (settlement + LSM)
- Property tests: Test invariants (determinism, balance conservation)
- Benchmarks: Measure throughput (ticks/sec, settlements/tick)

**Python Layer**:
- Unit tests: Test Python-side logic (config validation, routing)
- Integration tests: Test FFI boundary (Python → Rust → Python)
- E2E tests: Test full API flows (HTTP + WebSocket)
- Property tests: Test API contracts (Hypothesis)

**FFI Boundary**:
- Roundtrip tests: Python → Rust → Python conversion
- Error propagation: Rust errors → Python exceptions
- Memory safety: No leaks, no dangling pointers
- Performance: Measure FFI overhead

### Development Phases

**Phase 1: Core Rust Backend** ✅ (Completed)
- Transaction model
- Agent model
- SystemState
- TimeManager
- RNG Manager
- Basic settlement

**Phase 2: Settlement & LSM** ✅ (Completed)
- RTGS settlement
- Bilateral netting
- Cycle detection (3-cycles, 4-cycles)
- Settlement failure handling

**Phase 3: Orchestrator & Arrivals** ✅ (Completed)
- Tick loop
- Arrival generation
- Policy evaluation coordination
- Cost accrual
- Event logging

**Phase 4: FFI & Python API** ✅ (Completed)
- PyO3 bindings
- Python wrapper
- FastAPI routes
- WebSocket streaming
- Config management

**Phase 5: Testing & Validation** 🚧 (In Progress)
- Integration tests
- E2E tests
- Performance benchmarks
- Determinism verification

**Phase 6: LLM Integration** 🔜 (Future)
- Policy DSL compiler
- Shadow replay validation
- LLM Manager service
- Git-based policy versioning

---

## 7) Performance Characteristics

### Rust Backend Performance

**Expected Throughput**:
- **Ticks per second**: 10,000-50,000 (no LSM)
- **Ticks per second**: 5,000-10,000 (with LSM)
- **Settlements per tick**: 100-1,000
- **Agents supported**: 10-100 (performance degrades O(n²) for LSM)

**Memory Usage**:
- **Per transaction**: ~200 bytes
- **Per agent**: ~1 KB (base) + queues
- **Total**: ~10-100 MB for typical scenario

**Bottlenecks**:
1. LSM cycle detection (O(n³) for 3-cycles)
2. Event logging (if synchronous)
3. FFI boundary (if called too frequently)

### Python API Performance

**Expected Latency**:
- **GET /simulations/{id}/state**: 1-5 ms
- **POST /simulations/{id}/tick**: 10-100 ms (depends on tick complexity)
- **WebSocket updates**: 100 Hz (10 ms interval)

**Bottlenecks**:
1. JSON serialization (Pydantic)
2. WebSocket send queue
3. FFI overhead (if called per-request)

### Optimization Strategies

1. **Batch FFI calls**: Advance N ticks in one call
2. **Lazy state conversion**: Only serialize state when requested
3. **Event buffering**: Collect events, send in batches
4. **Zero-copy views**: Use memory views for large arrays
5. **GIL release**: Rust computation doesn't block Python

---

## 8) Policy Framework

### Phase 4a: Trait-Based Policies (Implemented - 2025-10-27)

**Status**: ✅ Complete

Cash manager policies control **Queue 1** (internal bank queues), deciding **when** to submit transactions to the central RTGS system (Queue 2).

**Core Trait**:
```rust
pub trait CashManagerPolicy {
    fn evaluate_queue(
        &mut self,
        agent: &Agent,
        state: &SimulationState,
        tick: usize,
    ) -> Vec<ReleaseDecision>;
}
```

**Evaluation Semantics**:
- Called **every tick** for each agent (not fire-and-forget)
- Allows re-evaluation as conditions change (liquidity, deadlines, system state)
- Returns decisions: `SubmitFull`, `SubmitPartial`, `Hold`, `Drop`

**Three Baseline Policies**:
1. **FifoPolicy**: Submit all transactions immediately (simplest baseline)
2. **DeadlinePolicy**: Prioritize urgent transactions (deadline-aware)
3. **LiquidityAwarePolicy**: Preserve liquidity buffer, override for urgency

**Example: Liquidity-Aware Policy**:
```rust
impl CashManagerPolicy for LiquidityAwarePolicy {
    fn evaluate_queue(
        &mut self,
        agent: &Agent,
        state: &SimulationState,
        tick: usize,
    ) -> Vec<ReleaseDecision> {
        let mut decisions = Vec::new();

        for tx_id in agent.outgoing_queue() {
            let tx = state.get_transaction(tx_id).unwrap();
            let amount = tx.remaining_amount();
            let deadline = tx.deadline_tick();
            let ticks_remaining = deadline - tick;

            // Urgent: submit regardless of liquidity
            if ticks_remaining <= self.urgency_threshold {
                if agent.can_pay(amount) {
                    decisions.push(ReleaseDecision::SubmitFull {
                        tx_id: tx_id.clone()
                    });
                }
            }
            // Safe: maintains liquidity buffer
            else if agent.balance() - amount >= self.target_buffer {
                decisions.push(ReleaseDecision::SubmitFull {
                    tx_id: tx_id.clone()
                });
            }
            // Hold: preserve liquidity for now
            else {
                decisions.push(ReleaseDecision::Hold {
                    tx_id: tx_id.clone(),
                    reason: HoldReason::InsufficientLiquidity,
                });
            }
        }

        decisions
    }
}
```

**Decision Context Available to Policies**:
- **Agent state**: balance, credit, liquidity_pressure(), outgoing_queue(), expected_inflows
- **Transaction details**: amount, deadline, priority, sender/receiver
- **System signals**: total queue sizes, urgent transactions, agent congestion
- **Time**: current tick, time-to-deadline, time-to-EoD

**Test Status**: 12 policy tests passing (60 total tests)

**Documentation**: See `/docs/queue_architecture.md` and `/backend/CLAUDE.md`

---

### Phase 6: Policy DSL Layer (Future - Designed But Not Implemented)

**Status**: 📋 Designed, deferred to Phase 6

**Why Deferred**:
- Phase 4a trait-based implementation allows fast iteration and validation
- Proves the abstraction works before adding 2,000+ lines of DSL infrastructure
- DSL needed only when starting RL/LLM-driven policy optimization

**JSON Decision Tree Format (Future)**:
```json
{
  "version": "1.0",
  "tree_id": "liquidity_aware_policy",
  "root": {
    "type": "condition",
    "condition": {
      "op": "<=",
      "left": {"field": "ticks_to_deadline"},
      "right": {"value": 5}
    },
    "on_true": {
      "type": "action",
      "action": "Release",
      "parameters": {}
    },
    "on_false": {
      "type": "condition",
      "condition": {
        "op": ">=",
        "left": {"field": "balance"},
        "right": {
          "compute": {
            "op": "+",
            "left": {"field": "amount"},
            "right": {"param": "liquidity_buffer"}
          }
        }
      },
      "on_true": {
        "type": "action",
        "action": "Release"
      },
      "on_false": {
        "type": "action",
        "action": "Hold"
      }
    }
  },
  "parameters": {
    "liquidity_buffer": 100000
  }
}
```

**Key Features (Phase 6)**:
- LLM-editable (safe JSON manipulation, no code execution)
- Sandboxed interpreter (~2,000 lines Rust)
- Hot-reloadable (update policies without recompiling)
- Version-controlled (git tracks policy evolution)
- Hybrid execution: support both Rust traits and JSON DSL

**Hybrid Execution**:
```rust
pub enum PolicyExecutor {
    Trait(Box<dyn CashManagerPolicy>),  // Rust policies (fast, compile-time checked)
    Tree(TreeInterpreter),               // JSON DSL (LLM-editable)
}
```

**LLM Manager Service (Phase 6)**:
- Policy mutation prompting patterns
- Git-based version control for policy evolution
- Shadow replay validation (test new policy on historical episodes)
- Monte Carlo opponent sampling
- Guardband checking (performance regression detection)
- Rollback procedures

**Policy Validation Pipeline (Phase 6)**:
1. **Schema check**: JSON schema validation (structure correctness)
2. **Safety check**: No cycles, depth limits, division-by-zero protection
3. **Property test**: Fuzzing (no crashes on edge cases)
4. **Shadow replay**: Monte Carlo (performance impact estimation)
5. **Guardband check**: Live deployment (rollback if KPIs degrade)

**Shadow Replay Example (Phase 6)**:
```python
def validate_policy_change(old_policy, new_policy, history, n_samples=100):
    """
    Replay past episodes with new policy, sample opponent behaviors.

    Returns:
        (mean_cost_delta, std_cost_delta, pareto_dominated)
    """
    cost_deltas = []
    for episode in sample(history, n_samples):
        old_cost = replay_with_policy(episode, old_policy, sample_opponents())
        new_cost = replay_with_policy(episode, new_policy, sample_opponents())
        cost_deltas.append(new_cost - old_cost)

    mean_delta = np.mean(cost_deltas)
    std_delta = np.std(cost_deltas)
    pareto_dominated = all(d >= 0 for d in cost_deltas)

    return mean_delta, std_delta, pareto_dominated
```

**Complete DSL Specification**: See `/docs/policy_dsl_design.md` (to be created)

---

## 9) Data Models

### Core Types (Rust)

#### Transaction
```rust
pub struct Transaction {
    id: String,                         // Unique identifier
    sender_id: String,                  // Agent ID
    receiver_id: String,                // Agent ID
    rail_id: String,                    // Payment rail
    original_amount: i64,               // Cents
    remaining_amount: i64,              // Cents (decreases with partial settlement)
    settled_amount: i64,                // Cents (increases with partial settlement)
    arrival_tick: u32,                  // When payment arrived
    deadline_tick: u32,                 // Hard deadline
    priority: Priority,                 // URGENT, NORMAL, LOW
    divisible: bool,                    // Can be split?
    settlement_tick: Option<u32>,       // When fully settled
    settlement_status: SettlementStatus,// PENDING, PARTIALLY_SETTLED, SETTLED, DROPPED
    drop_reason: Option<DropReason>,    // If dropped
    parent_id: Option<String>,          // If split from another tx
}
```

#### Agent
```rust
pub struct Agent {
    id: String,
    opening_balance: i64,               // Cents
    current_balance: i64,               // Cents (updated during day)
    peak_net_debit: i64,                // Most negative balance (tracking)
    overdraft_limit: i64,               // Maximum negative balance allowed
    collateral_posted: i64,             // Collateral value (haircut-adjusted)
    outgoing_queue: Vec<Transaction>,   // Scheduled payments
    incoming_queue: Vec<Transaction>,   // Awaiting receipt
    bilateral_caps: HashMap<String, i64>, // Agent ID → max net exposure
    throughput_target: Option<f64>,     // E.g., 0.5 = 50% by noon
    target_tick: Option<u32>,           // When throughput target applies
}
```

#### SystemState
```rust
pub struct SystemState {
    time_manager: TimeManager,
    agents: HashMap<String, Agent>,
    transactions: HashMap<String, Transaction>,
    bilateral_ledger: HashMap<(String, String), i64>, // Net positions
    lsm_queue: Vec<String>,             // Transaction IDs awaiting LSM
    event_log: Vec<Event>,
    rng_manager: RngManager,
    config: SimulationConfig,
}
```

### API Models (Python/Pydantic)

#### SimulationConfig
```python
class SimulationConfig(BaseModel):
    ticks_per_day: int = Field(ge=1, le=1000)
    num_days: int = Field(ge=1)
    agents: List[AgentConfig]
    arrivals: List[ArrivalConfig]
    market: MarketConfig
    lsm_enabled: bool = True
```

#### AgentConfig
```python
class AgentConfig(BaseModel):
    id: str
    opening_balance: int = Field(ge=0)
    overdraft_limit: int = Field(ge=0)
    collateral: Optional[CollateralConfig]
    throughput_target: Optional[float] = Field(ge=0.0, le=1.0)
    target_tick: Optional<int> = Field(ge=0)
```

#### TransactionResponse
```python
class TransactionResponse(BaseModel):
    id: str
    sender_id: str
    receiver_id: str
    original_amount: int
    remaining_amount: int
    settled_amount: int
    settlement_status: str
    arrival_tick: int
    deadline_tick: int
    settlement_tick: Optional[int]
```

---

## 10) Event Schema (Rust)

### Event Types

```rust
pub enum Event {
    ArrivalEvent {
        tick: u32,
        tx_id: String,
        sender_id: String,
        receiver_id: String,
        amount: i64,
        rail_id: String,
        priority: Priority,
        deadline_tick: u32,
    },
    
    SettlementEvent {
        tick: u32,
        tx_id: String,
        amount: i64,  // May be partial
        sender_balance_after: i64,
        receiver_balance_after: i64,
    },
    
    LSMReleaseEvent {
        tick: u32,
        mechanism: LSMMechanism,  // BILATERAL, CYCLE_3, CYCLE_4
        tx_ids: Vec<String>,
        total_value_released: i64,
    },
    
    CostAccrualEvent {
        tick: u32,
        agent_id: String,
        liquidity_cost: i64,
        delay_cost: i64,
        penalty_cost: i64,
    },
    
    DropEvent {
        tick: u32,
        tx_id: String,
        reason: DropReason,  // DEADLINE_MISSED, CAP_BREACH, etc.
    },
    
    PolicyUpdateEvent {
        tick: u32,
        agent_id: String,
        policy_version: String,  // Git commit hash
        change_type: String,  // STRUCTURAL, PARAMETER
    },
}
```

### Event Log Format

**Append-only log** (Rust Vec, optionally serialized to Parquet):
```
[tick, event_type, event_data]
[0, "arrival", {"tx_id": "tx001", "sender": "A", ...}]
[0, "arrival", {"tx_id": "tx002", "sender": "B", ...}]
[1, "settlement", {"tx_id": "tx001", "amount": 1000, ...}]
[1, "lsm_release", {"mechanism": "bilateral", "tx_ids": ["tx002", "tx003"], ...}]
...
```

---

## 11) Metrics & KPIs

### Agent-Level Metrics (Rust)

```rust
pub struct AgentMetrics {
    // Liquidity
    peak_net_debit: i64,
    average_balance: f64,
    headroom_utilization: f64,
    
    // Costs
    total_liquidity_cost: i64,
    total_delay_cost: i64,
    total_penalty_cost: i64,
    
    // Throughput
    value_arrived: i64,
    value_settled: i64,
    throughput_ratio: f64,
    
    // Timeliness
    average_settlement_delay: f64,
    on_time_percentage: f64,
    
    // Settlement
    num_settled: u32,
    num_dropped: u32,
    num_partially_settled: u32,
}
```

### System-Level Metrics (Rust)

```rust
pub struct SystemMetrics {
    // Throughput
    total_value_arrived: i64,
    total_value_settled: i64,
    system_throughput: f64,
    
    // LSM Efficacy
    value_released_bilateral: i64,
    value_released_3cycle: i64,
    value_released_4cycle: i64,
    lsm_efficiency_ratio: f64,
    
    // Gridlock
    gridlock_ticks: u32,  // Ticks with no settlements
    max_queue_depth: u32,
    
    // Performance
    ticks_per_second: f64,
    settlements_per_tick: f64,
}
```

---

## 12) Testing Strategy

### Rust Tests

#### Unit Tests (in each module)
```rust
// backend/src/models/transaction.rs
#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn transaction_creation_defaults() {
        let tx = Transaction::new(...);
        assert_eq!(tx.remaining_amount(), tx.original_amount());
        assert!(tx.settlement_status().is_pending());
    }
    
    #[test]
    fn transaction_full_settlement() {
        let mut tx = Transaction::new(...);
        tx.settle(tx.original_amount(), 3).unwrap();
        assert_eq!(tx.remaining_amount(), 0);
        assert_eq!(tx.settlement_status(), SettlementStatus::Settled);
    }
}
```

#### Integration Tests (in backend/tests/)
```rust
// backend/tests/settlement_core.rs
#[test]
fn settlement_with_insufficient_liquidity() {
    let mut state = SystemState::new(...);
    let tx = Transaction::new(sender: "A", receiver: "B", amount: 1000, ...);
    
    // Set sender balance to 500 (insufficient)
    state.agents.get_mut("A").unwrap().current_balance = 500;
    
    let result = state.settle_transaction(&tx);
    assert!(result.is_err());
    assert_eq!(state.agents.get("A").unwrap().current_balance, 500);  // Unchanged
}
```

#### Property Tests (using quickcheck or proptest)
```rust
use proptest::prelude::*;

proptest! {
    #[test]
    fn balance_conservation(
        initial_balance in 0i64..1_000_000,
        tx_amount in 0i64..1_000_000,
    ) {
        let mut state = SystemState::new(...);
        state.agents.get_mut("A").unwrap().current_balance = initial_balance;
        state.agents.get_mut("B").unwrap().current_balance = 0;
        
        let total_before = state.total_balance();
        
        if tx_amount <= initial_balance {
            let tx = Transaction::new(sender: "A", receiver: "B", amount: tx_amount, ...);
            state.settle_transaction(&tx).unwrap();
        }
        
        let total_after = state.total_balance();
        assert_eq!(total_before, total_after);
    }
}
```

### Python Tests

#### Unit Tests (pytest)
```python
# api/tests/unit/test_config.py
def test_simulation_config_validation():
    config = SimulationConfig(
        ticks_per_day=100,
        num_days=1,
        agents=[AgentConfig(id="A", opening_balance=10000)],
        arrivals=[],
        market=MarketConfig(),
    )
    assert config.ticks_per_day == 100
    
def test_simulation_config_invalid_ticks():
    with pytest.raises(ValidationError):
        SimulationConfig(ticks_per_day=0, ...)  # Must be >= 1
```

#### Integration Tests (pytest + Rust backend)
```python
# api/tests/integration/test_rust_ffi_integration.py
def test_rust_backend_create_simulation():
    config = SimulationConfig(...)
    backend = RustBackend()
    sim_id = backend.create_simulation(config)
    assert sim_id is not None
    
def test_rust_backend_advance_tick():
    backend = RustBackend()
    sim_id = backend.create_simulation(config)
    
    initial_tick = backend.get_current_tick(sim_id)
    backend.advance_tick(sim_id)
    final_tick = backend.get_current_tick(sim_id)
    
    assert final_tick == initial_tick + 1
```

#### E2E Tests (httpx + WebSocket)
```python
# api/tests/e2e/test_api_simulation_lifecycle.py
async def test_simulation_lifecycle():
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # Create simulation
        response = await client.post("/simulations", json=config_dict)
        assert response.status_code == 200
        sim_id = response.json()["id"]
        
        # Start simulation
        response = await client.post(f"/simulations/{sim_id}/start")
        assert response.status_code == 200
        
        # Advance tick
        response = await client.post(f"/simulations/{sim_id}/tick")
        assert response.status_code == 200
        
        # Get state
        response = await client.get(f"/simulations/{sim_id}/state")
        assert response.status_code == 200
        state = response.json()
        assert state["current_tick"] == 1
```

---

## 13) Deployment Architecture (Future)

### Container Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Container 1: API Server (Python)                       │
│  - FastAPI + Uvicorn                                    │
│  - Gunicorn for multi-worker                            │
│  - Linked to libpayment_simulator_core_rs.so (Rust)    │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│  Container 2: Redis (Message Queue)                     │
│  - Event streaming                                      │
│  - LLM update pub/sub                                   │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│  Container 3: LLM Manager (Future)                      │
│  - Policy generation                                    │
│  - Shadow replay validation                             │
│  - Git service (policy versioning)                      │
└─────────────────────────────────────────────────────────┘
```

### Kubernetes Deployment (Future)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-simulator-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: payment-simulator
  template:
    metadata:
      labels:
        app: payment-simulator
    spec:
      containers:
      - name: api
        image: payment-simulator:latest
        ports:
        - containerPort: 8000
        env:
        - name: RUST_BACKEND
          value: "enabled"
        resources:
          limits:
            memory: "2Gi"
            cpu: "1"
```

---

## 14) Monitoring & Observability

### Metrics to Collect

**System Metrics**:
- CPU usage (per container)
- Memory usage (per container)
- Request latency (P50, P95, P99)
- Request rate (requests/sec)
- Error rate (errors/sec)

**Simulation Metrics**:
- Ticks per second (throughput)
- Settlements per tick
- LSM releases per tick
- Queue depth (current, max)

**Business Metrics**:
- Total value settled (per day)
- System throughput ratio
- Gridlock frequency (gridlock ticks / total ticks)
- Average settlement delay

### Logging Strategy

**Rust Side**:
- Structured logging (JSON)
- Log levels: DEBUG, INFO, WARN, ERROR
- Event log (append-only, deterministic)

**Python Side**:
- uvicorn access logs
- FastAPI request/response logs
- Error logs with stack traces

**Centralized Logging** (Future):
- ELK stack (Elasticsearch, Logstash, Kibana)
- Or Grafana Loki + Promtail

---

## 15) Security Considerations

### FFI Safety

1. **Memory safety**: Rust's ownership system prevents use-after-free
2. **Type safety**: PyO3 enforces type conversions
3. **Error handling**: Rust panics caught by PyO3, converted to Python exceptions
4. **No unsafe blocks**: Avoid `unsafe` unless absolutely necessary

### API Security

1. **Authentication**: JWT tokens (future)
2. **Authorization**: Role-based access control (future)
3. **Rate limiting**: Per-client rate limits
4. **Input validation**: Pydantic schemas prevent injection
5. **CORS**: Restrict origins in production

### Simulation Integrity

1. **Determinism**: Seed-based RNG prevents non-deterministic behavior
2. **Replay protection**: Event log integrity (checksums, signatures)
3. **Policy versioning**: Git commit hashes for audit trail

---

## 16) RNG Details (Deterministic Randomness)

### xorshift64* Implementation (Rust)

```rust
pub struct RngManager {
    state: u64,
}

impl RngManager {
    pub fn new(seed: u64) -> Self {
        let state = if seed == 0 { 1 } else { seed };
        RngManager { state }
    }
    
    pub fn next(&mut self) -> u64 {
        let mut x = self.state;
        x ^= x << 13;
        x ^= x >> 7;
        x ^= x << 17;
        self.state = x;
        x
    }
    
    pub fn uniform(&mut self) -> f64 {
        (self.next() as f64) / (u64::MAX as f64)
    }
    
    pub fn exponential(&mut self, rate: f64) -> f64 {
        -self.uniform().ln() / rate
    }
    
    pub fn poisson(&mut self, lambda: f64) -> u32 {
        let mut count = 0;
        let mut p = 1.0;
        let threshold = (-lambda).exp();
        
        while p > threshold {
            p *= self.uniform();
            count += 1;
        }
        
        count - 1
    }
}
```

**Key Properties**:
- **Fast**: ~1-2 ns per call
- **Deterministic**: Same seed → same sequence
- **Sufficient quality**: Passes basic statistical tests (not cryptographic)

**Seed Persistence**:
```rust
// After every RNG call, return new seed
let (new_seed, value) = rng.next_with_seed(old_seed);
state.rng_seed = new_seed;  // MUST persist
```

---

## 17) Research Questions & Experiments

(Unchanged from original - see sections 17-19 in original plan)

---

## 18) Migration Path (Original Python → Rust)

### What Was Migrated

**Phase 1: Core Data Structures**
- Transaction model → `backend/src/models/transaction.rs`
- Agent model → `backend/src/models/agent.rs`
- SystemState → `backend/src/models/state.rs`

**Phase 2: Time & RNG**
- TimeManager → `backend/src/core/time.rs`
- RngManager → `backend/src/rng/manager.rs`

**Phase 3: Settlement**
- RTGS settlement → `backend/src/settlement/core.rs`
- Bilateral caps → `backend/src/settlement/caps.rs`
- Failure handling → `backend/src/settlement/failure.rs`

**Phase 4: LSM**
- Bilateral netting → `backend/src/lsm/bilateral.rs`
- Cycle detection → `backend/src/lsm/cycle.rs`
- Coordinator → `backend/src/lsm/coordinator.rs`

**Phase 5: Orchestrator**
- Tick loop → `backend/src/orchestrator/engine.rs`
- Arrival generation → `backend/src/arrivals/generator.rs`

**Phase 6: FFI**
- PyO3 bindings → `backend/src/lib.rs`
- Python wrapper → `api/payment_simulator/backends/rust_ffi_wrapper.py`

### What Remained in Python

- FastAPI application (`api/payment_simulator/api/`)
- Configuration management (`api/config/`, `api/payment_simulator/config/`)
- Test infrastructure (`api/tests/`)
- Service layer (`api/payment_simulator/api/services/`)

### Performance Improvements

| Component | Python (ms) | Rust (ms) | Speedup |
|-----------|-------------|-----------|---------|
| Tick loop (1000 ticks) | 5000 | 50 | 100x |
| Settlement (1000 tx) | 200 | 2 | 100x |
| LSM bilateral (100 agents) | 500 | 5 | 100x |
| LSM 3-cycle (100 agents) | 2000 | 20 | 100x |

---

## 19) Future Work

### Short Term (Next 3 Months)
1. Complete integration test suite
2. Performance benchmarking and optimization
3. WebSocket streaming improvements
4. API documentation (OpenAPI/Swagger)

### Medium Term (3-6 Months)
1. Policy DSL compiler (Rust)
2. Shadow replay validation (Python + Rust)
3. LLM Manager service (Python)
4. Git-based policy versioning

### Long Term (6-12 Months)
1. Multi-currency support
2. CLS-style PvP mechanism
3. Dynamic agent creation/deletion
4. Federated learning (multi-agent RL)

---

## 20) References & Prior Art

(Unchanged from original plan)

### Academic Literature
- Bech, M. L., & Garratt, R. (2003). "The intraday liquidity management game." *Journal of Economic Theory*
- Koponen, R., & Soramäki, K. (2005). "Intraday liquidity needs in a modern interbank payment system"
- Martin, A., & McAndrews, J. (2008). "Liquidity-saving mechanisms." *Journal of Monetary Economics*

### Industry Standards
- CPMI (2013). "Principles for financial market infrastructures" (PFMI)
- FSB (2017). "Guidance on Central Counterparty Resolution and Resolution Planning"
- ISO 20022 Payment messaging standards

### Related Projects
- Bank of England RTGS Renewal Programme
- ECB TARGET2 documentation
- Federal Reserve Fedwire Funds Service
- CLS settlement system (PvP mechanism)

### Technical Inspirations
- AlphaGo/AlphaZero (self-play policy improvement)
- OpenAI Dota 2 (multi-agent coordination)
- DeepMind AlphaDev (code optimization via RL)

---

## 21) Glossary Updates

| Term | Definition |
|------|------------|
| **PyO3** | Rust library for creating Python bindings |
| **Maturin** | Build tool for Rust Python extensions |
| **FFI** | Foreign Function Interface; boundary between Rust and Python |
| **Zero-cost abstraction** | Rust design principle: abstractions with no runtime overhead |
| **xorshift64*** | Fast, deterministic PRNG algorithm |
| **GIL** | Global Interpreter Lock; Python's concurrency limitation (Rust releases it) |
| **Editable install** | Development mode where changes to code take effect without reinstall |
| **Property-based testing** | Testing strategy that validates invariants across random inputs |

---

## 22) Critical Invariants & Pitfalls

### Critical Invariants

1. **Determinism**: All randomness via seeded RNG; same inputs → same outputs
2. **Balance conservation**: Total system balance never changes (except arrivals/settlements)
3. **Agent-local validation**: Shadow replay only validates agent-controllable metrics
4. **Asynchronous learning**: LLM Manager never blocks simulation tick loop
5. **Once-on-arrival**: Payment policies evaluate once when payment arrives
6. **Integer arithmetic**: All monetary values in minor units (cents/pence)
7. **Per-priority LSM**: LSM operates independently per priority class
8. **Seed persistence**: New seed must be saved after every RNG call
9. **FFI safety**: No undefined behavior across Rust-Python boundary
10. **Memory ownership**: Rust owns simulation state; Python only holds references

### Common Pitfalls

1. **Forgetting to persist new RNG seed** → Non-deterministic replay
2. **Using float for money** → Rounding errors, type contamination
3. **Re-evaluating payment policies** → Breaks action schema semantics
4. **Validating system metrics in shadow replay** → Impossible in multi-agent system
5. **Running LLM synchronously** → Simulation becomes unusably slow
6. **Using nested attribute access in expressions** → Evaluator crash
7. **Confusing splits and execution attempts** → Invalid actions for indivisible payments
8. **Crossing FFI boundary too frequently** → Performance degradation
9. **Holding Python references to Rust objects** → Memory leaks
10. **Panicking in Rust without PyO3 catch** → Python process crash

---

## 23) Development Best Practices

### Rust Development

1. **Use `cargo clippy`**: Catch common mistakes
2. **Use `cargo fmt`**: Consistent code formatting
3. **Write unit tests first**: TDD for new features
4. **Avoid `unsafe`**: Only when necessary, document why
5. **Benchmark critical paths**: Use `cargo bench`
6. **Profile before optimizing**: Use `perf` or `flamegraph`

### Python Development

1. **Type hints everywhere**: Use `mypy` for type checking
2. **Use Pydantic for validation**: Don't trust user input
3. **Async where appropriate**: Use `async`/`await` for I/O
4. **Test FFI boundary**: Integration tests for every Rust function
5. **Mock Rust backend for unit tests**: Don't require Rust for all tests

### FFI Development

1. **Minimize crossings**: Batch operations when possible
2. **Validate at boundary**: Check types and ranges before crossing
3. **Handle errors gracefully**: Convert Rust errors to Python exceptions
4. **Document ownership**: Who owns what, when
5. **Test memory safety**: Use valgrind, ASAN, MSAN

---

## Appendix A: Build System Details

### Maturin Configuration

**`pyproject.toml`**:
```toml
[build-system]
requires = ["maturin>=1.9.6"]
build-backend = "maturin"

[tool.maturin]
python-source = "api"
module-name = "payment_simulator_core_rs"
```

**Build Commands**:
```bash
# Development build (with debug symbols)
maturin develop

# Release build (optimized)
maturin develop --release

# Build wheel
maturin build --release

# Install wheel
pip install target/wheels/payment_simulator_core_rs-*.whl
```

### Cargo Configuration

**`backend/Cargo.toml`**:
```toml
[package]
name = "payment-simulator-core-rs"
version = "0.1.0"
edition = "2021"

[lib]
name = "payment_simulator_core_rs"
crate-type = ["cdylib"]  # For Python extension

[dependencies]
pyo3 = { version = "0.22", features = ["extension-module"] }

[profile.release]
opt-level = 3
lto = true
codegen-units = 1
```

---

## Appendix B: API Endpoints Reference

### Simulations

```
POST   /simulations              Create simulation
GET    /simulations/{id}         Get simulation info
DELETE /simulations/{id}         Delete simulation
POST   /simulations/{id}/start   Start simulation
POST   /simulations/{id}/stop    Stop simulation
POST   /simulations/{id}/reset   Reset simulation
POST   /simulations/{id}/tick    Advance one tick
GET    /simulations/{id}/state   Get state snapshot
```

### Transactions

```
POST   /transactions             Submit transaction
GET    /transactions/{id}        Get transaction details
GET    /transactions             Query transactions (filters)
GET    /transactions/statistics  Get transaction statistics
```

### Settlements

```
GET    /settlements/bilateral-ledger    Get bilateral ledger
GET    /settlements/history             Get settlement history
GET    /settlements/statistics          Get settlement statistics
```

### LSM

```
GET    /lsm/statistics          Get LSM statistics
GET    /lsm/queue               Get LSM queue state
```

### KPIs

```
GET    /kpis/costs              Get cost breakdown
GET    /kpis/throughput         Get throughput metrics
GET    /kpis/liquidity          Get liquidity metrics
```

### Queue

```
GET    /queue/state             Get queue state
GET    /queue/history           Get queue history
```

### System

```
GET    /system/health           Health check
GET    /system/metrics          System metrics
```

### WebSocket

```
WS     /websocket               Real-time updates stream
```

---

## Appendix C: Testing Checklist

### Rust Tests

- [ ] Unit tests for all modules (100% coverage)
- [ ] Integration tests for module interactions
- [ ] Property tests for invariants (determinism, balance conservation)
- [ ] Benchmarks for critical paths (tick loop, settlement, LSM)
- [ ] Fuzz tests for edge cases

### Python Tests

- [ ] Unit tests for configuration validation
- [ ] Unit tests for service layer logic
- [ ] Integration tests for FFI boundary
- [ ] E2E tests for all API endpoints
- [ ] WebSocket streaming tests
- [ ] Load tests (concurrent requests)

### FFI Tests

- [ ] Roundtrip tests (Python → Rust → Python)
- [ ] Error propagation tests
- [ ] Memory leak tests (valgrind)
- [ ] Type safety tests (invalid inputs)
- [ ] Performance tests (FFI overhead)

### System Tests

- [ ] Determinism verification (replay)
- [ ] Multi-day simulation tests
- [ ] Shock scenario tests
- [ ] Gridlock recovery tests
- [ ] Policy convergence tests

---

*End of Project Plan*