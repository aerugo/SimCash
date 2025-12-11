# ai-game

> AI Cash Management CLI commands for LLM-based policy optimization

**Version**: 0.1.0
**Last Updated**: 2025-12-11

---

## Overview

The `ai-game` command group provides utilities for the AI Cash Management module, which enables LLM-based policy optimization for bank payment strategies.

```bash
payment-sim ai-game <subcommand> [OPTIONS]
```

## Subcommands

| Command | Description |
|---------|-------------|
| `validate` | Validate a game configuration file |
| `info` | Show module information and capabilities |
| `config-template` | Generate a configuration template |
| `schema` | Output JSON schema for configuration types |

---

## validate

Validate a game configuration file against the GameConfig schema.

### Synopsis

```bash
payment-sim ai-game validate <config-path>
```

### Arguments

| Argument | Description |
|----------|-------------|
| `config-path` | Path to game configuration YAML file |

### Examples

```bash
# Validate a config file
payment-sim ai-game validate my_game.yaml

# Output on success:
# Configuration is valid!
# Game ID: my_optimization_game
# Master seed: 42
# Optimized agents: ['BANK_A', 'BANK_B']

# Output on failure:
# Error: Configuration validation failed:
#   • master_seed: Input should be greater than or equal to 0
#   • optimized_agents: Field required
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Configuration is valid |
| 1 | Validation failed or file not found |

---

## info

Display information about the AI Cash Management module.

### Synopsis

```bash
payment-sim ai-game info
```

### Output

Shows:
- Available game modes (RL Optimization, Campaign Learning)
- Key features
- Available commands

### Example

```bash
payment-sim ai-game info

# AI Cash Management Module
# ========================================
#
# LLM-based policy optimization for payment settlement simulation.
#
# Available Game Modes:
#   • rl_optimization
#     Intra-simulation optimization with tick-based triggers
#   • campaign_learning
#     Inter-simulation optimization between complete runs
#
# Key Features:
#   • Bootstrap evaluation of policies
#   • Per-agent LLM configuration (different banks, different models)
#   • Deterministic execution (same seed = same results)
#   • Convergence detection with configurable thresholds
#   • Transaction sampling from historical data
```

---

## config-template

Generate a YAML configuration template with sensible defaults.

### Synopsis

```bash
payment-sim ai-game config-template [OPTIONS]
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `-o`, `--output` | PATH | stdout | Output file path |
| `-m`, `--mode` | TEXT | `rl_optimization` | Game mode |

### Examples

```bash
# Print template to stdout
payment-sim ai-game config-template

# Save to file
payment-sim ai-game config-template -o my_game_config.yaml

# Generate campaign learning template
payment-sim ai-game config-template --mode campaign_learning -o campaign.yaml
```

### Template Structure

```yaml
game_id: my_optimization_game
scenario_config: path/to/scenario.yaml
master_seed: 42

optimized_agents:
  BANK_A:
    llm_config: null  # Uses default_llm_config
  BANK_B:
    llm_config:
      provider: anthropic
      model: claude-3-opus
      reasoning_effort: high

default_llm_config:
  provider: openai
  model: gpt-5.2
  reasoning_effort: high
  temperature: 0.0
  max_retries: 3
  timeout_seconds: 120

optimization_schedule:
  type: every_x_ticks  # or on_simulation_end
  interval_ticks: 50

bootstrap:
  num_samples: 20
  sample_method: bootstrap
  evaluation_ticks: 100
  parallel_workers: 4

convergence:
  stability_threshold: 0.05
  stability_window: 3
  max_iterations: 50
  improvement_threshold: 0.01
```

---

## schema

Output JSON schema for configuration types.

### Synopsis

```bash
payment-sim ai-game schema <schema-type>
```

### Arguments

| Argument | Description |
|----------|-------------|
| `schema-type` | Schema to output |

### Available Schema Types

| Type | Description |
|------|-------------|
| `game-config` | Full GameConfig schema |
| `llm-config` | LLMConfig schema |
| `bootstrap` | BootstrapConfig schema |
| `convergence` | ConvergenceCriteria schema |

### Examples

```bash
# Get full game config schema
payment-sim ai-game schema game-config

# Get LLM config schema for editor integration
payment-sim ai-game schema llm-config > llm-config.schema.json

# Pipe to jq for pretty printing
payment-sim ai-game schema bootstrap | jq .
```

### Use Cases

- **IDE Integration**: Use schemas for YAML autocompletion
- **Documentation**: Generate documentation from schemas
- **Validation**: Custom validation tooling

---

## Configuration Reference

For detailed configuration documentation, see:
- [AI Cash Management Index](../../ai_cash_mgmt/index.md)
- [Configuration Reference](../../ai_cash_mgmt/configuration.md)

### Quick Configuration Example

```yaml
# game_config.yaml
game_id: policy_optimization_001
scenario_config: scenarios/3bank_stochastic.yaml
master_seed: 42

optimized_agents:
  BANK_A: {}
  BANK_B: {}

default_llm_config:
  provider: anthropic
  model: claude-sonnet-4-5-20250929
  temperature: 0.0

optimization_schedule:
  type: after_eod
  min_remaining_days: 2

bootstrap:
  num_samples: 30
  sample_method: bootstrap
  evaluation_ticks: 200

convergence:
  stability_threshold: 0.03
  stability_window: 5
  max_iterations: 100
```

---

## Game Modes

### RL Optimization

Intra-simulation optimization where policies are updated during a single simulation run.

```yaml
optimization_schedule:
  type: every_x_ticks
  interval_ticks: 50
```

- Optimizes at tick intervals (e.g., every 50 ticks)
- Good for adaptive policies that respond to changing conditions
- Higher computational cost

### Campaign Learning

Inter-simulation optimization where complete simulations are run, then policies are updated.

```yaml
optimization_schedule:
  type: on_simulation_end
  min_remaining_repetitions: 1
```

- Optimizes between full simulation runs
- Lower computational cost per iteration
- Better for finding stable equilibrium strategies

---

## Related Documentation

- [AI Cash Management Overview](../../ai_cash_mgmt/index.md)
- [Configuration Reference](../../ai_cash_mgmt/configuration.md)
- [Components Reference](../../ai_cash_mgmt/components.md)
- [CLI Index](../index.md)

---

## Navigation

**Up**: [CLI Reference](../index.md)
