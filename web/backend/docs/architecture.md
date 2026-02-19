# Technical Architecture

*A comprehensive guide to SimCash's hybrid Rust–Python architecture for software architects.*

---

## 1. System Overview

SimCash simulates high-value Real-Time Gross Settlement (RTGS) payment operations between banks. It models how cash managers strategically time and fund outgoing payments during the business day, balancing liquidity costs, payment deadlines, gridlock avoidance, and system throughput.

The system is built on a **three-tier hybrid architecture**:

```
┌─────────────────────────────────────────────────────────┐
│  Presentation Layer                                     │
│  • Web Frontend (React + TypeScript + Vite)             │
│  • CLI (Typer) — payment-sim run / replay / db          │
│  • REST API (FastAPI) — programmatic control             │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP / WS / CLI
┌──────────────────────▼──────────────────────────────────┐
│  Python Orchestration Layer                             │
│  • Configuration validation (Pydantic)                  │
│  • Execution engine (SimulationRunner + OutputStrategy) │
│  • Persistence (DuckDB, EventWriter, Replay)            │
│  • LLM integration (PolicyOptimizer, experiments)       │
└──────────────────────┬──────────────────────────────────┘
                       │ PyO3 FFI (simple types only)
┌──────────────────────▼──────────────────────────────────┐
│  Rust Core Engine                                       │
│  • Orchestrator tick loop                               │
│  • RTGS settlement + LSM optimisation                   │
│  • Policy decision-tree evaluation                      │
│  • Deterministic RNG (xorshift64*)                      │
│  • i64 integer arithmetic — no floats for money         │
└─────────────────────────────────────────────────────────┘
```

### Why Rust + Python?

| Language | Responsibility | Rationale |
|----------|---------------|-----------|
| **Rust** | Simulation engine | Performance-critical tick loop (1,200+ ticks/sec), deterministic execution, memory safety, zero-cost abstractions |
| **Python** | Orchestration & interfaces | Developer ergonomics, rich ecosystem (Pydantic, FastAPI, Polars, DuckDB), rapid iteration on configs and analysis |

### Core Design Principles

1. **Rust owns state; Python orchestrates.** Python never holds mutable references into Rust memory — only snapshots and copies.
2. **FFI boundary is minimal.** Only primitives, strings, lists, and dicts cross the boundary. One FFI call per tick, not per transaction.
3. **Money is `i64`.** All monetary values are 64-bit signed integers representing cents. No floating-point arithmetic, no rounding errors.
4. **Determinism is sacred.** `seed + config → identical execution trace`, always. The RNG is xorshift64\*, and seeds are persisted after every use.
5. **Replay identity.** Running a simulation with `--verbose --persist` and replaying from the database produce byte-identical output.

---

## 2. The Rust Core Engine

The Rust engine comprises ~10,000 lines across 8 modules: **core**, **models**, **orchestrator**, **settlement**, **rng**, **policy**, **arrivals**, **events**, and **ffi**.

### 2.1 Orchestrator & Tick Loop

The `Orchestrator` is the central coordinator. It owns all simulation state and advances the simulation one tick at a time:

```
tick() →
  1. Advance time
  2. Check end-of-day → reset daily state if needed
  3. Generate transaction arrivals (Poisson-sampled)
  4. Entry Disposition Offsetting (EDO)
  5. For each agent: evaluate policy → collect ReleaseDecisions
  6. RTGS immediate settlement (FIFO from Queue 2)
  7. LSM optimisation (bilateral offset → multilateral cycle detection)
  8. Cost accrual (overdraft, delay, collateral)
  9. Drop expired transactions
  10. Log events → return TickResult
```

The `Orchestrator` struct holds:

| Field | Type | Purpose |
|-------|------|---------|
| `state` | `SimulationState` | All agents, transactions, queues, event log |
| `rng` | `RngManager` | Seeded xorshift64\* generator |
| `time` | `TimeManager` | Tick/day tracking (`current_tick / ticks_per_day`) |
| `policies` | `HashMap<String, Policy>` | Per-agent cash management policies |
| `arrival_generators` | `HashMap<String, ArrivalGenerator>` | Per-agent transaction generators |
| `config` | `OrchestratorConfig` | Immutable simulation parameters |

Each `tick()` call returns a `TickResult` dict containing tick number, day, arrival/settlement counts, queue sizes, costs, and the full event list.

### 2.2 State Management

`SimulationState` is the container for all mutable state:

- **`agents`**: `BTreeMap<String, Agent>` — O(log n) sorted access to bank entities.
- **`transactions`**: `BTreeMap<String, Transaction>` — all payment instructions, keyed by UUID.
- **`rtgs_queue`**: `Vec<String>` — Queue 2 (central RTGS settlement queue), transaction IDs in submission order.
- **`event_log`**: `EventLog` — append-only vector of 50+ event types.
- **`queue2_index`**: `AgentQueueIndex` — HashMap providing O(1) lookup of an agent's Queue 2 transactions with cached metrics.

### 2.3 Deterministic RNG

All randomness flows through `RngManager`, a xorshift64\* implementation:

```rust
fn next(&mut self) -> u64 {
    self.state ^= self.state >> 12;
    self.state ^= self.state << 25;
    self.state ^= self.state >> 27;
    self.state.wrapping_mul(0x2545F4914F6CDD1D)
}
```

The RNG provides `range()`, `poisson()`, `normal()`, `lognormal()`, and `next_f64()` — all derived from a single state word. The state is persisted after every call, ensuring that `seed + config` always produces an identical execution trace. The algorithm passes TestU01's BigCrush statistical tests.

### 2.4 Integer Money (`i64`)

**All** monetary values are `i64` (signed 64-bit integers) representing cents:

```rust
let amount: i64 = 100_000; // $1,000.00
// FORBIDDEN: let amount: f64 = 1000.00;
```

This eliminates floating-point rounding errors that compound over millions of transactions, guarantees exact arithmetic, and provides faster, deterministic operations. The only place `f64` appears is in cost-rate parameters (basis points) and RNG distribution parameters — never in balances or amounts.

### 2.5 Settlement Engines

Settlement is a two-stage process:

**RTGS Immediate**: Process Queue 2 in FIFO order. If `sender.can_pay(amount)`, debit sender, credit receiver, mark settled. Otherwise the transaction remains queued.

**LSM Optimisation** (three algorithms, applied sequentially to remaining Queue 2 items):
1. **Algorithm 1 — FIFO re-sweep**: Simple second pass.
2. **Algorithm 2 — Bilateral offset**: For each A↔B pair, net opposing flows. E.g., A→B $100 and B→A $80 settle with only $20 liquidity instead of $180.
3. **Algorithm 3 — Multilateral cycle detection**: Find cycles (A→B→C→A) using graph algorithms (O(V+E)), compute net positions, and settle the cycle using only the maximum single-party outflow.

---

## 3. FFI Boundary: Python ↔ Rust

SimCash uses **PyO3** to compile the Rust engine as a native Python extension module (`payment_simulator_core_rs`). The FFI boundary follows strict rules:

### 3.1 Type Constraints

Only simple types cross the boundary:

| Direction | Allowed | Forbidden |
|-----------|---------|-----------|
| Python → Rust | `int`, `float`, `str`, `bool`, `list`, `dict` | Python classes, closures, references, complex objects |
| Rust → Python | `i64`, `f64`, `String`, `bool`, `Vec`, `HashMap` → converted to Python dicts/lists | Rust references, `&mut`, interior mutability |

### 3.2 `PyOrchestrator` Wrapper

The `PyOrchestrator` `#[pyclass]` wraps the Rust `Orchestrator` and exposes these methods:

| Method | Signature | Description |
|--------|-----------|-------------|
| `new()` | `config: &PyDict → PyResult<Self>` | Parse config dict → create Orchestrator |
| `tick()` | `→ PyResult<PyObject>` | Execute one tick, return result dict |
| `current_tick()` | `→ usize` | Current tick number |
| `current_day()` | `→ usize` | Current business day |
| `get_agent_balance()` | `agent_id: &str → PyResult<i64>` | Query agent balance |
| `get_tick_events()` | `tick: usize → PyResult<PyObject>` | Events at a specific tick |
| `get_all_events()` | `→ PyResult<PyObject>` | All accumulated events |
| `checkpoint()` | `path: &str → PyResult<()>` | Serialize state to file |
| `restore()` | `path: &str → PyResult<Self>` | Deserialize state from file |

### 3.3 Config Parsing

Configuration flows: **YAML → PyYAML → Pydantic validation → Python dict → FFI → `parse_orchestrator_config()` → Rust structs**. Helper functions `extract_required()` and `extract_with_default()` provide type-safe extraction from `PyDict` with clear error messages.

Policy trees enter the engine as JSON strings: `{"type": "InlineJson", "json_string": "..."}` on the agent config. The Rust side parses, validates, and compiles the tree into an executable `TreePolicy`.

### 3.4 Error Propagation

Rust errors map to Python exceptions:

| Rust Error | Python Exception |
|------------|-----------------|
| `SimulationError::AgentNotFound` | `KeyError` |
| `SimulationError::InvalidConfiguration` | `ValueError` |
| `SimulationError::InsufficientLiquidity` | `RuntimeError` |
| `SettlementError::*` | `RuntimeError` |

### 3.5 Safety Guarantees

- **Ownership**: `PyOrchestrator` owns the `Orchestrator`. Rust state lives exactly as long as the Python wrapper.
- **No cross-references**: Python never holds references into Rust memory. All queries return owned copies.
- **Batch operations**: One `tick()` FFI call processes all arrivals, policies, settlements, and costs — not one call per transaction.
- **Validated inputs**: All configuration is validated by Pydantic before crossing the FFI boundary.

FFI overhead is approximately **~10μs per method call**, **~1μs per event serialisation**, and **~0.5μs per list item**. This is negligible compared to the ~800μs typical tick computation.

---

## 4. Domain Models

### 4.1 Agent (Bank)

An `Agent` represents a participating bank with:

- **`balance: i64`** — central bank settlement account (cents).
- **`outgoing_queue: Vec<String>`** — Queue 1 (internal), transactions awaiting policy release.
- **`posted_collateral: i64`** — secured collateral, contributing to credit limit via `(1 - haircut) * collateral`.
- **`unsecured_cap: i64`** — maximum unsecured overdraft.
- **`release_budget_remaining: i64`** — per-tick budget set by `bank_tree` policy.
- **`state_registers: HashMap<String, f64>`** — up to 10 named registers for policy memory across ticks.
- **`bilateral_limits: HashMap<String, i64>`** — TARGET2-style per-counterparty outflow caps.

**Available liquidity** = `balance + unsecured_cap + collateral_credit`. Debit/credit operations enforce balance conservation atomically.

### 4.2 Transaction

A `Transaction` represents a payment instruction with full lifecycle tracking:

- **Amount tracking**: `amount` (original) and `remaining_amount` (unsettled). All `i64` cents.
- **Temporal**: `arrival_tick`, `deadline_tick`, `rtgs_submission_tick`.
- **Dual priority**: internal `priority: u8` (0–10) and `rtgs_priority: Option<RtgsPriority>` (HighlyUrgent / Urgent / Normal).
- **Status**: `Pending → PartiallySettled → Settled` (with `Overdue` branching when deadline passes).
- **Splitting**: `divisible: bool`, `parent_id: Option<String>` for split children.

### 4.3 Two-Queue Architecture

This is a critical architectural decision that models real RTGS systems:

- **Queue 1** (internal, per-agent): Transactions awaiting the agent's policy decision. Delay costs accrue here because holding is a strategic *choice*.
- **Queue 2** (central RTGS): Transactions submitted for settlement, waiting for sufficient liquidity. No delay penalty — the bank has already acted.

```
Arrival → Queue 1 → [Policy: Submit/Hold/Split] → Queue 2 → [RTGS/LSM] → Settled
```

### 4.4 Events

The engine emits 50+ event types as an append-only log. Events are **self-contained** — each includes all data needed for display, not just IDs. This is critical for replay identity (no external lookups needed). Key event types include: `Arrival`, `PolicyDecision`, `RtgsImmediateSettlement`, `QueuedRtgs`, `BilateralOffset`, `CycleSettlement`, `CostAccrual`, `CollateralPost`, `CollateralWithdraw`, `StateRegisterSet`, `OverdueMarked`, and `EndOfDay`.

---

## 5. Policy System Architecture

The policy system implements cash management decision-making through **decision tree policies** — a JSON DSL evaluated by the Rust engine.

### 5.1 Policy Trait & Implementations

All policies implement the `CashManagerPolicy` trait with a single method: `evaluate_queue(agent, state, tick, ...) → Vec<ReleaseDecision>`.

Built-in implementations: `FifoPolicy` (release all), `DeadlinePolicy` (prioritise by deadline), `LiquidityAwarePolicy` (check liquidity first). The primary implementation is `TreePolicy`, which evaluates user-defined (or LLM-generated) JSON decision trees.

### 5.2 Four Evaluation Points per Tick

A `TreePolicy` can contain up to four trees, evaluated in order:

1. **`bank_tree`** (Step 1.75) — Strategic decisions: set release budgets, update state registers. Runs once per agent per tick.
2. **`strategic_collateral_tree`** (Step 2) — Post or withdraw collateral based on market conditions. Runs once per agent.
3. **`payment_tree`** (Step 3) — Per-transaction release decision: `Submit`, `Hold`, `Split`, `Drop`, or `Reprioritize`. Evaluated for every transaction in Queue 1.
4. **`end_of_tick_collateral_tree`** (Step 8) — Post-settlement collateral adjustment.

### 5.3 Expression Language

The DSL supports:

- **Operands**: `field` (e.g., `"tx.amount"`), `value` (literal), `param` (from `parameters` dict), `state` (agent register).
- **Operators**: comparison (`eq`, `ne`, `gt`, `gte`, `lt`, `lte`), boolean (`and`, `or`, `not`), arithmetic (`add`, `sub`, `mul`, `div`, `mod`).
- **50+ context fields**: Transaction fields (`tx.amount`, `tx.ticks_until_deadline`, `tx.is_overdue`), agent fields (`agent.balance`, `agent.available_liquidity`, `agent.queue1_value`), system fields (`system.tick_within_day`, `system.ticks_until_eod`, `system.eod_rush_active`), Queue 2 fields (`queue2.agent_count`, `queue2.agent_value`), and cost fields.

### 5.4 Parsing, Validation & Execution

1. **Parsing**: JSON tree enters via FFI as a string, deserialized into `DecisionTreeDef` (a recursive enum of `ConditionNode` and `ActionNode`).
2. **Validation**: Before simulation starts, `validation.rs` checks syntax, verifies all field references exist, validates operators are compatible with operand types, and confirms actions are valid for the tree type. Invalid policies fail fast with descriptive errors.
3. **Execution**: At runtime, `executor.rs` builds an `EvalContext` (50+ fields populated from agent/state/transaction), then `interpreter.rs` recursively evaluates the tree: condition nodes resolve to boolean, branching to `if_true`/`if_false`; action nodes produce `ReleaseDecision` values.

### 5.5 State Registers

Policies can maintain state across ticks via `state_registers` (max 10 per agent, `f64` values). The `bank_tree` can `set_state` or `add_state` to a named register; subsequent trees (including `payment_tree`) can read registers in conditions. Registers persist across ticks within an episode and reset at the start of a new episode. All register changes emit `StateRegisterSet` events for full auditability.

### 5.6 LLM Policy Pipeline

In experiment/web-sandbox mode, an LLM generates JSON policy trees:

1. LLM generates JSON policy (via `PolicyOptimizer`)
2. `ConstraintValidator` checks against scenario constraints
3. Extract `initial_liquidity_fraction` → set on agent config
4. Wrap policy tree → `{"type": "InlineJson", "json_string": "..."}`
5. `SimulationConfig.from_dict()` → `to_ffi_dict()`
6. `Orchestrator.new(ffi_config)` → run ticks

---

## 6. Python API Layer

The Python layer comprises ~34 source files in 6 major components.

### 6.1 CLI (`payment_simulator/cli/`)

Built on Typer, the CLI provides:

| Command | Description |
|---------|-------------|
| `payment-sim run config.yaml` | Execute simulation (modes: `normal`, `verbose`, `stream`, `event_stream`) |
| `payment-sim replay --simulation-id ID` | Replay from DuckDB |
| `payment-sim checkpoint save/load/list/delete` | State snapshot management |
| `payment-sim db init/validate/migrate/schema` | Database schema management |

### 6.2 Execution Engine

`SimulationRunner` implements the Template Method pattern: it drives the tick loop and delegates output formatting to pluggable `OutputStrategy` implementations (`QuietOutputStrategy`, `VerboseModeOutput`, `StreamModeOutput`, `EventStreamOutput`).

The `StateProvider` protocol is the key abstraction for replay identity. Both `OrchestratorStateProvider` (live FFI calls) and `DatabaseStateProvider` (SQL queries) implement the same interface. The single `display_tick_verbose_output()` function produces identical output regardless of which provider is used.

### 6.3 Configuration

Pydantic models (`SimulationConfig`, `AgentConfig`, `ArrivalConfig`, `PolicyConfig`, `CostConfig`) provide strict validation of YAML input with fail-fast error reporting. Distribution types (`Normal`, `LogNormal`, `Uniform`, `Exponential`) are discriminated unions. All config is validated *before* crossing the FFI boundary.

### 6.4 REST API

FastAPI provides programmatic simulation control: `POST /simulations` (create), `POST /simulations/{id}/tick` (advance), `GET /simulations/{id}/state` (snapshot), `GET /simulations/{id}/costs` (breakdown), `GET /simulations/{id}/events` (filtered query). The API uses its own async `APIOutputStrategy` protocol (`JSONOutputStrategy`, `WebSocketOutputStrategy`, `NullOutputStrategy`) parallel to the CLI's sync strategies.

---

## 7. Persistence: DuckDB & Replay Identity

### 7.1 Storage Architecture

SimCash uses **DuckDB** (embedded columnar OLAP) with a schema-as-code approach: Pydantic models define tables, a `SchemaGenerator` produces DDL, and a `MigrationRunner` applies incremental changes.

Core tables:

| Table | Primary Key | Purpose |
|-------|------------|---------|
| `simulation_runs` | `simulation_id` | Run metadata + config JSON |
| `simulation_events` | `(simulation_id, tick, event_id)` | All events with full details in JSON column |
| `transactions` | `(simulation_id, transaction_id)` | Transaction lifecycle |
| `daily_agent_metrics` | `(simulation_id, day, agent_id)` | Daily aggregate metrics |
| `simulation_checkpoints` | `checkpoint_id` | Serialised Rust state snapshots |

### 7.2 Event Persistence

The `EventWriter` receives events from the FFI tick result and performs bulk `INSERT` into `simulation_events`. Events are stored with full details in a JSON column — they are self-contained, requiring no joins or external lookups for display. `StateRegisterSet` events are dual-written to `agent_state_registers` for efficient register queries.

### 7.3 Replay Identity

The **replay identity guarantee** states:

```
payment-sim run config.yaml --verbose --persist --simulation-id my-sim > run.txt
payment-sim replay --simulation-id my-sim --verbose > replay.txt
# run.txt and replay.txt are byte-identical (excluding timing metadata)
```

This is achieved through:
1. **Single display function** — `display_tick_verbose_output()` used for both live and replay.
2. **StateProvider abstraction** — display code is agnostic to whether data comes from FFI or SQL.
3. **Complete events** — events contain ALL data needed for display (not just IDs).
4. **No reconstruction** — replay queries only `simulation_events`, never recalculates.

### 7.4 Checkpoints

State can be serialised at any tick via `orch.checkpoint(path)` (Rust serialises full `Orchestrator` state to JSON). The checkpoint is stored in the `simulation_checkpoints` table with type (`manual`, `auto`, `eod`, `final`) and description. `Orchestrator.restore(path)` reconstructs the exact state for continued execution.

### 7.5 Analytical Queries

DuckDB's columnar storage and vectorised execution make analytical queries fast. Polars DataFrames integrate via zero-copy Arrow for analysis pipelines: `get_agent_performance()`, `get_settlement_rate_by_day()`, `get_cost_analysis()`, `get_transaction_journeys()`.

---

## 8. Key Invariants

These properties must hold at all times:

### INV-1: Balance Conservation
```
sum(all_agent_balances) == sum(initial_balances) + sum(external_transfers)
```
Settlement moves money between agents but never creates or destroys it.

### INV-2: Determinism
```
seed + config → identical_execution_trace
```
Given the same seed and configuration, the simulation produces byte-for-byte identical results across runs, platforms, and Rust compiler versions.

### INV-3: Integer Arithmetic
All monetary computations use `i64`. No floating-point values ever represent money. Cost rates (bps) are `f64` parameters but are applied to `i64` amounts and truncated back to `i64`.

### INV-4: Replay Identity
```
run_verbose_output == replay_verbose_output
```
The StateProvider abstraction guarantees identical output from live execution and database replay.

### INV-5: Queue Validity
All transaction IDs in Queue 1 and Queue 2 reference existing transactions. Queue 2 entries are always `Pending` status.

### INV-6: Settlement Atomicity
Settlement is all-or-nothing. `sender.balance -= amount` and `receiver.balance += amount` happen atomically. Partial settlement only occurs via explicit transaction splitting.

### INV-7: Event Completeness
Every event contains all data needed for display. No event requires external lookups or state reconstruction.

---

## 9. Performance Characteristics

| Metric | Value |
|--------|-------|
| Tick throughput | 1,200+ ticks/sec |
| Typical tick time | ~800μs |
| LSM cycle detection | ~0.5ms |
| FFI overhead per call | ~10μs |
| Event serialisation | ~1μs per event |
| Bootstrap evaluation (50 × 2) | ~100ms |
| 2-bank 12-tick scenario | <1ms |
| Tested scale | 200+ agents |

The system has been tested with the paper experiments using a large language model with reasoning effort `high`, temperature 0.5, and up to 25 iterations per experiment pass, with 3 independent passes for reproducibility assessment. The web sandbox defaults to algorithmic mode for zero-cost exploration, with optional LLM mode (currently Gemini 2.5 Flash via Google Vertex AI, admin-switchable).

---

## 10. Security Boundaries

```
┌─────────────────────────────────────────┐
│  Validation Boundary                    │
│  • Pydantic config validation           │
│  • FastAPI request validation           │
│  • PyO3 type safety at FFI              │
├─────────────────────────────────────────┤
│  Trusted Zone                           │
│  • Rust engine (no network access)      │
│  • Python orchestration layer           │
│  • DuckDB (embedded, no external proc)  │
└─────────────────────────────────────────┘
```

All external input (YAML configs, API requests) is validated before entering the trusted zone. The Rust simulation engine has zero network access. DuckDB is embedded with no external process.
