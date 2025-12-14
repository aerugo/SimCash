# run

Execute a simulation from a configuration file.

## Synopsis

```bash
payment-sim run [OPTIONS]
```

## Description

The `run` command executes a payment simulation based on a YAML or JSON configuration file. It supports multiple output modes (normal, verbose, stream, event-stream), optional persistence to DuckDB, and event filtering capabilities.

## Required Options

| Option | Short | Type | Description |
|--------|-------|------|-------------|
| `--config` | `-c` | Path | Configuration file path (YAML or JSON). Must exist and be readable. |

## Optional Flags

### Simulation Control

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--ticks` | `-t` | Integer | Config value | Override number of ticks to run. Overrides the config's `num_days * ticks_per_day`. |
| `--seed` | `-s` | Integer | Config value | Override RNG seed for deterministic simulation. |

### Output Mode Selection

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--quiet` | `-q` | Boolean | `false` | Suppress logs; output only results to stdout (AI-friendly mode). |
| `--output` | `-o` | String | `json` | Output format (currently only `json` supported). |
| `--stream` | - | Boolean | `false` | Stream tick results as JSONL (one JSON object per line). |
| `--verbose` | `-v` | Boolean | `false` | Show detailed real-time events grouped by category. |
| `--debug` | - | Boolean | `false` | Show performance diagnostics per tick. Requires `--verbose`. |
| `--event-stream` | - | Boolean | `false` | Event stream mode: chronological one-line events in JSON format. |

### Persistence Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--persist` | `-p` | Boolean | `false` | Persist transactions, metrics, and events to database. |
| `--full-replay` | - | Boolean | `false` | Capture all per-tick data for perfect replay. Requires `--persist`. |
| `--db-path` | - | String | `simulation_data.db` | Database file path for persistence. |
| `--simulation-id` | - | String | Auto-generated | Custom simulation ID (UUID format generated if not provided). |

### Event Filtering

Filters require `--verbose` or `--event-stream` mode.

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--filter-event-type` | - | String | None | Filter by event type(s), comma-separated. |
| `--filter-agent` | - | String | None | Filter by agent ID (matches `agent_id` or `sender_id` fields). |
| `--filter-tx` | - | String | None | Filter by transaction ID. |
| `--filter-tick-range` | - | String | None | Filter by tick range: `min-max`, `min-`, or `-max`. |

### Cost Visualization

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--cost-chart` | - | String | None | Generate cost charts after simulation. Auto-enables `--persist`. Format: `PER_TICK[:ACCUMULATED]` in dollars. |

## Mutually Exclusive Options

- `--verbose` and `--event-stream` cannot be used together
- Filter options (`--filter-*`) require either `--verbose` or `--event-stream`
- `--full-replay` requires `--persist`

## Output Modes

### Normal Mode (Default)

Produces a single JSON summary at simulation end:

```json
{
  "simulation": {
    "config_file": "/path/to/config.yaml",
    "seed": 42,
    "simulation_id": "sim-abc123",
    "database": "simulation_data.db",
    "ticks_executed": 300,
    "duration_seconds": 1.234,
    "ticks_per_second": 243.41
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
  "performance": {"ticks_per_second": 243.41}
}
```

### Verbose Mode (`--verbose`)

Displays detailed tick-by-tick output with:

- Tick header with day/tick numbers
- Transaction arrivals (sender, receiver, amount, priority, deadline)
- Settlement details (RTGS immediate, Queue-2 releases, LSM offsets)
- Policy decisions (submit, hold, drop, split)
- Agent queue states and balances
- Cost breakdowns per agent
- End-of-day statistics

Example output:

```
═══════════════════════════════════════════════════════════════════
                            TICK 0 (Day 0)
═══════════════════════════════════════════════════════════════════

📥 ARRIVALS (3)
┌──────────────────┬────────────┬────────────┬──────────┬──────────┐
│ Transaction      │ Sender     │ Receiver   │ Amount   │ Deadline │
├──────────────────┼────────────┼────────────┼──────────┼──────────┤
│ tx-abc123        │ BANK_A     │ BANK_B     │ $1,500.00│ 50       │
└──────────────────┴────────────┴────────────┴──────────┴──────────┘

✅ RTGS IMMEDIATE SETTLEMENTS (2)
...
```

### Stream Mode (`--stream`)

Outputs one JSON object per tick (JSONL format):

```
{"tick":0,"day":0,"arrivals":5,"settlements":0,"lsm":0}
{"tick":1,"day":0,"arrivals":3,"settlements":2,"lsm":0}
{"tick":2,"day":0,"arrivals":4,"settlements":1,"lsm":1}
```

### Event Stream Mode (`--event-stream`)

Outputs individual events as JSON lines (one event per line):

```json
{"tick":0,"event_type":"Arrival","tx_id":"tx1","sender_id":"BANK_A","receiver_id":"BANK_B","amount":100000}
{"tick":0,"event_type":"RtgsImmediateSettlement","tx_id":"tx1","sender":"BANK_A","receiver":"BANK_B","amount":100000}
```

## Examples

### Basic Simulation

```bash
# Run with default output (JSON summary)
payment-sim run --config scenario.yaml

# AI-friendly quiet mode
payment-sim run --config scenario.yaml --quiet
```

### Override Parameters

```bash
# Override seed for reproducibility
payment-sim run --config scenario.yaml --seed 12345

# Run only 100 ticks
payment-sim run --config scenario.yaml --ticks 100

# Both overrides
payment-sim run --config scenario.yaml --seed 999 --ticks 500
```

### Verbose Output

```bash
# Real-time verbose output
payment-sim run --config scenario.yaml --verbose

# Verbose with performance diagnostics
payment-sim run --config scenario.yaml --verbose --debug

# Verbose with filtering
payment-sim run --config scenario.yaml --verbose \
  --filter-agent BANK_A \
  --filter-event-type Arrival,Settlement
```

### Streaming Output

```bash
# Stream JSONL for long simulations
payment-sim run --config large_scenario.yaml --stream

# Event stream for real-time processing
payment-sim run --config scenario.yaml --event-stream
```

### Persistence

```bash
# Persist to default database
payment-sim run --config scenario.yaml --persist

# Custom simulation ID (same unified database)
payment-sim run --config scenario.yaml \
  --persist \
  --simulation-id run-2024-01-15

# Specify different database location
payment-sim run --config scenario.yaml \
  --persist \
  --db-path /path/to/simulation_data.db

# Full replay data capture
payment-sim run --config scenario.yaml --persist --full-replay
```

### Cost Charts

```bash
# Generate charts with fixed Y-axis scales
payment-sim run --config scenario.yaml --cost-chart 5000:50000

# Adaptive Y-axis for both charts
payment-sim run --config scenario.yaml --cost-chart 0

# Per-tick chart fixed, accumulated chart adaptive
payment-sim run --config scenario.yaml --cost-chart 10000:0
```

**Cost chart format**: `PER_TICK[:ACCUMULATED]` where values are in dollars.

- `5000` - Per-tick max $5,000, accumulated adaptive
- `5000:50000` - Per-tick max $5,000, accumulated max $50,000
- `0` - Both adaptive
- `5000:0` - Per-tick max $5,000, accumulated adaptive

Charts are saved to `examples/charts/<config-name>_accumulated.png` and `examples/charts/<config-name>_per_tick.png`.

### Complex Filtering

```bash
# Filter by event type
payment-sim run --config scenario.yaml --verbose \
  --filter-event-type Arrival,RtgsImmediateSettlement,LsmBilateralOffset

# Filter by agent
payment-sim run --config scenario.yaml --verbose --filter-agent BANK_A

# Filter by transaction
payment-sim run --config scenario.yaml --verbose --filter-tx tx-abc123

# Filter by tick range
payment-sim run --config scenario.yaml --verbose --filter-tick-range 50-100

# Combined filters (AND logic)
payment-sim run --config scenario.yaml --verbose \
  --filter-agent BANK_A \
  --filter-tick-range 0-50 \
  --filter-event-type Arrival,Settlement
```

## Configuration File Format

The configuration file can be YAML or JSON. See [Scenario Configuration](../../scenario/index.md) for complete details.

### Minimal Example

```yaml
simulation:
  ticks_per_day: 100
  num_days: 1
  rng_seed: 42

agents:
  - id: BANK_A
    opening_balance: 1000000
  - id: BANK_B
    opening_balance: 1000000
```

### Supported Extensions

- `.yaml`, `.yml` - YAML format
- `.json` - JSON format

## Event Types

Events that can be filtered with `--filter-event-type`:

| Event Type | Description |
|------------|-------------|
| `Arrival` | Transaction arrival in the system |
| `RtgsImmediateSettlement` | RTGS immediate settlement |
| `Queue2LiquidityRelease` | Queue-2 liquidity release |
| `LsmBilateralOffset` | LSM bilateral (2-agent) offset |
| `LsmCycleSettlement` | LSM multi-agent cycle settlement |
| `TransactionWentOverdue` | Transaction exceeded deadline |
| `CostAccrual` | Continuous cost accrual event |
| `PolicySubmit` | Policy decision: submit to RTGS |
| `PolicyHold` | Policy decision: hold in queue |
| `PolicyDrop` | Policy decision: drop transaction |
| `PolicySplit` | Policy decision: split transaction |
| `CollateralPost` | Collateral posting |
| `CollateralWithdraw` | Collateral withdrawal |
| `EndOfDay` | End-of-day marker event |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (configuration, database, simulation failure) |
| 130 | Interrupted by user (Ctrl+C) |

## Related Commands

- [`replay`](replay.md) - Replay persisted simulations
- [`db simulations`](db.md#simulations) - List persisted simulations
- [`db costs`](db.md#costs) - Query cost data

## Implementation Details

**File**: `api/payment_simulator/cli/commands/run.py`

The run command uses the new SimulationRunner architecture (Phase 5.2) by default. This can be overridden by setting `USE_NEW_RUNNER=false` environment variable.
