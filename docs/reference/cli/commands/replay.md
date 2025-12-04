# replay

Replay a persisted simulation from the database with verbose logging.

## Synopsis

```bash
payment-sim replay [OPTIONS]
```

## Description

The `replay` command loads a simulation that was previously run with `--persist` and displays the tick-by-tick events that occurred during the original run. This is useful for:

- Debugging specific tick ranges of a simulation
- Reviewing simulation behavior without re-running
- Generating machine-readable event streams from stored data
- Auditing simulation outcomes

The configuration is automatically loaded from the database, so you don't need to provide the original config file.

## Required Options

| Option | Short | Type | Description |
|--------|-------|------|-------------|
| `--simulation-id` | `-s` | String | Simulation ID to replay from database. |

## Optional Flags

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--from-tick` | - | Integer | `0` | Starting tick for verbose output (inclusive). |
| `--to-tick` | - | Integer | Last tick | Ending tick for verbose output (inclusive). |
| `--db-path` | - | String | `simulation_data.db` | Database file path. |
| `--verbose` | `-v` | Boolean | `false` | Show detailed tick-by-tick events. |
| `--event-stream` | - | Boolean | `false` | Output events as JSON lines (machine-readable). |

## Filter Options

Filter options allow focusing on specific events during replay. See [Event Filtering](../filtering.md) for full details.

| Option | Type | Description |
|--------|------|-------------|
| `--filter-event-type` | String | Filter by event type(s), comma-separated (e.g., `Arrival,Settlement`). |
| `--filter-agent` | String | Filter by agent ID. Shows all events where agent is sender/actor, plus incoming settlements. |
| `--filter-tx` | String | Filter by transaction ID. |
| `--filter-tick-range` | String | Filter by tick range (format: `min-max`, `min-`, or `-max`). |

**Note:** Filter options require either `--verbose` or `--event-stream` mode.

## Output Modes

### Summary Mode (Default)

Without `--verbose` or `--event-stream`, outputs a JSON summary matching the format of the original `run` command:

```json
{
  "simulation": {
    "config_file": "loaded from database",
    "seed": 42,
    "ticks_executed": 300,
    "replay_range": "0-299",
    "ticks_replayed": 300,
    "duration_seconds": 0.523,
    "ticks_per_second": 573.61,
    "simulation_id": "sim-abc123",
    "database": "simulation_data.db"
  },
  "metrics": {
    "total_arrivals": 450,
    "total_settlements": 405,
    "total_lsm_releases": 12,
    "settlement_rate": 0.9
  },
  "agents": [
    {"id": "BANK_A", "final_balance": 950000, "queue1_size": 5}
  ],
  "costs": {"total_cost": 125000},
  "performance": {"ticks_per_second": 573.61}
}
```

### Verbose Mode (`--verbose`)

Displays detailed tick-by-tick output identical to `run --verbose`:

- Tick headers
- Transaction arrivals
- Settlement events (RTGS, Queue-2, LSM)
- Policy decisions (if `--full-replay` was used during run)
- Agent states and cost breakdowns
- End-of-day statistics

### Event Stream Mode (`--event-stream`)

Outputs each event as a JSON line, suitable for processing by external tools:

```json
{"simulation_id":"sim-abc123","tick":0,"day":0,"event_type":"Arrival","event_id":"evt-1","timestamp":"2024-01-15T10:00:00Z","tx_id":"tx-001","details":{...}}
{"simulation_id":"sim-abc123","tick":0,"day":0,"event_type":"RtgsImmediateSettlement","event_id":"evt-2","timestamp":"2024-01-15T10:00:01Z","tx_id":"tx-001","details":{...}}
```

Final line contains metadata:

```json
{"_metadata":true,"replay_complete":true,"simulation_id":"sim-abc123","from_tick":0,"to_tick":99,"duration_seconds":0.234,"ticks_per_second":427.35}
```

## Replay Identity

The replay command is designed to produce **byte-for-byte identical output** to the original `run` command (modulo timing information). This is called the **Replay Identity** principle.

This is achieved through:

1. **Single Source of Truth**: All events are stored in the `simulation_events` table and replayed from there
2. **Shared Display Logic**: Both `run` and `replay` use the same `display_tick_verbose_output()` function
3. **StateProvider Pattern**: Abstracts data source so display code doesn't know if it's live or replay

## Examples

### Basic Replay

```bash
# Replay entire simulation
payment-sim replay --simulation-id sim-abc123

# Replay with verbose output
payment-sim replay --simulation-id sim-abc123 --verbose
```

### Tick Range Replay

```bash
# Replay first 10 ticks
payment-sim replay --simulation-id sim-abc123 --to-tick 10 --verbose

# Replay ticks 50-100 for debugging
payment-sim replay --simulation-id sim-abc123 --from-tick 50 --to-tick 100 --verbose

# Replay last 50 ticks
payment-sim replay --simulation-id sim-abc123 --from-tick 250 --verbose
```

### Event Stream for Processing

```bash
# Output as JSON lines for processing
payment-sim replay --simulation-id sim-abc123 --event-stream

# Pipe to analysis tool
payment-sim replay --simulation-id sim-abc123 --event-stream | jq 'select(.event_type == "LsmBilateralOffset")'

# Save to file
payment-sim replay --simulation-id sim-abc123 --event-stream > events.jsonl
```

### Custom Database Path

```bash
# Use different database
payment-sim replay --simulation-id sim-abc123 --db-path my_simulations.db --verbose
```

### Filtered Replay

```bash
# Replay events for a specific bank (sender/actor events + incoming settlements)
payment-sim replay --simulation-id sim-abc123 --verbose --filter-agent BANK_A

# Replay only LSM events
payment-sim replay --simulation-id sim-abc123 --verbose \
  --filter-event-type LsmBilateralOffset,LsmCycleSettlement

# Track a specific transaction through the simulation
payment-sim replay --simulation-id sim-abc123 --verbose --filter-tx tx-large-payment

# Combine agent filter with tick range
payment-sim replay --simulation-id sim-abc123 --verbose \
  --filter-agent BANK_B \
  --filter-tick-range 50-100

# Event stream with filters for external processing
payment-sim replay --simulation-id sim-abc123 --event-stream \
  --filter-event-type Arrival | jq 'select(.details.amount > 100000)'
```

## Finding Simulation IDs

Use the `db simulations` command to list available simulations:

```bash
# List recent simulations
payment-sim db simulations

# List more simulations
payment-sim db simulations --limit 50
```

## Data Availability

The replay command works with different levels of persisted data:

### Minimum Data (Always Available)

With just `--persist`:
- Transaction arrivals and settlements
- Daily agent metrics
- Simulation events
- Final summary statistics

### Full Replay Data

With `--persist --full-replay`:
- All minimum data, plus:
- Policy decisions per tick
- Per-tick agent states (balances, queue sizes)
- Complete cost breakdowns per tick

If full replay data is not available, the replay command will display a notice:

```
Note: Policy decisions and per-tick agent states not available
      (run with --persist --full-replay to capture full data)
```

## Configuration Loading

The replay command automatically loads the simulation configuration from the database. No config file is needed:

```bash
# Config is loaded from database automatically
payment-sim replay --simulation-id sim-abc123 --verbose
```

If the configuration is not found in the database (for simulations run before config persistence was implemented), an error message will be displayed.

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (simulation not found, database error) |
| 130 | Interrupted by user (Ctrl+C) |

## Related Commands

- [`run`](run.md) - Run simulations with persistence
- [`db simulations`](db.md#simulations) - List available simulations
- [`db costs`](db.md#costs) - Query cost data for a simulation

## Troubleshooting

### Simulation Not Found

```
Error: Simulation sim-xyz123 not found in database
Available simulations:
  - sim-abc123
  - sim-def456
```

**Solution**: Check the simulation ID with `payment-sim db simulations`.

### Configuration Not Found

```
Error: Configuration not found in database.
This simulation may have been created before config persistence was implemented.
```

**Solution**: Re-run the simulation with `--persist` to capture the configuration.

### Different Output from Run

If replay output differs from run output, this indicates a bug. Check:

1. Ensure `--full-replay` was used if policy decisions are expected
2. Verify the same filters are applied
3. Report the discrepancy as it violates Replay Identity

## Implementation Details

**File**: `api/payment_simulator/cli/commands/replay.py`

The replay command uses the unified replay architecture (Phase 6) which reads all events from the `simulation_events` table as the single source of truth.
