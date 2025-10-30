# Payment Simulator

> **Production-grade real-time payment settlement simulation for research and policy optimization**

[![Tests](https://img.shields.io/badge/tests-passing-success)]()
[![Rust](https://img.shields.io/badge/rust-1.70%2B-orange)]()
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()

A hybrid Rust-Python simulator for modeling Real-Time Gross Settlement (RTGS) systems like TARGET2, Fedwire, and CHAPS. Built for financial researchers, central banks, and policy analysts who need deterministic, high-performance payment system simulation with programmable settlement strategies.

## 🎯 Key Features

### Settlement & Optimization

- **RTGS Engine**: Real-time gross settlement
- **LSM Optimization**: Bilateral offsetting and cycle detection
- **Transaction Splitting**: Voluntary payment pacing for large transactions
- **Gridlock Resolution**: Automatic detection and resolution via LSM
- **Cost Modeling**: Overdraft, delay, split friction, deadline penalties

### Policy Framework

- **Built-in Policies**: FIFO, Deadline-aware, Liquidity-aware
- **Policy Tree DSL**: JSON decision trees with 15+ condition types
- **Extensible**: Add custom policies via Rust or JSON
- **LLM-Ready**: Structured format for AI-driven policy evolution (coming soon)

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

### Liquidity-Saving Mechanisms (LSM)

**Bilateral Offsetting**: Net transactions between two banks
- Example: Bank A owes B $100M, B owes A $80M → settle net $20M A→B

**Cycle Detection**: Find circular payment chains and settle simultaneously
- Example: A→B→C→A cycle with $100M each → settles with zero net liquidity

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

**Test Coverage**: 60+ Rust tests + 24 FFI tests + 23 API tests + 71 persistence tests = **178+ tests passing**

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

**Status**: Phase 7 (Integration) + Phase 10 (Persistence) Complete | Ready for Phase 11 (LLM Manager)
**Version**: 0.10.0 | **Tests**: 178+ passing | **Performance**: 1000+ ticks/s
**Next Milestone**: LLM-driven policy optimization with shadow replay validation (Phase 11)

**Phase 10 Achievement**: Full database persistence with DuckDB + Polars (71 tests passing)
- ✅ Mandatory daily persistence of all transactions and agent metrics
- ✅ Policy provenance tracking for reproducible research
- ✅ Checkpoint system for save/load orchestrator state
- ✅ Query interface with 9 analytical functions

*Built for researchers who demand reproducibility, performance, and correctness.*
*Designed for the future of AI-assisted financial system optimization.*