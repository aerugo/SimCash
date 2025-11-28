# Python API Layer

**Version**: 1.0
**Last Updated**: 2025-11-28

---

## Overview

The Python layer provides developer-friendly interfaces for configuration, execution, persistence, and analysis. It comprises **34 source files** organized into **6 major components**.

---

## Package Structure

```mermaid
flowchart TB
    subgraph pkg["payment_simulator/"]
        init["__init__.py"]
        core["_core.py<br/>(FFI Shim)"]

        subgraph cli["cli/"]
            main["main.py<br/>(Typer App)"]
            output["output.py"]
            filters["filters.py"]

            subgraph commands["commands/"]
                run["run.py"]
                replay["replay.py"]
                checkpoint["checkpoint.py"]
                db["db.py"]
            end

            subgraph execution["execution/"]
                runner["runner.py"]
                strategies["strategies.py"]
                state_provider["state_provider.py"]
                display["display.py"]
                persistence["persistence.py"]
                stats["stats.py"]
            end
        end

        subgraph config["config/"]
            schemas["schemas.py"]
            loader["loader.py"]
        end

        subgraph persist["persistence/"]
            connection["connection.py"]
            models["models.py"]
            writers["writers.py"]
            event_writer["event_writer.py"]
            event_queries["event_queries.py"]
            queries["queries.py"]
            checkpoint_mgr["checkpoint.py"]
        end

        subgraph api["api/"]
            api_main["main.py<br/>(FastAPI)"]
        end
    end

    init --> core
    main --> commands
    main --> execution
    commands --> config
    commands --> persist
    execution --> core
    api_main --> core
    api_main --> config

    style cli fill:#e3f2fd
    style config fill:#fff3e0
    style persist fill:#e8f5e9
    style api fill:#fce4ec
```

---

## 1. CLI Module (`cli/`)

### Purpose
Command-line interface for running simulations, replay, and database management.

### Entry Point

**Source**: `api/payment_simulator/cli/main.py`

```mermaid
flowchart TB
    subgraph CLI["payment-sim CLI"]
        Run["run<br/>Execute simulation"]
        Replay["replay<br/>Replay from DB"]
        Checkpoint["checkpoint<br/>Save/Load state"]
        DB["db<br/>Schema management"]
    end

    Run --> Config["Load YAML"]
    Run --> Execute["SimulationRunner"]
    Replay --> LoadDB["Load from DuckDB"]
    Replay --> Display["Display events"]
    Checkpoint --> Save["Save state"]
    Checkpoint --> Load["Load state"]
    DB --> Init["init"]
    DB --> Validate["validate"]
    DB --> Migrate["migrate"]
```

### Command Structure

```python
# main.py
app = typer.Typer(name="payment-sim")

@app.command("run")
def run_simulation(config: Path, mode: str = "normal", persist: bool = False, ...)

@app.command("replay")
def replay_simulation(db: Path, tick_start: int = 0, tick_end: int = None, ...)

app.add_typer(checkpoint_app, name="checkpoint")
app.add_typer(db_app, name="db")
```

### Commands Reference

| Command | Arguments | Options | Description |
|---------|-----------|---------|-------------|
| `run` | `config.yaml` | `--mode`, `--persist`, `--verbose` | Execute simulation |
| `replay` | `db.db` | `--tick-start`, `--tick-end`, `--verbose` | Replay from database |
| `checkpoint save` | `db.db` `sim_id` `tick` | `--description` | Save state snapshot |
| `checkpoint load` | `checkpoint_id` | | Restore from checkpoint |
| `checkpoint list` | `sim_id` | | List checkpoints |
| `checkpoint delete` | `checkpoint_id` | | Remove checkpoint |
| `db init` | `db.db` | | Initialize schema |
| `db validate` | `db.db` | | Validate schema |
| `db migrate` | `db.db` | | Apply migrations |
| `db schema` | | | Print DDL |

---

## 2. Execution Engine (`cli/execution/`)

### Purpose
Template Method pattern for simulation execution with pluggable output strategies.

### SimulationRunner

**Source**: `api/payment_simulator/cli/execution/runner.py`

```mermaid
classDiagram
    class SimulationRunner {
        -orch: Orchestrator
        -config: SimulationConfig
        -output: OutputStrategy
        -persistence: Optional~PersistenceManager~
        -stats: SimulationStats
        +run() dict
        -_execute_tick(tick) TickResult
        -_is_end_of_day(tick) bool
    }

    class SimulationConfig {
        +total_ticks: int
        +ticks_per_day: int
        +num_days: int
        +persist: bool
        +full_replay: bool
        +db_path: str
        +sim_id: str
        +event_filter: EventFilter
    }

    class SimulationStats {
        +total_arrivals: int
        +total_settlements: int
        +total_costs: int
        +day_arrivals: int
        +day_settlements: int
        +update(result: TickResult)
        +reset_day_stats()
        +to_dict() dict
    }

    SimulationRunner --> SimulationConfig
    SimulationRunner --> SimulationStats
    SimulationRunner --> OutputStrategy
    SimulationRunner --> PersistenceManager
```

### Template Method Pattern

```mermaid
sequenceDiagram
    participant Runner as SimulationRunner
    participant Output as OutputStrategy
    participant Orch as Orchestrator (FFI)
    participant Persist as PersistenceManager

    Runner->>Output: on_simulation_start(config)
    Runner->>Persist: persist_initial_snapshots()

    loop For each tick
        Runner->>Orch: tick()
        Orch-->>Runner: TickResult
        Runner->>Runner: stats.update(result)
        Runner->>Output: on_tick_complete(result)
        Runner->>Persist: on_tick_complete(tick)

        alt End of Day
            Runner->>Output: on_day_complete(day, stats)
            Runner->>Persist: on_day_complete(day)
            Runner->>Runner: stats.reset_day_stats()
        end
    end

    Runner->>Output: on_simulation_complete(final_stats)
    Runner-->>Runner: return final_stats
```

### OutputStrategy Protocol

**Source**: `api/payment_simulator/cli/execution/strategies.py`

```mermaid
classDiagram
    class OutputStrategy {
        <<protocol>>
        +on_simulation_start(config)
        +on_tick_start(tick)
        +on_tick_complete(result, orch)
        +on_day_complete(day, stats, orch)
        +on_simulation_complete(final_stats)
    }

    class QuietOutputStrategy {
        +on_simulation_complete(final_stats)
    }

    class VerboseModeOutput {
        -provider: OrchestratorStateProvider
        -console: Console
        +on_tick_complete(result, orch)
    }

    class StreamModeOutput {
        +on_tick_complete(result, orch)
    }

    class EventStreamOutput {
        -event_filter: EventFilter
        +on_tick_complete(result, orch)
    }

    OutputStrategy <|.. QuietOutputStrategy
    OutputStrategy <|.. VerboseModeOutput
    OutputStrategy <|.. StreamModeOutput
    OutputStrategy <|.. EventStreamOutput
```

### Strategy Selection

| Mode | Strategy | Output |
|------|----------|--------|
| `normal` | QuietOutputStrategy | Final JSON only |
| `verbose` | VerboseModeOutput | Rich formatted logs |
| `stream` | StreamModeOutput | Per-tick JSONL |
| `event_stream` | EventStreamOutput | Per-event JSONL |

---

## 3. StateProvider Pattern

### Purpose
Abstract data access to ensure replay identity (run output = replay output).

**Source**: `api/payment_simulator/cli/execution/state_provider.py`

```mermaid
classDiagram
    class StateProvider {
        <<protocol>>
        +get_transaction_details(tx_id) dict
        +get_agent_balance(agent_id) int
        +get_agent_unsecured_cap(agent_id) int
        +get_agent_queue1_contents(agent_id) list
        +get_rtgs_queue_contents() list
        +get_agent_collateral_posted(agent_id) int
        +get_agent_accumulated_costs(agent_id) dict
        +get_queue1_size(agent_id) int
        +get_queue2_size(agent_id) int
        +get_transactions_near_deadline(within_ticks) list
        +get_overdue_transactions() list
    }

    class OrchestratorStateProvider {
        -orch: Orchestrator
        +get_agent_balance(agent_id) int
    }

    class DatabaseStateProvider {
        -conn: DuckDBConnection
        -sim_id: str
        +get_agent_balance(agent_id) int
    }

    StateProvider <|.. OrchestratorStateProvider : implements
    StateProvider <|.. DatabaseStateProvider : implements
```

### Replay Identity Guarantee

```mermaid
flowchart TB
    subgraph Run["Run Mode"]
        Code1["display_tick_verbose_output()"]
        Provider1["OrchestratorStateProvider"]
        FFI["FFI calls"]
    end

    subgraph Replay["Replay Mode"]
        Code2["display_tick_verbose_output()"]
        Provider2["DatabaseStateProvider"]
        SQL["SQL queries"]
    end

    Code1 --> Provider1 --> FFI
    Code2 --> Provider2 --> SQL

    FFI --> Output1[/"Identical<br/>Output"/]
    SQL --> Output2[/"Identical<br/>Output"/]

    Note["Same function,<br/>same output"]
```

---

## 4. Display System

### Purpose
Single source of truth for verbose output (used by both run and replay).

**Source**: `api/payment_simulator/cli/execution/display.py`

### Output Sections (12 total)

```mermaid
flowchart TB
    subgraph DisplaySections["display_tick_verbose_output()"]
        S1["1. Transaction Arrivals"]
        S2["2. Policy Decisions"]
        S3["3. Settlement Details"]
        S4["4. Queued RTGS"]
        S5["5. LSM Visualization"]
        S6["6. Collateral Activity"]
        S7["7. Overdue Summary"]
        S8["8. Agent Financial Stats"]
        S9["9. Agent States"]
        S10["10. Cost Accruals"]
        S11["11. Cost Breakdown"]
        S12["12. Tick Summary"]
    end

    Events["Events List"] --> S1
    S1 --> S2 --> S3 --> S4 --> S5 --> S6
    S6 --> S7 --> S8 --> S9 --> S10 --> S11 --> S12
```

### Console Output

**Source**: `api/payment_simulator/cli/output.py`

```python
# Golden Rule: stdout = data, stderr = logs
console = Console(stderr=True)  # Logs go to stderr

def output_json(data):       # stdout (machine-readable)
def output_jsonl(data):      # stdout (streaming)
def log_info(msg):           # stderr (blue)
def log_success(msg):        # stderr (green)
def log_error(msg):          # stderr (red)
def log_warning(msg):        # stderr (yellow)
```

---

## 5. Configuration Module (`config/`)

### Purpose
Pydantic-based configuration validation.

**Source**: `api/payment_simulator/config/schemas.py`

### Schema Hierarchy

```mermaid
classDiagram
    class SimulationConfig {
        +agents: List~AgentConfig~
        +rails: List~RailConfig~
        +costs: CostConfig
        +arrival_configs: Optional~List~
        +scenario_events: Optional~List~
    }

    class AgentConfig {
        +id: str
        +opening_balance: int
        +credit_limit: int
        +unsecured_cap: int
        +policy: PolicyConfig
        +arrival_config: Optional~ArrivalConfig~
    }

    class ArrivalConfig {
        +rate_per_tick: float
        +amount_distribution: AmountDistribution
        +counterparty_weights: Dict~str, float~
        +deadline_range: Tuple~int, int~
        +priority_distribution: Optional~PriorityDistribution~
        +divisible: bool
    }

    class PolicyConfig {
        +type: str
        +payment_tree: Optional~dict~
        +bank_tree: Optional~dict~
        +parameters: Optional~dict~
    }

    class CostConfig {
        +overdraft_cost_bps: float
        +delay_penalty_per_tick: int
        +deadline_penalty: int
        +split_friction_cost: int
        +eod_unsettled_penalty: int
        +collateral_cost_per_tick_bps: float
    }

    SimulationConfig --> AgentConfig
    AgentConfig --> ArrivalConfig
    AgentConfig --> PolicyConfig
    SimulationConfig --> CostConfig
```

### Distribution Types

```mermaid
classDiagram
    class AmountDistribution {
        <<union>>
    }

    class NormalDistribution {
        +type: "normal"
        +mean: int
        +std_dev: int
    }

    class LogNormalDistribution {
        +type: "lognormal"
        +mean: float
        +std_dev: float
    }

    class UniformDistribution {
        +type: "uniform"
        +min: int
        +max: int
    }

    class ExponentialDistribution {
        +type: "exponential"
        +lambda: float
    }

    AmountDistribution <|-- NormalDistribution
    AmountDistribution <|-- LogNormalDistribution
    AmountDistribution <|-- UniformDistribution
    AmountDistribution <|-- ExponentialDistribution
```

### Config Loader

**Source**: `api/payment_simulator/config/loader.py`

```mermaid
flowchart LR
    YAML["YAML File"] --> PyYAML["PyYAML<br/>Parser"]
    PyYAML --> Dict["Python Dict"]
    Dict --> Pydantic["Pydantic<br/>Validation"]
    Pydantic --> Config["SimulationConfig"]

    Pydantic -->|"Invalid"| Error["ValidationError"]
```

---

## 6. Persistence Module (`persistence/`)

### Purpose
DuckDB integration for event storage and analytical queries.

### DatabaseManager

**Source**: `api/payment_simulator/persistence/connection.py`

```mermaid
classDiagram
    class DatabaseManager {
        -db_path: Path
        -conn: DuckDBConnection
        -migrations_dir: Path
        +get_connection() DuckDBConnection
        +setup()
        +__enter__()
        +__exit__()
    }

    class SchemaGenerator {
        +generate_ddl(models) str
        +create_tables(conn, models)
    }

    class MigrationRunner {
        +apply_migrations(conn, migrations_dir)
        +get_pending_migrations() list
    }

    DatabaseManager --> SchemaGenerator
    DatabaseManager --> MigrationRunner
```

### Database Schema

**Source**: `api/payment_simulator/persistence/models.py`

```mermaid
erDiagram
    simulation_runs ||--o{ simulation_events : contains
    simulation_runs ||--o{ transactions : contains
    simulation_runs ||--o{ daily_agent_metrics : contains
    simulation_runs ||--o{ policy_snapshots : contains
    simulation_runs ||--o{ simulation_checkpoints : contains

    simulation_runs {
        string simulation_id PK
        json config_json
        timestamp created_at
        int total_ticks
        int ticks_per_day
    }

    simulation_events {
        string simulation_id PK
        int tick PK
        int event_id PK
        string event_type
        string tx_id
        string agent_id
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
        string status
    }

    daily_agent_metrics {
        string simulation_id PK
        int day PK
        string agent_id PK
        bigint opening_balance
        bigint closing_balance
        bigint total_costs
    }
```

### Event Writer

**Source**: `api/payment_simulator/persistence/event_writer.py`

```mermaid
flowchart TB
    Events["Events from FFI"] --> Writer["write_events_batch()"]
    Writer --> Transform["Transform to rows"]
    Transform --> Insert["Bulk INSERT"]
    Insert --> DB[(simulation_events)]

    Writer --> Check{"StateRegisterSet?"}
    Check -->|Yes| DualWrite["Also write to<br/>agent_state_registers"]
    DualWrite --> DB2[(agent_state_registers)]
```

### Query Interface

**Source**: `api/payment_simulator/persistence/event_queries.py`

```python
def get_simulation_events(
    conn: DuckDBConnection,
    simulation_id: str,
    tick: Optional[int] = None,
    tick_min: Optional[int] = None,
    tick_max: Optional[int] = None,
    day: Optional[int] = None,
    agent_id: Optional[str] = None,
    tx_id: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    sort: str = "tick_asc",
) -> Dict[str, Any]:
    """Query events with filtering, pagination, sorting."""
```

---

## 7. HTTP API (`api/`)

### Purpose
FastAPI-based REST API for programmatic simulation control.

**Source**: `api/payment_simulator/api/main.py`

### Endpoints

```mermaid
flowchart TB
    subgraph API["FastAPI Application"]
        Create["POST /api/simulations<br/>Create simulation"]
        Tick["POST /api/simulations/{id}/tick<br/>Execute tick"]
        State["GET /api/simulations/{id}/state<br/>Get state"]
        Txs["GET /api/simulations/{id}/transactions<br/>List transactions"]
        Delete["DELETE /api/simulations/{id}<br/>Delete simulation"]
        Checkpoint["POST /api/simulations/{id}/checkpoint<br/>Save checkpoint"]
    end

    Create --> Registry["In-memory<br/>Registry"]
    Tick --> FFI["FFI Call"]
    State --> FFI
```

### Endpoint Reference

| Endpoint | Method | Request | Response |
|----------|--------|---------|----------|
| `/api/simulations` | POST | `SimulationConfig` | `{simulation_id, status}` |
| `/api/simulations/{id}/tick` | POST | - | `TickResponse` |
| `/api/simulations/{id}/state` | GET | - | Full state dict |
| `/api/simulations/{id}/transactions` | GET | - | Transaction list |
| `/api/simulations/{id}` | DELETE | - | `{deleted: bool}` |
| `/api/simulations/{id}/checkpoint` | POST | `{description}` | `{checkpoint_id}` |

---

## 8. Event Filtering

### Purpose
Filter events for targeted analysis.

**Source**: `api/payment_simulator/cli/filters.py`

```mermaid
classDiagram
    class EventFilter {
        -event_types: Optional~list~
        -agent_id: Optional~str~
        -tx_id: Optional~str~
        -tick_min: Optional~int~
        -tick_max: Optional~int~
        +matches(event, tick) bool
        +from_cli_args(...) EventFilter
    }
```

### Filter Logic

```mermaid
flowchart TB
    Event["Event Dict"] --> TypeCheck{"event_types<br/>filter?"}
    TypeCheck -->|"No filter"| AgentCheck
    TypeCheck -->|"Has filter"| TypeMatch{"Type in list?"}
    TypeMatch -->|No| Reject([Filtered Out])
    TypeMatch -->|Yes| AgentCheck

    AgentCheck{"agent_id<br/>filter?"} -->|"No filter"| TxCheck
    AgentCheck -->|"Has filter"| AgentMatch{"ID matches?"}
    AgentMatch -->|No| Reject
    AgentMatch -->|Yes| TxCheck

    TxCheck{"tx_id<br/>filter?"} -->|"No filter"| TickCheck
    TxCheck -->|"Has filter"| TxMatch{"ID matches?"}
    TxMatch -->|No| Reject
    TxMatch -->|Yes| TickCheck

    TickCheck{"tick_range<br/>filter?"} -->|"No filter"| Accept([Passes Filter])
    TickCheck -->|"Has filter"| TickMatch{"In range?"}
    TickMatch -->|No| Reject
    TickMatch -->|Yes| Accept
```

---

## 9. FFI Integration

### _core.py Shim

**Source**: `api/payment_simulator/_core.py`

```python
# Re-export everything from Rust module
from payment_simulator_core_rs import *  # noqa: F401, F403
```

### Usage Pattern

```python
from payment_simulator._core import Orchestrator

# Create orchestrator with validated config
config_dict = {
    "ticks_per_day": 100,
    "seed": 12345,
    "agents": [...],
    # ...
}
orch = Orchestrator.new(config_dict)

# Execute tick
result = orch.tick()  # Returns dict

# Query state
balance = orch.get_agent_balance("BANK_A")
events = orch.get_tick_events(orch.current_tick())
```

See [04-ffi-boundary.md](./04-ffi-boundary.md) for detailed patterns.

---

## Data Flow Diagrams

### Run Command Flow

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant CLI as CLI
    participant Config as Config Layer
    participant Runner as SimulationRunner
    participant Output as OutputStrategy
    participant FFI as FFI Bridge
    participant Rust as Rust Engine
    participant DB as DuckDB

    User->>CLI: payment-sim run config.yaml --persist

    CLI->>Config: load_config(path)
    Config-->>CLI: SimulationConfig

    CLI->>FFI: Orchestrator.new(config)
    FFI->>Rust: Create engine
    Rust-->>FFI: PyOrchestrator

    CLI->>Runner: SimulationRunner(orch, output, persist)

    loop Each Tick
        Runner->>FFI: orch.tick()
        FFI->>Rust: Execute tick
        Rust-->>FFI: TickResult
        FFI-->>Runner: dict

        Runner->>Output: on_tick_complete()
        Runner->>DB: Persist events
    end

    Runner-->>CLI: Final stats
    CLI-->>User: JSON output
```

### Replay Command Flow

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant CLI as CLI
    participant DB as DuckDB
    participant Provider as DatabaseStateProvider
    participant Display as display_tick_verbose_output

    User->>CLI: payment-sim replay db.db

    CLI->>DB: Load simulation config
    DB-->>CLI: Config JSON

    CLI->>Provider: DatabaseStateProvider(conn, sim_id)

    loop Each Tick
        CLI->>DB: get_simulation_events(tick)
        DB-->>CLI: Events list

        CLI->>Display: display_tick_verbose_output(provider, events)
        Display->>Provider: get_agent_balance()
        Provider->>DB: SQL query
        DB-->>Provider: Result
        Display-->>CLI: Formatted output
    end

    CLI-->>User: Output
```

---

## Testing Strategy

### Test Organization

```
api/tests/
├── conftest.py              # Pytest fixtures
├── unit/                    # Pure Python tests
│   ├── test_config.py
│   ├── test_filters.py
│   └── test_stats.py
├── integration/             # FFI + persistence
│   ├── test_determinism.py
│   ├── test_replay_identity.py
│   └── test_persistence.py
├── cli/                     # CLI command tests
│   ├── test_run.py
│   └── test_replay.py
└── e2e/                     # End-to-end API tests
    └── test_api.py
```

### Test Commands

```bash
# Run all Python tests
cd api
.venv/bin/python -m pytest

# Run specific test
.venv/bin/python -m pytest tests/integration/test_replay_identity.py

# With coverage
.venv/bin/python -m pytest --cov=payment_simulator
```

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| pydantic | ≥2.0.0 | Configuration validation |
| pyyaml | ≥6.0 | YAML parsing |
| typer | ≥0.9.0 | CLI framework |
| rich | ≥13.0.0 | Terminal formatting |
| duckdb | ≥0.9.0 | OLAP database |
| polars | ≥0.19.0 | DataFrames |
| pyarrow | ≥14.0.0 | Arrow format |
| fastapi | ≥0.104.0 | HTTP API |
| uvicorn | ≥0.24.0 | ASGI server |

---

## Related Documents

- [02-rust-core-engine.md](./02-rust-core-engine.md) - Rust backend details
- [04-ffi-boundary.md](./04-ffi-boundary.md) - Integration patterns
- [09-persistence-layer.md](./09-persistence-layer.md) - Database details
- [10-cli-architecture.md](./10-cli-architecture.md) - CLI details

---

*Next: [04-ffi-boundary.md](./04-ffi-boundary.md) - FFI integration patterns*
