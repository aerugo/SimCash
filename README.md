# Payment Simulator

> **Production-grade real-time payment settlement simulation for research and policy optimization**

[![Tests](https://img.shields.io/badge/tests-passing-success)]()
[![Rust](https://img.shields.io/badge/rust-1.70%2B-orange)]()
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()

A hybrid Rust-Python simulator for modeling Real-Time Gross Settlement (RTGS) systems like TARGET2, Fedwire, and CHAPS. Built for financial researchers, central banks, and policy analysts who need deterministic, high-performance payment system simulation with programmable settlement strategies.

## 🎯 Key Features

### Settlement & Optimization

- **RTGS Engine**: Real-time gross settlement with immediate finality
- **T2-Compliant LSM**: Bilateral offsetting and multilateral cycle settlement with unequal payment values
- **Net Position Settlement**: Settles full transaction values when participants can cover net positions
- **Transaction Splitting**: Voluntary payment pacing for large transactions
- **Gridlock Resolution**: Automatic detection and resolution via LSM
- **Cost Modeling**: Overdraft, delay, split friction, deadline penalties, collateral costs

### Policy Framework ✨ **Enhanced**

- **Built-in Policies**: FIFO, Deadline-aware, Liquidity-aware, Cost-optimizing
- **Policy Tree DSL**: JSON decision trees with 60+ context fields, 20+ operators
- **Four Decision Trees**: Payment, Bank-Level Budget, Strategic Collateral, EOD Collateral
- **Bank-Level Budgets** (Phase 3.3): Control release pace, prioritize counterparties, manage throughput
- **Collateral Timers** (Phase 3.4): Auto-withdraw collateral after N ticks
- **State Registers** (Phase 4.5): Policy micro-memory for stateful strategies (cooldowns, counters, modes)
- **Extensible**: Add custom policies via Rust or JSON
- **LLM-Ready**: Structured format for AI-driven policy evolution

### Integration & Deployment

- **REST API**: FastAPI with OpenAPI docs at `/docs`
- **CLI Tool**: `payment-sim run scenarios/demo.yaml`
- **FFI Bridge**: High-performance PyO3 bindings (Rust ↔ Python)
- **Scenario Library**: Pre-built configs for stress testing, gridlock, large-scale

---

## 🚀 Quick Start

### Prerequisites

- **Rust 1.70+**: `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`
- **Python 3.11+** (3.13 recommended)
- **uv**: `pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh` (Astral's ultra-fast Python package manager)

### Installation (5 minutes)

```bash
# 1. Clone repository
git clone https://github.com/yourusername/payment-simulator.git
cd payment-simulator

# 2. Build Rust simulation engine
cd backend
cargo build --release
cd ..

# 3. Install Python CLI/API with uv
cd api
uv sync  # Creates venv and installs dependencies automatically
cd ..

# 4. Verify installation
cargo test --manifest-path backend/Cargo.toml --no-default-features
uv run --directory api pytest tests/
```

### Run Your First Simulation (CLI)

```bash
# Run realistic demo scenario (3 banks, 100 ticks)
uv run --directory api payment-sim run scenarios/realistic_demo.yaml

# Output shows:
# - Settlement statistics (throughput, delays)
# - Cost breakdown (liquidity, delay, penalties)
# - Final agent balances
```

### Start API Server

```bash
# Start the development server with auto-reload
uv run --directory api uvicorn payment_simulator.api.main:app --reload
```

Visit **http://localhost:8000/docs** for interactive API documentation.

### Python API Example

```python
import requests

# Create simulation with 2 banks
config = {
    "simulation": {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 42,
    },
    "cost_rates": {
        "overdraft_bps_per_tick": 0.0001,
        "delay_cost_per_tick_per_cent": 0.00001,
        "split_friction_cost": 500,
    },
    "agents": [
        {
            "id": "BANK_A",
            "opening_balance": 1_000_000,  # $10,000 in cents
            "credit_limit": 500_000,
            "policy": {"type": "Fifo"},
        },
        {
            "id": "BANK_B",
            "opening_balance": 1_000_000,
            "credit_limit": 500_000,
            "policy": {"type": "LiquidityAware", "buffer_target": 200_000},
        },
    ],
}

# Create simulation
response = requests.post("http://localhost:8000/simulations", json=config)
sim_id = response.json()["simulation_id"]

# Submit transaction: BANK_A → BANK_B for $500
tx = requests.post(
    f"http://localhost:8000/simulations/{sim_id}/transactions",
    json={
        "sender": "BANK_A",
        "receiver": "BANK_B",
        "amount": 50_000,      # $500 in cents
        "deadline_tick": 50,
        "priority": 5,
    },
)
tx_id = tx.json()["transaction_id"]

# Advance simulation 10 ticks
requests.post(f"http://localhost:8000/simulations/{sim_id}/tick", params={"count": 10})

# Check transaction status
status = requests.get(f"http://localhost:8000/simulations/{sim_id}/transactions/{tx_id}")
print(f"Status: {status.json()['status']}")  # "settled"

# Get cost breakdown
costs = requests.get(f"http://localhost:8000/simulations/{sim_id}/costs")
print(f"Total costs: {costs.json()}")

# Cleanup
requests.delete(f"http://localhost:8000/simulations/{sim_id}")
```

---

## 🖥️ CLI Reference

The `payment-sim` CLI provides comprehensive tools for running, replaying, and managing simulations.

### Core Commands

#### Run a New Simulation

```bash
# Basic run with JSON output
payment-sim run --config scenarios/demo.yaml

# Run with verbose real-time output (detailed events)
payment-sim run --config scenarios/demo.yaml --verbose

# Run and persist to database
payment-sim run --config scenarios/demo.yaml --persist

# Override parameters
payment-sim run --config cfg.yaml --seed 999 --ticks 500

# AI-friendly quiet mode (stdout only)
payment-sim run --config cfg.yaml --quiet

# Stream results for long simulations (JSONL output)
payment-sim run --config large.yaml --stream
```

#### Replay a Persisted Simulation

**NEW**: Replay enables debugging and analysis of specific tick ranges with identical verbose output.

```bash
# Replay entire simulation from database
payment-sim replay --simulation-id sim-abc123 --config original_config.yaml

# Replay specific tick range (e.g., debug ticks 50-100)
payment-sim replay \
  --simulation-id sim-abc123 \
  --config original_config.yaml \
  --from-tick 50 \
  --to-tick 100

# Replay with custom database location
payment-sim replay \
  --simulation-id sim-abc123 \
  --config original_config.yaml \
  --db-path /path/to/simulation_data.db
```

**Key Features**:
- **Deterministic replay**: Same seed guarantees identical results
- **Fast-forward**: Silently advances to `--from-tick`, then shows verbose output
- **Identical output**: Produces exact same verbose logs as original run
- **Use cases**: Debug specific ticks, analyze edge cases, reproduce issues

### Database Management

```bash
# Initialize database from Pydantic models
payment-sim db init

# Apply pending schema migrations
payment-sim db migrate

# Validate schema matches models
payment-sim db validate

# List all tables
payment-sim db list

# Show database statistics
payment-sim db info
```

### Checkpoint Management

Save and load simulation state for resumption or analysis.

```bash
# Save checkpoint (requires state JSON from orchestrator.save_state())
payment-sim checkpoint save \
  --simulation-id sim-001 \
  --state-file state.json \
  --config config.yaml \
  --description "After 50 ticks"

# Load checkpoint
payment-sim checkpoint load \
  --checkpoint-id abc123 \
  --config config.yaml

# Load latest checkpoint for a simulation
payment-sim checkpoint load \
  --checkpoint-id latest \
  --simulation-id sim-001 \
  --config config.yaml

# List checkpoints
payment-sim checkpoint list
payment-sim checkpoint list --simulation-id sim-001
payment-sim checkpoint list --type manual --limit 10

# Delete checkpoint
payment-sim checkpoint delete --checkpoint-id abc123
payment-sim checkpoint delete --simulation-id sim-001 --confirm
```

### Common Workflows

#### 1. Run and Persist for Later Analysis

```bash
# Run simulation with persistence
payment-sim run \
  --config scenarios/18_agent_3_policy_simulation.yaml \
  --persist \
  --simulation-id my-test-001

# Later: Query database to find interesting tick ranges
# (Use Python query interface or SQL)

# Replay specific tick range with verbose output
payment-sim replay \
  --simulation-id my-test-001 \
  --config scenarios/18_agent_3_policy_simulation.yaml \
  --from-tick 45 \
  --to-tick 55
```

#### 2. Debug Specific Tick Range

```bash
# First run identifies issue around tick 75
payment-sim run --config test.yaml --verbose | tee run.log

# Replay just the problematic tick range
payment-sim replay \
  --simulation-id sim-xxx \
  --config test.yaml \
  --from-tick 70 \
  --to-tick 80 > debug.log
```

#### 3. Compare Real-time vs Replay Output

```bash
# Original run with verbose output
payment-sim run --config test.yaml --persist --verbose > original.log

# Replay with identical output (should match exactly)
payment-sim replay \
  --simulation-id <id_from_original> \
  --config test.yaml > replay.log

# Verify identical output (determinism check)
diff original.log replay.log
```

### Output Formats

- **JSON** (default): Structured summary at end of simulation
- **JSONL** (`--stream`): One JSON object per tick (for long simulations)
- **Verbose** (`--verbose`): Rich formatted output with detailed events
- **Quiet** (`--quiet`): Suppresses logs, stdout only (AI-friendly)

### Environment Variables

```bash
# Custom database location
export PAYMENT_SIM_DB_PATH=/path/to/simulation_data.db

# Then all commands use this database
payment-sim run --config test.yaml --persist
payment-sim replay --simulation-id sim-001 --config test.yaml
```

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| **[Getting Started](docs/getting_started.md)** | Installation, concepts, first simulation |
| **[API Examples](docs/api_examples.md)** | Production patterns, research workflows |
| **[Architecture](docs/architecture.md)** | System design, Rust-Python bridge |
| **[Game Design](docs/game_concept_doc.md)** | Domain model, settlement mechanics |
| **[CLI Reference](docs/cli.md)** | Command-line usage and scenarios |
| **[Policy Tree DSL](docs/policy_trees.md)** | JSON decision tree specification |
| **[API Reference](http://localhost:8000/docs)** | Interactive OpenAPI docs (when server running) |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│  CLI Tool (payment-sim)                         │
│  • Scenario loading from YAML                   │
│  • Verbose/quiet output modes                   │
│  • Cost and throughput reporting               │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│  REST API (FastAPI + Pydantic V2)              │
│  • Simulation lifecycle management              │
│  • Transaction submission & tracking            │
│  • Configuration validation                     │
└──────────────────┬──────────────────────────────┘
                   │ FFI (PyO3)
┌──────────────────▼──────────────────────────────┐
│  Rust Simulation Engine (High Performance)      │
│  ┌─────────────────────────────────────────┐   │
│  │ 9-Step Tick Loop:                       │   │
│  │ 1. Arrivals → Queue 1                   │   │
│  │ 2. Policy Evaluation                    │   │
│  │ 3. Transaction Splitting                │   │
│  │ 4. RTGS Submission → Queue 2            │   │
│  │ 5. RTGS Settlement                      │   │
│  │ 6. LSM Optimization                     │   │
│  │ 7. Cost Accrual                         │   │
│  └─────────────────────────────────────────┘   │
│  • Deterministic RNG (xorshift64*)              │
│  • Integer-only money arithmetic                │
│  • Event logging for observability              │
└─────────────────────────────────────────────────┘
```

**Design Philosophy**:
- **Rust owns state**: Python gets snapshots, never mutable references
- **Python orchestrates**: Configuration, CLI, API, research tooling
- **FFI is thin**: Minimal, stable API surface (24 tests validate boundary)
- **Performance-critical in Rust**: Settlement, policies, simulation loop
- **Developer-friendly in Python**: YAML configs, CLI, REST API
- **Mandatory persistence**: All data persisted to DuckDB at end of each simulated day

**Data Persistence Architecture** (Phase 10 - Complete):
```
End of Each Simulated Day:
    ↓
Rust FFI: get_transactions_for_day(day) → List[Dict]
    ↓
Python: Convert to Polars DataFrame (zero-copy Arrow)
    ↓
DuckDB: INSERT INTO transactions SELECT * FROM df (<100ms for 40K txs)
    ↓
Rust FFI: get_daily_agent_metrics(day) → List[Dict]
    ↓
Python: Convert to Polars DataFrame
    ↓
DuckDB: INSERT INTO daily_agent_metrics SELECT * FROM df (<20ms)
    ↓
Database Updated: Ready for analytical queries
```

**Why Mandatory Persistence?**
- **Research Reproducibility**: Every simulation fully queryable
- **Policy Evolution**: Track changes over time (Phase 11 LLM Manager)
- **Historical Analysis**: Compare 200+ runs with SQL
- **Audit Trail**: Complete provenance of all decisions

---

## 🎯 Core Concepts

### Two-Queue Architecture

The simulator models real-world payment flows through **two distinct queues**:

#### Queue 1: Internal Bank Queues
- **Purpose**: Strategic decision point for cash managers
- **Control**: Bank policy determines release timing
- **Costs**: Delay costs accrue (strategic hold)
- **Actions**: Submit now, hold, split transaction, drop

#### Queue 2: RTGS Central Queue
- **Purpose**: Mechanical liquidity wait at central bank
- **Control**: Automatic retry every tick
- **Costs**: No delay costs (liquidity-constrained, not policy choice)
- **Actions**: LSM optimization attempts settlement

**Why separate?** This captures the reality that banks choose *when* to submit payments (Queue 1), but cannot force settlement — that depends on liquidity availability and LSM optimization (Queue 2).

### Settlement Flow

```
Transaction Arrival → Queue 1 (Internal Bank)
    ↓
Policy Decision: Submit? Hold? Split?
    ↓
Queue 2 (RTGS Central) → RTGS Settlement Attempt
    ↓
If insufficient liquidity → LSM Optimization
    ↓
Settlement (bilateral offset / cycle / gross)
    ↓
Balance Updates & Cost Accrual
    ↓
End of Day → MANDATORY DATABASE PERSISTENCE
```

**CRITICAL**: At the end of each simulated day, ALL data is automatically persisted to the database:
- All transaction records (arrival, settlement, status, costs)
- Daily agent metrics (balance stats, queue sizes, transaction counts)
- Policy snapshots (if policies changed)
- Simulation progress and metadata

This persistence is **mandatory** (not optional) and enables:
- Research reproducibility (re-run any simulation from stored data)
- Policy evolution tracking (LLM Manager Phase 11)
- Historical analysis and comparison
- Monte Carlo validation of policy improvements

### Built-in Policies

1. **FIFO**: Submit all transactions immediately (baseline)
2. **Deadline**: Prioritize transactions approaching deadline
3. **LiquidityAware**: Preserve liquidity buffer, hold when low
4. **LiquiditySplitting**: Intelligently split large transactions to improve settlement probability
5. **PolicyTree**: JSON decision trees (see [Policy Tree DSL](docs/policy_trees.md))

### Transaction Splitting

Banks can **voluntarily split** large payments at Queue 1 decision point:
- Creates N independent child transactions
- Each child processed separately by RTGS
- Split friction cost: `cost × (N-1)` where N = number of children
- Useful when liquidity insufficient for full amount but available for partial

### Settlement Rate

**Definition**: Percentage of original payment requests that successfully completed.

The settlement rate uses recursive checking to properly handle split transactions:

```python
def is_effectively_settled(tx_id, transactions, children_map):
    tx = transactions[tx_id]
    
    # Base case 1: Transaction itself settled
    if tx.is_fully_settled():
        return True
    
    # Base case 2: All children settled (recursive)
    if tx_id in children_map:
        return all(
            is_effectively_settled(child_id, transactions, children_map)
            for child_id in children_map[tx_id]
        )
    
    # Base case 3: Not settled, no children
    return False

settlement_rate = effectively_settled_count / original_arrivals
```

**Key principle**: Only count ORIGINAL arrivals (not split children) and recursively check that all descendants settled.

This ensures:
- Settlement rate ≤ 100% (mathematically correct)
- Measures actual payment completion (semantically correct)
- Handles nested splits properly (technically correct)

### Liquidity-Saving Mechanisms (LSM)

**T2-Compliant Implementation**: Our LSM follows TARGET2 RTGS specifications for realistic settlement behavior.

**Bilateral Offsetting with Unequal Amounts**:
- Example: Bank A owes B $500k, B owes A $300k → both settle in full if A can cover net $200k outflow
- Settles BOTH transactions at full value (not partial amounts)
- Net sender must have liquidity to cover difference

**Multilateral Cycle Detection with Unequal Amounts**:
- Example: A→B ($500k), B→C ($800k), C→A ($700k)
- Net positions: A: +$200k, B: -$300k, C: +$100k
- If B has $300k liquidity → all three transactions settle at full value
- All-or-nothing: If any participant lacks liquidity for net position, entire cycle fails atomically

**Key T2 Principle**: Individual payments settle in full or not at all (no transaction splitting by LSM). Liquidity savings achieved through smart grouping of whole payments based on net positions.

### Determinism

**Same seed + same actions = identical results**

```yaml
simulation:
  rng_seed: 42  # Fixed seed for reproducibility
```

Critical for:
- Research validation (peer review requires reproducibility)
- Debugging (replay exact scenarios)
- Policy comparison (fair evaluation across runs)
- Monte Carlo studies (statistical reliability)

---

## 🎬 Scenario Events

**Scenario events** enable precise control over simulation state through scheduled interventions. Unlike random arrivals, scenario events execute deterministically at specified ticks, allowing researchers to model shock scenarios, policy changes, and controlled experiments.

### Event Types

#### 1. DirectTransfer
Instantly transfers money between agents, bypassing normal settlement.

**Use cases:** Emergency liquidity injection, interbank loans, central bank operations

```yaml
scenario_events:
  - type: DirectTransfer
    from_agent: CENTRAL_BANK
    to_agent: BANK_A
    amount: 500000  # $5,000 in cents
    schedule:
      type: OneTime
      tick: 50
```

#### 2. CustomTransactionArrival
Creates a transaction through the normal arrival → settlement path (Queue 1 → RTGS → LSM).

**Use cases:** Testing settlement behavior with precise timing, controlled stress tests

```yaml
scenario_events:
  - type: CustomTransactionArrival
    from_agent: BANK_A
    to_agent: BANK_B
    amount: 250000        # $2,500
    priority: 8           # 0-10, higher = more urgent
    deadline: 10          # Ticks from arrival
    is_divisible: false   # Can be split?
    schedule:
      type: OneTime
      tick: 25
```

**Key difference from DirectTransfer:** Goes through Queue 1 (policy decides timing) → Queue 2 (RTGS) → potential LSM optimization. Tests real settlement behavior.

#### 3. CollateralAdjustment
Modifies agent's available collateral, affecting credit capacity.

**Use cases:** Margin calls, collateral haircuts, regulatory changes

```yaml
scenario_events:
  - type: CollateralAdjustment
    agent: BANK_A
    delta: -100000  # Reduce collateral by $1,000
    schedule:
      type: OneTime
      tick: 75
```

#### 4. GlobalArrivalRateChange
Scales all agents' arrival rates by a multiplier.

**Use cases:** Market-wide activity surges, holiday slowdowns

```yaml
scenario_events:
  - type: GlobalArrivalRateChange
    multiplier: 2.0  # Double all arrival rates
    schedule:
      type: OneTime
      tick: 30
```

#### 5. AgentArrivalRateChange
Adjusts a specific agent's transaction arrival rate.

**Use cases:** Bank-specific shocks, operational changes

```yaml
scenario_events:
  - type: AgentArrivalRateChange
    agent: BANK_C
    multiplier: 0.5  # Halve arrival rate
    schedule:
      type: OneTime
      tick: 40
```

#### 6. CounterpartyWeightChange
Modifies preferred counterparty relationships.

**Use cases:** Correspondent banking changes, credit limit adjustments

```yaml
scenario_events:
  - type: CounterpartyWeightChange
    agent: BANK_A
    counterparty: BANK_B
    new_weight: 0.5
    schedule:
      type: OneTime
      tick: 60
```

#### 7. DeadlineWindowChange
Adjusts agent's default deadline window for new transactions.

**Use cases:** Policy changes, urgency shifts

```yaml
scenario_events:
  - type: DeadlineWindowChange
    agent: BANK_A
    new_window: 20  # Ticks
    schedule:
      type: OneTime
      tick: 10
```

### Scheduling

**OneTime Execution:**
```yaml
schedule:
  type: OneTime
  tick: 50  # Execute once at tick 50
```

**Repeating Execution:**
```yaml
schedule:
  type: Repeating
  start_tick: 10
  interval: 5      # Every 5 ticks
  end_tick: 50     # Stop after tick 50 (optional)
```

### Example: Liquidity Crisis Scenario

```yaml
simulation:
  ticks_per_day: 100
  num_days: 1
  rng_seed: 42

agents:
  - id: BANK_A
    opening_balance: 1000000
    credit_limit: 200000
    policy: {type: LiquidityAware, buffer_target: 100000}
  - id: BANK_B
    opening_balance: 1000000
    credit_limit: 200000
    policy: {type: Fifo}

scenario_events:
  # Morning: Normal operations
  - type: CustomTransactionArrival
    from_agent: BANK_A
    to_agent: BANK_B
    amount: 150000
    priority: 5
    deadline: 20
    schedule: {type: OneTime, tick: 10}

  # Midday: Liquidity shock (margin call)
  - type: DirectTransfer
    from_agent: BANK_A
    to_agent: CLEARING_HOUSE
    amount: 500000
    schedule: {type: OneTime, tick: 50}

  # Afternoon: Reduced collateral capacity
  - type: CollateralAdjustment
    agent: BANK_A
    delta: -100000
    schedule: {type: OneTime, tick: 60}

  # Result: BANK_A faces tight liquidity, policy must adapt
```

### Replay Identity

Scenario events are **fully deterministic** and persist to the database:
- Events logged to `simulation_events` table with complete details
- Replay produces byte-for-byte identical output
- Event execution visible in verbose mode (`--verbose`)

```bash
# Run with persistence
payment-sim run --config crisis.yaml --persist --verbose > run.log

# Replay exact scenario
payment-sim replay --simulation-id <id> --config crisis.yaml --verbose > replay.log

# Verify identical output
diff <(grep -v "Duration:" run.log) <(grep -v "Duration:" replay.log)
```

### Verbose Output

Scenario events appear in verbose mode with full details:

```
🎬 Scenario Events (3):
   • DirectTransfer: CENTRAL_BANK → BANK_A ($5,000.00)
   • CustomTransactionArrival: BANK_A → BANK_B ($2,500.00)
     Priority: 8, TX: tx_abc123
   • CollateralAdjustment: BANK_A -$1,000.00 collateral
```

### Use Cases

**Stress Testing:**
- Liquidity shocks (large outflows at specific times)
- Collateral haircuts (regulatory changes mid-day)
- Counterparty failures (zero new arrivals from failed bank)

**Policy Evaluation:**
- Test policy behavior under known conditions
- Compare DirectTransfer (instant) vs CustomTransactionArrival (realistic settlement)
- Validate gridlock resolution strategies

**Reproducible Research:**
- Exact control over experimental conditions
- Deterministic shock timing enables peer review
- Database persistence ensures full provenance

---

## 📊 Performance & Scale

**Hardware**: Apple M1 Max, 32GB RAM

| Metric | Value |
|--------|-------|
| **Simulation Throughput** | 1,200 ticks/second |
| **Agent Scale** | 200+ banks tested |
| **Transaction Volume** | 50+ transactions/tick/agent |
| **CLI Performance** | 200 agents × 100 ticks in ~8 seconds |
| **API Latency** | <10ms per tick (REST) |
| **FFI Overhead** | <1% (high-performance PyO3 bindings) |

**Large-Scale Validation** (from `scenarios/LARGE_SCALE_RESULTS.md`):
- 200 agents × 100 ticks = 20,000 total ticks
- 10,000+ transactions processed
- scenario 97.2% settlement rate with LSM enabled vs 63.4% without LSM

### Running Tests

```bash
# Rust tests (unit + integration)
cd backend
cargo test --no-default-features

# Rust doc tests
cargo test --doc --no-default-features

# Python FFI tests
uv run --directory api pytest tests/ffi/

# Python API integration tests
uv run --directory api pytest tests/integration/

# Python config tests
uv run --directory api pytest tests/unit/

# All Python tests
uv run --directory api pytest
```

### Code Quality Standards

**Critical Invariants** (enforced by tests):
1. ✅ **Money is always i64** (integer cents, never floats)
2. ✅ **Determinism is sacred** (seeded RNG, no system time)
3. ✅ **FFI boundary is minimal** (simple types, batch operations)
4. ✅ **Balance conservation** (total system balance unchanged by settlement)
5. ✅ **Two-queue separation** (Queue 1 = strategic, Queue 2 = mechanical)

See [CLAUDE.md](CLAUDE.md) for comprehensive development guidelines.

---

## 🗺️ Roadmap & Future Vision

### ✅ Foundation & Integration (COMPLETE)

**Core Engine**:
- [x] Time management & deterministic RNG (xorshift64*)
- [x] Agent state & transaction models
- [x] RTGS settlement engine
- [x] LSM (bilateral offsetting + cycle detection)
- [x] T2-compliant LSM with unequal payment values (net position settlement)
- [x] Queue 1 (internal bank queues) + Cash manager policies
- [x] 9-step orchestrator tick loop
- [x] Transaction splitting with split friction costs
- [x] Arrival generation (Poisson, normal, lognormal, uniform)
- [x] Cost modeling (overdraft, delay, split friction, deadline penalties)

**Integration Layer**:
- [x] PyO3 FFI bindings (24 tests passing)
- [x] Python API with FastAPI (23 integration tests)
- [x] CLI tool with scenario loading
- [x] Policy tree DSL (JSON decision trees)
- [x] Large-scale validation (200 agents tested)
- [x] Comprehensive documentation

**Test Coverage**: 70+ Rust tests + 24 FFI tests + 23 API tests + 71 persistence tests = **188+ tests passing**

---

### ✅ Data Persistence (Phase 10 - COMPLETE)

**Status**: 100% complete with 71/71 tests passing

**Capabilities**:
- **DuckDB + Polars**: Columnar database with zero-copy Arrow integration
- **Automatic Daily Persistence**: All data saved at end of each simulated day
- **Schema-as-Code**: Pydantic models auto-generate DDL, migrations automated
- **Query Interface**: 9 pre-built analytical queries returning Polars DataFrames
- **Checkpoint System**: Save/load full orchestrator state for resumption

**Database Tables**:
1. `simulations` - Simulation run metadata and KPIs
2. `transactions` - All transaction records (arrival, settlement, costs)
3. `daily_agent_metrics` - Daily balance stats, queue sizes, cost breakdowns
4. `policy_snapshots` - Policy version tracking with SHA256 hashing
5. `simulation_checkpoints` - Save/load orchestrator state

**Performance**:
- Daily transaction batch write: <100ms (40K transactions)
- Daily metrics batch write: <20ms (200 agent records)
- Analytical queries: <1s (250M transaction aggregates)
- Database file: <10 GB (200 runs, compressed columnar)

**CLI Commands**:
```bash
# Database management
payment-sim db init              # Create database from Pydantic models
payment-sim db migrate           # Apply pending migrations
payment-sim db validate          # Verify schema matches models

# Checkpoint management
payment-sim checkpoint save <sim_id> --description "Before policy change"
payment-sim checkpoint load <checkpoint_id>
payment-sim checkpoint list <sim_id>
```

**Why This Matters**:
- **Research Reproducibility**: Query any simulation's complete history
- **Policy Evolution**: Track policy changes over time (enables Phase 11 LLM Manager)
- **Historical Analysis**: Compare 200+ simulation runs with SQL queries
- **Monte Carlo Validation**: Sample from episode database for statistical testing

---

### 🎯 Advanced Features

#### LLM-Driven Policy Evolution

**Goal**: Enable AI-assisted policy improvement through structured decision tree editing

**Components**:
1. **LLM Manager Service** (async)
   - Analyzes simulation outcomes (costs, throughput, gridlock incidents)
   - Proposes policy tree modifications in JSON format
   - Generates natural language explanations for changes
   - Iterative refinement based on A/B test results

2. **Shadow Replay System**
   - Monte Carlo validation: run new policy on 100+ historical scenarios
   - Statistical comparison: paired t-tests, confidence intervals
   - Safety checks: ensure no catastrophic degradation
   - Automated rollback if validation fails

3. **Policy Version Control**
   - Git-based versioning for policy trees
   - Diff visualization for tree changes
   - Rollback capability to any previous version
   - Audit trail of all modifications

**Example Workflow**:
```
1. Run baseline simulation with FIFO policy → collect episode data
2. LLM analyzes: "High delay costs due to holding all transactions equally"
3. LLM proposes: Add deadline urgency check to prioritize time-critical payments
4. Shadow replay: Test modified policy on 100 seeds
5. Statistical validation: 15% cost reduction with p<0.01
6. Automated deployment: New policy promoted to production
```

---

#### Phase 9: Multi-Rail & Cross-Border

**Goal**: Model heterogeneous payment systems (RTGS + DNS, cross-border corridors)

**Multi-Rail Support**:
- **RTGS Rail**: Real-time gross settlement (existing)
- **DNS Rail**: Deferred net settlement with batch windows
- **Agent Choice**: Policies decide which rail to use per transaction
- **Cost Differences**: RTGS faster but requires more liquidity, DNS cheaper but delayed

**Cross-Border Corridors**:
- **Nostro Accounts**: Pre-funded balances at correspondent banks
- **FX Settlement**: Simplified currency conversion (fixed rates initially)
- **PvP Timing**: Payment-versus-Payment coordination
- **Multiple Central Banks**: Model domestic + foreign RTGS systems

**Use Cases**:
- Optimize RTGS/DNS split for cost vs speed
- Study cross-border gridlock (Herstatt risk)
- Evaluate CBDC settlement architectures
- Model intraday FX market liquidity

**Timeline**: 8-10 weeks

---

### 🚀 Phase 10-12: Production Readiness (6-12 Months)

#### Phase 10: Real-Time Visualization & Monitoring

**Frontend Dashboard** (React + WebSocket):
- Live simulation visualization (network graph, queue depths)
- Real-time metrics (throughput, costs, liquidity usage)
- Interactive policy editing (drag-and-drop decision trees)
- Historical comparison charts

**Observability**:
- Prometheus metrics export
- Grafana dashboards
- Distributed tracing (OpenTelemetry)
- Structured logging (JSON)

**Timeline**: 10-12 weeks

---

#### Phase 11: Shock Scenarios & Stress Testing

**Operational Shocks**:
- **System Outages**: RTGS unavailable for N ticks
- **LSM Degradation**: Cycle detection disabled
- **Agent Failures**: Bank cannot send/receive payments
- **Capacity Limits**: Message processing throttling

**Market Shocks**:
- **Liquidity Squeeze**: Reduced opening balances across all banks
- **Collateral Crunch**: Increased haircuts, higher credit costs
- **Large Outflows**: Idiosyncratic margin calls, settlements
- **Contagion**: Cascading liquidity pressures

**Regulatory Scenarios**:
- **Throughput Requirements**: "75% settled by 14:00" rule
- **Exposure Limits**: Bilateral credit caps
- **Capital Requirements**: Link to Basel III metrics
- **Recovery Plans**: Test resolution scenarios

**Timeline**: 6-8 weeks

---

#### Phase 12: Reinforcement Learning Integration

**Goal**: Train RL agents to optimize settlement policies

**RL Environment** (OpenAI Gym interface):
- **State Space**: Balance, queues, incoming/outgoing forecasts, time
- **Action Space**: Queue 1 release decisions, liquidity draws, split factors
- **Reward Function**: Negative total costs (liquidity + delay + penalties)
- **Episode**: One business day (60-100 ticks)

**Training Infrastructure**:
- **Algorithms**: PPO, SAC, TD3 (continuous control)
- **Multi-Agent**: Self-play for coordination learning
- **Curriculum**: Start simple (2 banks), scale to 50+
- **Distributed Training**: Ray/RLlib for parallelization

**Validation**:
- Compare RL policies vs. hand-crafted baselines
- Test robustness to distribution shift
- Interpretability analysis (extract decision rules)
- Safety constraints (never violate regulatory limits)

**Timeline**: 12-16 weeks

---

### 🌟 Long-Term Vision (12+ Months)

**Advanced Research Capabilities**:
- **CBDC Settlement Layer**: Model central bank digital currency transactions
- **Smart Contract Integration**: Programmable payment conditions (DvP, PvP)
- **Privacy-Preserving Analytics**: Differential privacy for sensitive data
- **Federated Learning**: Multi-institution policy optimization without data sharing

**Production Deployment**:
- **Cloud-Native**: Kubernetes deployment, autoscaling
- **Multi-Tenancy**: Isolated simulations for different institutions
- **SaaS Platform**: Web-based simulation-as-a-service
- **Enterprise Features**: SSO, RBAC, audit logs, SLAs

**Ecosystem Integration**:
- **Data Pipelines**: Import real TARGET2/Fedwire message logs
- **Regulatory Reporting**: Automated PFMIs compliance reports
- **Risk Systems**: Integration with bank risk management platforms
- **Research Collaboration**: Open datasets for academic research

---

## 📖 Citation

If you use this simulator in academic research, please cite:

```bibtex
@software{payment_simulator_2025,
  title = {Payment Simulator: High-Performance RTGS Simulation with Policy Trees},
  author = {Payment Simulator Team},
  year = {2025},
  url = {https://github.com/yourusername/payment-simulator},
  note = {Version 0.8.0 - Phase 7 Complete}
}
```

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Follow coding guidelines in [CLAUDE.md](CLAUDE.md)
4. Ensure all tests pass:
   ```bash
   cargo test --manifest-path backend/Cargo.toml --no-default-features
   uv run --directory api pytest tests/
   ```
5. Add tests for new features
6. Update documentation
7. Submit a pull request

**Areas needing contribution**:
- Frontend visualization (React + D3.js)
- Additional policy strategies
- Real-world calibration datasets
- Performance optimizations
- Documentation improvements

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Built with [PyO3](https://pyo3.rs/) for high-performance Rust-Python interop
- Powered by [FastAPI](https://fastapi.tiangolo.com/) for REST API
- Inspired by TARGET2, Fedwire, and CHAPS settlement systems
- Research-grade determinism via xorshift64* RNG
- Validated against academic literature on LSM efficacy (Danmarks Nationalbank, ECB)

---

## 📞 Support & Resources

- **Documentation**: [/docs](docs/) directory
- **Issues**: [GitHub Issues](https://github.com/yourusername/payment-simulator/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/payment-simulator/discussions)
- **API Docs**: http://localhost:8000/docs (when server running)
- **Examples**: [/api/scenarios](api/scenarios/) directory

---

## 🎯 Quick Links

| Resource | Link |
|----------|------|
| **Getting Started** | [docs/getting_started.md](docs/getting_started.md) |
| **CLI Usage** | `payment-sim --help` |
| **API Reference** | http://localhost:8000/docs |
| **Policy Trees** | [docs/policy_trees.md](docs/policy_trees.md) |
| **Scenarios** | [/api/scenarios](api/scenarios/) |
| **Architecture** | [docs/architecture.md](docs/architecture.md) |
| **Game Design** | [docs/game_concept_doc.md](docs/game_concept_doc.md) |

---

**Status**: Phase 7 (Integration) + Phase 10 (Persistence) + Phase 3.5 (T2 LSM) Complete | Ready for Phase 11 (LLM Manager)
**Version**: 0.10.1 | **Tests**: 188+ passing | **Performance**: 1000+ ticks/s
**Next Milestone**: LLM-driven policy optimization with shadow replay validation (Phase 11)

**Phase 10 Achievement**: Full database persistence with DuckDB + Polars (71 tests passing)
- ✅ Mandatory daily persistence of all transactions and agent metrics
- ✅ Policy provenance tracking for reproducible research
- ✅ Checkpoint system for save/load orchestrator state
- ✅ Query interface with 9 analytical functions

*Built for researchers who demand reproducibility, performance, and correctness.*
*Designed for the future of AI-assisted financial system optimization.*
