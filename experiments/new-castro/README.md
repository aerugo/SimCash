# Castro Experiments

Clean-slate implementation of Castro et al. (2025) experiments using the `ai_cash_mgmt` module.

## Overview

This module replicates the experiments from "Estimating Policy Functions in Payment Systems Using Reinforcement Learning" (Castro et al., 2025) using LLM-based policy optimization instead of traditional RL methods.

**Key Features**:
- Three experiments matching the paper's scenarios
- LLM-based policy generation (Anthropic Claude, OpenAI GPT)
- Monte Carlo policy evaluation
- Deterministic execution via seeded RNG
- Full persistence to DuckDB

## Quick Start

```bash
# Install dependencies
cd experiments/new-castro
pip install -e .

# List available experiments
python cli.py list

# Run experiment 1 (2-period deterministic)
python cli.py run exp1

# Run with custom settings
python cli.py run exp2 --model gpt-4o --max-iter 50 --output ./results
```

## Experiments

| Experiment | Description | Ticks | Samples |
|------------|-------------|-------|---------|
| `exp1` | 2-Period Deterministic Nash Equilibrium | 2 | 1 |
| `exp2` | 12-Period Stochastic LVTS-Style | 12 | 10 |
| `exp3` | Joint Liquidity & Timing Optimization | 3 | 10 |

### Experiment 1: 2-Period Deterministic

Validates Nash equilibrium with deferred crediting. Two banks exchange payments with known amounts and deadlines.

**Expected Outcome**: Bank A posts 0 collateral, Bank B posts 20,000.

```bash
python cli.py run exp1
```

### Experiment 2: 12-Period Stochastic

LVTS-style realistic scenario with Poisson arrivals and LogNormal payment amounts.

```bash
python cli.py run exp2 --seed 42
```

### Experiment 3: Joint Optimization

Tests interaction between initial liquidity decisions and payment timing strategies.

```bash
python cli.py run exp3
```

## Architecture

```
new-castro/
├── castro/
│   ├── __init__.py          # Public API
│   ├── constraints.py       # CASTRO_CONSTRAINTS
│   ├── experiments.py       # Experiment definitions
│   ├── llm_client.py        # LLM client (Anthropic/OpenAI)
│   ├── runner.py            # ExperimentRunner
│   └── simulation.py        # CastroSimulationRunner
├── configs/
│   ├── exp1_2period.yaml    # 2-period scenario
│   ├── exp2_12period.yaml   # 12-period scenario
│   └── exp3_joint.yaml      # Joint optimization scenario
├── tests/
│   └── test_experiments.py  # Unit tests
├── cli.py                   # Typer CLI
├── pyproject.toml           # Package config
└── README.md                # This file
```

## CLI Commands

### `run` - Run an experiment

```bash
python cli.py run <experiment> [OPTIONS]

Arguments:
  experiment    Experiment key: exp1, exp2, or exp3

Options:
  -m, --model TEXT      LLM model [default: claude-sonnet-4-5-20250929]
  -i, --max-iter INT    Max iterations [default: 25]
  -o, --output PATH     Output directory [default: results]
  -s, --seed INT        Master seed [default: 42]
```

### `list` - List experiments

```bash
python cli.py list
```

### `info` - Show experiment details

```bash
python cli.py info exp1
```

### `validate` - Validate configuration

```bash
python cli.py validate exp2
```

## Configuration

### Castro Constraints

The module enforces Castro paper rules via `CASTRO_CONSTRAINTS`:

```python
from castro.constraints import CASTRO_CONSTRAINTS

# Allowed parameters
# - initial_liquidity_fraction: 0.0 - 1.0
# - urgency_threshold: 0 - 20
# - liquidity_buffer: 0.5 - 3.0

# Allowed actions
# - payment_tree: Release, Hold (no Split)
# - collateral_tree: PostCollateral, HoldCollateral
# - bank_tree: NoAction
```

### LLM Providers

Supports both Anthropic and OpenAI:

```bash
# Anthropic (default)
python cli.py run exp1 --model claude-sonnet-4-5-20250929

# OpenAI
python cli.py run exp1 --model gpt-4o
```

Set API keys via environment variables:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
```

## Programmatic Usage

```python
import asyncio
from castro import create_exp1, ExperimentRunner

# Create experiment
exp = create_exp1(model="claude-sonnet-4-5-20250929")

# Run optimization
runner = ExperimentRunner(exp)
result = asyncio.run(runner.run())

# Access results
print(f"Final cost: ${result.final_cost / 100:.2f}")
print(f"Converged: {result.converged}")
print(f"Iterations: {result.num_iterations}")

# Per-agent costs
for agent_id, cost in result.per_agent_costs.items():
    print(f"  {agent_id}: ${cost / 100:.2f}")

# Best policies found
for agent_id, policy in result.best_policies.items():
    print(f"{agent_id} policy: {policy}")
```

## Output

Results are persisted to DuckDB:

```
results/
├── exp1.db    # Experiment 1 results
├── exp2.db    # Experiment 2 results
└── exp3.db    # Experiment 3 results
```

Query results:

```python
import duckdb

conn = duckdb.connect("results/exp1.db")

# View game sessions
conn.execute("SELECT * FROM game_sessions").fetchall()

# View policy iterations
conn.execute("""
    SELECT agent_id, iteration_number, old_cost, new_cost, was_accepted
    FROM policy_iterations
    ORDER BY iteration_number
""").fetchall()
```

## Testing

```bash
cd experiments/new-castro
pytest tests/ -v
```

## Dependencies

- `payment-simulator` - SimCash core with ai_cash_mgmt module
- `anthropic` - Anthropic API client
- `openai` - OpenAI API client
- `typer` - CLI framework
- `rich` - Terminal formatting
- `pyyaml` - YAML parsing

## Design Principles

1. **No Legacy Code**: Built from scratch using only `ai_cash_mgmt`
2. **No Backwards Compatibility**: Clean break from legacy Castro experiments
3. **Deterministic**: Same seed produces identical results
4. **Type Safe**: Full type annotations, mypy strict mode
5. **Testable**: Comprehensive unit tests

## References

- Castro, M., et al. (2025). "Estimating Policy Functions in Payment Systems Using Reinforcement Learning"
- [ai_cash_mgmt Documentation](../../docs/reference/ai_cash_mgmt/index.md)
- [SimCash Architecture](../../docs/architecture.md)
