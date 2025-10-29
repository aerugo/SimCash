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
- **Phase 8 Addition**: Collateral events tracking (estimated 50-100 events/agent/day = 2-4M events)

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

    # Collateral management (Phase 8)
    opening_posted_collateral: int = 0
    closing_posted_collateral: int = 0
    peak_posted_collateral: int = 0
    collateral_capacity: int = 0  # 10x credit_limit
    num_collateral_posts: int = 0
    num_collateral_withdrawals: int = 0

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
    collateral_cost: int = 0  # Phase 8: Opportunity cost of posted collateral
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
    """Policy snapshot tracking.

    Phase 8+: Policies use three-tree structure (payment, strategic_collateral, end_of_tick_collateral).
    """

    id: Optional[int] = None  # Auto-increment
    simulation_id: str
    agent_id: str
    day: int

    policy_version: str
    policy_type: str  # 'fifo', 'deadline', 'liquidity_aware', 'tree'
    policy_file_path: Optional[str] = None
    policy_hash: Optional[str] = None

    # Phase 8: Three-tree structure metadata
    has_payment_tree: bool = True
    has_strategic_collateral_tree: bool = False
    has_end_of_tick_collateral_tree: bool = False

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
# Collateral Events (Phase 8)
# ============================================================================

class CollateralActionType(str, Enum):
    POST = "post"
    WITHDRAW = "withdraw"
    HOLD = "hold"


class CollateralEventRecord(BaseModel):
    """Collateral management events.

    Tracks when agents post or withdraw collateral during simulation.
    Added in Phase 8 (two-layer collateral management).
    """

    id: Optional[int] = None  # Auto-increment
    simulation_id: str
    agent_id: str
    tick: int
    day: int

    action: CollateralActionType
    amount: int  # Amount posted/withdrawn (cents), 0 for hold
    reason: str  # Decision reason from tree policy

    # Layer context
    layer: str  # 'strategic' or 'end_of_tick'

    # Agent state at time of action
    balance_before: int
    posted_collateral_before: int
    posted_collateral_after: int
    available_capacity_after: int

    class Config:
        table_name = "collateral_events"
        primary_key = ["id"]
        indexes = [
            ("idx_collateral_sim_agent", ["simulation_id", "agent_id"]),
            ("idx_collateral_sim_day", ["simulation_id", "day"]),
            ("idx_collateral_action", ["action"]),
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
        CollateralEventRecord,
        ConfigArchiveRecord,
    )

    models = [
        SimulationRecord,
        TransactionRecord,
        DailyAgentMetricsRecord,
        PolicySnapshotRecord,
        CollateralEventRecord,
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
    CollateralEventRecord,
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
            CollateralEventRecord,
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

### 4.4 Test-Driven Development Approach

This section outlines how to apply TDD (Test-Driven Development) principles throughout the implementation of the persistence feature. Following TDD ensures correctness, maintainability, and confidence in the schema synchronization system.

#### TDD Principles for Persistence

**Red-Green-Refactor Cycle**:
1. **Red**: Write a failing test that defines desired behavior
2. **Green**: Write minimal code to make the test pass
3. **Refactor**: Improve code quality while keeping tests green

**Key TDD Rules for This Feature**:
- Write tests BEFORE implementation code
- Each test should verify ONE specific behavior
- Tests should fail for the right reason (not syntax errors)
- No production code without a failing test first
- Keep tests fast (<10ms for unit tests)
- Integration tests can be slower but should complete in <1s

---

#### Phase 1: Infrastructure (TDD Workflow)

**Goal**: Build schema management foundation with tests driving design.

**Test Order** (each test written before implementation):

**1. Test Pydantic Model Metadata**
```python
# api/tests/unit/test_persistence_models.py

def test_transaction_record_has_table_metadata():
    """Verify Pydantic model includes table configuration."""
    # RED: Write test first, model doesn't exist yet
    from payment_simulator.persistence.models import TransactionRecord

    assert hasattr(TransactionRecord, 'Config')
    assert hasattr(TransactionRecord.Config, 'table_name')
    assert TransactionRecord.Config.table_name == 'transactions'
    assert hasattr(TransactionRecord.Config, 'primary_key')
    assert TransactionRecord.Config.primary_key == ['simulation_id', 'tx_id']

# GREEN: Now implement TransactionRecord with Config class
# REFACTOR: Extract TableConfig base class if needed
```

**2. Test DDL Generation**
```python
# api/tests/unit/test_schema_generator.py

def test_generate_ddl_from_simple_model():
    """DDL generator converts Pydantic model to SQL."""
    # RED: Write test, generator doesn't exist
    from pydantic import BaseModel, Field
    from payment_simulator.persistence.schema_generator import generate_create_table_ddl

    class SimpleModel(BaseModel):
        id: int
        name: str
        amount: int

        class Config:
            table_name = 'simple_table'
            primary_key = ['id']

    ddl = generate_create_table_ddl(SimpleModel)

    assert 'CREATE TABLE IF NOT EXISTS simple_table' in ddl
    assert 'id BIGINT' in ddl
    assert 'name VARCHAR' in ddl
    assert 'amount BIGINT' in ddl
    assert 'PRIMARY KEY (id)' in ddl

# GREEN: Implement generate_create_table_ddl()
# REFACTOR: Extract type mapping logic
```

**3. Test Optional Field Handling**
```python
def test_ddl_handles_optional_fields():
    """Optional fields should allow NULL."""
    # RED: Test fails because NULL handling not implemented
    from typing import Optional

    class ModelWithOptional(BaseModel):
        required_field: str
        optional_field: Optional[str] = None

        class Config:
            table_name = 'test_optional'
            primary_key = ['required_field']

    ddl = generate_create_table_ddl(ModelWithOptional)

    # Required field has NOT NULL
    assert 'required_field VARCHAR NOT NULL' in ddl
    # Optional field allows NULL
    assert 'optional_field VARCHAR' in ddl
    assert 'optional_field VARCHAR NOT NULL' not in ddl

# GREEN: Add Optional detection logic to generator
# REFACTOR: Clean up type introspection code
```

**4. Test Enum Field Handling**
```python
def test_ddl_converts_enums_to_varchar():
    """Enum fields should map to VARCHAR."""
    # RED: Enum handling not implemented
    from enum import Enum

    class Status(str, Enum):
        PENDING = 'pending'
        COMPLETED = 'completed'

    class ModelWithEnum(BaseModel):
        status: Status

        class Config:
            table_name = 'test_enum'
            primary_key = ['status']

    ddl = generate_create_table_ddl(ModelWithEnum)
    assert 'status VARCHAR' in ddl

# GREEN: Add Enum detection to type mapper
```

**5. Test Index Generation**
```python
def test_generate_indexes_from_model():
    """Indexes defined in model metadata should generate DDL."""
    # RED: Index generation not implemented
    from payment_simulator.persistence.schema_generator import generate_create_indexes_ddl

    class ModelWithIndexes(BaseModel):
        id: int
        user_id: int
        created_at: str

        class Config:
            table_name = 'test_indexes'
            primary_key = ['id']
            indexes = [
                ('idx_user', ['user_id']),
                ('idx_user_time', ['user_id', 'created_at']),
            ]

    index_statements = generate_create_indexes_ddl(ModelWithIndexes)

    assert len(index_statements) == 2
    assert any('idx_user ON test_indexes (user_id)' in stmt for stmt in index_statements)
    assert any('idx_user_time ON test_indexes (user_id, created_at)' in stmt for stmt in index_statements)

# GREEN: Implement generate_create_indexes_ddl()
```

**6. Test Schema Validation**
```python
def test_validate_schema_detects_missing_column():
    """Validator should detect when database missing a column."""
    # RED: Validation not implemented
    import duckdb
    from payment_simulator.persistence.schema_generator import validate_table_schema

    conn = duckdb.connect(':memory:')
    conn.execute("""
        CREATE TABLE transactions (
            simulation_id VARCHAR NOT NULL,
            tx_id VARCHAR NOT NULL
            -- Missing 'amount' column
        )
    """)

    class TransactionModel(BaseModel):
        simulation_id: str
        tx_id: str
        amount: int

        class Config:
            table_name = 'transactions'
            primary_key = ['simulation_id', 'tx_id']

    is_valid, errors = validate_table_schema(conn, TransactionModel)

    assert not is_valid
    assert len(errors) > 0
    assert any('amount' in err.lower() for err in errors)

# GREEN: Implement validate_table_schema()
# REFACTOR: Make error messages more descriptive
```

**7. Test Migration Manager**
```python
def test_migration_manager_tracks_applied_versions():
    """Migration manager should record applied migrations."""
    # RED: MigrationManager doesn't exist
    import duckdb
    from pathlib import Path
    from payment_simulator.persistence.migrations import MigrationManager

    conn = duckdb.connect(':memory:')
    migrations_dir = Path('/tmp/test_migrations')
    migrations_dir.mkdir(exist_ok=True)

    manager = MigrationManager(conn, migrations_dir)

    # Initially no migrations applied
    applied = manager.get_applied_versions()
    assert len(applied) == 0

    # Apply a migration
    manager.apply_migration(1, "initial schema", "CREATE TABLE test (id INT);")

    # Now version 1 is tracked
    applied = manager.get_applied_versions()
    assert 1 in applied

# GREEN: Implement MigrationManager class
```

**TDD Summary for Phase 1**:
- Write 15-20 unit tests covering all schema generator edge cases
- Each test drives a small piece of functionality
- Run tests continuously: `pytest -x` (stop on first failure)
- Achieve >95% coverage for schema management code

---

#### Phase 2: Transaction Batch Writes (TDD Workflow)

**Goal**: Test batch write performance and correctness.

**Test Order**:

**1. Test FFI Method Returns Transaction Data**
```python
# api/tests/unit/test_ffi_transactions.py

def test_get_transactions_for_day_returns_dicts():
    """FFI method should return transactions as list of dicts."""
    # RED: Method doesn't exist in orchestrator
    from payment_simulator.backends import Orchestrator

    config = create_minimal_config()
    orch = Orchestrator.new(config)

    # Simulate a day
    for _ in range(10):
        orch.tick()

    # Get transactions for day 0
    daily_txs = orch.get_transactions_for_day(0)

    assert isinstance(daily_txs, list)
    assert all(isinstance(tx, dict) for tx in daily_txs)

    # Check required fields present
    if daily_txs:
        tx = daily_txs[0]
        assert 'simulation_id' in tx
        assert 'tx_id' in tx
        assert 'amount' in tx
        assert 'status' in tx

# GREEN: Implement get_transactions_for_day() in Rust FFI
```

**2. Test Transaction Data Validates Against Pydantic Model**
```python
def test_ffi_transaction_validates_with_pydantic():
    """FFI output should validate with TransactionRecord model."""
    # RED: FFI might return wrong types or missing fields
    from payment_simulator.backends import Orchestrator
    from payment_simulator.persistence.models import TransactionRecord

    orch = Orchestrator.new(create_minimal_config())
    for _ in range(10):
        orch.tick()

    daily_txs = orch.get_transactions_for_day(0)

    # Each transaction should validate
    for tx_dict in daily_txs:
        tx_record = TransactionRecord(**tx_dict)  # Should not raise ValidationError
        assert tx_record.amount >= 0
        assert tx_record.simulation_id

# GREEN: Fix FFI to return correct types
# REFACTOR: Add type conversion helper in FFI layer
```

**3. Test Polars DataFrame Creation**
```python
def test_create_polars_dataframe_from_transactions():
    """Should convert transaction dicts to Polars DataFrame."""
    # RED: Conversion logic doesn't exist
    import polars as pl
    from payment_simulator.persistence.writers import create_transaction_dataframe

    transactions = [
        {
            'simulation_id': 'test-001',
            'tx_id': 'tx-001',
            'sender_id': 'A',
            'receiver_id': 'B',
            'amount': 100000,
            'status': 'settled',
            # ... all required fields
        },
        # ... more transactions
    ]

    df = create_transaction_dataframe(transactions)

    assert isinstance(df, pl.DataFrame)
    assert len(df) == len(transactions)
    assert 'simulation_id' in df.columns
    assert df['amount'].dtype == pl.Int64

# GREEN: Implement create_transaction_dataframe()
```

**4. Test DuckDB Insert Via Polars**
```python
def test_insert_transactions_via_polars_arrow():
    """DuckDB should accept Polars DataFrame via Arrow zero-copy."""
    # RED: Insert logic not implemented
    import duckdb
    import polars as pl
    from payment_simulator.persistence.writers import write_transactions

    conn = duckdb.connect(':memory:')
    # Create schema
    init_database(conn)

    transactions = [create_sample_transaction(i) for i in range(100)]

    write_transactions(conn, transactions)

    # Verify data inserted
    count = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    assert count == 100

    # Verify data correctness
    first_tx = conn.execute("SELECT * FROM transactions LIMIT 1").fetchone()
    assert first_tx is not None

# GREEN: Implement write_transactions()
```

**5. Test Batch Write Performance**
```python
def test_batch_write_40k_transactions_under_100ms():
    """Performance requirement: 40K inserts in <100ms."""
    # RED: Might be too slow initially
    import duckdb
    import time
    from payment_simulator.persistence.writers import write_transactions

    conn = duckdb.connect(':memory:')
    init_database(conn)

    # Generate 40K transactions (typical day for 200 agents)
    transactions = [create_sample_transaction(i) for i in range(40_000)]

    start = time.perf_counter()
    write_transactions(conn, transactions)
    duration = time.perf_counter() - start

    assert duration < 0.1, f"Batch write took {duration:.3f}s, expected <0.1s"

# GREEN: If slow, optimize (use Arrow, disable indexes during insert, etc.)
# REFACTOR: Add bulk insert optimization
```

**6. Test Determinism Preserved**
```python
def test_persistence_preserves_determinism():
    """Same seed should produce identical database contents."""
    # RED: Might break determinism with DB operations
    import duckdb
    from payment_simulator.backends import Orchestrator

    config = create_test_config_with_seed(12345)

    # Run 1
    orch1 = Orchestrator.new(config)
    for _ in range(100):
        orch1.tick()
    txs1 = orch1.get_transactions_for_day(0)

    # Run 2 (same seed)
    orch2 = Orchestrator.new(config)
    for _ in range(100):
        orch2.tick()
    txs2 = orch2.get_transactions_for_day(0)

    # Transactions should be identical
    assert len(txs1) == len(txs2)
    for tx1, tx2 in zip(txs1, txs2):
        assert tx1['tx_id'] == tx2['tx_id']
        assert tx1['amount'] == tx2['amount']
        assert tx1['status'] == tx2['status']

# GREEN: Ensure no non-deterministic operations in persistence
```

**TDD Summary for Phase 2**:
- 10-15 tests covering FFI, DataFrame conversion, bulk inserts
- Performance tests define success criteria
- Determinism tests prevent regressions

---

#### Phase 3: Agent Metrics (TDD Workflow)

**Goal**: Test daily agent metrics collection and persistence.

**Test Order**:

**1. Test Daily Metrics Collection**
```python
# api/tests/unit/test_agent_metrics.py

def test_collect_daily_metrics_for_agent():
    """Should collect opening/closing balance, costs, counts."""
    # RED: Metrics collection doesn't exist
    from payment_simulator.backends import Orchestrator

    orch = Orchestrator.new(create_test_config())

    # Simulate a day
    for _ in range(100):
        orch.tick()

    metrics = orch.get_daily_agent_metrics(day=0)

    assert isinstance(metrics, list)
    assert len(metrics) > 0  # At least one agent

    agent_metric = metrics[0]
    assert 'agent_id' in agent_metric
    assert 'opening_balance' in agent_metric
    assert 'closing_balance' in agent_metric
    assert 'total_cost' in agent_metric

# GREEN: Implement get_daily_agent_metrics() in Rust
```

**2. Test Metrics Validate With Pydantic**
```python
def test_agent_metrics_validate_with_model():
    """FFI metrics should validate with DailyAgentMetricsRecord."""
    # RED: FFI might return wrong types
    from payment_simulator.persistence.models import DailyAgentMetricsRecord

    orch = Orchestrator.new(create_test_config())
    for _ in range(100):
        orch.tick()

    metrics = orch.get_daily_agent_metrics(0)

    for metric_dict in metrics:
        # Should not raise ValidationError
        record = DailyAgentMetricsRecord(**metric_dict)
        assert record.day == 0
        assert record.closing_balance >= record.min_balance

# GREEN: Fix FFI type conversions
```

**3. Test Metrics Persistence**
```python
def test_persist_daily_agent_metrics():
    """Should write agent metrics to database."""
    # RED: Writer function doesn't exist
    import duckdb
    from payment_simulator.persistence.writers import write_agent_metrics

    conn = duckdb.connect(':memory:')
    init_database(conn)

    metrics = [
        {
            'simulation_id': 'test-001',
            'agent_id': 'BANK_A',
            'day': 0,
            'opening_balance': 1000000,
            'closing_balance': 950000,
            # ... all fields
        },
        # ... more agents
    ]

    write_agent_metrics(conn, metrics)

    count = conn.execute("SELECT COUNT(*) FROM daily_agent_metrics").fetchone()[0]
    assert count == len(metrics)

# GREEN: Implement write_agent_metrics()
```

**4. Test Metrics Consistency**
```python
def test_metrics_sum_to_transaction_totals():
    """Agent metrics should be consistent with transaction data."""
    # RED: Might have calculation bugs
    import duckdb

    conn = duckdb.connect(':memory:')
    init_database(conn)

    # Run simulation and persist both transactions and metrics
    run_test_simulation_with_persistence(conn, days=2, agents=3)

    # Sum transaction counts for BANK_A on day 0
    tx_sent = conn.execute("""
        SELECT COUNT(*) FROM transactions
        WHERE simulation_id = 'test-001'
          AND sender_id = 'BANK_A'
          AND arrival_day = 0
    """).fetchone()[0]

    # Should match agent metrics
    metrics_sent = conn.execute("""
        SELECT num_sent FROM daily_agent_metrics
        WHERE simulation_id = 'test-001'
          AND agent_id = 'BANK_A'
          AND day = 0
    """).fetchone()[0]

    assert tx_sent == metrics_sent

# GREEN: Fix calculation bugs in Rust metrics collector
```

**TDD Summary for Phase 3**:
- 8-10 tests for metrics collection, validation, persistence
- Cross-validation tests ensure consistency

---

#### Phase 4: Policy Snapshots (TDD Workflow)

**Goal**: Test policy version tracking.

**Test Order**:

**1. Test Policy Snapshot Creation**
```python
# api/tests/unit/test_policy_snapshots.py

def test_create_policy_snapshot_record():
    """Should create policy snapshot with hash and file path."""
    # RED: Snapshot creation logic doesn't exist
    from payment_simulator.persistence.policy_tracking import create_policy_snapshot

    snapshot = create_policy_snapshot(
        simulation_id='test-001',
        agent_id='BANK_A',
        day=0,
        policy_json='{"type": "fifo"}',
        created_by='init'
    )

    assert snapshot['simulation_id'] == 'test-001'
    assert snapshot['agent_id'] == 'BANK_A'
    assert snapshot['policy_hash'] is not None
    assert len(snapshot['policy_hash']) == 64  # SHA256

# GREEN: Implement create_policy_snapshot()
```

**2. Test Policy Deduplication By Hash**
```python
def test_identical_policies_have_same_hash():
    """Identical policies should deduplicate via hash."""
    # RED: Hash calculation might vary
    from payment_simulator.persistence.policy_tracking import compute_policy_hash

    policy_json = '{"type": "fifo", "threshold": 1000}'

    hash1 = compute_policy_hash(policy_json)
    hash2 = compute_policy_hash(policy_json)

    assert hash1 == hash2

# GREEN: Implement deterministic hash function
```

**3. Test Policy File Management**
```python
def test_save_policy_to_file():
    """Should save policy JSON to versioned file."""
    # RED: File management doesn't exist
    from payment_simulator.persistence.policy_tracking import save_policy_file
    from pathlib import Path

    policy_json = '{"type": "liquidity_aware"}'

    file_path = save_policy_file(
        agent_id='BANK_A',
        version='v1',
        policy_json=policy_json,
        base_dir=Path('/tmp/test_policies')
    )

    assert file_path.exists()
    assert file_path.name == 'BANK_A_policy_v1.json'
    assert file_path.read_text() == policy_json

# GREEN: Implement save_policy_file()
```

**TDD Summary for Phase 4**:
- 5-7 tests for policy tracking, hashing, file management
- Integration with Phase 9 DSL infrastructure

---

#### Phase 5: Query Interface (TDD Workflow)

**Goal**: Test analytical query functions.

**Test Order**:

**1. Test Agent Performance Query**
```python
# api/tests/unit/test_queries.py

def test_query_agent_performance():
    """Should return agent metrics over time."""
    # RED: Query function doesn't exist
    import duckdb
    from payment_simulator.persistence.queries import get_agent_performance

    conn = duckdb.connect(':memory:')
    init_database(conn)
    seed_test_data(conn)

    df = get_agent_performance(conn, 'test-001', 'BANK_A')

    assert len(df) > 0
    assert 'day' in df.columns
    assert 'closing_balance' in df.columns
    assert 'total_cost' in df.columns

# GREEN: Implement get_agent_performance()
```

**2. Test Settlement Rate Query**
```python
def test_query_settlement_rate_by_day():
    """Should calculate settlement rate per day."""
    # RED: Aggregation query doesn't exist
    from payment_simulator.persistence.queries import get_settlement_rate_by_day

    conn = duckdb.connect(':memory:')
    init_database(conn)
    seed_test_data(conn)

    df = get_settlement_rate_by_day(conn, 'test-001')

    assert len(df) > 0
    assert 'day' in df.columns
    assert 'settlement_rate' in df.columns
    assert all(0 <= rate <= 1 for rate in df['settlement_rate'])

# GREEN: Implement get_settlement_rate_by_day()
```

**3. Test Query Performance**
```python
def test_aggregate_query_on_1m_transactions_fast():
    """Aggregate queries should complete in <1 second."""
    # RED: Might be slow without indexes
    import duckdb
    import time
    from payment_simulator.persistence.queries import get_daily_transaction_summary

    conn = duckdb.connect(':memory:')
    init_database(conn)
    seed_large_dataset(conn, num_transactions=1_000_000)

    start = time.perf_counter()
    df = get_daily_transaction_summary(conn, 'test-001')
    duration = time.perf_counter() - start

    assert duration < 1.0, f"Query took {duration:.2f}s, expected <1s"

# GREEN: Add indexes to optimize queries
```

**TDD Summary for Phase 5**:
- 10-15 tests for each query function
- Performance benchmarks define acceptable latency
- Edge case tests (empty data, single row, etc.)

---

#### Integration Testing Strategy

**End-to-End TDD Workflow**:

```python
# api/tests/integration/test_full_persistence.py

def test_complete_simulation_persistence_workflow():
    """Full workflow: run simulation, persist, query, verify."""
    # RED: Write this test BEFORE integrating all pieces
    import duckdb
    from pathlib import Path
    from payment_simulator.backends import Orchestrator
    from payment_simulator.persistence.connection import DatabaseManager
    from payment_simulator.persistence.writers import (
        write_transactions,
        write_agent_metrics,
    )
    from payment_simulator.persistence.queries import get_agent_performance

    # Setup
    db_path = Path('/tmp/test_full_persistence.db')
    if db_path.exists():
        db_path.unlink()

    db_manager = DatabaseManager(db_path)
    db_manager.setup()
    conn = db_manager.conn

    # Run simulation
    config = create_test_config(agents=5, days=3, ticks_per_day=100)
    orch = Orchestrator.new(config)

    for day in range(3):
        # Simulate day
        for _ in range(100):
            orch.tick()

        # Persist data
        daily_txs = orch.get_transactions_for_day(day)
        write_transactions(conn, daily_txs)

        daily_metrics = orch.get_daily_agent_metrics(day)
        write_agent_metrics(conn, daily_metrics)

    # Query and verify
    agent_perf = get_agent_performance(conn, config['simulation_id'], 'BANK_A')

    assert len(agent_perf) == 3  # 3 days
    assert 'closing_balance' in agent_perf.columns

    # Verify determinism
    sim_record = conn.execute("""
        SELECT rng_seed, total_ticks_executed
        FROM simulations
        WHERE simulation_id = ?
    """, [config['simulation_id']]).fetchone()

    assert sim_record[0] == config['seed']
    assert sim_record[1] == 300  # 3 days × 100 ticks

# GREEN: Integrate all phases to make this pass
# REFACTOR: Extract reusable test fixtures
```

---

#### TDD Best Practices for This Feature

**1. Test Naming Convention**
```python
# Good test names:
def test_ddl_generation_handles_optional_fields()
def test_batch_write_40k_transactions_under_100ms()
def test_schema_validation_detects_missing_column()

# Bad test names:
def test_ddl()  # Too vague
def test_performance()  # What aspect?
def test_1()  # Meaningless
```

**2. Test Organization**
```
api/tests/
├── unit/
│   ├── test_persistence_models.py       # Pydantic models
│   ├── test_schema_generator.py         # DDL generation
│   ├── test_migrations.py               # Migration system
│   ├── test_ffi_transactions.py         # FFI data extraction
│   ├── test_agent_metrics.py            # Metrics collection
│   ├── test_policy_snapshots.py         # Policy tracking
│   └── test_queries.py                  # Query interface
├── integration/
│   ├── test_full_persistence.py         # End-to-end workflow
│   ├── test_determinism.py              # Determinism verification
│   └── test_large_dataset.py            # Stress testing
└── performance/
    ├── test_batch_write_benchmarks.py   # Performance baselines
    └── test_query_benchmarks.py         # Query performance
```

**3. Running Tests During Development**
```bash
# Run single test file (fast feedback)
pytest api/tests/unit/test_schema_generator.py -v

# Run with coverage
pytest api/tests/unit/ --cov=payment_simulator.persistence --cov-report=term-missing

# Run in watch mode (auto-rerun on file change)
pytest-watch api/tests/unit/

# Run only failed tests
pytest --lf

# Run integration tests separately (slower)
pytest api/tests/integration/ -v -s
```

**4. Test Data Fixtures**
```python
# api/tests/conftest.py

import pytest
import duckdb
from pathlib import Path

@pytest.fixture
def in_memory_db():
    """Provide clean in-memory database for each test."""
    conn = duckdb.connect(':memory:')
    from payment_simulator.persistence.connection import DatabaseManager
    manager = DatabaseManager(conn)
    manager.initialize_schema()
    yield conn
    conn.close()

@pytest.fixture
def sample_transactions():
    """Generate sample transaction data."""
    return [
        {
            'simulation_id': 'test-001',
            'tx_id': f'tx-{i:04d}',
            'sender_id': 'BANK_A',
            'receiver_id': 'BANK_B',
            'amount': 100000,
            'status': 'settled',
            # ... all fields
        }
        for i in range(100)
    ]

@pytest.fixture
def test_orchestrator():
    """Provide configured orchestrator for testing."""
    from payment_simulator.backends import Orchestrator
    config = create_minimal_config()
    return Orchestrator.new(config)
```

**5. Mocking Strategy**
```python
# Mock expensive operations in unit tests

def test_write_transactions_calls_polars_correctly(mocker):
    """Unit test: verify Polars DataFrame creation without DB."""
    # RED: Write test that mocks DuckDB connection
    mock_conn = mocker.Mock()

    from payment_simulator.persistence.writers import write_transactions

    transactions = [{'tx_id': 'test', 'amount': 100}]
    write_transactions(mock_conn, transactions)

    # Verify execute was called
    assert mock_conn.execute.called

    # Verify correct SQL pattern
    call_args = mock_conn.execute.call_args[0][0]
    assert 'INSERT INTO transactions' in call_args

# GREEN: Implement write_transactions()
```

**6. Property-Based Testing**
```python
# Use Hypothesis for schema validation edge cases

from hypothesis import given, strategies as st

@given(
    field_name=st.text(min_size=1, max_size=50),
    py_type=st.sampled_from([str, int, float, bool]),
)
def test_type_mapping_never_fails(field_name, py_type):
    """DDL generator should handle any valid Python type."""
    from payment_simulator.persistence.schema_generator import python_type_to_sql_type

    sql_type = python_type_to_sql_type(py_type)

    assert isinstance(sql_type, str)
    assert len(sql_type) > 0
    assert sql_type in ['VARCHAR', 'BIGINT', 'DOUBLE', 'BOOLEAN']
```

---

#### Success Metrics for TDD Approach

| Metric | Target | Why |
|--------|--------|-----|
| Test coverage | >90% | Confidence in schema management |
| Unit test speed | <10ms avg | Fast feedback loop |
| Integration test speed | <1s each | Reasonable CI time |
| Tests written first | 100% | True TDD discipline |
| Test-to-code ratio | 2:1 | Comprehensive coverage |
| Failing tests before code | Yes | Red-green-refactor |

---

#### Daily TDD Workflow Example

**Day 1: Phase 1 Infrastructure**
```bash
# Morning: Write tests for DDL generation
09:00 - Write test_generate_ddl_from_simple_model() [RED]
09:15 - Implement generate_create_table_ddl() [GREEN]
09:30 - Refactor type mapping logic [REFACTOR]
09:45 - Write test_ddl_handles_optional_fields() [RED]
10:00 - Implement Optional detection [GREEN]
10:15 - Write test_ddl_converts_enums_to_varchar() [RED]
10:30 - Implement Enum handling [GREEN]

# Afternoon: Write tests for validation
14:00 - Write test_validate_schema_detects_missing_column() [RED]
14:20 - Implement validate_table_schema() [GREEN]
14:40 - Write test_validate_schema_detects_extra_columns() [RED]
14:55 - Enhance validation logic [GREEN]
15:10 - Refactor validation to use descriptive errors [REFACTOR]

# End of day: Run full test suite
17:00 - pytest api/tests/unit/ --cov
17:05 - Fix any failing tests
17:10 - Commit: "feat: DDL generation and schema validation"
```

**Key Point**: Never commit failing tests. Always end day with green tests.

---

#### Troubleshooting TDD Issues

**Problem**: Test is hard to write
- **Solution**: Design issue. Rethink API before implementing.

**Problem**: Test takes too long to run
- **Solution**: Use mocks for unit tests, move slow tests to integration suite.

**Problem**: Not sure what to test next
- **Solution**: Follow implementation plan phases. Test public APIs, then internals.

**Problem**: Tests are brittle (break on refactoring)
- **Solution**: Test behavior, not implementation details. Use fixtures.

**Problem**: Don't know if test is correct
- **Solution**: Make it fail first. Verify it fails for the right reason.

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

## Part X: Phase 8 Update - Collateral Management

### Overview

Phase 8 introduced two-layer collateral management to the simulation, allowing agents to dynamically post and withdraw collateral to optimize liquidity access. This required significant schema extensions to track:

1. **Agent collateral state** (opening/closing/peak amounts)
2. **Collateral operations** (post/withdraw/hold actions)
3. **Collateral costs** (opportunity cost of posted collateral)
4. **Policy structure changes** (three-tree decision framework)

### Schema Changes

#### 1. Updated: DailyAgentMetricsRecord

Added 6 new fields to track collateral metrics:

```python
# Collateral management (Phase 8)
opening_posted_collateral: int = 0      # Collateral at day start
closing_posted_collateral: int = 0      # Collateral at day end
peak_posted_collateral: int = 0         # Maximum during day
collateral_capacity: int = 0            # 10x credit_limit heuristic
num_collateral_posts: int = 0           # Count of post operations
num_collateral_withdrawals: int = 0     # Count of withdrawal operations

# Added to Costs section
collateral_cost: int = 0                # Opportunity cost (basis points per tick)
```

**Rationale**: Daily snapshots enable analysis of collateral usage patterns, capacity utilization, and cost impact over time.

#### 2. New Table: CollateralEventRecord

Track every collateral operation for fine-grained analysis:

```python
class CollateralEventRecord(BaseModel):
    """Collateral management events."""

    id: Optional[int] = None  # Auto-increment
    simulation_id: str
    agent_id: str
    tick: int
    day: int

    action: CollateralActionType  # POST, WITHDRAW, HOLD
    amount: int                   # Cents (0 for HOLD)
    reason: str                   # Decision reason from tree
    layer: str                    # 'strategic' or 'end_of_tick'

    # Agent state snapshots
    balance_before: int
    posted_collateral_before: int
    posted_collateral_after: int
    available_capacity_after: int
```

**Key Indexes**:
- `idx_collateral_sim_agent` - Query all events for an agent
- `idx_collateral_sim_day` - Daily aggregations
- `idx_collateral_action` - Filter by POST/WITHDRAW/HOLD

**Use Cases**:
- Analyze timing of collateral operations (strategic vs. end-of-tick)
- Correlate collateral posts with liquidity gaps
- Identify capacity constraints
- Evaluate policy effectiveness

#### 3. Updated: PolicySnapshotRecord

Extended to track three-tree policy structure:

```python
# Phase 8: Three-tree structure metadata
has_payment_tree: bool = True                      # Queue 1 release decisions
has_strategic_collateral_tree: bool = False        # Forward-looking collateral
has_end_of_tick_collateral_tree: bool = False      # Reactive collateral
```

**Rationale**: Policies now consist of three independent decision trees:
1. **Payment Tree**: Queue 1 release decisions (existing functionality)
2. **Strategic Collateral Tree**: Runs at STEP 1.5, before policy evaluation, sees full Queue 1
3. **End-of-Tick Collateral Tree**: Runs at STEP 5.5, after LSM, responds to final state

This allows tracking which agents use collateral automation and which trees are active.

### Implementation Notes

#### Two-Layer Architecture

The collateral system operates at two distinct points in the tick loop:

**Layer 1 - Strategic (STEP 1.5)**:
- Runs BEFORE policy evaluation
- Sees full Queue 1 (transactions not yet released)
- Forward-looking decisions based on `queue1_liquidity_gap`
- Posts collateral to enable upcoming settlements

**Layer 2 - End-of-Tick (STEP 5.5)**:
- Runs AFTER LSM completion
- Sees final Queue 2 state
- Reactive cleanup operations
- Withdraws excess collateral, posts for remaining gridlock

Both layers are tracked separately in the `layer` field of `CollateralEventRecord`.

#### Collateral Capacity Model

Agents have a maximum collateral capacity calculated as:
```
collateral_capacity = credit_limit × 10
```

This 10x multiplier is a heuristic based on typical collateralization ratios. The `collateral_capacity` field in `DailyAgentMetricsRecord` stores this value for reference.

#### Cost Accrual

Collateral costs accrue per tick at a rate defined by `collateral_cost_per_tick_bps` in `CostRates`. The `collateral_cost` field tracks the cumulative opportunity cost for the day, separate from other cost components (liquidity, delay, deadlines).

### Query Examples

**1. Agent Collateral Utilization Over Time**
```sql
SELECT
    day,
    closing_posted_collateral,
    collateral_capacity,
    (closing_posted_collateral * 100.0 / collateral_capacity) as utilization_pct,
    collateral_cost
FROM daily_agent_metrics
WHERE simulation_id = ? AND agent_id = ?
ORDER BY day;
```

**2. Collateral Operations Timeline**
```sql
SELECT
    tick,
    action,
    amount,
    layer,
    reason,
    posted_collateral_after
FROM collateral_events
WHERE simulation_id = ? AND agent_id = ?
ORDER BY tick;
```

**3. Strategic vs. End-of-Tick Comparison**
```sql
SELECT
    layer,
    action,
    COUNT(*) as operation_count,
    SUM(amount) as total_amount
FROM collateral_events
WHERE simulation_id = ? AND agent_id = ?
GROUP BY layer, action;
```

**4. Collateral Capacity Constraints**
```sql
SELECT
    agent_id,
    day,
    peak_posted_collateral,
    collateral_capacity,
    CASE
        WHEN peak_posted_collateral >= collateral_capacity * 0.95
        THEN 'constrained'
        ELSE 'unconstrained'
    END as capacity_status
FROM daily_agent_metrics
WHERE simulation_id = ?
ORDER BY agent_id, day;
```

### Migration Path

For existing databases, apply migration to add:

```sql
-- Migration: Add Phase 8 collateral fields

-- Update daily_agent_metrics
ALTER TABLE daily_agent_metrics ADD COLUMN opening_posted_collateral BIGINT DEFAULT 0;
ALTER TABLE daily_agent_metrics ADD COLUMN closing_posted_collateral BIGINT DEFAULT 0;
ALTER TABLE daily_agent_metrics ADD COLUMN peak_posted_collateral BIGINT DEFAULT 0;
ALTER TABLE daily_agent_metrics ADD COLUMN collateral_capacity BIGINT DEFAULT 0;
ALTER TABLE daily_agent_metrics ADD COLUMN num_collateral_posts BIGINT DEFAULT 0;
ALTER TABLE daily_agent_metrics ADD COLUMN num_collateral_withdrawals BIGINT DEFAULT 0;
ALTER TABLE daily_agent_metrics ADD COLUMN collateral_cost BIGINT DEFAULT 0;

-- Update policy_snapshots
ALTER TABLE policy_snapshots ADD COLUMN has_payment_tree BOOLEAN DEFAULT TRUE;
ALTER TABLE policy_snapshots ADD COLUMN has_strategic_collateral_tree BOOLEAN DEFAULT FALSE;
ALTER TABLE policy_snapshots ADD COLUMN has_end_of_tick_collateral_tree BOOLEAN DEFAULT FALSE;

-- Create collateral_events table
CREATE TABLE IF NOT EXISTS collateral_events (
    id INTEGER AUTOINCREMENT,
    simulation_id VARCHAR NOT NULL,
    agent_id VARCHAR NOT NULL,
    tick BIGINT NOT NULL,
    day BIGINT NOT NULL,
    action VARCHAR NOT NULL,
    amount BIGINT NOT NULL,
    reason VARCHAR NOT NULL,
    layer VARCHAR NOT NULL,
    balance_before BIGINT NOT NULL,
    posted_collateral_before BIGINT NOT NULL,
    posted_collateral_after BIGINT NOT NULL,
    available_capacity_after BIGINT NOT NULL,
    PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_collateral_sim_agent ON collateral_events (simulation_id, agent_id);
CREATE INDEX IF NOT EXISTS idx_collateral_sim_day ON collateral_events (simulation_id, day);
CREATE INDEX IF NOT EXISTS idx_collateral_action ON collateral_events (action);
```

### Testing Additions

The collateral edge case test suite (`backend/tests/test_collateral_edge_cases.rs`) covers:
- Capacity limit enforcement
- Post/withdraw validation
- Zero-amount rejection
- Liquidity impact verification
- Cost accrual correctness
- Cross-agent isolation

These tests ensure persistence layer receives correct data.

### Performance Impact

Estimated storage requirements (200 runs, 200 agents, 10 days):

| Data Type | Records | Size Estimate |
|-----------|---------|---------------|
| Daily agent metrics (7 new fields) | 400K | ~15 MB additional |
| Collateral events | 2-4M | ~150-300 MB |
| Policy snapshots (3 new fields) | 800K | ~5 MB additional |
| **Total Phase 8 Addition** | - | **~170-320 MB** |

Batch write performance impact: Minimal (<10ms additional per day for collateral events).

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

**Document Status**: Ready for Implementation (TDD methodology included)
**Last Updated**: 2025-10-29 (Phase 8 collateral management updates)
**Author**: Payment Simulator Team
**Technology Stack**: DuckDB + Polars + Pydantic (schema-as-code)
**Development Approach**: Test-Driven Development (Red-Green-Refactor)
**Phase 8 Status**: Schema extended for two-layer collateral management
**Next Action**: Begin Phase 1 implementation with test-first approach
