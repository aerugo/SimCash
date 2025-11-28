# Persistence Layer

**Version**: 1.0
**Last Updated**: 2025-11-28

---

## Overview

SimCash uses DuckDB for analytical persistence, with a schema-as-code approach using Pydantic models. The **StateProvider pattern** ensures replay identity.

---

## Architecture

```mermaid
flowchart TB
    subgraph Python["Python Layer"]
        Manager["DatabaseManager"]
        Writer["EventWriter"]
        Query["QueryInterface"]
        Checkpoint["CheckpointManager"]
    end

    subgraph Schema["Schema Management"]
        Models["Pydantic Models"]
        Generator["SchemaGenerator"]
        Migrations["MigrationRunner"]
    end

    subgraph DB["DuckDB"]
        Events[(simulation_events)]
        Txs[(transactions)]
        Metrics[(daily_agent_metrics)]
        Checkpoints[(simulation_checkpoints)]
    end

    Manager --> Generator
    Generator --> DB
    Migrations --> DB

    Writer --> Events
    Query --> DB
    Checkpoint --> Checkpoints

    Models --> Generator
```

---

## Database Schema

### Core Tables

```mermaid
erDiagram
    simulation_runs ||--o{ simulation_events : contains
    simulation_runs ||--o{ transactions : contains
    simulation_runs ||--o{ daily_agent_metrics : contains
    simulation_runs ||--o{ policy_snapshots : contains
    simulation_runs ||--o{ simulation_checkpoints : has

    simulation_runs {
        string simulation_id PK
        json config_json
        timestamp created_at
        int total_ticks
        int ticks_per_day
        int num_days
    }

    simulation_events {
        string simulation_id PK
        int tick PK
        int event_id PK
        string event_type
        string tx_id
        string agent_id
        int day
        json details
    }

    transactions {
        string simulation_id PK
        string transaction_id PK
        string sender_id
        string receiver_id
        bigint amount
        int arrival_tick
        int deadline_tick
        int settlement_tick
        string status
    }

    daily_agent_metrics {
        string simulation_id PK
        int day PK
        string agent_id PK
        bigint opening_balance
        bigint closing_balance
        bigint total_costs
        int settlements_count
    }
```

### Pydantic Models

**Source**: `api/payment_simulator/persistence/models.py`

```python
class SimulationEventRecord(BaseModel):
    model_config = ConfigDict(
        table_name="simulation_events",
        primary_key=["simulation_id", "tick", "event_id"],
        indexes=["event_type", "tx_id", "agent_id"]
    )

    simulation_id: str
    tick: int
    event_id: int
    event_type: str
    tx_id: Optional[str]
    agent_id: Optional[str]
    day: int
    details: dict  # JSON column
```

---

## Event Persistence

### Event Writer

**Source**: `api/payment_simulator/persistence/event_writer.py`

```mermaid
sequenceDiagram
    participant Runner as SimulationRunner
    participant Writer as EventWriter
    participant DB as DuckDB

    Runner->>Runner: orch.tick()
    Runner->>Runner: orch.get_tick_events()
    Runner->>Writer: write_events_batch(events)

    Writer->>Writer: Transform to rows
    Writer->>DB: Bulk INSERT

    alt StateRegisterSet events
        Writer->>DB: Also INSERT to agent_state_registers
    end
```

### Event Storage

Events stored with full details in JSONB column:

```sql
INSERT INTO simulation_events
    (simulation_id, tick, event_id, event_type, tx_id, agent_id, day, details)
VALUES
    ('sim-123', 42, 1, 'Arrival', 'tx-abc', 'BANK_A', 0,
     '{"tick": 42, "tx_id": "tx-abc", "sender_id": "BANK_A", ...}');
```

---

## StateProvider Pattern

### Purpose

Abstract data access to ensure **replay identity**: `run --verbose` = `replay --verbose`.

### Protocol

**Source**: `api/payment_simulator/cli/execution/state_provider.py`

```python
class StateProvider(Protocol):
    def get_agent_balance(self, agent_id: str) -> int: ...
    def get_transaction_details(self, tx_id: str) -> Optional[dict]: ...
    def get_agent_queue1_contents(self, agent_id: str) -> List[str]: ...
    def get_rtgs_queue_contents(self) -> List[str]: ...
    # ... 10+ methods
```

### Implementations

```mermaid
flowchart TB
    subgraph Protocol["StateProvider Protocol"]
        Methods["get_agent_balance()<br/>get_transaction_details()<br/>get_queue_contents()<br/>..."]
    end

    subgraph Live["OrchestratorStateProvider"]
        FFI["FFI calls to Rust"]
    end

    subgraph Replay["DatabaseStateProvider"]
        SQL["SQL queries to DuckDB"]
    end

    Protocol --> Live
    Protocol --> Replay

    Live --> Output1[/"Verbose Output"/]
    Replay --> Output2[/"Verbose Output"/]

    Output1 --> Same["Identical!"]
    Output2 --> Same
```

### Usage

```python
# Live execution
provider = OrchestratorStateProvider(orchestrator)
display_tick_verbose_output(provider, events, tick, ...)

# Replay
provider = DatabaseStateProvider(conn, simulation_id)
display_tick_verbose_output(provider, events, tick, ...)
# Same function, same output!
```

---

## Query Interface

### Event Queries

**Source**: `api/payment_simulator/persistence/event_queries.py`

```python
def get_simulation_events(
    conn: DuckDBConnection,
    simulation_id: str,
    tick: Optional[int] = None,
    tick_min: Optional[int] = None,
    tick_max: Optional[int] = None,
    agent_id: Optional[str] = None,
    event_type: Optional[str] = None,  # Comma-separated
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    Returns: {
        "events": [...],
        "total": 1234,
        "limit": 100,
        "offset": 0,
        "filters": {...}
    }
    """
```

### Analytical Queries

**Source**: `api/payment_simulator/persistence/queries.py`

| Function | Returns | Purpose |
|----------|---------|---------|
| `get_agent_performance()` | DataFrame | Performance by agent |
| `get_settlement_rate_by_day()` | DataFrame | Settlement trends |
| `get_cost_analysis()` | DataFrame | Cost breakdown |
| `get_transaction_journeys()` | DataFrame | Lifecycle analysis |

```python
import polars as pl

# Example: Settlement rate analysis
df = get_settlement_rate_by_day(conn, simulation_id)
# Returns Polars DataFrame with zero-copy Arrow integration
```

---

## Checkpoint System

### Save Checkpoint

```mermaid
sequenceDiagram
    participant CLI as CLI
    participant Orch as Orchestrator
    participant Mgr as CheckpointManager
    participant DB as DuckDB

    CLI->>Orch: save_state()
    Orch-->>CLI: state_json

    CLI->>Mgr: save_checkpoint(sim_id, tick, state_json)
    Mgr->>Mgr: Generate checkpoint_id
    Mgr->>DB: INSERT INTO simulation_checkpoints
    Mgr-->>CLI: checkpoint_id
```

### Load Checkpoint

```mermaid
sequenceDiagram
    participant CLI as CLI
    participant Mgr as CheckpointManager
    participant DB as DuckDB
    participant Orch as Orchestrator

    CLI->>Mgr: load_checkpoint(checkpoint_id)
    Mgr->>DB: SELECT FROM simulation_checkpoints
    DB-->>Mgr: state_json
    Mgr-->>CLI: checkpoint_data

    CLI->>Orch: Orchestrator.restore(state_json)
    Orch-->>CLI: Restored orchestrator
```

### Checkpoint Table

```sql
CREATE TABLE simulation_checkpoints (
    checkpoint_id VARCHAR PRIMARY KEY,
    simulation_id VARCHAR NOT NULL,
    checkpoint_tick INTEGER NOT NULL,
    state_json TEXT NOT NULL,  -- Serialized Rust state
    checkpoint_type VARCHAR NOT NULL,  -- manual, auto, eod, final
    description VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Database Manager

**Source**: `api/payment_simulator/persistence/connection.py`

```mermaid
classDiagram
    class DatabaseManager {
        -db_path: Path
        -conn: DuckDBConnection
        +get_connection() DuckDBConnection
        +setup()
        +__enter__()
        +__exit__()
    }
```

### Setup Process

```mermaid
flowchart TB
    Init["DatabaseManager(path)"] --> Connect["Connect to DuckDB"]
    Connect --> GenSchema["Generate DDL from models"]
    GenSchema --> CreateTables["Create tables (if not exist)"]
    CreateTables --> Migrate["Apply pending migrations"]
    Migrate --> Validate["Validate schema"]
    Validate --> Ready["Ready"]
```

### Usage

```python
with DatabaseManager("simulation.db") as db:
    conn = db.get_connection()
    events = get_simulation_events(conn, sim_id, tick=42)
```

---

## Schema Generation

### Pydantic to DDL

```mermaid
flowchart LR
    Model["Pydantic Model"] --> Generator["SchemaGenerator"]
    Generator --> DDL["CREATE TABLE DDL"]

    subgraph Model
        Fields["Fields + Types"]
        Config["table_name, primary_key, indexes"]
    end

    subgraph DDL
        Table["CREATE TABLE"]
        PK["PRIMARY KEY"]
        Indexes["CREATE INDEX"]
    end
```

### Type Mapping

| Python | DuckDB |
|--------|--------|
| `str` | VARCHAR |
| `int` | INTEGER |
| `float` | DOUBLE |
| `bool` | BOOLEAN |
| `dict` | JSON |
| `datetime` | TIMESTAMP |
| `Optional[T]` | T (nullable) |

---

## Migrations

**Source**: `api/payment_simulator/persistence/migrations.py`

```mermaid
flowchart TB
    Start["Apply migrations"] --> GetPending["Get pending migrations"]
    GetPending --> ForMigration["For each migration"]

    ForMigration --> Execute["Execute SQL"]
    Execute --> Record["Record in schema_migrations"]
    Record --> Next["Next migration"]

    Next --> More{"More?"}
    More -->|Yes| ForMigration
    More -->|No| Done["Done"]
```

### Migration Format

```sql
-- migrations/001_add_priority_column.sql
ALTER TABLE transactions ADD COLUMN priority INTEGER DEFAULT 5;
```

---

## Performance

### DuckDB Advantages

| Feature | Benefit |
|---------|---------|
| Columnar storage | Better compression |
| Vectorized execution | Fast analytical queries |
| Zero-copy Arrow | Polars integration |
| Embedded | No external process |

### Query Optimization

```python
# Use column projection
conn.execute("""
    SELECT event_type, COUNT(*)
    FROM simulation_events
    WHERE simulation_id = ?
    GROUP BY event_type
""", [sim_id])

# Use predicate pushdown
df = pl.read_database(
    "SELECT * FROM events WHERE tick BETWEEN 0 AND 100",
    conn
)
```

---

## Replay Identity

### Guarantee

```
run_output = payment-sim run config.yaml --verbose
replay_output = payment-sim replay db.db --verbose

assert run_output == replay_output  # Byte-for-byte
```

### Implementation

1. **Same display function**: `display_tick_verbose_output()` used for both
2. **StateProvider abstraction**: Display code doesn't know data source
3. **Complete events**: Events contain ALL display data
4. **No reconstruction**: Query only `simulation_events` table

### Verification

```bash
# Run with persistence
payment-sim run config.yaml --persist db.db --verbose > run.txt

# Replay
payment-sim replay db.db --verbose > replay.txt

# Compare (should be identical except timing)
diff <(grep -v "Duration:" run.txt) <(grep -v "Duration:" replay.txt)
```

---

## Related Documents

- [03-python-api-layer.md](./03-python-api-layer.md) - Python persistence module
- [08-event-system.md](./08-event-system.md) - Event storage
- [10-cli-architecture.md](./10-cli-architecture.md) - CLI persistence options

---

*Next: [10-cli-architecture.md](./10-cli-architecture.md) - CLI commands*
