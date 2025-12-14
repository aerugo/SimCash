# Experiment Configuration

> YAML configuration reference for experiments

**Version**: 2.0 (YAML-only experiments)

## Overview

Experiments are defined entirely in YAML—no Python code required. All configuration including LLM system prompts and policy constraints are specified inline in the experiment YAML file.

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
print(f"System Prompt: {config.llm.system_prompt[:50]}...")  # Inline prompt
print(f"Constraints: {config.get_constraints()}")  # Inline constraints
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

# LLM configuration with inline system prompt
llm:
  model: "anthropic:claude-sonnet-4-5"
  temperature: 0.0
  max_retries: 3
  timeout_seconds: 120
  # thinking_budget: 8000   # Anthropic extended thinking (optional)
  # reasoning_effort: high  # OpenAI reasoning effort (optional)
  system_prompt: |
    You are an expert in payment system optimization.
    Generate valid JSON policies for the SimCash payment simulator.

    When generating policies, consider:
    - Cost minimization through strategic timing
    - Liquidity efficiency using bilateral offsets
    - Risk management via deadline awareness

# Inline policy constraints (preferred over constraints module)
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

# Agents to optimize
optimized_agents:
  - BANK_A
  - BANK_B

# Output settings
output:
  directory: results              # Output directory
  database: simulation_data.db    # Database filename
  verbose: true                   # Verbose logging

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
| `policy_constraints` | object | `null` | Inline policy constraints (preferred) |
| `constraints` | string | `""` | Python module path (legacy, deprecated) |
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
1. **Initial simulation**: Run one simulation to collect transaction history
2. **Sample generation**: Bootstrap resample N transaction sets from history
3. **Sandbox evaluation**: Each sample runs on isolated 3-agent sandbox (AGENT, SOURCE, SINK)
4. **Paired comparison**: Evaluate BOTH old and new policies on SAME N samples
5. **Decision**: Accept new policy if `mean(cost_old - cost_new) > 0`

**Key Features**:
- **True bootstrap**: Resamples from observed transactions (not parametric Monte Carlo)
- **Isolated evaluation**: 3-agent sandbox removes inter-agent confounding
- **Paired deltas**: Same samples ensure statistical validity
- **LLM context**: Includes initial simulation output + best/worst sample traces

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

#### Convergence Behavior by Evaluation Mode

**Important**: The meaning of "cost stability" differs between evaluation modes:

| Mode | Behavior |
|------|----------|
| **Deterministic** | Same seed every iteration. Cost changes **only** when policy changes. If policy stays the same, `relative_change = 0` (always "stable"). |
| **Bootstrap** | Sample seeds are deterministic per `sample_idx`. Same policy → same costs. Behaves identically to deterministic mode. |

**Practical implication**: In both modes, convergence triggers when **policies stop being accepted** for `stability_window` consecutive iterations. This could mean:

1. **Optimization complete**: LLM can't find improvements → rejections → stable costs → converged ✓
2. **LLM stuck**: LLM generates invalid/worse policies → rejections → stable costs → converged (false positive)

To distinguish these cases, monitor the `accepted_changes` field in iteration records. If all recent iterations show rejections, the convergence may be due to LLM limitations rather than true optimization completion.

### llm

LLM provider configuration with inline system prompt.

```yaml
llm:
  model: "anthropic:claude-sonnet-4-5"
  temperature: 0.0
  max_retries: 3
  timeout_seconds: 120
  system_prompt: |
    You are an expert in payment system optimization.
    Generate valid JSON policies for the SimCash payment simulator.
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `model` | string | *required* | Model in `provider:model` format |
| `temperature` | float | `0.0` | Sampling temperature |
| `max_retries` | integer | `3` | Retry attempts on failure |
| `timeout_seconds` | integer | `120` | Request timeout |
| `system_prompt` | string | `null` | Inline system prompt (preferred) |
| `system_prompt_file` | path | `null` | Path to prompt file (alternative) |
| `thinking_budget` | integer | `null` | Anthropic thinking tokens |
| `reasoning_effort` | string | `null` | OpenAI: `low`, `medium`, `high` |

**System Prompt Priority**: If both `system_prompt` (inline) and `system_prompt_file` are specified, the inline `system_prompt` takes precedence.

See [LLM Configuration](../llm/configuration.md) for details.

### policy_constraints

Inline policy constraints define what the LLM can generate. This is the **preferred** approach (replaces the legacy `constraints` module pattern).

```yaml
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
```

| Field | Type | Description |
|-------|------|-------------|
| `allowed_parameters` | list | Parameters the LLM can set |
| `allowed_fields` | list | Context fields the LLM can use in conditions |
| `allowed_actions` | object | Actions per tree type |

#### allowed_parameters

Each parameter has:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Parameter name |
| `param_type` | string | `"int"` or `"float"` |
| `min_value` | number | Minimum allowed value |
| `max_value` | number | Maximum allowed value |

#### allowed_actions

Maps tree names to allowed action lists:

```yaml
allowed_actions:
  payment_tree:      # Decision tree for payments
    - Release        # Send payment immediately
    - Hold           # Queue payment
  collateral_tree:   # Decision tree for collateral
    - PostCollateral
    - HoldCollateral
```

### output

Output settings.

```yaml
output:
  directory: results
  database: simulation_data.db
  verbose: true
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `directory` | path | `"results"` | Output directory |
| `database` | string | `"simulation_data.db"` | Database filename |
| `verbose` | boolean | `true` | Enable verbose logging |

## Dataclass Reference

### ExperimentConfig

```python
@dataclass(frozen=True)
class ExperimentConfig:
    name: str
    description: str
    scenario_path: Path
    evaluation: EvaluationConfig
    convergence: ConvergenceConfig
    llm: LLMConfig
    optimized_agents: tuple[str, ...]
    constraints_module: str  # Legacy, deprecated
    output: OutputConfig
    master_seed: int = 42
    policy_constraints: ScenarioConstraints | None = None  # Preferred

    @classmethod
    def from_yaml(cls, path: Path) -> ExperimentConfig: ...

    def get_constraints(self) -> ScenarioConstraints | None:
        """Get constraints (inline or from module). Prefers inline."""
        ...

    def with_seed(self, seed: int) -> ExperimentConfig:
        """Return new config with updated seed (immutable)."""
        ...
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
    database: str = "simulation_data.db"
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

*Last updated: 2025-12-13*
