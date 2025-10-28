# Payment Simulator

> **High-performance real-time payment settlement simulation for research and policy optimization**

[![Tests](https://img.shields.io/badge/tests-401%20passing-success)]()
[![Rust](https://img.shields.io/badge/rust-1.70%2B-orange)]()
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()

A hybrid Rust-Python simulator for modeling Real-Time Gross Settlement (RTGS) systems like TARGET2, Fedwire, and CHAPS. Built for financial researchers, central banks, and policy analysts who need deterministic, high-performance payment system simulation.

---

## ✨ Key Features

- **🚀 High Performance**: 1000+ ticks/second simulation throughput (Rust core)
- **🎯 100% Deterministic**: Same seed = identical results (perfect reproducibility for research)
- **💰 Exact Money Arithmetic**: Integer-only financial calculations (no floating-point errors)
- **🔄 RESTful API**: Complete FastAPI interface for easy integration
- **🧪 Comprehensive Testing**: 401 tests passing (279 Rust + 66 doc + 56 Python)
- **📊 Advanced Settlement**: RTGS + Liquidity-Saving Mechanisms (LSM) with gridlock resolution
- **🤖 Policy Framework**: FIFO, Deadline-aware, and Liquidity-aware strategies (extensible)
- **⚡ FFI Bridge**: High-performance PyO3 bindings (Rust ↔ Python)

---

## 🚀 Quick Start

### Prerequisites

- **Rust 1.70+**: `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`
- **Python 3.11+**: Recommended: Python 3.13
- **uv**: `pip install uv` (Python package manager)

### Installation (5 minutes)

```bash
# 1. Clone repository
git clone https://github.com/yourusername/cashman.git
cd cashman

# 2. Build Rust simulation engine
cd backend
cargo build --release
cd ..

# 3. Install Python API
cd api
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"
cd ..

# 4. Verify installation
pytest api/tests/  # Run Python tests
cargo test --no-default-features  # Run Rust tests
```

### Start API Server

```bash
cd api
source .venv/bin/activate
uvicorn payment_simulator.api.main:app --reload
```

Visit **http://localhost:8000/docs** for interactive API documentation.

### Run Your First Simulation (Python)

```python
import requests
import yaml

# Configuration
config = {
    "simulation": {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 42,  # For determinism
    },
    "agents": [
        {
            "id": "BANK_A",
            "opening_balance": 1_000_000,  # $10,000 in cents
            "credit_limit": 500_000,       # $5,000 overdraft
            "policy": {"type": "Fifo"},
        },
        {
            "id": "BANK_B",
            "opening_balance": 1_000_000,
            "credit_limit": 500_000,
            "policy": {"type": "Fifo"},
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
        "divisible": False,
    },
)
tx_id = tx.json()["transaction_id"]

# Advance simulation
requests.post(f"http://localhost:8000/simulations/{sim_id}/tick", params={"count": 10})

# Check result
status = requests.get(f"http://localhost:8000/simulations/{sim_id}/transactions/{tx_id}")
print(f"Status: {status.json()['status']}")  # "settled"

# Cleanup
requests.delete(f"http://localhost:8000/simulations/{sim_id}")
```

**Output**: Transaction settles immediately (sufficient liquidity + FIFO policy).

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| **[Getting Started](docs/getting_started.md)** | Installation, concepts, first simulation |
| **[API Examples](docs/api_examples.md)** | Production patterns, research workflows |
| **[Architecture](docs/architecture.md)** | System design, Rust-Python bridge |
| **[Game Design](docs/game_concept_doc.md)** | Domain model, settlement mechanics |
| **[API Reference](http://localhost:8000/docs)** | Interactive OpenAPI docs (when server running) |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│  REST API (FastAPI + Pydantic V2)              │
│  • Simulation lifecycle management              │
│  • Transaction submission & tracking            │
│  • Configuration validation                     │
└──────────────────┬──────────────────────────────┘
                   │ FFI (PyO3 0.27.1)
┌──────────────────▼──────────────────────────────┐
│  Rust Simulation Engine (High Performance)      │
│  • Discrete-event simulation (1000+ ticks/s)    │
│  • RTGS + LSM settlement engines                │
│  • Deterministic RNG (xorshift64*)              │
│  • Integer-only money arithmetic                │
└─────────────────────────────────────────────────┘
```

**Design Philosophy**:
- **Rust owns state**: Python gets snapshots, never mutable references
- **Python orchestrates**: Configuration, API, testing
- **FFI is thin**: Minimal, stable API surface
- **Performance-critical code in Rust**: Settlement, policies, simulation loop
- **Developer ergonomics in Python**: API, configuration, research tools

---

## 🎯 Core Concepts

### Domain Model

- **Agents** = Banks with settlement accounts at the central bank
- **Transactions** = Payment instructions (sender → receiver)
- **Ticks** = Discrete time steps (e.g., 1 tick ≈ 10 minutes)
- **Policies** = Algorithms that decide when to submit queued transactions
- **RTGS** = Real-Time Gross Settlement (immediate if liquidity sufficient)
- **LSM** = Liquidity-Saving Mechanisms (bilateral offsetting + cycle settlement)

### Settlement Flow

```
Transaction Arrival
    → Internal Queue (Queue 1)
    → Policy Evaluation (Submit? Hold? Drop?)
    → RTGS Attempt (settle immediately or queue)
    → LSM Optimization (bilateral/cycle resolution)
    → Balance Updates & Cost Accrual
```

### Built-in Policies

1. **FIFO**: Submit all transactions immediately (baseline)
2. **Deadline**: Prioritize transactions approaching deadline
3. **LiquidityAware**: Preserve liquidity buffer, hold when low

### Determinism

**Same seed + same actions = identical results**

```yaml
simulation:
  rng_seed: 42  # Fixed seed for reproducibility
```

Critical for:
- Research validation (peer review)
- Debugging (replay exact scenarios)
- Policy comparison (fair evaluation)

---

## 🧪 Use Cases

### 1. Central Bank Research

Model payment system behavior under stress:
- Liquidity shortages
- Bank failures
- Gridlock scenarios
- Policy interventions

### 2. Policy Optimization

Compare settlement strategies:
- FIFO vs Deadline vs LiquidityAware
- Custom policy development
- RL-based optimization (future)

### 3. Financial Network Analysis

Study systemic risk:
- Contagion modeling
- Network topology effects
- Critical node identification

### 4. Benchmarking & Standards

Validate compliance with:
- Basel III liquidity requirements
- PFMIs (Principles for Financial Market Infrastructures)
- Operational resilience standards

---

## 📊 Performance

**Hardware**: Apple M1 Max, 32GB RAM

| Metric | Value |
|--------|-------|
| **Simulation Throughput** | 1,200 ticks/second |
| **Agent Scale** | 50+ banks per simulation |
| **Transaction Volume** | 5 transactions/tick/agent |
| **Test Coverage** | 401 tests passing |
| **API Latency** | <10ms per tick (REST) |

---

## 🛠️ Development

### Project Structure

```
cashman/
├── backend/           # Rust simulation engine
│   ├── src/
│   │   ├── core/      # Time management, initialization
│   │   ├── models/    # Agent, Transaction, State
│   │   ├── settlement/# RTGS + LSM engines
│   │   ├── policy/    # Cash manager policies
│   │   ├── orchestrator/ # Main tick loop
│   │   └── ffi/       # PyO3 bindings
│   └── tests/         # 279 Rust tests
│
├── api/               # Python FastAPI layer
│   ├── payment_simulator/
│   │   ├── api/       # FastAPI endpoints
│   │   ├── config/    # Pydantic models
│   │   └── core/      # Lifecycle management
│   └── tests/         # 56 Python tests
│
└── docs/              # Documentation
    ├── getting_started.md
    ├── api_examples.md
    ├── architecture.md
    └── game_concept_doc.md
```

### Running Tests

```bash
# Rust tests (unit + integration)
cd backend
cargo test --no-default-features

# Python tests (FFI + API + config)
cd api
source .venv/bin/activate
pytest

# Rust doc tests
cd backend
cargo test --doc --no-default-features
```

### Code Quality

**Critical Invariants (Never Violate)**:
1. ✅ **Money is always i64** (integer cents, no floats)
2. ✅ **Determinism is sacred** (seeded RNG, no system time)
3. ✅ **FFI boundary is minimal** (simple types, batch operations)

See [CLAUDE.md](CLAUDE.md) for comprehensive development guidelines.

---

## 🔬 Research Examples

### Policy Comparison Study

```python
policies = [
    ("FIFO", {"type": "Fifo"}),
    ("Deadline", {"type": "Deadline", "urgency_threshold": 10}),
    ("LiquidityAware", {"type": "LiquidityAware", "buffer_target": 100_000}),
]

for policy_name, policy_config in policies:
    results = run_simulation(config, policy_config, num_ticks=1000)
    print(f"{policy_name}: {results['settlement_rate']:.2%} settled")
```

### Monte Carlo Simulation

```python
from concurrent.futures import ThreadPoolExecutor

def run_trial(seed):
    config["simulation"]["rng_seed"] = seed
    return run_simulation(config)

with ThreadPoolExecutor(max_workers=5) as executor:
    results = list(executor.map(run_trial, range(100)))

# Analyze distribution of outcomes
settlement_rates = [r["settlement_rate"] for r in results]
print(f"Mean: {np.mean(settlement_rates):.2%}")
print(f"Std:  {np.std(settlement_rates):.2%}")
```

### Stress Testing

```python
# High-volume scenario
config = {
    "agents": [create_agent(i, arrival_rate=5.0) for i in range(50)],
    "simulation": {"ticks_per_day": 100, "num_days": 10},
}

sim_id = client.create_simulation(config)
client.tick(sim_id, count=1000)  # 10 business days

# Analyze results
transactions = client.list_transactions(sim_id)
print(f"Total: {len(transactions)}, Settled: {sum(1 for tx in transactions if tx['status'] == 'settled')}")
```

---

## 🗺️ Roadmap

### ✅ Phase 1-7 Complete (Foundation)

- [x] Rust simulation core (RTGS, LSM, policies, arrivals)
- [x] PyO3 FFI bindings (24 tests passing)
- [x] Python configuration layer (Pydantic V2)
- [x] FastAPI REST API (23 integration tests)
- [x] Documentation (getting started, examples, architecture)

### 🎯 Phase 8: Frontend & Visualization (Future)

- [ ] React visualization dashboard
- [ ] WebSocket streaming for real-time updates
- [ ] Interactive simulation control
- [ ] Performance dashboards

### 🚀 Phase 9: Advanced Features (Future)

- [ ] Policy DSL (JSON decision trees for LLM-editable policies)
- [ ] RL integration (OpenAI Gym environment)
- [ ] Multi-currency support
- [ ] Cross-border payment modeling
- [ ] Historical data replay

---

## 📖 Citation

If you use this simulator in academic research, please cite:

```bibtex
@software{payment_simulator_2025,
  title = {Payment Simulator: High-Performance RTGS Simulation},
  author = {Your Name},
  year = {2025},
  url = {https://github.com/yourusername/cashman},
  note = {Version 0.1.0}
}
```

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Follow coding guidelines in [CLAUDE.md](CLAUDE.md)
4. Ensure all tests pass (`cargo test && pytest`)
5. Submit a pull request

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Built with [PyO3](https://pyo3.rs/) for Rust-Python interop
- Powered by [FastAPI](https://fastapi.tiangolo.com/) for REST API
- Inspired by TARGET2 and Fedwire settlement systems
- Research-grade simulation thanks to deterministic RNG

---

## 📞 Support

- **Documentation**: See [/docs](docs/) directory
- **Issues**: [GitHub Issues](https://github.com/yourusername/cashman/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/cashman/discussions)

---

**Status**: Production-ready foundation (95% complete) | **Tests**: 401 passing | **Performance**: 1000+ ticks/s

*Built for researchers who demand reproducibility, performance, and correctness.*
