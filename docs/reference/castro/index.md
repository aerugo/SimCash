# Castro Experiments Reference

**Version**: 2.0
**Last Updated**: 2025-12-11

---

## Overview

Castro is a collection of **YAML-only experiment configurations** for replicating the work from Castro et al. (2025) "Estimating Policy Functions in Payment Systems Using Reinforcement Learning".

**Important**: As of version 2.0, Castro contains **no Python code**. All experiment execution is handled by the core `payment_simulator.experiments` framework.

---

## Directory Structure

```
experiments/castro/
├── experiments/               # Experiment YAML configurations
│   ├── exp1.yaml             # 2-Period Deterministic Nash Equilibrium
│   ├── exp2.yaml             # 12-Period Stochastic LVTS-Style
│   └── exp3.yaml             # Joint Liquidity & Timing Optimization
├── configs/                   # Scenario YAML configurations
│   ├── exp1_2period.yaml
│   ├── exp2_12period.yaml
│   └── exp3_joint.yaml
├── papers/                    # Reference papers
│   └── castro_et_al.md
├── README.md                  # Documentation
└── pyproject.toml             # Minimal metadata (no dependencies)
```

---

## Quick Start

### Prerequisites

Ensure you have the `api` package installed:

```bash
cd /path/to/SimCash/api
uv sync --extra dev
```

### Running Experiments

All experiments run via the core `payment-sim experiment` CLI:

```bash
# List available experiments
payment-sim experiment list experiments/castro/experiments/

# Show experiment details
payment-sim experiment info

# Validate configuration
payment-sim experiment validate experiments/castro/experiments/exp1.yaml

# Run an experiment (requires LLM API key)
payment-sim experiment run experiments/castro/experiments/exp1.yaml

# Run with verbose output
payment-sim experiment run experiments/castro/experiments/exp1.yaml --verbose

# Dry-run (validate without LLM calls)
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

## YAML Configuration

Each experiment YAML contains all configuration needed for execution:

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
    You are an expert in payment system optimization.
    Generate valid JSON policies for the SimCash payment simulator.
    ...

policy_constraints:
  allowed_parameters:
    - name: initial_liquidity_fraction
      param_type: float
      min_value: 0.0
      max_value: 1.0
    - name: urgency_threshold
      param_type: int
      min_value: 0
      max_value: 20
  allowed_fields:
    - system_tick_in_day
    - ticks_to_deadline
    - balance
    - effective_liquidity
  allowed_actions:
    payment_tree:
      - Release
      - Hold
    collateral_tree:
      - PostCollateral
      - HoldCollateral

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

## Key Features

### Inline System Prompt

The LLM system prompt is defined directly in the YAML, making experiments self-contained:

```yaml
llm:
  model: "anthropic:claude-sonnet-4-5"
  system_prompt: |
    You are an expert in payment system optimization.
    Generate valid JSON policies...
```

### Inline Policy Constraints

Policy constraints are also inline, defining what the LLM can generate:

```yaml
policy_constraints:
  allowed_parameters:
    - name: initial_liquidity_fraction
      param_type: float
      min_value: 0.0
      max_value: 1.0
```

### Multiple LLM Providers

Supports Anthropic, OpenAI, and Google models:

```yaml
# Anthropic
llm:
  model: "anthropic:claude-sonnet-4-5"

# OpenAI
llm:
  model: "openai:gpt-4o"

# Google
llm:
  model: "google:gemini-2.5-flash"
```

---

## Environment Variables

Set your API key for the LLM provider:

```bash
# Anthropic
export ANTHROPIC_API_KEY=sk-ant-...

# OpenAI
export OPENAI_API_KEY=sk-...

# Google
export GOOGLE_API_KEY=...
```

---

## Architecture

Castro experiments use the core experiment framework:

```
┌─────────────────────────────────────────────────────────────────┐
│  Castro YAML Configuration                                       │
│  ├── experiments/exp1.yaml                                       │
│  ├── experiments/exp2.yaml                                       │
│  └── experiments/exp3.yaml                                       │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  Core Experiment Framework (payment_simulator.experiments)       │
│  ├── ExperimentConfig.from_yaml()                               │
│  ├── GenericExperimentRunner                                    │
│  ├── Bootstrap evaluation                                        │
│  └── CLI commands (run, validate, list, info)                   │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  LLM Module (payment_simulator.llm)                              │
│  ├── PydanticAILLMClient                                        │
│  └── AuditCaptureLLMClient                                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Migration from Version 1.x

Version 2.0 removed all Python code from Castro. If you were using the old `castro` CLI:

| Old Command | New Command |
|-------------|-------------|
| `castro run exp1` | `payment-sim experiment run experiments/castro/experiments/exp1.yaml` |
| `castro list` | `payment-sim experiment list experiments/castro/experiments/` |
| `castro info exp1` | `payment-sim experiment validate experiments/castro/experiments/exp1.yaml` |
| `castro results` | Use experiment database directly |
| `castro replay <id>` | Not yet available in core CLI |

---

## Related Documentation

- [Experiment Framework](../experiments/index.md) - Core experiment infrastructure
- [LLM Module](../llm/index.md) - LLM client protocols and configuration
- [CLI Reference](../cli/commands/experiment.md) - Experiment CLI commands
- [AI Cash Management](../ai_cash_mgmt/index.md) - Bootstrap evaluation details

---

## Reference

Castro, P., et al. (2025). "Estimating Policy Functions in Payment Systems Using Reinforcement Learning". ACM Transactions on Economics and Computation.

---

*Last updated: 2025-12-11*
