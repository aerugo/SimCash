# CLI Reference

> Command-line interface for running and analyzing payment simulations

The `payment-sim` CLI is the primary interface for running simulations, replaying persisted results, managing databases, and generating documentation.

## Documentation

| Document | Description |
|----------|-------------|
| [run](commands/run.md) | Execute a simulation from a configuration file |
| [replay](commands/replay.md) | Replay a persisted simulation from database |
| [validate-policy](commands/validate-policy.md) | Validate a policy tree JSON file |
| [policy-schema](commands/policy-schema.md) | Generate policy schema documentation |
| [checkpoint](commands/checkpoint.md) | Manage simulation checkpoints |
| [db](commands/db.md) | Database management commands |
| [output-modes](output-modes.md) | Understanding different output formats |
| [filtering](filtering.md) | Filtering events during verbose output |
| [exit-codes](exit-codes.md) | Exit codes and error handling |

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

## Installation

The CLI is installed automatically with the payment-simulator package:

```bash
cd api
uv sync --extra dev
```

## Command Structure

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

## Global Options

| Option | Description |
|--------|-------------|
| `--version` | Show version and exit |
| `--help` | Show help message and exit |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PAYMENT_SIM_DB_PATH` | `simulation_data.db` | Default database path |
| `USE_NEW_RUNNER` | `true` | Enable new simulation runner |

## Related Documentation

- [Scenario Configuration](../scenario/index.md) - YAML configuration format
- [Policy Reference](../policy/index.md) - Policy DSL documentation
- [Architecture](../architecture/index.md) - System architecture

---

*Last updated: 2025-11-28*
