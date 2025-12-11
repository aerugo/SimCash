# Castro Experiments

YAML configuration files for replicating Castro et al. (2025) "Estimating Policy Functions in Payment Systems Using Reinforcement Learning" using the SimCash payment simulator.

## Overview

This directory contains **YAML-only experiment configurations** for the Castro paper experiments. All Python code for running experiments is in the core `payment_simulator` module.

**Key Features:**
- Three experiments matching the paper's scenarios (2-period, 12-period, joint optimization)
- LLM-based policy generation via the core experiments framework
- Support for Anthropic Claude, OpenAI GPT, and Google Gemini
- Bootstrap policy evaluation with paired comparison
- Deterministic execution via seeded RNG
- Full persistence with replay support

---

## Directory Structure

```
experiments/castro/
├── experiments/           # Experiment YAML configurations
│   ├── exp1.yaml         # 2-Period Deterministic Nash Equilibrium
│   ├── exp2.yaml         # 12-Period Stochastic LVTS-Style
│   └── exp3.yaml         # Joint Liquidity & Timing Optimization
├── configs/               # Scenario YAML configurations
│   ├── exp1_2period.yaml
│   ├── exp2_12period.yaml
│   └── exp3_joint.yaml
├── papers/                # Reference papers
│   └── castro_et_al.md
├── README.md              # This file
└── pyproject.toml         # Minimal metadata (no dependencies)
```

---

## Requirements

All experiments run via the core SimCash CLI. Make sure you have the `api` package installed:

```bash
cd /path/to/SimCash/api
uv sync --extra dev
```

---

## Running Experiments

Use the core `payment-sim experiment` CLI:

```bash
# List available experiments
payment-sim experiment list experiments/castro/experiments/

# Show experiment details
payment-sim experiment info

# Validate configuration
payment-sim experiment validate experiments/castro/experiments/exp1.yaml

# Run an experiment
payment-sim experiment run experiments/castro/experiments/exp1.yaml

# Run with verbose output
payment-sim experiment run experiments/castro/experiments/exp1.yaml --verbose

# Run with custom seed
payment-sim experiment run experiments/castro/experiments/exp1.yaml --seed 12345

# Dry run (validate without executing)
payment-sim experiment run experiments/castro/experiments/exp1.yaml --dry-run
```

---

## Experiments

| Experiment | Description | Mode | Ticks |
|------------|-------------|------|-------|
| **exp1** | 2-Period Deterministic Nash Equilibrium | deterministic | 2 |
| **exp2** | 12-Period Stochastic LVTS-Style | bootstrap (10 samples) | 12 |
| **exp3** | Joint Liquidity & Timing Optimization | bootstrap (10 samples) | 10 |

### Experiment 1: 2-Period Deterministic

Validates Nash equilibrium with deferred crediting:
- 2 ticks per day, 1 day
- Deterministic payment arrivals
- Expected: Bank A posts 0%, Bank B posts 20%

### Experiment 2: 12-Period Stochastic

LVTS-style realistic scenario:
- 12 ticks per day
- Poisson arrivals, LogNormal amounts
- Uses bootstrap sampling for statistical validation

### Experiment 3: Joint Liquidity & Timing

Optimizes both initial collateral AND payment timing:
- Tests interaction between liquidity and timing decisions
- Uses bootstrap sampling for evaluation

---

## Configuration Schema

Each experiment YAML contains:

```yaml
name: exp1
description: "2-Period Deterministic Nash Equilibrium"

scenario: configs/exp1_2period.yaml

evaluation:
  mode: deterministic  # or "bootstrap"
  ticks: 2
  num_samples: 10      # for bootstrap mode

convergence:
  max_iterations: 25
  stability_threshold: 0.05
  stability_window: 5

llm:
  model: "anthropic:claude-sonnet-4-5"
  temperature: 0.0
  system_prompt: |
    You are an expert in payment system optimization...

policy_constraints:
  allowed_parameters: [...]
  allowed_fields: [...]
  allowed_actions:
    payment_tree: [Release, Hold]
    collateral_tree: [PostCollateral, HoldCollateral]

optimized_agents:
  - BANK_A
  - BANK_B

output:
  directory: results
  database: exp1.db
  verbose: true

master_seed: 42
```

---

## The Castro Paper

### Reference

Castro, P., Desai, A., Du, H., Garratt, R., & Rivadeneyra, F. (2025). *Estimating Policy Functions in Payment Systems Using Reinforcement Learning*. ACM Transactions on Economics and Computation, 13(1), Article 1.

### Paper Summary

The paper addresses **liquidity management in high-value payment systems (HVPS)**, where banks must balance:

1. **Initial liquidity cost** (`r_c`): Cost of posting collateral at the start of the day
2. **Delay cost** (`r_d`): Cost of delaying customer payments
3. **End-of-day borrowing cost** (`r_b`): Emergency borrowing from central bank

Banks face a **strategic game**: posting more liquidity is costly, but delaying payments to wait for incoming funds risks customer dissatisfaction.

---

## LLM Providers

Supports multiple providers with unified `provider:model` format:

| Provider | Example Models | API Key |
|----------|----------------|---------|
| `anthropic` | `claude-sonnet-4-5`, `claude-opus-4` | `ANTHROPIC_API_KEY` |
| `openai` | `gpt-4o`, `gpt-5.2`, `o1`, `o3` | `OPENAI_API_KEY` |
| `google` | `gemini-2.5-flash`, `gemini-2.5-pro` | `GOOGLE_API_KEY` |

Set API keys via environment variables:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
export GOOGLE_API_KEY=...
```

---

## Expected Outcomes

### Experiment 1: Nash Equilibrium

| Agent | Optimal Liquidity | Reasoning |
|-------|-------------------|-----------|
| Bank A | 0% | Free-rides on B's payment in period 1 |
| Bank B | 20% | Must cover period-1 demand |

**Pass criteria:** Nash gap < 0.02 for both agents

### Experiment 2: Learning Curve

- Total costs decrease monotonically over iterations
- Cost reduction > 30% from initial to final iteration
- Higher-demand agent posts more collateral

### Experiment 3: Joint Optimization

- When `r_d < r_c`: Agents delay more, post less collateral
- When `r_d > r_c`: Agents post more, delay less

---

## References

- Castro, M., et al. (2025). "Estimating Policy Functions in Payment Systems Using Reinforcement Learning"
- [Experiments Framework Documentation](../../docs/reference/experiments/index.md)
- [LLM Module Documentation](../../docs/reference/llm/index.md)
- [SimCash Architecture](../../docs/architecture.md)

---

*Last updated: 2025-12-11*
