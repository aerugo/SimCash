# Configuration Reference

> Game configuration schemas for AI Cash Management

**Version**: 0.1.0
**Last Updated**: 2025-12-09

---

## Overview

The AI Cash Management module uses Pydantic models for configuration validation. All configurations can be defined in YAML or passed programmatically.

---

## GameConfig

Top-level configuration for an AI Cash Management game.

### Schema

```yaml
game_id: <string>                    # Required: Unique identifier
scenario_config: <path>              # Required: Path to scenario YAML
master_seed: <int>                   # Required: RNG seed for determinism

game_mode: <GameMode>                # Default: campaign_learning
optimized_agents: <dict>             # Required: Agents to optimize
default_llm_config: <LLMConfig>      # Required: Default LLM settings

optimization_schedule: <Schedule>    # Default: on_simulation_end
bootstrap: <BootstrapConfig>         # Default: see below
convergence: <ConvergenceCriteria>   # Default: see below
output: <OutputConfig>               # Optional: Persistence settings
```

### Field Reference

#### `game_id`

**Type**: `str`
**Required**: Yes
**Constraint**: Non-empty, valid identifier

Unique identifier for this game instance. Used for database storage and logging.

```yaml
game_id: "castro-exp1-2025-12-09"
```

---

#### `scenario_config`

**Type**: `str` (path)
**Required**: Yes

Path to the SimCash scenario YAML file defining agents, arrivals, and cost rates.

```yaml
scenario_config: "configs/12period_stochastic.yaml"
```

---

#### `master_seed`

**Type**: `int`
**Required**: Yes
**Constraint**: `0 <= seed <= 2^63 - 1`

Master RNG seed for deterministic execution. All derived seeds flow from this value.

```yaml
master_seed: 42
```

**Determinism Guarantee**: Same `master_seed` produces identical optimization trajectories.

---

#### `game_mode`

**Type**: `GameMode` enum
**Required**: No
**Default**: `campaign_learning`

| Value | Description |
|-------|-------------|
| `rl_optimization` | Optimize during running simulation (intra-simulation) |
| `campaign_learning` | Optimize between complete simulation runs (inter-simulation) |

```yaml
game_mode: campaign_learning
```

---

#### `optimized_agents`

**Type**: `dict[str, AgentOptimizationConfig]`
**Required**: Yes

Map of agent IDs to their optimization configurations.

```yaml
optimized_agents:
  BANK_A:
    llm_config: null  # Uses default_llm_config
  BANK_B:
    llm_config:
      provider: openai
      model: gpt-4o
```

---

#### `default_llm_config`

**Type**: `LLMConfig`
**Required**: Yes

Default LLM configuration for agents without explicit config.

```yaml
default_llm_config:
  provider: anthropic
  model: claude-sonnet-4-5-20250929
  temperature: 0.0
  max_retries: 3
```

---

#### `optimization_schedule`

**Type**: `OptimizationSchedule`
**Required**: No
**Default**: `{type: on_simulation_end}`

When to trigger optimization.

```yaml
optimization_schedule:
  type: every_x_ticks
  interval_ticks: 50
```

---

#### `bootstrap`

**Type**: `BootstrapConfig`
**Required**: No
**Default**: See BootstrapConfig defaults

Bootstrap sampling configuration for policy evaluation.

```yaml
bootstrap:
  num_samples: 20
  sample_method: bootstrap
  evaluation_ticks: 100
```

---

#### `convergence`

**Type**: `ConvergenceCriteria`
**Required**: No
**Default**: See ConvergenceCriteria defaults

Convergence detection settings.

```yaml
convergence:
  stability_threshold: 0.05
  stability_window: 5
  max_iterations: 50
```

---

#### `output`

**Type**: `OutputConfig`
**Required**: No
**Default**: `None`

Persistence and output settings.

```yaml
output:
  database_path: "results/game.db"
  verbose: true
```

---

## LLMConfig

Configuration for LLM providers.

### Schema

```yaml
provider: <LLMProviderType>          # Required: anthropic, openai, google
model: <string>                      # Required: Model identifier

temperature: <float>                 # Default: 0.0
max_retries: <int>                   # Default: 3
timeout_seconds: <int>               # Default: 120

# Provider-specific
reasoning_effort: <ReasoningEffort>  # OpenAI o1/o3 only
thinking_budget: <int>               # Anthropic extended thinking only
```

### Field Reference

#### `provider`

**Type**: `LLMProviderType` enum
**Required**: Yes

| Value | Description |
|-------|-------------|
| `anthropic` | Anthropic Claude models |
| `openai` | OpenAI GPT models |
| `google` | Google Gemini models |

```yaml
provider: anthropic
```

---

#### `model`

**Type**: `str`
**Required**: Yes

Model identifier as recognized by the provider.

| Provider | Example Models |
|----------|---------------|
| `anthropic` | `claude-sonnet-4-5-20250929`, `claude-opus-4-5-20251101` |
| `openai` | `gpt-4o`, `gpt-4-turbo`, `o1`, `o3` |
| `google` | `gemini-pro`, `gemini-1.5-pro` |

```yaml
model: claude-sonnet-4-5-20250929
```

---

#### `temperature`

**Type**: `float`
**Required**: No
**Constraint**: `0.0 <= temperature <= 2.0`
**Default**: `0.0`

Sampling temperature. Use `0.0` for deterministic output.

```yaml
temperature: 0.0  # Deterministic
```

---

#### `max_retries`

**Type**: `int`
**Required**: No
**Constraint**: `1 <= max_retries <= 10`
**Default**: `3`

Maximum retry attempts on validation failure.

```yaml
max_retries: 3
```

---

#### `timeout_seconds`

**Type**: `int`
**Required**: No
**Constraint**: `10 <= timeout <= 600`
**Default**: `120`

Request timeout in seconds.

```yaml
timeout_seconds: 120
```

---

#### `reasoning_effort`

**Type**: `ReasoningEffortType` enum
**Required**: No
**Default**: `None`

OpenAI o1/o3 reasoning effort level.

| Value | Description |
|-------|-------------|
| `low` | Minimal reasoning |
| `medium` | Moderate reasoning |
| `high` | Maximum reasoning |

```yaml
reasoning_effort: high
```

---

#### `thinking_budget`

**Type**: `int`
**Required**: No
**Constraint**: `1024 <= budget <= 128000`
**Default**: `None`

Anthropic extended thinking token budget.

```yaml
thinking_budget: 32000
```

---

## BootstrapConfig

Bootstrap sampling configuration for policy evaluation.

### Schema

```yaml
num_samples: <int>                   # Default: 20
sample_method: <SampleMethod>        # Default: bootstrap
evaluation_ticks: <int>              # Default: 100
parallel_workers: <int>              # Default: 1
```

### Field Reference

#### `num_samples`

**Type**: `int`
**Required**: No
**Constraint**: `5 <= num_samples <= 1000`
**Default**: `20`

Number of bootstrap samples per evaluation.

```yaml
num_samples: 20
```

---

#### `sample_method`

**Type**: `SampleMethod` enum
**Required**: No
**Default**: `bootstrap`

| Value | Description | Use Case |
|-------|-------------|----------|
| `bootstrap` | Sample with replacement | Standard bootstrap resampling |
| `permutation` | Shuffle order, preserve all | Test arrival order effects |
| `stratified` | Sample within quartiles | Preserve amount distribution |

```yaml
sample_method: bootstrap
```

---

#### `evaluation_ticks`

**Type**: `int`
**Required**: No
**Constraint**: `1 <= ticks <= 10000`
**Default**: `100`

Number of simulation ticks per sample evaluation.

```yaml
evaluation_ticks: 100
```

---

#### `parallel_workers`

**Type**: `int`
**Required**: No
**Constraint**: `1 <= workers <= 32`
**Default**: `1`

Number of parallel workers for evaluation (future enhancement).

```yaml
parallel_workers: 8
```

---

## ConvergenceCriteria

Convergence detection configuration.

### Schema

```yaml
metric: <string>                     # Default: total_cost
stability_threshold: <float>         # Default: 0.05
stability_window: <int>              # Default: 5
max_iterations: <int>                # Default: 50
improvement_threshold: <float>       # Default: 0.01
```

### Field Reference

#### `metric`

**Type**: `str`
**Required**: No
**Default**: `"total_cost"`

Metric to track for convergence detection.

```yaml
metric: total_cost
```

---

#### `stability_threshold`

**Type**: `float`
**Required**: No
**Constraint**: `0.001 <= threshold <= 0.5`
**Default**: `0.05`

Percentage change threshold to consider stable (5% = 0.05).

```yaml
stability_threshold: 0.05  # 5% change = stable
```

---

#### `stability_window`

**Type**: `int`
**Required**: No
**Constraint**: `2 <= window <= 20`
**Default**: `5`

Consecutive stable iterations required for convergence.

```yaml
stability_window: 5
```

---

#### `max_iterations`

**Type**: `int`
**Required**: No
**Constraint**: `5 <= max <= 500`
**Default**: `50`

Maximum iterations before forced convergence.

```yaml
max_iterations: 50
```

---

#### `improvement_threshold`

**Type**: `float`
**Required**: No
**Constraint**: `0.0 <= threshold <= 0.5`
**Default**: `0.01`

Minimum relative improvement to accept a new policy (1% = 0.01).

```yaml
improvement_threshold: 0.01  # Must improve >1% to accept
```

---

## OptimizationSchedule

When to trigger optimization.

### Schema

```yaml
type: <OptimizationScheduleType>     # Required
interval_ticks: <int>                # Required for every_x_ticks
```

### Schedule Types

#### `every_x_ticks`

Trigger every N ticks during simulation.

```yaml
optimization_schedule:
  type: every_x_ticks
  interval_ticks: 50
```

#### `after_eod`

Trigger after each end-of-day.

```yaml
optimization_schedule:
  type: after_eod
```

#### `on_simulation_end`

Trigger only after simulation completes.

```yaml
optimization_schedule:
  type: on_simulation_end
```

---

## OutputConfig

Persistence and output settings.

### Schema

```yaml
database_path: <path>                # Default: None
save_policy_diffs: <bool>            # Default: true
save_iteration_metrics: <bool>       # Default: true
verbose: <bool>                      # Default: false
```

### Field Reference

#### `database_path`

**Type**: `str` (path)
**Required**: No
**Default**: `None`

Path to DuckDB database for persistence.

```yaml
database_path: "results/game.db"
```

---

## Complete Example

```yaml
# AI Cash Management Game Configuration
game_id: "castro-exp2-stochastic"
scenario_config: "configs/castro_12period_aligned.yaml"
master_seed: 42

game_mode: campaign_learning

optimized_agents:
  BANK_A:
    llm_config: null  # Uses default
  BANK_B:
    llm_config:
      provider: openai
      model: gpt-4o
      temperature: 0.0

default_llm_config:
  provider: anthropic
  model: claude-sonnet-4-5-20250929
  temperature: 0.0
  max_retries: 3
  timeout_seconds: 120

optimization_schedule:
  type: on_simulation_end

bootstrap:
  num_samples: 10
  sample_method: bootstrap
  evaluation_ticks: 12

convergence:
  metric: total_cost
  stability_threshold: 0.05
  stability_window: 5
  max_iterations: 25
  improvement_threshold: 0.01

output:
  database_path: "results/exp2.db"
  verbose: true
```

---

## Implementation Location

| Component | File |
|-----------|------|
| GameConfig | `api/payment_simulator/ai_cash_mgmt/config/game_config.py` |
| LLMConfig | `api/payment_simulator/ai_cash_mgmt/config/llm_config.py` |
| BootstrapConfig | `api/payment_simulator/ai_cash_mgmt/config/game_config.py` |
| ConvergenceCriteria | `api/payment_simulator/ai_cash_mgmt/config/game_config.py` |
| CLI validation | `api/payment_simulator/cli/commands/ai_game.py` |

---

## Navigation

**Previous**: [Index](index.md)
**Next**: [Components](components.md)
