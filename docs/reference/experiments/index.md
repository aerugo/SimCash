# Experiment Framework

> YAML-driven LLM policy optimization experiments

**Version**: 2.0 (YAML-only experiments)

The `payment_simulator.experiments` module provides a framework for running LLM-based policy optimization experiments with bootstrap evaluation and statistical validation.

## Documentation

| Document | Description |
|----------|-------------|
| [Configuration](configuration.md) | ExperimentConfig YAML reference |
| [Runner](runner.md) | GenericExperimentRunner and VerboseConfig |
| [Analysis](analysis.md) | Charting, policy evolution, and analysis tools |

## Key Features

- **YAML-Only Configuration**: No Python code required
- **Inline System Prompts**: LLM prompts defined in YAML
- **Inline Policy Constraints**: Parameter bounds, allowed fields/actions in YAML
- **Bootstrap Evaluation**: Statistical policy comparison with paired samples
- **Deterministic Execution**: Same seed = same results
- **Multiple LLM Providers**: Anthropic, OpenAI, Google
- **Structured Verbose Logging**: Granular control via VerboseConfig

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Experiment Configuration (YAML)               │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  experiment.yaml                                         │    │
│  │  ├── name, description                                   │    │
│  │  ├── scenario: path/to/scenario.yaml                     │    │
│  │  ├── evaluation: {mode, num_samples, ticks}              │    │
│  │  ├── convergence: {max_iterations, stability_*}          │    │
│  │  ├── llm: {model, temperature, system_prompt}            │    │
│  │  ├── policy_constraints: {allowed_parameters, ...}       │    │
│  │  └── optimized_agents: [BANK_A, BANK_B]                  │    │
│  └─────────────────────────────────────────────────────────┘    │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    GenericExperimentRunner                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  For each iteration:                                     │    │
│  │  1. Generate bootstrap samples                           │    │
│  │  2. Evaluate current policy (old) on samples             │    │
│  │  3. LLM proposes new policy (using inline system_prompt) │    │
│  │  4. Validate against policy_constraints                  │    │
│  │  5. Evaluate new policy on SAME samples (paired)         │    │
│  │  6. Compute delta = old_cost - new_cost                  │    │
│  │  7. Accept if mean_delta > 0 (new is cheaper)            │    │
│  │  8. Check convergence                                    │    │
│  └─────────────────────────────────────────────────────────┘    │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Experiment Result                             │
│  ├── run_id, experiment_name                                    │
│  ├── final_costs, num_iterations, converged                     │
│  ├── convergence_reason                                         │
│  └── total_duration_seconds                                     │
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
  system_prompt: |
    You are an expert in payment system optimization.
    Generate valid JSON policies for the SimCash payment simulator.

policy_constraints:
  allowed_parameters:
    - name: urgency_threshold
      param_type: int
      min_value: 0
      max_value: 20
  allowed_fields:
    - system_tick_in_day
    - balance
  allowed_actions:
    payment_tree:
      - Release
      - Hold

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
├── analysis/
│   ├── __init__.py
│   ├── charting.py             # ExperimentChartService, render_convergence_chart
│   ├── evolution_model.py      # AgentEvolution, IterationEvolution
│   ├── evolution_service.py    # PolicyEvolutionService
│   └── policy_diff.py          # compute_policy_diff
├── persistence/
│   ├── __init__.py
│   └── repository.py           # ExperimentRepository
└── runner/
    ├── __init__.py
    ├── experiment_runner.py    # GenericExperimentRunner
    ├── result.py               # ExperimentResult, ExperimentState
    ├── verbose.py              # VerboseConfig, VerboseLogger
    └── optimization.py         # OptimizationLoop
```

## Related Documentation

- [CLI Commands](../cli/commands/experiment.md) - Command reference
- [LLM Module](../llm/index.md) - LLM configuration
- [Castro Reference](../castro/index.md) - Example YAML experiments

---

*Last updated: 2025-12-15*
