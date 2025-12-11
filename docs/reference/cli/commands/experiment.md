# experiment

Commands for running LLM policy optimization experiments.

**Version**: 2.0 (YAML-only experiments)

## Synopsis

```bash
payment-sim experiment <command> [OPTIONS]
```

## Description

The `experiment` command group provides tools for running, validating, and managing LLM policy optimization experiments. Experiments are configured entirely via YAML files—no Python code required. Includes inline system prompts and policy constraints for self-contained experiment definitions.

## Commands

| Command | Description |
|---------|-------------|
| `validate` | Validate an experiment configuration file |
| `info` | Show information about the experiment framework |
| `template` | Generate an experiment configuration template |
| `list` | List experiments in a directory |
| `run` | Run an experiment from configuration |

## validate

Validate an experiment YAML configuration file.

### Synopsis

```bash
payment-sim experiment validate <config-path>
```

### Arguments

| Argument | Type | Description |
|----------|------|-------------|
| `config-path` | Path | Path to experiment YAML configuration file |

### Examples

```bash
# Validate a configuration file
payment-sim experiment validate experiments/exp1.yaml

# Validate with full path
payment-sim experiment validate /path/to/my_experiment.yaml
```

### Output

```
Configuration is valid!
Name: exp1
Description: 2-Period Deterministic Nash Equilibrium
Scenario: configs/exp1_2period.yaml
Evaluation mode: deterministic
Optimized agents: ['BANK_A', 'BANK_B']
Master seed: 42
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Configuration is valid |
| 1 | Configuration file not found, invalid YAML, or missing required fields |

---

## info

Show information about the experiment framework.

### Synopsis

```bash
payment-sim experiment info
```

### Description

Displays module capabilities, evaluation modes, key features, and available commands.

### Output

```
Experiment Framework
========================================

YAML-driven LLM policy optimization experiments.

Evaluation Modes:
  • bootstrap - Bootstrap resampling for statistical validation
    Uses paired comparison: same samples, both policies
    Accepts new policy when mean_delta > 0

  • deterministic - Single deterministic evaluation
    Faster but no statistical confidence

Key Features:
  • YAML configuration for experiments
  • Bootstrap paired comparison for policy acceptance
  • Configurable convergence criteria
  • Per-agent LLM configuration
  • Deterministic execution (same seed = same results)

Commands:
  experiment validate <config.yaml>  - Validate a config file
  experiment template                - Generate a config template
  experiment list <directory>        - List experiments in directory
  experiment run <config.yaml>       - Run an experiment
  experiment info                    - Show this information
```

---

## template

Generate an experiment configuration template.

### Synopsis

```bash
payment-sim experiment template [OPTIONS]
```

### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--output` | `-o` | Path | stdout | Write template to file instead of stdout |

### Examples

```bash
# Print template to stdout
payment-sim experiment template

# Write to file
payment-sim experiment template -o my_experiment.yaml
```

### Output

Generates a YAML template with all configuration options:

```yaml
name: my_experiment
description: Description of your experiment
scenario: configs/scenario.yaml
evaluation:
  mode: bootstrap
  num_samples: 10
  ticks: 12
convergence:
  max_iterations: 50
  stability_threshold: 0.05
  stability_window: 5
  improvement_threshold: 0.01
llm:
  model: anthropic:claude-sonnet-4-5
  temperature: 0.0
  max_retries: 3
  timeout_seconds: 120
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
output:
  directory: results
  database: experiments.db
  verbose: true
master_seed: 42
```

---

## list

List all experiments in a directory.

### Synopsis

```bash
payment-sim experiment list <directory>
```

### Arguments

| Argument | Type | Description |
|----------|------|-------------|
| `directory` | Path | Directory containing experiment YAML files |

### Examples

```bash
# List experiments in castro directory
payment-sim experiment list experiments/castro/experiments/

# List experiments in current directory
payment-sim experiment list .
```

### Output

```
Experiments in experiments/castro/experiments:
----------------------------------------

  exp1.yaml
    Name: exp1
    Description: 2-Period Deterministic Nash Equilibrium
    Mode: deterministic
    Agents: ['BANK_A', 'BANK_B']

  exp2.yaml
    Name: exp2
    Description: 12-Period Stochastic LVTS-Style
    Mode: bootstrap
    Agents: ['BANK_A', 'BANK_B']

  exp3.yaml
    Name: exp3
    Description: Joint Liquidity & Timing Optimization
    Mode: bootstrap
    Agents: ['BANK_A', 'BANK_B']

Total: 3 experiment(s)
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success (directory found, even if empty) |
| 1 | Directory not found or not a directory |

---

## run

Run an experiment from a configuration file.

### Synopsis

```bash
payment-sim experiment run <config-path> [OPTIONS]
```

### Arguments

| Argument | Type | Description |
|----------|------|-------------|
| `config-path` | Path | Path to experiment YAML configuration file |

### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--seed` | `-s` | Integer | from config | Override master seed |
| `--dry-run` | - | Boolean | `false` | Validate config without running |
| `--verbose` | `-v` | Boolean | `false` | Enable verbose output |

### Examples

```bash
# Run with defaults
payment-sim experiment run experiments/exp1.yaml

# Dry run (validate only)
payment-sim experiment run experiments/exp1.yaml --dry-run

# Override seed for reproducibility
payment-sim experiment run experiments/exp1.yaml --seed 12345

# Verbose output
payment-sim experiment run experiments/exp1.yaml --verbose
```

### Output (--dry-run)

```
Loaded experiment: exp1
  Description: 2-Period Deterministic Nash Equilibrium
  Evaluation: deterministic (None samples)
  Agents: ['BANK_A', 'BANK_B']
  Max iterations: 25

[Dry run] Configuration is valid. Skipping execution.
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Configuration error or execution failure |
| 130 | Interrupted by user (Ctrl+C) |

---

## Configuration File Format

Experiments are configured via YAML files. See the full schema below.

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Experiment identifier |
| `scenario` | path | Path to scenario YAML file |
| `evaluation` | object | Evaluation settings |
| `convergence` | object | Convergence criteria |
| `llm` | object | LLM configuration |
| `optimized_agents` | list | Agent IDs to optimize |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `description` | string | `""` | Human-readable description |
| `policy_constraints` | object | `null` | Inline policy constraints (preferred) |
| `constraints` | string | `""` | Python module path (legacy, deprecated) |
| `output` | object | see below | Output configuration |
| `master_seed` | integer | `42` | Master seed for reproducibility |

### Evaluation Section

```yaml
evaluation:
  mode: bootstrap      # or "deterministic"
  num_samples: 10      # Number of bootstrap samples (bootstrap mode only)
  ticks: 12            # Ticks per evaluation
```

**Bootstrap Mode**: Uses paired comparison - same samples evaluated with both old and new policies. Policy accepted when `mean_delta > 0` (new policy is cheaper).

**Deterministic Mode**: Single evaluation with no sampling. Best for deterministic scenarios.

### Convergence Section

```yaml
convergence:
  max_iterations: 25           # Maximum optimization iterations
  stability_threshold: 0.05    # Cost stability threshold (5%)
  stability_window: 5          # Number of stable iterations required
  improvement_threshold: 0.01  # Minimum improvement to continue (1%)
```

### LLM Section

```yaml
llm:
  model: "anthropic:claude-sonnet-4-5"  # provider:model format
  temperature: 0.0                       # Sampling temperature
  max_retries: 3                        # Retry attempts on failure
  timeout_seconds: 120                  # Request timeout
  system_prompt: |                       # Inline system prompt (preferred)
    You are an expert in payment system optimization.
    Generate valid JSON policies for the SimCash payment simulator.
  # Provider-specific (optional):
  # thinking_budget: 8000               # Anthropic extended thinking
  # reasoning_effort: high              # OpenAI reasoning effort
```

**Supported Providers**:
- `anthropic:` - Claude models (claude-sonnet-4-5, etc.)
- `openai:` - GPT models (gpt-4o, o1, o3, etc.)
- `google:` - Gemini models (gemini-2.5-flash, etc.)

### Policy Constraints Section (Inline)

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

Defines what the LLM can generate:
- **allowed_parameters**: Parameter bounds (name, type, min/max)
- **allowed_fields**: Context fields usable in conditions
- **allowed_actions**: Valid actions per decision tree

### Output Section

```yaml
output:
  directory: results           # Output directory
  database: experiments.db     # Database filename
  verbose: true               # Enable verbose logging
```

### Complete Example

```yaml
name: exp2
description: "12-Period Stochastic LVTS-Style"

scenario: configs/exp2_12period.yaml

evaluation:
  mode: bootstrap
  num_samples: 10
  ticks: 12

convergence:
  max_iterations: 25
  stability_threshold: 0.05
  stability_window: 5
  improvement_threshold: 0.01

llm:
  model: "anthropic:claude-sonnet-4-5"
  temperature: 0.0
  max_retries: 3
  timeout_seconds: 120
  system_prompt: |
    You are an expert in payment system optimization.
    Generate valid JSON policies for the SimCash payment simulator.

    Key considerations:
    - Minimize total cost (delay penalties + overdraft fees)
    - Balance liquidity efficiency against settlement risk
    - Consider timing based on ticks_to_deadline

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

optimized_agents:
  - BANK_A
  - BANK_B

output:
  directory: results
  database: exp2.db
  verbose: true

master_seed: 42
```

---

## Related Commands

- [`ai-game`](ai-game.md) - AI Cash Management game commands
- [`run`](run.md) - Run a simulation
- [`replay`](replay.md) - Replay a persisted simulation

## Related Documentation

- [Experiments Module](../../experiments/index.md) - Full experiments reference
- [LLM Module](../../llm/index.md) - LLM configuration reference
- [AI Cash Management](../../ai_cash_mgmt/index.md) - Bootstrap evaluation details

## Implementation Details

**File**: `api/payment_simulator/cli/commands/experiment.py`

The experiment command uses the experiment framework from `payment_simulator.experiments`.

---

*Last updated: 2025-12-11*
