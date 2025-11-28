# CLI Reference

> **Command**: `payment-sim`
> **Version**: 0.1.0
> **Framework**: Typer (Python CLI framework)

The Payment Simulator CLI (`payment-sim`) is the primary interface for running simulations, replaying persisted results, managing databases, and generating documentation.

## Installation

The CLI is installed automatically when you install the payment-simulator package:

```bash
cd api
uv sync --extra dev
```

After installation, the `payment-sim` command is available in your terminal.

## Quick Start

```bash
# Run a simulation
payment-sim run --config scenario.yaml

# Run with verbose output
payment-sim run --config scenario.yaml --verbose

# Persist results to database
payment-sim run --config scenario.yaml --persist

# Replay a simulation from database
payment-sim replay --simulation-id sim-abc123 --verbose

# List available simulations
payment-sim db simulations
```

## Command Overview

| Command | Description |
|---------|-------------|
| [`run`](commands/run.md) | Execute a simulation from a configuration file |
| [`replay`](commands/replay.md) | Replay a persisted simulation from database |
| [`validate-policy`](commands/validate-policy.md) | Validate a policy tree JSON file |
| [`policy-schema`](commands/policy-schema.md) | Generate policy schema documentation |
| [`checkpoint`](commands/checkpoint.md) | Manage simulation checkpoints (save/load/list/delete) |
| [`db`](commands/db.md) | Database management commands |

## Global Options

These options are available for all commands:

| Option | Description |
|--------|-------------|
| `--version` | Show version and exit |
| `--help` | Show help message and exit |

## Documentation Index

### Commands
- [run](commands/run.md) - Run simulations with various output modes
- [replay](commands/replay.md) - Replay persisted simulations
- [validate-policy](commands/validate-policy.md) - Validate policy tree JSON files
- [policy-schema](commands/policy-schema.md) - Generate policy documentation
- [checkpoint](commands/checkpoint.md) - Checkpoint management subcommands
- [db](commands/db.md) - Database management subcommands

### Concepts
- [Output Modes](output-modes.md) - Understanding different output formats
- [Event Filtering](filtering.md) - Filtering events during verbose/event-stream output
- [Exit Codes](exit-codes.md) - Exit codes and error handling

## Architecture

```
payment-sim
├── run                    # Main simulation command
├── replay                 # Database replay
├── validate-policy        # Policy validation
├── policy-schema          # Schema documentation
├── checkpoint             # Checkpoint subcommands
│   ├── save
│   ├── load
│   ├── list
│   └── delete
└── db                     # Database subcommands
    ├── init
    ├── migrate
    ├── validate
    ├── create-migration
    ├── list
    ├── info
    ├── simulations
    └── costs
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PAYMENT_SIM_DB_PATH` | `simulation_data.db` | Default database path for checkpoint commands |
| `USE_NEW_RUNNER` | `true` | Enable new simulation runner architecture (Phase 5.2) |

## Related Documentation

- [Scenario Configuration](../scenario/index.md) - YAML configuration format
- [Policy Reference](../policy/index.md) - Policy DSL documentation
- [Architecture](../architecture/10-cli-architecture.md) - CLI architecture details
