# checkpoint

Manage simulation checkpoints for save/load functionality.

## Synopsis

```bash
payment-sim checkpoint [SUBCOMMAND] [OPTIONS]
```

## Description

The `checkpoint` command group provides tools for saving and restoring simulation state. Checkpoints allow you to:

- Save simulation state at any point
- Resume simulations from saved checkpoints
- Create snapshots for debugging or analysis
- Manage checkpoint storage

## Subcommands

| Subcommand | Description |
|------------|-------------|
| [`save`](#save) | Save simulation checkpoint to database |
| [`load`](#load) | Load simulation checkpoint from database |
| [`list`](#list) | List available checkpoints |
| [`delete`](#delete) | Delete checkpoint(s) from database |

---

## save

Save a simulation checkpoint to the database.

### Synopsis

```bash
payment-sim checkpoint save [OPTIONS]
```

### Required Options

| Option | Short | Type | Description |
|--------|-------|------|-------------|
| `--simulation-id` | `-s` | String | Simulation ID for this checkpoint. |
| `--state-file` | `-f` | Path | Path to state JSON file from `orchestrator.save_state()`. |
| `--config` | `-c` | Path | Path to simulation config YAML file. |

### Optional Flags

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--description` | `-d` | String | None | Human-readable description. |
| `--type` | `-t` | String | `manual` | Checkpoint type: `manual`, `auto`, `eod`, `final`. |

### Checkpoint Types

| Type | Use Case |
|------|----------|
| `manual` | User-initiated checkpoint (default) |
| `auto` | Automatically created at regular intervals |
| `eod` | End-of-day checkpoint |
| `final` | Final simulation state |

### Examples

```bash
# Basic checkpoint save
payment-sim checkpoint save \
  --simulation-id sim_001 \
  --state-file state.json \
  --config config.yaml

# With description
payment-sim checkpoint save \
  --simulation-id sim_001 \
  --state-file state.json \
  --config config.yaml \
  --description "After 50 ticks - before stress event"

# End-of-day checkpoint
payment-sim checkpoint save \
  --simulation-id sim_001 \
  --state-file eod_state.json \
  --config config.yaml \
  --type eod \
  --description "End of day 1"
```

### Output

```
✓ Checkpoint saved successfully
  Checkpoint ID: abc12345-6789-0123-4567-890abcdef012
  Simulation ID: sim_001
  Tick: 50
  Day: 0
```

### State File Format

The state file should be JSON output from `orchestrator.save_state()`:

```json
{
  "current_tick": 50,
  "current_day": 0,
  "agents": [...],
  "transactions": [...],
  "rng_seed": 12345
}
```

---

## load

Load and restore a simulation from a checkpoint.

### Synopsis

```bash
payment-sim checkpoint load [OPTIONS]
```

### Required Options

| Option | Short | Type | Description |
|--------|-------|------|-------------|
| `--config` | - | Path | Configuration file (YAML). |

### Optional Flags

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--checkpoint-id` | `-c` | String | None | Checkpoint ID to load. |
| `--simulation-id` | `-s` | String | None | Simulation ID (for `latest` checkpoint). |
| `--output` | `-o` | Path | None | Save restored state to file. |

**Note**: Either `--checkpoint-id` or `--simulation-id` (with `latest`) must be provided.

### Loading Methods

1. **By Checkpoint ID**: Load a specific checkpoint
2. **By Simulation ID (latest)**: Load the most recent checkpoint for a simulation

### Examples

```bash
# Load specific checkpoint
payment-sim checkpoint load \
  --checkpoint-id abc12345-6789-0123-4567-890abcdef012 \
  --config config.yaml

# Load latest checkpoint for simulation
payment-sim checkpoint load \
  --checkpoint-id latest \
  --simulation-id sim_001 \
  --config config.yaml

# Load and save state to file
payment-sim checkpoint load \
  --checkpoint-id abc12345 \
  --config config.yaml \
  --output restored_state.json
```

### Output

```
Loading checkpoint...
✓ Simulation restored from checkpoint
  Checkpoint ID: abc12345-6789-0123-4567-890abcdef012
  Simulation ID: sim_001
  Tick: 50
  Day: 0
  Config loaded from checkpoint database
```

### Notes

- The configuration is loaded from the checkpoint database, not from the CLI `--config` parameter
- The `--config` parameter is kept for backwards compatibility but is not used for loading

---

## list

List available checkpoints in the database.

### Synopsis

```bash
payment-sim checkpoint list [OPTIONS]
```

### Optional Flags

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--simulation-id` | `-s` | String | All | Filter by simulation ID. |
| `--type` | `-t` | String | All | Filter by checkpoint type. |
| `--limit` | `-n` | Integer | All | Maximum number of results. |

### Examples

```bash
# List all checkpoints
payment-sim checkpoint list

# Filter by simulation
payment-sim checkpoint list --simulation-id sim_001

# Filter by type
payment-sim checkpoint list --type manual --limit 10

# Combined filters
payment-sim checkpoint list --simulation-id sim_001 --type eod
```

### Output

```
                     Simulation Checkpoints (15 found)
┌──────────────┬────────────┬──────┬─────┬────────┬────────────────────────────┐
│ Checkpoint ID│ Sim ID     │ Tick │ Day │ Type   │ Description                │
├──────────────┼────────────┼──────┼─────┼────────┼────────────────────────────┤
│ abc12345...  │ sim_001    │   50 │   0 │ manual │ Before stress event        │
│ def67890...  │ sim_001    │  100 │   1 │ eod    │ End of day 1               │
│ ghi11223...  │ sim_001    │  150 │   1 │ manual │ After LSM optimization     │
└──────────────┴────────────┴──────┴─────┴────────┴────────────────────────────┘
```

---

## delete

Delete checkpoint(s) from the database.

### Synopsis

```bash
payment-sim checkpoint delete [OPTIONS]
```

### Optional Flags

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--checkpoint-id` | `-c` | String | None | Specific checkpoint ID to delete. |
| `--simulation-id` | `-s` | String | None | Delete all checkpoints for simulation. |
| `--confirm` | `-y` | Boolean | `false` | Skip confirmation prompt. |

**Note**: Either `--checkpoint-id` or `--simulation-id` must be provided.

### Examples

```bash
# Delete specific checkpoint
payment-sim checkpoint delete --checkpoint-id abc12345

# Delete with confirmation skip
payment-sim checkpoint delete --checkpoint-id abc12345 --confirm

# Delete all checkpoints for simulation
payment-sim checkpoint delete --simulation-id sim_001

# Delete all for simulation (no prompt)
payment-sim checkpoint delete --simulation-id sim_001 --confirm
```

### Output

Single checkpoint:

```
Delete checkpoint abc12345? [y/N]: y
✓ Checkpoint abc12345 deleted
```

All for simulation:

```
Delete 5 checkpoint(s) for simulation sim_001? [y/N]: y
✓ Deleted 5 checkpoint(s) for simulation sim_001
```

---

## Database Storage

Checkpoints are stored in the `simulation_checkpoints` table with:

| Column | Description |
|--------|-------------|
| `checkpoint_id` | Unique UUID |
| `simulation_id` | Parent simulation ID |
| `checkpoint_tick` | Tick at checkpoint |
| `checkpoint_day` | Day at checkpoint |
| `checkpoint_type` | Type (manual/auto/eod/final) |
| `state_json` | Complete simulation state |
| `config_json` | Simulation configuration |
| `description` | Optional description |
| `created_at` | Timestamp |

---

## Use Cases

### Debug Specific Tick Range

```bash
# Save checkpoint before problem area
payment-sim checkpoint save -s sim_001 -f state.json -c config.yaml -d "Before tick 50"

# If issue found, restore and re-run with verbose
payment-sim checkpoint load -c latest -s sim_001 --config config.yaml
```

### Resume Interrupted Simulation

```bash
# List available checkpoints
payment-sim checkpoint list -s sim_001

# Load latest checkpoint
payment-sim checkpoint load -c latest -s sim_001 --config config.yaml -o restored.json
```

### End-of-Day Analysis

```bash
# Create EOD checkpoints during simulation (programmatic)
# Then list and compare
payment-sim checkpoint list -s sim_001 -t eod
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PAYMENT_SIM_DB_PATH` | `simulation_data.db` | Default database path. |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (checkpoint not found, validation failed, database error) |

---

## Related Commands

- [`run`](run.md) - Run simulations
- [`replay`](replay.md) - Replay persisted simulations
- [`db`](db.md) - Database management

---

## Implementation Details

**File**: `api/payment_simulator/cli/commands/checkpoint.py`

Checkpoints use the `CheckpointManager` class which handles serialization via the Rust FFI layer (`orchestrator.save_state()` and `Orchestrator.load_state()`).
