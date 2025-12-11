# Experiment Configuration

> YAML configuration reference for experiments

## ExperimentConfig

The `ExperimentConfig` class loads and validates experiment configuration from YAML files.

### Import

```python
from payment_simulator.experiments.config import ExperimentConfig
```

### Loading Configuration

```python
from pathlib import Path
from payment_simulator.experiments.config import ExperimentConfig

config = ExperimentConfig.from_yaml(Path("experiments/exp1.yaml"))

print(f"Name: {config.name}")
print(f"Scenario: {config.scenario_path}")
print(f"Mode: {config.evaluation.mode}")
print(f"Agents: {config.optimized_agents}")
```

## YAML Schema

### Complete Example

```yaml
# Experiment identification
name: exp2
description: "12-Period Stochastic LVTS-Style"

# Scenario configuration file (relative path)
scenario: configs/exp2_12period.yaml

# Evaluation settings
evaluation:
  mode: bootstrap          # "bootstrap" or "deterministic"
  num_samples: 10          # Bootstrap samples (bootstrap mode only)
  ticks: 12                # Ticks per evaluation

# Convergence criteria
convergence:
  max_iterations: 25       # Maximum optimization iterations
  stability_threshold: 0.05  # Cost stability threshold (5%)
  stability_window: 5        # Stable iterations required
  improvement_threshold: 0.01  # Minimum improvement to continue

# LLM configuration
llm:
  model: "anthropic:claude-sonnet-4-5"
  temperature: 0.0
  max_retries: 3
  timeout_seconds: 120
  # thinking_budget: 8000   # Anthropic extended thinking (optional)
  # reasoning_effort: high  # OpenAI reasoning effort (optional)

# Agents to optimize
optimized_agents:
  - BANK_A
  - BANK_B

# Constraints module (Python import path)
constraints: castro.constraints.CASTRO_CONSTRAINTS

# Output settings
output:
  directory: results       # Output directory
  database: exp2.db        # Database filename
  verbose: true            # Verbose logging

# Master seed for reproducibility
master_seed: 42
```

## Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Unique experiment identifier |
| `scenario` | path | Path to scenario YAML file |
| `evaluation` | object | Evaluation mode settings |
| `convergence` | object | Convergence criteria |
| `llm` | object | LLM provider configuration |
| `optimized_agents` | list | Agent IDs to optimize |

## Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `description` | string | `""` | Human-readable description |
| `constraints` | string | `""` | Python module path for constraints |
| `output` | object | see below | Output settings |
| `master_seed` | integer | `42` | Master seed for determinism |

## Section Reference

### evaluation

Controls how policies are evaluated.

```yaml
evaluation:
  mode: bootstrap    # Evaluation mode
  num_samples: 10    # Bootstrap samples (required for bootstrap mode)
  ticks: 12          # Ticks per evaluation run
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mode` | string | `"bootstrap"` | `"bootstrap"` or `"deterministic"` |
| `num_samples` | integer | `10` | Number of bootstrap samples |
| `ticks` | integer | *required* | Ticks per evaluation |

#### Bootstrap Mode

Uses paired comparison with bootstrap resampling:

```yaml
evaluation:
  mode: bootstrap
  num_samples: 10
  ticks: 12
```

**Process**:
1. Generate N bootstrap samples from transaction history
2. Evaluate OLD policy on all N samples
3. Evaluate NEW policy on SAME N samples
4. Compute paired delta for each sample
5. Accept if mean(delta) > 0

#### Deterministic Mode

Single evaluation without sampling:

```yaml
evaluation:
  mode: deterministic
  ticks: 2
```

Best for scenarios with no random elements.

### convergence

Controls when optimization stops.

```yaml
convergence:
  max_iterations: 25
  stability_threshold: 0.05
  stability_window: 5
  improvement_threshold: 0.01
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_iterations` | integer | `50` | Maximum iterations |
| `stability_threshold` | float | `0.05` | Cost stability % |
| `stability_window` | integer | `5` | Consecutive stable iterations |
| `improvement_threshold` | float | `0.01` | Minimum improvement % |

**Stopping Conditions** (any triggers stop):
- Reached `max_iterations`
- Cost within `stability_threshold` for `stability_window` iterations
- Improvement below `improvement_threshold`

### llm

LLM provider configuration.

```yaml
llm:
  model: "anthropic:claude-sonnet-4-5"
  temperature: 0.0
  max_retries: 3
  timeout_seconds: 120
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `model` | string | *required* | Model in `provider:model` format |
| `temperature` | float | `0.0` | Sampling temperature |
| `max_retries` | integer | `3` | Retry attempts on failure |
| `timeout_seconds` | integer | `120` | Request timeout |
| `thinking_budget` | integer | `null` | Anthropic thinking tokens |
| `reasoning_effort` | string | `null` | OpenAI: `low`, `medium`, `high` |

See [LLM Configuration](../llm/configuration.md) for details.

### output

Output settings.

```yaml
output:
  directory: results
  database: experiments.db
  verbose: true
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `directory` | path | `"results"` | Output directory |
| `database` | string | `"experiments.db"` | Database filename |
| `verbose` | boolean | `true` | Enable verbose logging |

## Dataclass Reference

### ExperimentConfig

```python
@dataclass
class ExperimentConfig:
    name: str
    description: str
    scenario_path: Path
    evaluation: EvaluationConfig
    convergence: ConvergenceCriteria
    llm: LLMConfig
    optimized_agents: list[str]
    constraints_module: str
    output: OutputConfig
    master_seed: int = 42

    @classmethod
    def from_yaml(cls, path: Path) -> ExperimentConfig: ...

    def load_constraints(self) -> Any: ...
```

### EvaluationConfig

```python
@dataclass
class EvaluationConfig:
    ticks: int
    mode: str = "bootstrap"
    num_samples: int | None = 10
```

### OutputConfig

```python
@dataclass
class OutputConfig:
    directory: Path = Path("results")
    database: str = "experiments.db"
    verbose: bool = True
```

## Validation

Configuration is validated on load:

```python
from payment_simulator.experiments.config import ExperimentConfig

try:
    config = ExperimentConfig.from_yaml(Path("experiment.yaml"))
except FileNotFoundError:
    print("Config file not found")
except ValueError as e:
    print(f"Invalid config: {e}")
```

### Validation Rules

- `name` must be non-empty
- `scenario` path must be specified
- `evaluation.ticks` must be positive
- `evaluation.mode` must be `"bootstrap"` or `"deterministic"`
- `convergence.max_iterations` must be positive
- `llm.model` must be in `provider:model` format
- `optimized_agents` must be non-empty list

## CLI Validation

```bash
# Validate configuration
payment-sim experiment validate experiments/exp1.yaml

# Output:
# Configuration is valid!
# Name: exp1
# Description: 2-Period Deterministic Nash Equilibrium
# Scenario: configs/exp1_2period.yaml
# Evaluation mode: deterministic
# Optimized agents: ['BANK_A', 'BANK_B']
# Master seed: 42
```

## Related Documentation

- [Experiment Runner](runner.md) - Runner and result types
- [Experiment CLI](../cli/commands/experiment.md) - CLI reference
- [LLM Configuration](../llm/configuration.md) - LLM settings

---

*Last updated: 2025-12-10*
