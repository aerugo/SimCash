# Implementation Plan: DuckDB-Based Simulation Persistence

## Document Purpose
This plan details the implementation of file-based data persistence for the payment simulator using DuckDB, enabling storage and analysis of simulation runs, transactions, agent states, and policy evolution across hundreds of simulation episodes.

## Executive Summary

**Goal**: Implement batch-write persistence that saves simulation state at the beginning of each run and after each simulated "day", using DuckDB as a single, unified data store for both operational data and analytical queries.

**Key Design Decisions**:
1. **Database**: DuckDB exclusively (columnar, analytical, file-based)
2. **DataFrame Library**: Polars (faster than Pandas, Arrow-native, zero-copy with DuckDB)
3. **Schema Management**: Pydantic models as single source of truth with automated DDL generation
4. **Migration Strategy**: Versioned migrations + runtime validation to prevent schema drift

**Scope**:
- 200 simulation runs × 1.2M transactions/run = 240M+ transaction records
- 200 runs × 200 agents × 10 days × 2 policy files/day = 800K policy snapshots
- Agent metrics collected daily (200 agents × 10 days × 200 runs = 400K daily summaries)

---

## Part I: Architecture Overview

### 1.1 Data Persistence Points

**Persistence Trigger Points**:
1. **Simulation Start**: Record run metadata, initial configuration, opening balances
2. **End of Each Day**: Batch-write all transactions, agent metrics, policy changes for that day
3. **Simulation End**: Record final metrics, completion status

**Why Not Real-Time?**
- Real-time writes during tick loop would slow simulation by 10-50x
- DuckDB excels at bulk appends (millions of rows/sec), not frequent small writes
- Batch writes leverage columnar storage efficiency

### 1.2 Database File Structure

```
/Users/hugi/GitRepos/cashman/
├── simulation_data.db          # Single DuckDB file (all data)
├── backend/policies/           # Policy JSON files (git-tracked separately)
│   ├── BANK_A_policy_v1.json
│   ├── BANK_A_policy_v2.json
│   └── ...
└── configs/                    # Simulation configs (YAML/JSON)
```

**Design Rationale**:
- Single `.db` file simplifies backups, migrations, and deployment
- Policy JSON files stored separately for git versioning (LLM manager Phase 9)
- Database stores policy metadata + file paths, not full JSON

---

## Part II: Schema Management Strategy

### 2.1 The Schema Drift Problem

**Challenge**: As the project evolves, we'll add new fields to Pydantic models, change field types, add new tables, etc. We need to ensure:
1. Database schema stays in sync with Pydantic models
2. Existing databases can be migrated automatically
3. No runtime errors from schema mismatches
4. Minimal manual work to keep things in sync

**Bad Scenario** (what we want to avoid):
```python
# Developer adds field to Pydantic model
class TransactionRecord(BaseModel):
    tx_id: str
    amount: int
    settlement_type: str  # ← NEW FIELD

# Database still has old schema (no settlement_type column)
# Runtime error: "column settlement_type does not exist"
```

---

### 2.2 Solution: Single Source of Truth Pattern

**Core Principle**: **Pydantic models are the source of truth**. Database schema is derived from models, not the other way around.

**Architecture**:
```
┌──────────────────────────────────────────────────────┐
│  Pydantic Models (persistence/models.py)             │
│  - Define all data structures                        │
│  - Include metadata (indexes, constraints)           │
└────────────────┬─────────────────────────────────────┘
                 │
                 ├─── Auto-generate DDL ──────────────┐
                 │                                     ▼
                 │                        ┌────────────────────────┐
                 │                        │  DDL Generator         │
                 │                        │  - Convert models      │
                 │                        │    to CREATE TABLE     │
                 │                        └───────┬────────────────┘
                 │                                │
                 ├─── Validate at runtime ────┐   │
                 │                             ▼   ▼
                 │                        ┌────────────────────────┐
                 │                        │  DuckDB Database       │
                 │                        │  - Tables + Indexes    │
                 │                        └────────────────────────┘
                 │
                 └─── Generate migrations ────────────────────────┐
                                                                  ▼
                                                    ┌──────────────────────────┐
                                                    │  Migration Scripts       │
                                                    │  - Versioned SQL files   │
                                                    └──────────────────────────┘
```

---

### 2.3 Implementation: Pydantic Models with Metadata

**File**: `api/payment_simulator/persistence/models.py`

```python
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from enum import Enum


# ============================================================================
# Table Configuration (metadata for DDL generation)
# ============================================================================

class TableConfig(BaseModel):
    """Metadata for table creation."""
    table_name: str
    primary_key: list[str]
    indexes: list[tuple[str, list[str]]] = []  # [(index_name, [columns])]
    unique_constraints: list[list[str]] = []


# ============================================================================
# Transaction Record
# ============================================================================

class TransactionStatus(str, Enum):
    PENDING = "pending"
    SETTLED = "settled"
    DROPPED = "dropped"


class TransactionRecord(BaseModel):
    """Transaction record for persistence.

    This model defines the schema for the transactions table.
    Changes to this model will trigger schema migration warnings.
    """

    # Identity
    simulation_id: str = Field(..., description="Foreign key to simulations table")
    tx_id: str = Field(..., description="Unique transaction identifier")

    # Participants
    sender_id: str = Field(..., description="Sender agent ID")
    receiver_id: str = Field(..., description="Receiver agent ID")

    # Transaction details
    amount: int = Field(..., description="Amount in cents", ge=0)
    priority: int = Field(..., description="Priority level", ge=0, le=10)
    divisible: bool = Field(..., description="Can be split")

    # Lifecycle timing
    arrival_tick: int = Field(..., description="Tick when arrived")
    arrival_day: int = Field(..., description="Day when arrived")
    deadline_tick: int = Field(..., description="Settlement deadline")
    settlement_tick: Optional[int] = Field(None, description="Tick when settled")
    settlement_day: Optional[int] = Field(None, description="Day when settled")

    # Status
    status: TransactionStatus = Field(..., description="Current status")
    drop_reason: Optional[str] = Field(None, description="Why dropped (if applicable)")

    # Metrics
    queue1_ticks: int = Field(0, description="Time spent in Queue 1")
    queue2_ticks: int = Field(0, description="Time spent in Queue 2")
    total_delay_ticks: int = Field(0, description="Total delay")

    # Costs
    delay_cost: int = Field(0, description="Queue 1 delay cost in cents")

    # Splitting
    parent_tx_id: Optional[str] = Field(None, description="Parent transaction if split")
    split_index: Optional[int] = Field(None, description="Split index (1, 2, ...)")

    class Config:
        # Table metadata for DDL generation
        table_name = "transactions"
        primary_key = ["simulation_id", "tx_id"]
        indexes = [
            ("idx_tx_sim_sender", ["simulation_id", "sender_id"]),
            ("idx_tx_sim_day", ["simulation_id", "arrival_day"]),
            ("idx_tx_status", ["status"]),
        ]


# ============================================================================
# Daily Agent Metrics
# ============================================================================

class DailyAgentMetricsRecord(BaseModel):
    """Daily agent metrics for persistence."""

    simulation_id: str
    agent_id: str
    day: int

    # Balance metrics
    opening_balance: int
    closing_balance: int
    min_balance: int
    max_balance: int

    # Credit usage
    credit_limit: int
    peak_overdraft: int

    # Transaction counts
    num_arrivals: int = 0
    num_sent: int = 0
    num_received: int = 0
    num_settled: int = 0
    num_dropped: int = 0

    # Queue metrics
    queue1_peak_size: int = 0
    queue1_eod_size: int = 0

    # Costs
    liquidity_cost: int = 0
    delay_cost: int = 0
    split_friction_cost: int = 0
    deadline_penalty_cost: int = 0
    total_cost: int = 0

    class Config:
        table_name = "daily_agent_metrics"
        primary_key = ["simulation_id", "agent_id", "day"]
        indexes = [
            ("idx_metrics_sim_day", ["simulation_id", "day"]),
        ]


# ============================================================================
# Simulation Metadata
# ============================================================================

class SimulationStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SimulationRecord(BaseModel):
    """Simulation run metadata."""

    simulation_id: str
    config_file: str
    config_hash: str
    rng_seed: int
    ticks_per_day: int
    num_days: int
    num_agents: int

    started_at: datetime
    completed_at: Optional[datetime] = None

    total_ticks_executed: Optional[int] = None
    duration_seconds: Optional[float] = None
    ticks_per_second: Optional[float] = None

    total_arrivals: Optional[int] = None
    total_settlements: Optional[int] = None
    total_lsm_releases: Optional[int] = None
    total_cost_cents: Optional[int] = None

    status: SimulationStatus
    error_message: Optional[str] = None

    class Config:
        table_name = "simulations"
        primary_key = ["simulation_id"]
        indexes = [
            ("idx_sim_config_seed", ["config_hash", "rng_seed"]),
            ("idx_sim_started", ["started_at"]),
        ]


# ============================================================================
# Policy Snapshots
# ============================================================================

class PolicySnapshotRecord(BaseModel):
    """Policy snapshot tracking."""

    id: Optional[int] = None  # Auto-increment
    simulation_id: str
    agent_id: str
    day: int

    policy_version: str
    policy_type: str
    policy_file_path: Optional[str] = None
    policy_hash: Optional[str] = None

    created_at: datetime
    created_by: str  # 'manual', 'llm_manager', 'init'

    estimated_cost_improvement: Optional[float] = None
    validation_status: Optional[str] = None

    class Config:
        table_name = "policy_snapshots"
        primary_key = ["id"]
        indexes = [
            ("idx_policy_sim_agent_day", ["simulation_id", "agent_id", "day"]),
            ("idx_policy_hash", ["policy_hash"]),
        ]


# ============================================================================
# Config Archive
# ============================================================================

class ConfigArchiveRecord(BaseModel):
    """Archived configuration files."""

    config_hash: str
    config_yaml: str
    first_used_at: datetime
    last_used_at: datetime
    usage_count: int = 1

    class Config:
        table_name = "config_archive"
        primary_key = ["config_hash"]
        indexes = []
```

---

### 2.4 DDL Auto-Generation

**File**: `api/payment_simulator/persistence/schema_generator.py`

```python
"""Generate DDL from Pydantic models."""
from typing import Type, get_type_hints, get_origin, get_args
from pydantic import BaseModel
from datetime import datetime
from enum import Enum
import inspect


PYTHON_TO_SQL_TYPE_MAP = {
    str: "VARCHAR",
    int: "BIGINT",
    float: "DOUBLE",
    bool: "BOOLEAN",
    datetime: "TIMESTAMP",
}


def python_type_to_sql_type(py_type) -> str:
    """Convert Python type to SQL type."""
    # Handle Optional types
    if get_origin(py_type) is type(None) or get_origin(py_type) is type(Optional):
        args = get_args(py_type)
        if args:
            py_type = args[0]

    # Handle enums
    if inspect.isclass(py_type) and issubclass(py_type, Enum):
        return "VARCHAR"

    # Direct mapping
    return PYTHON_TO_SQL_TYPE_MAP.get(py_type, "VARCHAR")


def generate_create_table_ddl(model: Type[BaseModel]) -> str:
    """Generate CREATE TABLE DDL from Pydantic model.

    Args:
        model: Pydantic model class with Config.table_name

    Returns:
        SQL CREATE TABLE statement
    """
    if not hasattr(model, 'Config') or not hasattr(model.Config, 'table_name'):
        raise ValueError(f"Model {model.__name__} missing Config.table_name")

    table_name = model.Config.table_name
    primary_key = getattr(model.Config, 'primary_key', [])

    # Get field definitions
    fields = model.model_fields
    columns = []

    for field_name, field_info in fields.items():
        py_type = field_info.annotation
        sql_type = python_type_to_sql_type(py_type)

        # Check if nullable
        is_optional = (
            get_origin(py_type) is type(None)
            or (hasattr(field_info, 'default') and field_info.default is None)
        )

        null_constraint = "" if is_optional else " NOT NULL"

        # Auto-increment for primary key integer fields
        auto_increment = ""
        if field_name == "id" and py_type is int:
            auto_increment = " AUTOINCREMENT"

        columns.append(f"    {field_name} {sql_type}{null_constraint}{auto_increment}")

    # Add primary key constraint
    if primary_key:
        pk_cols = ", ".join(primary_key)
        columns.append(f"    PRIMARY KEY ({pk_cols})")

    ddl = f"CREATE TABLE IF NOT EXISTS {table_name} (\n"
    ddl += ",\n".join(columns)
    ddl += "\n);"

    return ddl


def generate_create_indexes_ddl(model: Type[BaseModel]) -> list[str]:
    """Generate CREATE INDEX statements from Pydantic model."""
    if not hasattr(model, 'Config') or not hasattr(model.Config, 'indexes'):
        return []

    table_name = model.Config.table_name
    indexes = model.Config.indexes

    ddl_statements = []
    for index_name, columns in indexes:
        cols = ", ".join(columns)
        ddl = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({cols});"
        ddl_statements.append(ddl)

    return ddl_statements


def generate_full_schema_ddl() -> str:
    """Generate complete schema DDL for all models."""
    from .models import (
        SimulationRecord,
        TransactionRecord,
        DailyAgentMetricsRecord,
        PolicySnapshotRecord,
        ConfigArchiveRecord,
    )

    models = [
        SimulationRecord,
        TransactionRecord,
        DailyAgentMetricsRecord,
        PolicySnapshotRecord,
        ConfigArchiveRecord,
    ]

    ddl_parts = []

    # Generate CREATE TABLE statements
    for model in models:
        ddl_parts.append(generate_create_table_ddl(model))
        ddl_parts.extend(generate_create_indexes_ddl(model))

    # Add schema_migrations table
    ddl_parts.append("""
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL,
    description VARCHAR NOT NULL
);
""")

    return "\n\n".join(ddl_parts)


# ============================================================================
# Runtime Validation
# ============================================================================

def validate_table_schema(conn, model: Type[BaseModel]) -> tuple[bool, list[str]]:
    """Validate that database table matches Pydantic model.

    Args:
        conn: DuckDB connection
        model: Pydantic model to validate

    Returns:
        (is_valid, list of error messages)
    """
    table_name = model.Config.table_name

    # Get actual table schema from database
    try:
        result = conn.execute(f"DESCRIBE {table_name}").fetchall()
        db_columns = {row[0]: row[1] for row in result}  # column_name: column_type
    except Exception as e:
        return False, [f"Table {table_name} does not exist: {e}"]

    errors = []

    # Check all model fields exist in database
    for field_name, field_info in model.model_fields.items():
        if field_name not in db_columns:
            errors.append(f"Column {field_name} missing from table {table_name}")

    # Check for unexpected columns in database
    model_fields = set(model.model_fields.keys())
    db_fields = set(db_columns.keys())
    extra_cols = db_fields - model_fields
    if extra_cols:
        errors.append(f"Unexpected columns in {table_name}: {extra_cols}")

    return len(errors) == 0, errors
```

---

### 2.5 Migration System

**File**: `api/payment_simulator/persistence/migrations.py`

```python
"""Schema migration system."""
from pathlib import Path
from datetime import datetime
import duckdb


class MigrationManager:
    """Manages database schema migrations."""

    def __init__(self, conn: duckdb.DuckDBPyConnection, migrations_dir: Path):
        self.conn = conn
        self.migrations_dir = migrations_dir

        # Ensure schema_migrations table exists
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP NOT NULL,
                description VARCHAR NOT NULL
            )
        """)

    def get_applied_versions(self) -> set[int]:
        """Get set of applied migration versions."""
        result = self.conn.execute("""
            SELECT version FROM schema_migrations ORDER BY version
        """).fetchall()
        return {row[0] for row in result}

    def get_pending_migrations(self) -> list[tuple[int, str, str]]:
        """Get list of pending migrations.

        Returns:
            List of (version, description, sql_content)
        """
        applied = self.get_applied_versions()
        pending = []

        # Scan migrations directory for .sql files
        for migration_file in sorted(self.migrations_dir.glob("*.sql")):
            # Parse filename: 001_add_settlement_type.sql
            filename = migration_file.name
            if not filename[0].isdigit():
                continue

            version = int(filename.split('_')[0])
            if version not in applied:
                description = filename[4:-4].replace('_', ' ')  # Remove version and .sql
                sql_content = migration_file.read_text()
                pending.append((version, description, sql_content))

        return sorted(pending, key=lambda x: x[0])

    def apply_migration(self, version: int, description: str, sql_content: str):
        """Apply a single migration."""
        print(f"Applying migration {version}: {description}")

        self.conn.begin()
        try:
            # Execute migration SQL
            self.conn.execute(sql_content)

            # Record migration
            self.conn.execute("""
                INSERT INTO schema_migrations (version, applied_at, description)
                VALUES (?, ?, ?)
            """, [version, datetime.now(), description])

            self.conn.commit()
            print(f"  ✓ Migration {version} applied successfully")
        except Exception as e:
            self.conn.rollback()
            raise RuntimeError(f"Migration {version} failed: {e}")

    def apply_pending_migrations(self):
        """Apply all pending migrations in order."""
        pending = self.get_pending_migrations()

        if not pending:
            print("No pending migrations")
            return

        print(f"Found {len(pending)} pending migration(s)")

        for version, description, sql_content in pending:
            self.apply_migration(version, description, sql_content)

        print("All migrations applied successfully")

    def create_migration_template(self, description: str) -> Path:
        """Create a new migration file template.

        Args:
            description: Migration description (e.g., "add_settlement_type")

        Returns:
            Path to created migration file
        """
        # Get next version number
        applied = self.get_applied_versions()
        next_version = max(applied) + 1 if applied else 1

        # Create filename
        filename = f"{next_version:03d}_{description}.sql"
        filepath = self.migrations_dir / filename

        # Write template
        template = f"""-- Migration {next_version}: {description.replace('_', ' ')}
-- Created: {datetime.now().isoformat()}

-- Add your migration SQL here
-- Example:
-- ALTER TABLE transactions ADD COLUMN settlement_type VARCHAR;

-- Don't forget to update the corresponding Pydantic model!
"""
        filepath.write_text(template)

        print(f"Created migration template: {filepath}")
        return filepath
```

---

### 2.6 Database Initialization with Validation

**File**: `api/payment_simulator/persistence/connection.py`

```python
"""DuckDB connection manager with schema validation."""
import duckdb
from pathlib import Path
from .schema_generator import generate_full_schema_ddl, validate_table_schema
from .migrations import MigrationManager
from .models import (
    SimulationRecord,
    TransactionRecord,
    DailyAgentMetricsRecord,
    PolicySnapshotRecord,
    ConfigArchiveRecord,
)


class DatabaseManager:
    """Manages DuckDB connection and schema."""

    def __init__(self, db_path: str | Path = "simulation_data.db"):
        self.db_path = Path(db_path)
        self.conn = duckdb.connect(str(self.db_path))
        self.migrations_dir = Path(__file__).parent.parent.parent.parent / "migrations"
        self.migrations_dir.mkdir(exist_ok=True)

    def initialize_schema(self):
        """Initialize database schema from Pydantic models."""
        print("Initializing database schema...")

        # Generate DDL from models
        ddl = generate_full_schema_ddl()

        # Execute DDL
        self.conn.executescript(ddl)

        print("  ✓ Schema initialized")

    def validate_schema(self) -> bool:
        """Validate that database schema matches Pydantic models.

        Returns:
            True if valid, False otherwise (with error messages printed)
        """
        print("Validating database schema...")

        models = [
            SimulationRecord,
            TransactionRecord,
            DailyAgentMetricsRecord,
            PolicySnapshotRecord,
            ConfigArchiveRecord,
        ]

        all_valid = True
        for model in models:
            is_valid, errors = validate_table_schema(self.conn, model)
            if not is_valid:
                all_valid = False
                print(f"  ✗ {model.Config.table_name}:")
                for error in errors:
                    print(f"      {error}")
            else:
                print(f"  ✓ {model.Config.table_name}")

        return all_valid

    def apply_migrations(self):
        """Apply pending schema migrations."""
        manager = MigrationManager(self.conn, self.migrations_dir)
        manager.apply_pending_migrations()

    def setup(self):
        """Complete database setup: initialize + migrate + validate."""
        # 1. Initialize schema (creates tables if not exist)
        self.initialize_schema()

        # 2. Apply pending migrations
        self.apply_migrations()

        # 3. Validate schema matches models
        if not self.validate_schema():
            raise RuntimeError(
                "Database schema validation failed. "
                "This likely means the database schema is out of sync with Pydantic models. "
                "Create a migration file to fix the schema, or delete the database and reinitialize."
            )

        print("Database setup complete")

    def close(self):
        """Close database connection."""
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# ============================================================================
# Convenience functions
# ============================================================================

def get_connection(db_path: str | Path = "simulation_data.db") -> duckdb.DuckDBPyConnection:
    """Get database connection (creates/validates schema automatically)."""
    manager = DatabaseManager(db_path)
    manager.setup()
    return manager.conn
```

---

### 2.7 Developer Workflow

#### Adding a New Field to an Existing Table

**Scenario**: We want to add `settlement_type` field to track how a transaction was settled.

**Step 1**: Update Pydantic model:
```python
# api/payment_simulator/persistence/models.py

class TransactionRecord(BaseModel):
    # ... existing fields ...

    settlement_type: Optional[str] = Field(
        None,
        description="How settled: 'immediate', 'lsm_bilateral', 'lsm_cycle'"
    )
```

**Step 2**: Create migration:
```bash
cd api
python -m payment_simulator.persistence.migrations create add_settlement_type
```

This generates: `migrations/002_add_settlement_type.sql`

**Step 3**: Edit migration SQL:
```sql
-- Migration 002: add settlement type
-- Created: 2025-10-29T10:30:00

ALTER TABLE transactions ADD COLUMN settlement_type VARCHAR;
```

**Step 4**: Run database setup (applies migration automatically):
```bash
payment-sim db migrate
```

**Step 5**: Validation confirms schema matches:
```
Validating database schema...
  ✓ simulations
  ✓ transactions (includes new settlement_type column)
  ✓ daily_agent_metrics
  ...
Database setup complete
```

---

#### Adding a New Table

**Scenario**: We want to add a `lsm_events` table to track LSM optimization details.

**Step 1**: Create Pydantic model:
```python
# api/payment_simulator/persistence/models.py

class LsmEventRecord(BaseModel):
    """LSM optimization event."""

    simulation_id: str
    tick: int
    event_type: str  # 'bilateral', 'cycle'
    num_transactions: int
    liquidity_saved: int

    class Config:
        table_name = "lsm_events"
        primary_key = ["simulation_id", "tick"]
        indexes = [
            ("idx_lsm_sim", ["simulation_id"]),
        ]
```

**Step 2**: Update schema generator:
```python
# api/payment_simulator/persistence/schema_generator.py

def generate_full_schema_ddl() -> str:
    from .models import (
        # ... existing models ...
        LsmEventRecord,  # ← ADD THIS
    )

    models = [
        # ... existing models ...
        LsmEventRecord,  # ← ADD THIS
    ]
```

**Step 3**: Create migration:
```bash
python -m payment_simulator.persistence.migrations create add_lsm_events_table
```

**Step 4**: Edit migration (optional - DDL auto-generated from model):
```sql
-- Migration 003: add lsm events table
-- Created: 2025-10-29T11:00:00

-- This migration is auto-generated from LsmEventRecord model
-- Just run `payment-sim db migrate` and the table will be created
```

**Step 5**: Run migration:
```bash
payment-sim db migrate
```

---

### 2.8 Safeguards Against Schema Drift

**1. Pre-Commit Hook**: Run schema validation before allowing commits
```bash
# .git/hooks/pre-commit
#!/bin/bash
python -m payment_simulator.persistence.validate_schema || exit 1
```

**2. CI/CD Check**: Run validation in CI pipeline
```yaml
# .github/workflows/test.yml
- name: Validate schema
  run: |
    python -m payment_simulator.persistence.validate_schema
    if [ $? -ne 0 ]; then
      echo "Schema validation failed. Update migration files!"
      exit 1
    fi
```

**3. Runtime Warning**: On database connection, validate schema
```python
# This runs automatically when calling get_connection()
manager = DatabaseManager('simulation_data.db')
manager.setup()  # Validates schema, raises error if mismatch
```

**4. Developer Documentation**: Clear checklist for changes (see Part VI below)

---

## Part III: Implementation Strategy

### 3.1 Phased Rollout

#### Phase 1: Persistence Infrastructure (2-3 days)
**Goal**: Set up DuckDB integration, schema management, validation.

**Tasks**:
1. Add `duckdb` and `polars` Python dependencies to `api/pyproject.toml`
2. Create `api/payment_simulator/persistence/` module:
   - `models.py`: Pydantic models with table metadata
   - `schema_generator.py`: Auto-generate DDL from models
   - `migrations.py`: Migration management system
   - `connection.py`: Database manager with validation
3. Create `migrations/` directory for versioned SQL files
4. Add CLI commands:
   - `payment-sim db init` - Initialize database
   - `payment-sim db migrate` - Apply pending migrations
   - `payment-sim db validate` - Validate schema
   - `payment-sim db create-migration <desc>` - Create migration template

**Success Criteria**:
- Database created from Pydantic models automatically
- Schema validation detects mismatches
- Migration system applies changes correctly
- Developer can add fields without manual DDL writing

---

#### Phase 2: Daily Transaction Batch Writes (2-3 days)
**Goal**: Collect and save all transactions at end of each simulated day.

**Tasks**:
1. **Rust FFI Extension** (`backend/src/ffi/orchestrator.rs`):
   - Add method: `fn get_transactions_for_day(&self, day: usize) -> PyResult<Vec<PyDict>>`
   - Returns all transactions that arrived/settled/dropped during specified day
   - Includes full lifecycle details (arrival_tick, settlement_tick, status, costs)

2. **Python Data Collection** (`run.py`):
   - Modify day loop to call `orch.get_transactions_for_day(day)` after last tick of day
   - Convert to Polars DataFrame
   - Write to DuckDB via `conn.execute("INSERT INTO transactions SELECT * FROM df")`

3. **Transaction Tracking**:
   - Rust orchestrator already tracks transactions in `SimulationState`
   - Need to add "day completed" helper that filters transactions by day

**Code Sketch (Python)**:
```python
import polars as pl

for day in range(num_days):
    # Simulate entire day (200 ticks)
    for tick_in_day in range(ticks_per_day):
        orch.tick()

    # End of day: persist transactions
    daily_txs = orch.get_transactions_for_day(day)
    if daily_txs:
        # Create Polars DataFrame from list of dicts
        df = pl.DataFrame(daily_txs)

        # Write to DuckDB (zero-copy via Arrow)
        conn.execute("INSERT INTO transactions SELECT * FROM df")
```

**Success Criteria**:
- All transactions for a day written to DB in <100ms (40K txs)
- Data survives process restart
- Determinism preserved

---

#### Phase 3: Agent Metrics Collection (1-2 days)
**Goal**: Save daily agent state snapshots.

**Tasks**:
1. **Rust FFI Extension**:
   - Add method: `fn get_daily_agent_metrics(&self, day: usize) -> PyResult<Vec<PyDict>>`
   - Returns metrics for all agents for specified day

2. **Rust Metric Calculation** (`backend/src/orchestrator/engine.rs`):
   - Add `DailyMetricsCollector` that tracks per-agent stats during tick loop
   - Reset at start of each day
   - Track: min/max balance, peak overdraft, queue sizes, transaction counts, costs

3. **Python Persistence**:
   - Call `orch.get_daily_agent_metrics(day)` at end of day
   - Create Polars DataFrame
   - Write to `daily_agent_metrics` table

**Success Criteria**:
- Agent metrics match tick-by-tick accumulated values
- Can query historical agent state
- Fast analytical queries without scanning all transactions

---

#### Phase 4: Policy Snapshot Tracking (1 day)
**Goal**: Record policy changes and file paths.

**Tasks**:
1. Create policy snapshot records when:
   - Simulation starts (record initial policies)
   - Policy changes mid-simulation (manual or LLM-managed)

2. **Policy File Management**:
   - Store JSON policy files in `backend/policies/`
   - Use naming convention: `{agent_id}_policy_{version}.json`
   - Compute SHA256 hash for deduplication
   - Record file path + hash in `policy_snapshots` table

**Success Criteria**:
- Can reconstruct policy history for any agent
- Hash-based deduplication works
- Integration with Phase 9 DSL

---

#### Phase 5: Query Interface & Analytics (2-3 days)
**Goal**: Provide convenient API for querying stored data.

**Tasks**:
1. **Create Query Module** (`api/payment_simulator/persistence/queries.py`):
   - Pre-defined analytical queries as Python functions
   - Return Polars DataFrames

2. **DuckDB Analytical Queries**:
   ```python
   def get_agent_performance(sim_id: str, agent_id: str) -> pl.DataFrame:
       return conn.execute(f"""
           SELECT day, closing_balance, peak_overdraft, total_cost
           FROM daily_agent_metrics
           WHERE simulation_id = '{sim_id}' AND agent_id = '{agent_id}'
           ORDER BY day
       """).pl()
   ```

3. **CLI Integration**:
   - Add `payment-sim query` subcommand
   - Examples: `list-runs`, `show-run`, `agent-metrics`

**Success Criteria**:
- Can query 250M transactions in <1 second for aggregates
- Polars DataFrames integrate with data science workflows
- CLI provides quick insights

---

## Part IV: Testing Strategy

### 4.1 Schema Validation Tests

**File**: `api/tests/unit/test_schema_validation.py`

```python
import pytest
from payment_simulator.persistence.models import TransactionRecord
from payment_simulator.persistence.schema_generator import (
    generate_create_table_ddl,
    validate_table_schema,
)
import duckdb


def test_ddl_generation_from_model():
    """Verify DDL generation from Pydantic model."""
    ddl = generate_create_table_ddl(TransactionRecord)

    assert "CREATE TABLE IF NOT EXISTS transactions" in ddl
    assert "simulation_id VARCHAR NOT NULL" in ddl
    assert "tx_id VARCHAR NOT NULL" in ddl
    assert "amount BIGINT NOT NULL" in ddl
    assert "PRIMARY KEY (simulation_id, tx_id)" in ddl


def test_schema_validation_detects_missing_column():
    """Verify validation detects schema mismatch."""
    conn = duckdb.connect(':memory:')

    # Create table with missing column
    conn.execute("""
        CREATE TABLE transactions (
            simulation_id VARCHAR NOT NULL,
            tx_id VARCHAR NOT NULL,
            amount BIGINT NOT NULL
            -- Missing other columns!
        )
    """)

    is_valid, errors = validate_table_schema(conn, TransactionRecord)

    assert not is_valid
    assert len(errors) > 0
    assert any("missing" in err.lower() for err in errors)


def test_schema_validation_passes_for_matching_schema():
    """Verify validation passes when schema matches."""
    conn = duckdb.connect(':memory:')

    # Create table using auto-generated DDL
    ddl = generate_create_table_ddl(TransactionRecord)
    conn.execute(ddl)

    is_valid, errors = validate_table_schema(conn, TransactionRecord)

    assert is_valid
    assert len(errors) == 0
```

---

### 4.2 Integration Tests

**File**: `api/tests/integration/test_persistence_integration.py`

```python
def test_full_simulation_persistence():
    """Run small simulation and verify all data persisted."""
    # Create test config (2 agents, 2 days, 10 ticks/day)
    config = create_test_config()

    # Run simulation with persistence
    db_path = tmpdir / 'test.db'
    run_simulation_with_persistence(config, db_path)

    # Verify data
    conn = duckdb.connect(str(db_path))

    # Check simulation record exists
    sims = conn.execute("SELECT * FROM simulations").fetchall()
    assert len(sims) == 1

    # Check transactions recorded
    tx_count = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    assert tx_count > 0

    # Check agent metrics (2 agents × 2 days = 4 records)
    metrics_count = conn.execute("SELECT COUNT(*) FROM daily_agent_metrics").fetchone()[0]
    assert metrics_count == 4
```

---

### 4.3 Performance Tests

```python
def test_large_batch_write_performance():
    """Verify 40K transaction insert completes in <100ms."""
    conn = duckdb.connect(':memory:')
    init_database(conn)

    # Generate 40K sample transactions
    transactions = [generate_sample_transaction(i) for i in range(40000)]
    df = pl.DataFrame(transactions)

    start = time.time()
    conn.execute("INSERT INTO transactions SELECT * FROM df")
    conn.commit()
    duration = time.time() - start

    assert duration < 0.1  # Must complete in <100ms
```

---

## Part V: CLI Commands for Schema Management

**File**: `api/payment_simulator/cli/commands/db.py`

```python
"""Database management commands."""
import typer
from pathlib import Path
from payment_simulator.persistence.connection import DatabaseManager
from payment_simulator.persistence.migrations import MigrationManager


app = typer.Typer(name="db", help="Database schema management")


@app.command()
def init(db_path: str = "simulation_data.db"):
    """Initialize database schema from Pydantic models."""
    manager = DatabaseManager(db_path)
    manager.initialize_schema()
    typer.echo("✓ Database initialized")


@app.command()
def migrate(db_path: str = "simulation_data.db"):
    """Apply pending schema migrations."""
    manager = DatabaseManager(db_path)
    manager.apply_migrations()


@app.command()
def validate(db_path: str = "simulation_data.db"):
    """Validate database schema matches Pydantic models."""
    manager = DatabaseManager(db_path)

    if manager.validate_schema():
        typer.echo("✓ Schema validation passed")
    else:
        typer.echo("✗ Schema validation failed", err=True)
        raise typer.Exit(1)


@app.command()
def create_migration(description: str):
    """Create a new migration template."""
    migrations_dir = Path("migrations")
    migrations_dir.mkdir(exist_ok=True)

    manager = MigrationManager(None, migrations_dir)
    filepath = manager.create_migration_template(description)
    typer.echo(f"Created migration: {filepath}")
    typer.echo("Edit the file and then run: payment-sim db migrate")
```

---

## Part VI: Documentation & Developer Experience

### 6.1 Schema Change Documentation

**File**: `docs/SCHEMA_CHANGES.md`

```markdown
# Database Schema Changes

This document explains how to make changes to the database schema.

## Quick Reference

### Adding a field to existing table:
1. Update Pydantic model in `persistence/models.py`
2. Run `payment-sim db create-migration add_my_field`
3. Edit generated migration SQL
4. Run `payment-sim db migrate`

### Adding a new table:
1. Create Pydantic model in `persistence/models.py`
2. Add model to `schema_generator.py`
3. Run `payment-sim db migrate` (auto-generates table)

### Checking schema status:
```bash
payment-sim db validate
```

## Example: Adding settlement_type Field

**1. Update Pydantic model:**
```python
class TransactionRecord(BaseModel):
    # ... existing fields ...
    settlement_type: Optional[str] = None  # ← NEW
```

**2. Create migration:**
```bash
payment-sim db create-migration add_settlement_type
```

**3. Edit `migrations/002_add_settlement_type.sql`:**
```sql
ALTER TABLE transactions ADD COLUMN settlement_type VARCHAR;
```

**4. Apply migration:**
```bash
payment-sim db migrate
```

**5. Validate:**
```bash
payment-sim db validate
```

## Troubleshooting

**Error: "Column X missing from table Y"**
- You updated the Pydantic model but didn't create a migration
- Solution: Create and apply migration as shown above

**Error: "Unexpected columns in table Y"**
- Database has columns not in Pydantic model
- Solution: Either add column to model OR create migration to drop column

**Error: "Migration X failed"**
- SQL in migration file has errors
- Solution: Check migration SQL, fix errors, try again
```

---

## Part VII: Summary

### Key Benefits of This Approach

1. **Single Source of Truth**: Pydantic models define schema, DDL auto-generated
2. **Type Safety**: Python type hints → SQL types automatically
3. **Validation**: Runtime checks prevent schema drift
4. **Migrations**: Versioned SQL files for controlled schema evolution
5. **Developer Experience**: Simple CLI commands, clear error messages
6. **Testability**: Schema validation in tests + CI/CD
7. **Documentation**: Models self-document with Pydantic Field descriptions

### What Developers Do

**Before** (manual DDL):
1. Update Pydantic model
2. Manually write CREATE TABLE SQL
3. Manually write ALTER TABLE SQL
4. Hope database matches code
5. Debug runtime errors

**After** (automated):
1. Update Pydantic model
2. Run `payment-sim db create-migration <desc>`
3. Run `payment-sim db migrate`
4. Schema validation ensures match
5. No runtime errors from schema mismatch

### Success Metrics

| Metric | Target | Rationale |
|--------|--------|-----------|
| Daily transaction batch write | <100ms | 40K transactions, non-blocking |
| Daily metrics batch write | <20ms | 200 agent records, trivial overhead |
| Analytical query (1M txs) | <1s | Interactive analysis |
| Database file size (200 runs) | <10 GB | Compressed columnar storage |
| Memory overhead | <50 MB | Minimal impact on simulation |

---

## Part VIII: Complete File Structure

```
/Users/hugi/GitRepos/cashman/
├── simulation_data.db                       # DuckDB database
├── migrations/                              # Versioned migration scripts
│   ├── 001_initial_schema.sql
│   ├── 002_add_settlement_type.sql
│   └── 003_add_lsm_events_table.sql
├── api/
│   ├── pyproject.toml                       # ← Updated (duckdb, polars)
│   ├── payment_simulator/
│   │   ├── persistence/                     # ← NEW MODULE
│   │   │   ├── __init__.py
│   │   │   ├── models.py                    # Pydantic models (source of truth)
│   │   │   ├── schema_generator.py          # DDL auto-generation
│   │   │   ├── migrations.py                # Migration manager
│   │   │   ├── connection.py                # Database manager + validation
│   │   │   └── queries.py                   # Pre-defined analytical queries
│   │   └── cli/commands/
│   │       ├── run.py                       # ← Modified (use DatabaseManager)
│   │       ├── db.py                        # ← NEW (db management commands)
│   │       └── query.py                     # ← NEW (query commands)
│   └── tests/
│       └── unit/
│           └── test_schema_validation.py    # ← NEW
├── backend/
│   └── src/ffi/orchestrator.rs              # ← Modified (new FFI methods)
└── docs/
    ├── persistence_implementation_plan.md   # ← THIS DOCUMENT
    ├── SCHEMA_CHANGES.md                    # ← NEW (developer guide)
    └── persistence_schema.sql               # ← Auto-generated reference
```

---

## Part IX: Phased Implementation Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| 1. Infrastructure | 2-3 days | Database setup, schema management, validation |
| 2. Transaction batch writes | 2-3 days | Daily transaction persistence |
| 3. Agent metrics | 1-2 days | Daily agent snapshots |
| 4. Policy snapshots | 1 day | Policy evolution tracking |
| 5. Query interface | 2-3 days | CLI commands, analytics functions |
| **Total** | **8-12 days** | Full persistence system |

---

## Conclusion

This plan provides a comprehensive, maintainable approach to database persistence with **automatic schema synchronization**. By using Pydantic models as the single source of truth and auto-generating DDL, we eliminate manual schema management and prevent schema drift.

**Key Innovation**: The schema management system ensures that as the project evolves and new fields/tables are added, the database schema automatically stays in sync with the code through:
1. Pydantic models defining structure
2. Auto-generated DDL
3. Versioned migrations
4. Runtime validation
5. Developer-friendly CLI tools

This approach scales from initial development through hundreds of simulation runs and multiple developers making schema changes.

---

**Document Status**: Ready for Implementation
**Last Updated**: 2025-10-29
**Author**: Payment Simulator Team
**Technology Stack**: DuckDB + Polars + Pydantic (schema-as-code)
**Next Action**: Begin Phase 1 implementation
