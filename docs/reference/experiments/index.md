# Experiment Framework

> YAML-driven LLM policy optimization experiments

The `payment_simulator.experiments` module provides a framework for running LLM-based policy optimization experiments with bootstrap evaluation and statistical validation.

## Documentation

| Document | Description |
|----------|-------------|
| [Configuration](configuration.md) | ExperimentConfig YAML reference |
| [Runner](runner.md) | Runner protocols and result dataclasses |

## Key Features

- **YAML Configuration**: Define experiments declaratively
- **Bootstrap Evaluation**: Statistical policy comparison with paired samples
- **Deterministic Execution**: Same seed = same results
- **Multiple LLM Providers**: Anthropic, OpenAI, Google
- **Audit Trail**: Full LLM interaction capture

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Experiment Configuration                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  experiment.yaml                                         │    │
│  │  ├── name, description                                   │    │
│  │  ├── scenario: path/to/scenario.yaml                     │    │
│  │  ├── evaluation: {mode, num_samples, ticks}              │    │
│  │  ├── convergence: {max_iterations, stability_*}          │    │
│  │  ├── llm: {model, temperature, thinking_budget}          │    │
│  │  └── optimized_agents: [BANK_A, BANK_B]                  │    │
│  └─────────────────────────────────────────────────────────┘    │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Experiment Runner                             │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  For each iteration:                                     │    │
│  │  1. Generate bootstrap samples                           │    │
│  │  2. Evaluate current policy (old) on samples             │    │
│  │  3. LLM proposes new policy                              │    │
│  │  4. Evaluate new policy on SAME samples (paired)         │    │
│  │  5. Compute delta = old_cost - new_cost                  │    │
│  │  6. Accept if mean_delta > 0 (new is cheaper)            │    │
│  │  7. Check convergence                                    │    │
│  └─────────────────────────────────────────────────────────┘    │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Experiment Result                             │
│  ├── run_id, experiment_name                                    │
│  ├── final_cost, best_cost                                      │
│  ├── num_iterations, converged                                  │
│  ├── convergence_reason                                         │
│  ├── per_agent_costs                                            │
│  └── iteration_records[]                                        │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Create Experiment YAML

```yaml
# experiments/my_experiment.yaml
name: my_experiment
description: "Policy optimization experiment"

scenario: configs/scenario.yaml

evaluation:
  mode: bootstrap
  num_samples: 10
  ticks: 12

convergence:
  max_iterations: 25
  stability_threshold: 0.05

llm:
  model: "anthropic:claude-sonnet-4-5"
  temperature: 0.0

optimized_agents:
  - BANK_A
  - BANK_B

master_seed: 42
```

### 2. Validate Configuration

```bash
payment-sim experiment validate experiments/my_experiment.yaml
```

### 3. Run Experiment

```bash
payment-sim experiment run experiments/my_experiment.yaml
```

## Evaluation Modes

### Bootstrap Mode (Recommended)

Uses paired comparison for statistical validity:

1. Generate N bootstrap samples
2. Evaluate OLD policy on all samples → costs_old[]
3. LLM proposes NEW policy
4. Evaluate NEW policy on SAME samples → costs_new[]
5. Compute delta_i = costs_old[i] - costs_new[i] for each sample
6. Accept if mean(delta) > 0 (positive delta means new policy is cheaper)

```yaml
evaluation:
  mode: bootstrap
  num_samples: 10  # Number of bootstrap samples
  ticks: 12        # Ticks per evaluation
```

**Key Insight**: Using the SAME samples for both policies eliminates sampling variance, making the comparison statistically valid.

### Deterministic Mode

Single evaluation without sampling:

```yaml
evaluation:
  mode: deterministic
  ticks: 2  # Ticks per evaluation
```

Best for scenarios with no stochastic elements.

## Convergence Criteria

```yaml
convergence:
  max_iterations: 25         # Maximum optimization iterations
  stability_threshold: 0.05  # Cost must be stable within 5%
  stability_window: 5        # For 5 consecutive iterations
  improvement_threshold: 0.01  # Minimum improvement to continue (1%)
```

Experiment stops when:
- `max_iterations` reached, OR
- Cost stable within `stability_threshold` for `stability_window` iterations, OR
- No improvement greater than `improvement_threshold`

## Module Structure

```
payment_simulator/experiments/
├── __init__.py
├── config/
│   ├── __init__.py
│   └── experiment_config.py    # ExperimentConfig, EvaluationConfig
└── runner/
    ├── __init__.py
    ├── protocol.py             # ExperimentRunnerProtocol
    ├── result.py               # ExperimentResult, IterationRecord
    └── output.py               # OutputHandlerProtocol, SilentOutput
```

## Integration with Castro

The Castro experiments use this framework:

```bash
# List Castro experiments
payment-sim experiment list experiments/castro/experiments/

# Validate Castro experiment
payment-sim experiment validate experiments/castro/experiments/exp1.yaml

# Run Castro experiment
castro run exp1  # Castro CLI wrapper
```

## Related Documentation

- [CLI Commands](../cli/commands/experiment.md) - Command reference
- [LLM Module](../llm/index.md) - LLM configuration
- [AI Cash Management](../ai_cash_mgmt/index.md) - Bootstrap evaluation details
- [Castro Reference](../castro/index.md) - Castro-specific documentation

---

*Last updated: 2025-12-10*
