# Payment Simulator

> **Real-time payment settlement simulation for research and policy optimization**

[![Tests](https://img.shields.io/badge/tests-passing-success)]()
[![Rust](https://img.shields.io/badge/rust-1.70%2B-orange)]()
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()

A hybrid Rust-Python simulator for modeling Real-Time Gross Settlement (RTGS) systems like TARGET2, Fedwire, and CHAPS. Built for financial researchers, central banks, and policy analysts who need deterministic, high-performance payment system simulation.

## What is This?

Banks face a daily coordination problem: **liquidity costs money** (holding reserves, posting collateral), but **delay costs money too** (client SLAs, regulatory deadlines). This creates a game where banks must decide when to release payments—release early and risk running short, or hold back and risk gridlock.

This simulator models that game. It implements:

- **Two-Queue Architecture**: Internal bank queues (strategic) + RTGS central queue (mechanical)
- **T2-Compliant LSM**: Bilateral offsetting, multilateral cycle detection, algorithm sequencing
- **Programmable Policies**: JSON decision trees with 60+ context fields for AI-driven optimization
- **Deterministic Execution**: Same seed = identical results for reproducible research

For the full conceptual foundation, see **[Game Concept Document](docs/game_concept_doc.md)**.

## Quick Start

### Prerequisites

- **Rust 1.70+**: `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`
- **Python 3.11+** (3.13 recommended)
- **uv**: `pip install uv` (Astral's ultra-fast Python package manager)

### Installation

```bash
# Clone and build
git clone https://github.com/yourusername/payment-simulator.git
cd payment-simulator

# Build Rust engine + install Python package (one command)
cd api && uv sync --extra dev && cd ..

# Verify installation
cargo test --manifest-path backend/Cargo.toml --no-default-features
uv run --directory api pytest tests/
```

### Run Your First Simulation

```bash
# Run a demo scenario (3 banks, 100 ticks)
uv run --directory api payment-sim run scenarios/realistic_demo.yaml

# With verbose output (see every settlement event)
uv run --directory api payment-sim run scenarios/realistic_demo.yaml --verbose

# Persist results to database for later analysis
uv run --directory api payment-sim run scenarios/realistic_demo.yaml --persist
```

### Start API Server

```bash
uv run --directory api uvicorn payment_simulator.api.main:app --reload
# Visit http://localhost:8000/docs for interactive API documentation
```

## Key Features

| Feature | Description |
|---------|-------------|
| **RTGS Engine** | Real-time gross settlement with immediate finality |
| **LSM Optimization** | Bilateral offsets + multilateral cycles (T2-compliant) |
| **Policy Trees** | JSON decision trees for programmable bank strategies |
| **Scenario Events** | Scheduled interventions (liquidity shocks, collateral adjustments) |
| **Data Persistence** | DuckDB storage with checkpoint/replay support |
| **High Performance** | 1,000+ ticks/second, 200+ agent scale tested |

## Documentation

### Core Concepts
- **[Game Concept Document](docs/game_concept_doc.md)** — The "why" behind the simulation: RTGS, LSM, coordination problems, cost structures

### Reference Documentation

| Topic | Documentation |
|-------|---------------|
| **CLI** | [docs/reference/cli/](docs/reference/cli/index.md) — Commands, output modes, filtering |
| **Policy DSL** | [docs/reference/policy/](docs/reference/policy/index.md) — Decision trees, context fields, actions |
| **Configuration** | [docs/reference/orchestrator/](docs/reference/orchestrator/index.md) — Agent config, cost rates, scenario events |
| **Architecture** | [docs/reference/architecture/](docs/reference/architecture/) — System design, Rust-Python bridge |

### Developer Guide
- **[CLAUDE.md](CLAUDE.md)** — Development guidelines, invariants, testing strategy

## Architecture Overview

```
┌─────────────────────────────────────────────────┐
│  CLI (payment-sim) / REST API (FastAPI)         │
│  • Scenario loading, output modes               │
└──────────────────┬──────────────────────────────┘
                   │ FFI (PyO3)
┌──────────────────▼──────────────────────────────┐
│  Rust Simulation Engine                         │
│  • Tick loop, RTGS settlement, LSM optimization │
│  • Deterministic RNG, integer-only arithmetic   │
└─────────────────────────────────────────────────┘
```

**Design Philosophy**:
- Rust owns state; Python orchestrates
- FFI boundary is minimal and well-tested
- All persistence via DuckDB at end of each simulated day

## Running Tests

```bash
# Rust tests
cargo test --manifest-path backend/Cargo.toml --no-default-features

# Python tests
uv run --directory api pytest tests/
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Follow coding guidelines in [CLAUDE.md](CLAUDE.md)
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License — see [LICENSE](LICENSE) for details.

---

**Status**: Active development | **Tests**: 280+ passing | **Performance**: 1,000+ ticks/s

*Built for researchers who demand reproducibility, performance, and correctness.*
