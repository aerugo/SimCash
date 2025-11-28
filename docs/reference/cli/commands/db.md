# db

Database management commands for the DuckDB persistence layer.

## Synopsis

```bash
payment-sim db [SUBCOMMAND] [OPTIONS]
```

## Description

The `db` command group provides tools for managing the DuckDB database used for simulation persistence. This includes schema initialization, migrations, validation, and data queries.

## Subcommands

| Subcommand | Description |
|------------|-------------|
| [`init`](#init) | Initialize database schema |
| [`migrate`](#migrate) | Apply pending schema migrations |
| [`validate`](#validate) | Validate database schema |
| [`create-migration`](#create-migration) | Create new migration template |
| [`list`](#list) | List all tables in database |
| [`info`](#info) | Show database information and statistics |
| [`simulations`](#simulations) | List simulations in database |
| [`costs`](#costs) | Get tick-by-tick cost data for a simulation |

---

## init

Initialize the database schema from Pydantic models.

### Synopsis

```bash
payment-sim db init [OPTIONS]
```

### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--db-path` | `-d` | String | `simulation_data.db` | Path to database file. |

### Examples

```bash
# Initialize default database
payment-sim db init

# Initialize custom database
payment-sim db init --db-path my_simulations.db
```

### Output

```
Initializing database at simulation_data.db...
✓ Database initialized at simulation_data.db
```

---

## migrate

Apply pending schema migrations to the database.

### Synopsis

```bash
payment-sim db migrate [OPTIONS]
```

### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--db-path` | `-d` | String | `simulation_data.db` | Path to database file. |
| `--migrations-dir` | `-m` | String | Auto-detected | Path to migrations directory. |

### Examples

```bash
# Apply migrations to default database
payment-sim db migrate

# Apply migrations with custom paths
payment-sim db migrate --db-path sim.db --migrations-dir ./my_migrations
```

### Output

```
Checking for pending migrations...
Found 2 pending migration(s)
  • Migration 002: add_settlement_type
  • Migration 003: add_event_index
✓ Applied 2 migration(s)
```

If no migrations are pending:

```
Checking for pending migrations...
✓ No pending migrations
```

---

## validate

Validate the database schema against expected Pydantic models.

### Synopsis

```bash
payment-sim db validate [OPTIONS]
```

### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--db-path` | `-d` | String | `simulation_data.db` | Path to database file. |

### Examples

```bash
# Validate default database
payment-sim db validate

# Validate custom database
payment-sim db validate --db-path my_simulations.db
```

### Output

Success:

```
Validating database schema...
✓ Schema validation passed
```

Failure:

```
Validating database schema...
✗ Schema validation failed
Run 'payment-sim db migrate' to fix schema
```

---

## create-migration

Create a new migration template file.

### Synopsis

```bash
payment-sim db create-migration DESCRIPTION [OPTIONS]
```

### Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `DESCRIPTION` | String | Yes | Migration description (e.g., `add_settlement_type`). |

### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--db-path` | `-d` | String | `simulation_data.db` | Path to database file (for version tracking). |
| `--migrations-dir` | `-m` | String | Auto-detected | Path to migrations directory. |

### Examples

```bash
# Create new migration
payment-sim db create-migration "add_settlement_type"

# Create migration with custom paths
payment-sim db create-migration "add_index" --migrations-dir ./migrations
```

### Output

```
✓ Created migration template: migrations/004_add_settlement_type.sql
Next steps:
  1. Edit migrations/004_add_settlement_type.sql
  2. Add your SQL statements
  3. Run 'payment-sim db migrate'
```

---

## list

List all tables in the database.

### Synopsis

```bash
payment-sim db list [OPTIONS]
```

### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--db-path` | `-d` | String | `simulation_data.db` | Path to database file. |

### Examples

```bash
# List tables in default database
payment-sim db list
```

### Output

```
                     Database Tables
┌────────────────────────────┬─────────┐
│ Table Name                 │ Columns │
├────────────────────────────┼─────────┤
│ simulation_runs            │      11 │
│ simulations                │      16 │
│ transactions               │      15 │
│ daily_agent_metrics        │      12 │
│ simulation_events          │       9 │
│ policy_snapshots           │       7 │
│ agent_queue_snapshots      │       6 │
│ simulation_checkpoints     │       9 │
└────────────────────────────┴─────────┘

Total: 8 table(s)
```

---

## info

Show database information and statistics.

### Synopsis

```bash
payment-sim db info [OPTIONS]
```

### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--db-path` | `-d` | String | `simulation_data.db` | Path to database file. |

### Examples

```bash
# Show database info
payment-sim db info
```

### Output

```
Database Information
  Path: simulation_data.db
  Size: 12.45 MB

Table Statistics:
┌─────────────────────────┬───────────┐
│ Table                   │ Row Count │
├─────────────────────────┼───────────┤
│ simulation_runs         │        15 │
│ transactions            │    45,230 │
│ daily_agent_metrics     │       180 │
│ policy_snapshots        │        60 │
│ collateral_events       │     1,200 │
│ simulation_checkpoints  │        45 │
└─────────────────────────┴───────────┘
```

---

## simulations

List simulations stored in the database.

### Synopsis

```bash
payment-sim db simulations [OPTIONS]
```

### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--db-path` | `-d` | String | `simulation_data.db` | Path to database file. |
| `--limit` | `-n` | Integer | `20` | Maximum number of simulations to show. |

### Examples

```bash
# List recent simulations
payment-sim db simulations

# List more simulations
payment-sim db simulations --limit 50

# List from custom database
payment-sim db simulations --db-path my_sims.db
```

### Output

```
                  Simulations in Database (5 shown)
┌──────────────────┬─────────────────┬───────┬───────┬───────────┬──────────────────┐
│ Simulation ID    │ Config          │ Seed  │ Ticks │ Status    │ Started          │
├──────────────────┼─────────────────┼───────┼───────┼───────────┼──────────────────┤
│ sim-abc123       │ crisis.yaml     │ 42    │ 300   │ completed │ 2024-01-15 10:30 │
│ sim-def456       │ baseline.yaml   │ 1234  │ 500   │ completed │ 2024-01-15 09:15 │
│ sim-ghi789       │ stress_test.yaml│ 999   │ 1000  │ completed │ 2024-01-14 16:00 │
└──────────────────┴─────────────────┴───────┴───────┴───────────┴──────────────────┘

Use 'payment-sim replay --simulation-id <ID> --config <file>' to replay
```

---

## costs

Get tick-by-tick cost data for a simulation.

### Synopsis

```bash
payment-sim db costs SIMULATION_ID [OPTIONS]
```

### Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `SIMULATION_ID` | String | Yes | Simulation ID to get costs for. |

### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--db-path` | `-d` | String | `simulation_data.db` | Path to database file. |
| `--agent` | `-a` | String | All agents | Filter costs for specific agent. |
| `--output-csv` | `-o` | String | None | Export to CSV file. |
| `--chart-output` | `-c` | String | None | Generate PNG chart. |
| `--per-tick` | `-p` | Boolean | `false` | Show per-tick costs instead of accumulated. |
| `--limit` | `-n` | Integer | `50` | Max ticks to display (0 = show all). |

### Examples

```bash
# View accumulated costs (default)
payment-sim db costs sim-abc123

# View per-tick costs
payment-sim db costs sim-abc123 --per-tick

# Filter by agent
payment-sim db costs sim-abc123 --agent BANK_A

# Export to CSV
payment-sim db costs sim-abc123 --output-csv costs.csv

# Generate chart
payment-sim db costs sim-abc123 --chart-output costs.png

# Per-tick chart for specific agent
payment-sim db costs sim-abc123 --agent BANK_A --per-tick --chart-output bank_a_costs.png

# Show all ticks
payment-sim db costs sim-abc123 --limit 0
```

### Output

Terminal display:

```
Loading cost timeline for simulation sim-abc123...

Cost Timeline for sim-abc123
  Total ticks: 300
  Agents: BANK_A, BANK_B, BANK_C
  Mode: Accumulated

                   Accumulated Costs
┌──────┬─────┬─────────────┬─────────────┬─────────────┐
│ Tick │ Day │ BANK_A      │ BANK_B      │ BANK_C      │
├──────┼─────┼─────────────┼─────────────┼─────────────┤
│    0 │   0 │      $0.00  │      $0.00  │      $0.00  │
│    1 │   0 │     $12.50  │      $8.00  │     $15.00  │
│    2 │   0 │     $25.00  │     $16.00  │     $30.00  │
│  ... │ ... │        ...  │        ...  │        ...  │
│  298 │   2 │  $3,456.78  │  $2,890.12  │  $4,123.45  │
│  299 │   2 │  $3,500.00  │  $2,950.00  │  $4,200.00  │
└──────┴─────┴─────────────┴─────────────┴─────────────┘

             Final Costs Summary
┌────────┬─────────────┐
│ Agent  │ Total Cost  │
├────────┼─────────────┤
│ BANK_A │  $3,500.00  │
│ BANK_B │  $2,950.00  │
│ BANK_C │  $4,200.00  │
│ TOTAL  │ $10,650.00  │
└────────┴─────────────┘

Showing 52 of 300 ticks. Use --limit 0 to show all or --output-csv to export.
```

### Chart Output

When using `--chart-output`, generates a PNG chart with:

- X-axis: Tick number
- Y-axis: Cost in USD (formatted as currency)
- One line per agent
- Day boundary markers
- Legend with agent names and policy types (if available)

### CSV Format

When using `--output-csv`, produces:

```csv
tick,day,BANK_A,BANK_B,BANK_C
0,0,0,0,0
1,0,1250,800,1500
2,0,2500,1600,3000
...
```

Values are in cents (integer).

---

## Database Schema

The persistence layer uses the following main tables:

| Table | Description |
|-------|-------------|
| `simulation_runs` | Basic simulation metadata |
| `simulations` | Complete simulation records with config JSON |
| `transactions` | Transaction details (arrival, settlement, amounts) |
| `daily_agent_metrics` | Per-agent daily statistics |
| `simulation_events` | Event log (all event types) |
| `policy_snapshots` | Policy configuration snapshots |
| `agent_queue_snapshots` | Queue state at end of day |
| `simulation_checkpoints` | Saved simulation checkpoints |
| `tick_agent_states` | Per-tick agent states (with `--full-replay`) |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (database not found, schema invalid, query failed) |

---

## Related Commands

- [`run`](run.md) - Run simulations with `--persist`
- [`replay`](replay.md) - Replay persisted simulations
- [`checkpoint`](checkpoint.md) - Manage simulation checkpoints

---

## Implementation Details

**File**: `api/payment_simulator/cli/commands/db.py`

The database commands use DuckDB for persistence with Polars for efficient data manipulation. Cost data collection uses event-based queries from the `simulation_events` table.
