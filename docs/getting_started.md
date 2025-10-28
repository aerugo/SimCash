# Getting Started with Payment Simulator

> **High-performance payment settlement simulation for research and policy optimization**

This guide will get you up and running with the Payment Simulator in under 10 minutes.

---

## Quick Overview

The Payment Simulator models **Real-Time Gross Settlement (RTGS)** systems like TARGET2, Fedwire, or CHAPS. It simulates how banks manage liquidity, submit payments, and optimize settlement strategies.

**Key Features:**
- 🚀 **High Performance**: 1000+ ticks/second (Rust core)
- 🎯 **Deterministic**: Same seed = same results (perfect reproducibility)
- 💰 **Exact Money Arithmetic**: Integer-only (no floating-point errors)
- 🔄 **RESTful API**: Easy integration via FastAPI
- 🧪 **Fully Tested**: 401 tests passing (Rust + Python)

---

## Prerequisites

- **Python 3.11+** (Python 3.13 recommended)
- **Rust 1.70+** (for building the simulation engine)
- **uv** (Python package manager) - Install: `pip install uv`

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/cashman.git
cd cashman
```

### 2. Build the Rust Simulation Engine

```bash
cd backend
cargo build --release
cd ..
```

This compiles the high-performance Rust core. The `--release` flag enables optimizations.

### 3. Install Python Dependencies

```bash
cd api
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"
cd ..
```

This creates a virtual environment and installs:
- FastAPI (REST API framework)
- Pydantic V2 (configuration validation)
- PyO3 bindings (Rust ↔ Python bridge)
- Testing tools (pytest, httpx)

### 4. Verify Installation

Run the test suite to ensure everything is working:

```bash
# Test Rust core
cd backend
cargo test --no-default-features
cd ..

# Test Python API
cd api
source .venv/bin/activate
pytest
cd ..
```

You should see:
- ✅ 279 Rust unit tests passing
- ✅ 66 Rust doc tests passing
- ✅ 56 Python tests passing

---

## Running the API Server

### Start the Server

```bash
cd api
source .venv/bin/activate
uvicorn payment_simulator.api.main:app --reload
```

The server will start on `http://localhost:8000`

### Verify It's Running

Open your browser to:
- **API Root**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs (Swagger UI)
- **Health Check**: http://localhost:8000/health

You should see the interactive API documentation with all available endpoints.

---

## Your First Simulation

Let's create a simple 2-bank simulation and submit a transaction.

### 1. Create a Configuration File

Create `my_first_sim.yaml`:

```yaml
simulation:
  ticks_per_day: 100     # 100 ticks = 1 business day
  num_days: 1            # Run for 1 day
  rng_seed: 42           # For determinism

agents:
  - id: "BANK_A"
    opening_balance: 1_000_000   # $10,000 in cents
    credit_limit: 500_000        # $5,000 overdraft limit
    policy:
      type: "Fifo"               # Submit all transactions immediately

  - id: "BANK_B"
    opening_balance: 1_000_000
    credit_limit: 500_000
    policy:
      type: "Fifo"

lsm_config:
  bilateral_offsetting: true     # Enable payment netting
  cycle_detection: true          # Enable gridlock resolution
  max_iterations: 3
```

### 2. Create a Simulation (Python)

Create `run_simulation.py`:

```python
import requests
import yaml

# Load configuration
with open("my_first_sim.yaml") as f:
    config = yaml.safe_load(f)

# API base URL
BASE_URL = "http://localhost:8000"

# Create simulation
response = requests.post(f"{BASE_URL}/simulations", json=config)
response.raise_for_status()

sim_id = response.json()["simulation_id"]
print(f"✅ Simulation created: {sim_id}")

# Check initial state
state = requests.get(f"{BASE_URL}/simulations/{sim_id}/state").json()
print(f"\n📊 Initial State (Tick {state['current_tick']}):")
for agent_id, agent_data in state["agents"].items():
    print(f"  {agent_id}: Balance = ${agent_data['balance'] / 100:,.2f}")

# Submit a transaction: BANK_A → BANK_B for $500
tx_data = {
    "sender": "BANK_A",
    "receiver": "BANK_B",
    "amount": 50_000,        # $500 in cents
    "deadline_tick": 50,     # Must settle by tick 50
    "priority": 5,           # Normal priority
    "divisible": False,      # Cannot be split
}

tx_response = requests.post(
    f"{BASE_URL}/simulations/{sim_id}/transactions",
    json=tx_data
)
tx_id = tx_response.json()["transaction_id"]
print(f"\n💸 Transaction submitted: {tx_id}")

# Advance simulation by 10 ticks
tick_response = requests.post(
    f"{BASE_URL}/simulations/{sim_id}/tick",
    params={"count": 10}
)
print(f"\n⏩ Advanced 10 ticks")

# Check transaction status
tx_status = requests.get(
    f"{BASE_URL}/simulations/{sim_id}/transactions/{tx_id}"
).json()
print(f"\n📝 Transaction Status: {tx_status['status']}")

# Check final state
final_state = requests.get(f"{BASE_URL}/simulations/{sim_id}/state").json()
print(f"\n📊 Final State (Tick {final_state['current_tick']}):")
for agent_id, agent_data in final_state["agents"].items():
    balance = agent_data['balance'] / 100
    print(f"  {agent_id}: Balance = ${balance:,.2f}")

# Cleanup
requests.delete(f"{BASE_URL}/simulations/{sim_id}")
print(f"\n🗑️  Simulation deleted")
```

### 3. Run It!

```bash
python run_simulation.py
```

**Expected Output:**
```
✅ Simulation created: a1b2c3d4-5e6f-7g8h-9i0j-k1l2m3n4o5p6

📊 Initial State (Tick 0):
  BANK_A: Balance = $10,000.00
  BANK_B: Balance = $10,000.00

💸 Transaction submitted: tx_12345678

⏩ Advanced 10 ticks

📝 Transaction Status: settled

📊 Final State (Tick 10):
  BANK_A: Balance = $9,500.00
  BANK_B: Balance = $10,500.00

🗑️  Simulation deleted
```

**What happened?**
1. Created a simulation with 2 banks (each with $10,000)
2. BANK_A submitted a $500 payment to BANK_B
3. Advanced 10 ticks (simulated time)
4. Transaction settled immediately (sufficient liquidity + FIFO policy)
5. Balances updated: BANK_A lost $500, BANK_B gained $500

---

## Core Concepts

### Money = Integer Cents

All amounts are **i64 integers** representing cents (or the smallest currency unit).

```python
amount = 100_000  # $1,000.00
```

**Why?** Floating-point arithmetic causes rounding errors that compound over millions of transactions. Financial systems demand exact arithmetic.

### Determinism = Reproducibility

Same seed + same actions = **identical results**, every time.

```yaml
simulation:
  rng_seed: 42  # Use same seed for reproducible results
```

This is critical for:
- Debugging (replay exact scenarios)
- Research validation (peer review)
- Policy optimization (compare strategies fairly)

### Ticks = Discrete Time

Time advances in discrete **ticks** (e.g., 1 tick ≈ 10 minutes).

```yaml
simulation:
  ticks_per_day: 100  # 100 ticks = 1 business day
```

Each tick, the simulator:
1. Generates new transaction arrivals (if configured)
2. Policies decide which transactions to release
3. Settlement engine processes payments (RTGS + LSM)
4. Costs accrue (overdraft fees, delay penalties)

### Agents = Banks

Each **agent** represents a bank's settlement account at the central bank.

```yaml
agents:
  - id: "BANK_A"
    opening_balance: 1_000_000   # Initial reserves
    credit_limit: 500_000        # Daylight overdraft limit
    policy:
      type: "Fifo"  # Decision strategy
```

**Key Fields:**
- **Balance**: Current reserves in settlement account (can go negative up to credit limit)
- **Credit Limit**: Maximum daylight overdraft (intraday loan from central bank)
- **Policy**: Algorithm that decides when to submit queued transactions

### Policies = Decision Strategies

**Policies** control when agents release transactions to the settlement system.

**Built-in Policies:**

1. **FIFO (First-In-First-Out)**
   ```yaml
   policy:
     type: "Fifo"
   ```
   - Submit all transactions immediately
   - Simple baseline strategy

2. **Deadline-Aware**
   ```yaml
   policy:
     type: "Deadline"
     urgency_threshold: 10  # Submit if deadline within 10 ticks
   ```
   - Prioritize transactions approaching deadline
   - Hold non-urgent transactions

3. **Liquidity-Aware**
   ```yaml
   policy:
     type: "LiquidityAware"
     buffer_target: 100_000  # Keep $1,000 minimum balance
   ```
   - Preserve liquidity buffer
   - Hold transactions when balance is low
   - Submit urgent transactions even if buffer violated

### Settlement Flow

```
┌─────────────────────────────────────────────┐
│ 1. Transaction Arrival                      │
│    → Added to agent's internal queue        │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│ 2. Policy Evaluation (Each Tick)           │
│    → Agent's policy decides: Submit/Hold    │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│ 3. RTGS Settlement                          │
│    → Immediate settlement if liquidity OK   │
│    → Queue if insufficient liquidity        │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│ 4. LSM Optimization (If Enabled)            │
│    → Bilateral offsetting (A↔B netting)     │
│    → Cycle detection & settlement           │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│ 5. Balance Updates & Cost Accrual           │
│    → Overdraft fees, delay penalties        │
└─────────────────────────────────────────────┘
```

---

## Common Workflows

### Workflow 1: Manual Transaction Submission

Submit transactions explicitly via the API.

```python
# Create simulation
sim_id = create_simulation(config)

# Submit transaction
tx_id = submit_transaction(sim_id, {
    "sender": "BANK_A",
    "receiver": "BANK_B",
    "amount": 100_000,
    "deadline_tick": 50,
    "priority": 8,
    "divisible": False,
})

# Advance until settled
for tick in range(100):
    tick_result = advance_tick(sim_id)

    tx_status = get_transaction_status(sim_id, tx_id)
    if tx_status["status"] == "settled":
        print(f"Settled at tick {tick}")
        break
```

### Workflow 2: Automatic Arrivals

Configure automatic transaction generation (realistic simulation).

```yaml
agents:
  - id: "BANK_A"
    # ... other config ...
    arrival_config:
      rate_per_tick: 2.5  # Average 2-3 transactions per tick
      distribution:
        type: "LogNormal"
        mean_log: 11.5    # Median ~$1,000
        std_dev_log: 1.2  # Right-skewed distribution
      counterparty_weights:
        BANK_B: 0.5       # 50% of transactions go to BANK_B
        BANK_C: 0.3       # 30% to BANK_C
        BANK_D: 0.2       # 20% to BANK_D
      deadline_offset: 50 # Transactions have 50 ticks to settle
```

Then just advance ticks:

```python
# Run simulation
for day in range(10):
    for tick in range(100):
        result = advance_tick(sim_id)
        print(f"Day {day}, Tick {tick}: {result['num_arrivals']} arrivals, "
              f"{result['num_settlements']} settlements")
```

### Workflow 3: Policy Comparison

Compare different policies on the same scenario.

```python
import copy

# Base configuration
base_config = load_config("scenario.yaml")

# Run with FIFO policy
fifo_config = copy.deepcopy(base_config)
fifo_config["agents"][0]["policy"] = {"type": "Fifo"}
fifo_results = run_simulation(fifo_config, num_ticks=1000)

# Run with Deadline policy
deadline_config = copy.deepcopy(base_config)
deadline_config["agents"][0]["policy"] = {
    "type": "Deadline",
    "urgency_threshold": 10
}
deadline_results = run_simulation(deadline_config, num_ticks=1000)

# Compare metrics
print(f"FIFO:     {fifo_results['settlement_rate']:.2%} settled")
print(f"Deadline: {deadline_results['settlement_rate']:.2%} settled")
```

### Workflow 4: Deterministic Replay

Debug issues by replaying exact scenarios.

```python
# Original run
config = {"simulation": {"rng_seed": 12345}, ...}
result1 = run_simulation(config)

# Replay (identical results)
result2 = run_simulation(config)

assert result1 == result2  # Perfect determinism
```

---

## Configuration Reference

### Minimal Configuration

```yaml
simulation:
  ticks_per_day: 100
  num_days: 1
  rng_seed: 42

agents:
  - id: "BANK_A"
    opening_balance: 1_000_000
    credit_limit: 500_000
    policy:
      type: "Fifo"
```

### Full Configuration with All Options

See `sim_config_example.yaml` in the repository for a comprehensive example with:
- Multiple agents
- Automatic arrival generation
- Custom cost rates
- LSM configuration
- Advanced policies

---

## API Quick Reference

### Simulation Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/simulations` | Create new simulation |
| GET | `/simulations` | List all active simulations |
| GET | `/simulations/{id}/state` | Get current state |
| POST | `/simulations/{id}/tick` | Advance simulation |
| DELETE | `/simulations/{id}` | Delete simulation |

### Transaction Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/simulations/{id}/transactions` | Submit transaction |
| GET | `/simulations/{id}/transactions/{tx_id}` | Get transaction status |
| GET | `/simulations/{id}/transactions` | List/filter transactions |

### Utility Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API root (version info) |
| GET | `/health` | Health check |
| GET | `/docs` | Interactive API docs |

---

## Troubleshooting

### Problem: "ModuleNotFoundError: No module named 'payment_simulator'"

**Solution:** Install the Python package:
```bash
cd api
source .venv/bin/activate
uv pip install -e ".[dev]"
```

### Problem: "Simulation not found: {id}"

**Solution:** Simulations are stored in-memory. If the API server restarts, all simulations are lost. Create a new simulation.

### Problem: "Transaction submission failed: Agent not found"

**Solution:** Check that sender and receiver agent IDs match exactly (case-sensitive) the IDs in your configuration.

### Problem: Tests failing with "linker error"

**Solution:** Run Rust tests without PyO3:
```bash
cargo test --no-default-features
```

### Problem: Non-deterministic results with same seed

**Solution:** Ensure:
1. Same `rng_seed` in configuration
2. Same transaction submission order
3. Same tick advancement sequence
4. No external random sources (e.g., don't use `random.random()` in Python)

---

## Next Steps

- 📖 **Read API Examples**: See `docs/api_examples.md` for detailed usage patterns
- 🏗️ **Explore Architecture**: Read `docs/architecture.md` to understand system design
- 🎮 **Review Game Design**: See `docs/game_concept_doc.md` for domain model details
- 🧪 **Run Tests**: Explore test files for more usage examples
- 🚀 **Build Applications**: Use the API to build research tools, dashboards, or games

---

## Getting Help

- **Documentation**: See `/docs` directory
- **API Reference**: Interactive docs at http://localhost:8000/docs
- **Issues**: https://github.com/yourusername/cashman/issues
- **Examples**: Check `/api/tests/integration/` for working code

---

*Last updated: 2025-10-28*
