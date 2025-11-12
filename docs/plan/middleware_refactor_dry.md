# Python Middleware DRY Violations Analysis

**Date**: 2025-11-12
**Author**: Claude (Analysis Agent)
**Scope**: Payment Simulator Python Middleware (`api/payment_simulator/`)

## Executive Summary

This report identifies significant violations of the DRY (Don't Repeat Yourself) principle across the Python middleware layer of the Payment Simulator project. The analysis covers CLI commands, persistence layer, execution strategies, and display/output functions.

**Key Findings:**
- **11 major categories** of code duplication identified
- **~500+ lines** of duplicated logic that could be refactored
- **High-impact areas**: Credit utilization calculation, event reconstruction, configuration loading, database initialization
- **Risk Level**: Medium - Current duplication has already led to bugs (e.g., Issue #4 credit utilization bug)

## Severity Classification

| Severity | Description | Count |
|----------|-------------|-------|
| 🔴 Critical | Duplication causing or likely to cause bugs | 3 |
| 🟠 High | Significant maintenance burden, >3 duplicates | 4 |
| 🟡 Medium | Moderate duplication, 2-3 instances | 3 |
| 🟢 Low | Minor duplication, architectural choice | 1 |

---

## 1. Credit Utilization Calculation 🔴 CRITICAL

### Severity: CRITICAL
**Reason**: This duplication has **already caused a bug** (Issue #4). The same calculation logic exists in 3 places with inconsistent implementations, leading to incorrect credit utilization percentages.

### Locations
1. **`api/payment_simulator/cli/execution/strategies.py:129-136`**
   ```python
   credit_util = 0
   if credit_limit and credit_limit > 0:
       # If balance is negative, we're using credit equal to the overdraft amount
       # If balance is positive, we're not using any credit
       used = max(0, -balance)
       credit_util = (used / credit_limit) * 100
   ```

2. **`api/payment_simulator/cli/commands/replay.py:1019-1024`**
   ```python
   credit_util = 0
   if credit_limit and credit_limit > 0:
       # If balance is negative, we're using credit equal to the overdraft amount
       # If balance is positive, we're not using any credit
       used = max(0, -balance)
       credit_util = (used / credit_limit) * 100
   ```

3. **`api/payment_simulator/cli/output.py:212-224`** (Different formula!)
   ```python
   if credit_limit and credit_limit > 0:
       used = max(0, credit_limit - balance)  # ❌ WRONG FORMULA
       utilization_pct = (used / credit_limit) * 100
   ```

### Impact
- **Bug History**: Issue #4 revealed credit utilization showing incorrect values
- **Maintenance**: Bug fixes must be applied to 3 separate locations
- **Testing**: Unit tests must cover all 3 implementations

### Recommendation
**Refactor**: Create centralized function in `api/payment_simulator/core/metrics.py`:

```python
def calculate_credit_utilization(balance: int, credit_limit: int) -> float:
    """Calculate credit utilization percentage.

    Credit is only "used" when balance is negative (overdraft).

    Args:
        balance: Current balance in cents (can be negative)
        credit_limit: Maximum overdraft allowed in cents

    Returns:
        Credit utilization percentage (0-100)

    Examples:
        >>> calculate_credit_utilization(100000, 50000)
        0.0  # Positive balance = no credit used
        >>> calculate_credit_utilization(-30000, 50000)
        60.0  # Using 30k of 50k credit
        >>> calculate_credit_utilization(-60000, 50000)
        120.0  # Overdraft exceeds limit
    """
    if not credit_limit or credit_limit <= 0:
        return 0.0

    used = max(0, -balance)
    return (used / credit_limit) * 100
```

**Estimated Effort**: 2 hours (create function + replace all usages + add unit tests)

---

## 2. Event Reconstruction Functions 🟠 HIGH

### Severity: HIGH
**Reason**: 7 nearly-identical reconstruction functions with 200+ lines of duplicated boilerplate code. This creates a maintenance nightmare when event schemas change.

### Locations
All in **`api/payment_simulator/cli/commands/replay.py`**:

1. `_reconstruct_arrival_events_from_simulation_events()` (lines 52-80)
2. `_reconstruct_settlement_events_from_simulation_events()` (lines 83-108)
3. `_reconstruct_arrival_events()` (lines 111-137) - **Legacy, likely unused**
4. `_reconstruct_settlement_events()` (lines 140-164) - **Legacy, likely unused**
5. `_reconstruct_lsm_events_from_simulation_events()` (lines 167-212)
6. `_reconstruct_collateral_events_from_simulation_events()` (lines 215-243)
7. `_reconstruct_cost_accrual_events()` (lines 246-273)
8. `_reconstruct_scenario_events_from_simulation_events()` (lines 276-311)

### Pattern Analysis

All functions follow this pattern:
```python
def _reconstruct_X_events_from_simulation_events(events: list[dict]) -> list[dict]:
    """Reconstruct X events from simulation_events table."""
    result = []
    for event in events:
        details = event["details"]  # Already parsed by get_simulation_events
        result.append({
            "event_type": "X",
            # Extract fields from details dict
            "field1": details.get("field1"),
            "field2": details.get("field2"),
            # ... more fields
        })
    return result
```

### Problems
1. **Schema Changes**: Adding a new field to an event type requires updating the corresponding reconstruction function
2. **Type Safety**: No validation that extracted fields match expected schema
3. **Boilerplate**: ~15-30 lines per function, mostly identical structure
4. **Legacy Code**: Functions 3 and 4 appear to be unused legacy code

### Recommendation

**Refactor Option 1: Generic Reconstruction Factory**

Create `api/payment_simulator/persistence/event_reconstruction.py`:

```python
from typing import TypedDict, Callable, Any

class EventReconstructor:
    """Generic event reconstruction from simulation_events table.

    Eliminates per-event-type reconstruction functions by using
    configurable field mappings.
    """

    def __init__(self):
        self._reconstructors: dict[str, Callable] = {}
        self._register_default_reconstructors()

    def register(self, event_type: str, field_mapping: dict[str, str]):
        """Register reconstruction mapping for an event type.

        Args:
            event_type: Event type string (e.g., "Arrival")
            field_mapping: Maps output field -> details field
                          Use None to copy from event level

        Example:
            >>> reconstructor.register("Arrival", {
            ...     "event_type": None,  # From event.event_type
            ...     "tx_id": None,       # From event.tx_id
            ...     "sender_id": "sender_id",  # From details.sender_id
            ...     "amount": "amount",
            ... })
        """
        def reconstruct_fn(event: dict) -> dict:
            result = {}
            details = event.get("details", {})

            for output_field, source_field in field_mapping.items():
                if source_field is None:
                    # Copy from event level
                    result[output_field] = event.get(output_field)
                else:
                    # Extract from details
                    result[output_field] = details.get(source_field)

            return result

        self._reconstructors[event_type] = reconstruct_fn

    def reconstruct(self, events: list[dict], event_type: str) -> list[dict]:
        """Reconstruct events of given type.

        Args:
            events: Raw events from simulation_events table
            event_type: Event type to reconstruct

        Returns:
            List of reconstructed event dicts
        """
        if event_type not in self._reconstructors:
            raise ValueError(f"No reconstructor registered for {event_type}")

        reconstructor = self._reconstructors[event_type]
        return [reconstructor(event) for event in events]

    def _register_default_reconstructors(self):
        """Register all standard event types."""
        # Arrival events
        self.register("Arrival", {
            "event_type": None,
            "tx_id": None,
            "sender_id": "sender_id",
            "receiver_id": "receiver_id",
            "amount": "amount",
            "priority": "priority",
            "deadline_tick": "deadline",  # Note: FFI uses "deadline"
            "is_divisible": "is_divisible",
        })

        # Settlement events
        self.register("Settlement", {
            "event_type": None,
            "tx_id": None,
            "sender_id": "sender_id",
            "receiver_id": "receiver_id",
            "amount": "amount",
        })

        # LSM events
        self.register("LsmBilateralOffset", {
            "event_type": None,
            "agent_a": "agent_a",
            "agent_b": "agent_b",
            "tx_id_a": "tx_id_a",
            "tx_id_b": "tx_id_b",
            "tx_ids": "tx_ids",
            "amount_a": "amount_a",
            "amount_b": "amount_b",
        })

        # ... register other event types
```

**Usage in replay.py:**
```python
from payment_simulator.persistence.event_reconstruction import EventReconstructor

reconstructor = EventReconstructor()

# Instead of:
arrival_events = _reconstruct_arrival_events_from_simulation_events(arrival_events_raw)

# Do:
arrival_events = reconstructor.reconstruct(arrival_events_raw, "Arrival")
```

**Refactor Option 2: Pydantic Validation** (Preferred for type safety)

Use Pydantic models to define event schemas and auto-generate reconstruction:

```python
from pydantic import BaseModel, Field

class ArrivalEvent(BaseModel):
    event_type: str = "Arrival"
    tx_id: str
    sender_id: str
    receiver_id: str
    amount: int
    priority: int = 5
    deadline_tick: int = Field(alias="deadline")
    is_divisible: bool = False

    class Config:
        populate_by_name = True  # Allow both "deadline" and "deadline_tick"

def reconstruct_events(events: list[dict], model: type[BaseModel]) -> list[dict]:
    """Generic reconstruction using Pydantic validation."""
    result = []
    for event in events:
        details = event.get("details", {})
        # Merge event-level and detail-level fields
        merged = {**event, **details}
        # Validate and reconstruct
        validated = model(**merged)
        result.append(validated.model_dump())
    return result

# Usage:
arrival_events = reconstruct_events(arrival_events_raw, ArrivalEvent)
```

**Estimated Effort**:
- Option 1 (Factory): 4 hours
- Option 2 (Pydantic): 6 hours (includes defining all event models)

---

## 3. Configuration Loading & Validation 🟠 HIGH

### Severity: HIGH
**Reason**: Configuration loading boilerplate is duplicated across 5 files with slight variations. Changes to config handling require updating multiple locations.

### Locations

1. **`api/payment_simulator/cli/commands/run.py:475-501`**
   ```python
   with open(config) as f:
       if config.suffix in [".yaml", ".yml"]:
           config_dict = yaml.safe_load(f)
       elif config.suffix == ".json":
           import json
           config_dict = json.load(f)
       else:
           log_error(f"Unsupported file format: {config.suffix}")
           raise typer.Exit(1)

   # Validate configuration
   try:
       sim_config = SimulationConfig.from_dict(config_dict)
   except Exception as e:
       log_error(f"Invalid configuration: {e}")
       raise typer.Exit(1)

   # Convert to FFI format
   ffi_dict = sim_config.to_ffi_dict()
   ```

2. **`api/payment_simulator/cli/commands/replay.py:622-635`**
   ```python
   import json
   config_dict = json.loads(summary["config_json"])

   # Validate configuration
   try:
       sim_config = SimulationConfig.from_dict(config_dict)
   except Exception as e:
       log_error(f"Invalid configuration: {e}")
       raise typer.Exit(1)

   # Convert to FFI format
   ffi_dict = sim_config.to_ffi_dict()
   ```

3. **`api/payment_simulator/cli/commands/checkpoint.py:86-90`**
   ```python
   import yaml
   from payment_simulator.config import SimulationConfig
   with open(config_file, 'r') as f:
       config_dict = yaml.safe_load(f)
   config = SimulationConfig.from_dict(config_dict)
   ffi_dict = config.to_ffi_dict()
   ```

4. **`api/payment_simulator/config/loader.py:8-40`**
   ```python
   def load_config(config_path: Union[str, Path]) -> SimulationConfig:
       """Load and validate simulation configuration from YAML file."""
       config_path = Path(config_path)

       if not config_path.exists():
           raise FileNotFoundError(f"Configuration file not found: {config_path}")

       with open(config_path, "r") as f:
           config_dict = yaml.safe_load(f)

       if config_dict is None:
           raise ValueError(f"Empty configuration file: {config_path}")

       # Validate and create config
       try:
           config = SimulationConfig.from_dict(config_dict)
       except Exception as e:
           raise ValueError(f"Invalid configuration: {e}") from e

       return config
   ```

### Problems
1. **Inconsistent Error Handling**: Some raise exceptions, some use typer.Exit(1), some log errors
2. **Format Detection**: File format detection (YAML vs JSON) is duplicated
3. **Validation**: Validation + conversion to FFI format is repeated
4. **Import Statements**: Conditional imports (`import json`, `import yaml`) scattered across files

### Recommendation

**Centralize in `api/payment_simulator/config/loader.py`:**

```python
from pathlib import Path
from typing import Union
import yaml
import json
from .schemas import SimulationConfig

class ConfigLoadError(Exception):
    """Base exception for configuration loading errors."""
    pass

class ConfigFormatError(ConfigLoadError):
    """Configuration file format is invalid."""
    pass

class ConfigValidationError(ConfigLoadError):
    """Configuration validation failed."""
    pass

def load_config_from_file(
    config_path: Union[str, Path],
    *,
    validate: bool = True,
    to_ffi: bool = False
) -> Union[SimulationConfig, dict]:
    """Load and validate simulation configuration.

    Args:
        config_path: Path to YAML or JSON configuration file
        validate: If True, validate against SimulationConfig schema
        to_ffi: If True, return FFI dict instead of SimulationConfig

    Returns:
        SimulationConfig instance or FFI dict (if to_ffi=True)

    Raises:
        ConfigLoadError: If file doesn't exist
        ConfigFormatError: If file format is invalid
        ConfigValidationError: If validation fails

    Examples:
        >>> # Load and validate
        >>> config = load_config_from_file("scenario.yaml")

        >>> # Load as FFI dict
        >>> ffi_dict = load_config_from_file("scenario.yaml", to_ffi=True)

        >>> # Load without validation (for testing)
        >>> raw_dict = load_config_from_file("scenario.yaml", validate=False)
    """
    config_path = Path(config_path)

    # Check file exists
    if not config_path.exists():
        raise ConfigLoadError(f"Configuration file not found: {config_path}")

    # Load based on file extension
    try:
        with open(config_path, "r") as f:
            if config_path.suffix in [".yaml", ".yml"]:
                config_dict = yaml.safe_load(f)
            elif config_path.suffix == ".json":
                config_dict = json.load(f)
            else:
                raise ConfigFormatError(
                    f"Unsupported file format: {config_path.suffix}. "
                    "Supported formats: .yaml, .yml, .json"
                )
    except (yaml.YAMLError, json.JSONDecodeError) as e:
        raise ConfigFormatError(f"Failed to parse {config_path}: {e}") from e

    if config_dict is None:
        raise ConfigLoadError(f"Empty configuration file: {config_path}")

    # Return raw dict if validation disabled
    if not validate:
        return config_dict

    # Validate configuration
    try:
        sim_config = SimulationConfig.from_dict(config_dict)
    except Exception as e:
        raise ConfigValidationError(f"Invalid configuration: {e}") from e

    # Return FFI dict if requested
    if to_ffi:
        return sim_config.to_ffi_dict()

    return sim_config

def load_config_from_json_string(
    config_json: str,
    *,
    to_ffi: bool = False
) -> Union[SimulationConfig, dict]:
    """Load configuration from JSON string (for replay from database).

    Args:
        config_json: Configuration as JSON string
        to_ffi: If True, return FFI dict instead of SimulationConfig

    Returns:
        SimulationConfig instance or FFI dict

    Raises:
        ConfigFormatError: If JSON is invalid
        ConfigValidationError: If validation fails
    """
    try:
        config_dict = json.loads(config_json)
    except json.JSONDecodeError as e:
        raise ConfigFormatError(f"Invalid JSON: {e}") from e

    try:
        sim_config = SimulationConfig.from_dict(config_dict)
    except Exception as e:
        raise ConfigValidationError(f"Invalid configuration: {e}") from e

    if to_ffi:
        return sim_config.to_ffi_dict()

    return sim_config
```

**Updated Usage in Commands:**

```python
# In run.py:
from payment_simulator.config.loader import load_config_from_file, ConfigLoadError

try:
    ffi_dict = load_config_from_file(config, to_ffi=True)
except ConfigLoadError as e:
    log_error(str(e))
    raise typer.Exit(1)

# In replay.py:
from payment_simulator.config.loader import load_config_from_json_string

ffi_dict = load_config_from_json_string(summary["config_json"], to_ffi=True)

# In checkpoint.py:
from payment_simulator.config.loader import load_config_from_file

config = load_config_from_file(config_file, validate=False)  # Raw dict for wrapper
```

**Estimated Effort**: 3 hours (refactor + update all usages + add tests)

---

## 4. Database Manager Initialization Pattern 🟠 HIGH

### Severity: HIGH
**Reason**: Database initialization boilerplate is duplicated across 4 command files. Schema validation logic is inconsistent.

### Locations

1. **`api/payment_simulator/cli/commands/checkpoint.py:29-42`**
   ```python
   def get_database_manager() -> DatabaseManager:
       """Get database manager with configured path."""
       db_path = os.environ.get("PAYMENT_SIM_DB_PATH", "simulation_data.db")
       db_manager = DatabaseManager(db_path)

       # Initialize if database doesn't exist
       if not Path(db_path).exists():
           console.print(f"[yellow]Initializing database at {db_path}[/yellow]")
           db_manager.setup()
       else:
           # Just connect, don't re-setup
           pass

       return db_manager
   ```

2. **`api/payment_simulator/cli/commands/run.py:556-567`**
   ```python
   db_manager = DatabaseManager(db_path)

   # Initialize schema if needed (idempotent - safe to call multiple times)
   if not db_manager.is_initialized():
       # Fresh database - initialize without verbose validation
       log_info("Database not initialized, creating schema...", quiet)
       db_manager.initialize_schema()
   else:
       # Database exists - validate schema
       if not db_manager.validate_schema(quiet=quiet):
           log_info("Schema incomplete, re-initializing...", quiet)
           db_manager.initialize_schema(force_recreate=True)
   ```

3. **`api/payment_simulator/cli/commands/db.py`** (5 separate commands, each with similar initialization)

### Problems
1. **Environment Variable**: Only checkpoint.py reads `PAYMENT_SIM_DB_PATH`, others use CLI parameter
2. **Initialization Logic**: Different strategies for initializing/validating schema
3. **Error Handling**: Inconsistent approach to schema validation failures
4. **Logging**: Different logging approaches (console.print vs log_info)

### Recommendation

**Add Database Context Manager to `api/payment_simulator/persistence/connection.py`:**

```python
from contextlib import contextmanager
from pathlib import Path
import os

@contextmanager
def database_context(
    db_path: str | Path | None = None,
    *,
    auto_setup: bool = True,
    validate: bool = True,
    quiet: bool = False
):
    """Context manager for database connections with automatic setup.

    Args:
        db_path: Database path (defaults to PAYMENT_SIM_DB_PATH env or "simulation_data.db")
        auto_setup: If True, initialize schema and apply migrations
        validate: If True, validate schema after setup
        quiet: Suppress setup messages

    Yields:
        DatabaseManager instance

    Examples:
        >>> # Simple usage with defaults
        >>> with database_context() as db:
        ...     result = db.conn.execute("SELECT COUNT(*) FROM transactions").fetchone()

        >>> # Custom path, skip validation
        >>> with database_context("test.db", validate=False) as db:
        ...     # Use db.conn

        >>> # Read-only access, no setup
        >>> with database_context(auto_setup=False) as db:
        ...     # Query existing database
    """
    # Determine database path
    if db_path is None:
        db_path = os.environ.get("PAYMENT_SIM_DB_PATH", "simulation_data.db")

    db_path = Path(db_path)
    manager = DatabaseManager(db_path)

    try:
        # Setup if requested
        if auto_setup:
            # Initialize schema if needed
            if not manager.is_initialized():
                if not quiet:
                    print(f"Initializing database at {db_path}", file=sys.stderr)
                manager.initialize_schema()

            # Validate if requested
            if validate:
                if not manager.validate_schema(quiet=quiet):
                    if not quiet:
                        print("Schema validation failed, re-initializing...", file=sys.stderr)
                    manager.initialize_schema(force_recreate=True)

        yield manager

    finally:
        manager.close()
```

**Updated Command Usage:**

```python
# In checkpoint.py:
from payment_simulator.persistence.connection import database_context

@checkpoint_app.command(name="save")
def save_checkpoint(...):
    with database_context() as db:
        checkpoint_mgr = CheckpointManager(db)
        # ... use checkpoint_mgr

# In run.py:
with database_context(db_path, quiet=quiet) as db_manager:
    sim_id = simulation_id or f"sim-{uuid.uuid4().hex[:8]}"
    # ... use db_manager

# In db.py:
@db_app.command("list")
def db_list(db_path: str = "simulation_data.db"):
    with database_context(db_path, auto_setup=False) as manager:
        # Query tables
```

**Estimated Effort**: 2 hours (add context manager + update all commands)

---

## 5. Agent State Display Logic 🟡 MEDIUM

### Severity: MEDIUM
**Reason**: Agent state formatting and display logic is partially duplicated. The StateProvider pattern has helped, but cost formatting and queue display still has duplication.

### Locations

1. **`api/payment_simulator/cli/output.py:279-375`** - `log_agent_financial_stats_table()`
   - 97 lines of agent state formatting

2. **`api/payment_simulator/cli/execution/strategies.py:116-180`** - `VerboseModeOutput.on_day_complete()`
   - 65 lines of similar agent state gathering for EOD

3. **`api/payment_simulator/cli/commands/replay.py:1001-1034`** - EOD agent metrics formatting
   - 34 lines with similar credit utilization, queue size logic

### Pattern Analysis

All three locations:
1. Loop through agent_ids
2. Query balance, credit_limit, queue sizes
3. Calculate credit utilization
4. Calculate queue values
5. Get cost breakdown
6. Format and display

### Recommendation

**Create Agent Display Utilities in `api/payment_simulator/cli/display/agent_stats.py`:**

```python
from dataclasses import dataclass
from typing import Protocol

@dataclass
class AgentSnapshot:
    """Snapshot of agent state at a point in time."""
    agent_id: str
    balance: int
    credit_limit: int
    collateral: int
    queue1_size: int
    queue1_value: int
    queue2_size: int
    queue2_value: int
    costs: dict[str, int]

    @property
    def credit_utilization(self) -> float:
        """Calculate credit utilization percentage."""
        from payment_simulator.core.metrics import calculate_credit_utilization
        return calculate_credit_utilization(self.balance, self.credit_limit)

    @property
    def total_cost(self) -> int:
        """Sum of all cost components."""
        return sum([
            self.costs.get("liquidity_cost", 0),
            self.costs.get("delay_cost", 0),
            self.costs.get("collateral_cost", 0),
            self.costs.get("deadline_penalty", 0),
            self.costs.get("split_friction_cost", 0),
        ])

    @classmethod
    def from_state_provider(
        cls,
        provider: Any,  # StateProvider
        agent_id: str
    ) -> "AgentSnapshot":
        """Create snapshot from state provider."""
        balance = provider.get_agent_balance(agent_id)
        credit_limit = provider.get_agent_credit_limit(agent_id) or 0
        collateral = provider.get_agent_collateral_posted(agent_id) or 0
        queue1_contents = provider.get_agent_queue1_contents(agent_id)
        costs = provider.get_agent_accumulated_costs(agent_id)

        # Calculate queue values
        queue1_value = 0
        for tx_id in queue1_contents:
            tx = provider.get_transaction_details(tx_id)
            if tx:
                queue1_value += tx.get("remaining_amount", 0)

        # Calculate Queue 2 (RTGS) for this agent
        rtgs_queue = provider.get_rtgs_queue_contents()
        agent_rtgs_txs = [
            tx_id for tx_id in rtgs_queue
            if (tx := provider.get_transaction_details(tx_id))
            and tx.get("sender_id") == agent_id
        ]
        queue2_value = sum(
            provider.get_transaction_details(tx_id).get("remaining_amount", 0)
            for tx_id in agent_rtgs_txs
            if provider.get_transaction_details(tx_id)
        )

        return cls(
            agent_id=agent_id,
            balance=balance,
            credit_limit=credit_limit,
            collateral=collateral,
            queue1_size=len(queue1_contents),
            queue1_value=queue1_value,
            queue2_size=len(agent_rtgs_txs),
            queue2_value=queue2_value,
            costs=costs,
        )

def gather_agent_snapshots(
    provider: Any,  # StateProvider
    agent_ids: list[str]
) -> list[AgentSnapshot]:
    """Gather snapshots for all agents."""
    return [
        AgentSnapshot.from_state_provider(provider, agent_id)
        for agent_id in agent_ids
    ]
```

**Usage:**
```python
# In strategies.py:
from payment_simulator.cli.display.agent_stats import gather_agent_snapshots

snapshots = gather_agent_snapshots(orch, self.agent_ids)
agent_stats = [
    {
        "id": snap.agent_id,
        "final_balance": snap.balance,
        "credit_utilization": snap.credit_utilization,
        "queue1_size": snap.queue1_size,
        "queue2_size": snap.queue2_size,
        "total_costs": snap.total_cost,
    }
    for snap in snapshots
]
```

**Estimated Effort**: 3 hours

---

## 6. Final Output JSON Construction 🟡 MEDIUM

### Severity: MEDIUM
**Reason**: Similar JSON output structure is constructed 4 times in run.py (once per execution mode) with minor variations.

### Locations

All in **`api/payment_simulator/cli/commands/run.py`**:

1. Lines 679-707 - Verbose mode output
2. Lines 896-935 - Normal mode output
3. Similar structure in stream/event_stream modes (not shown but likely similar)

### Pattern

```python
output_data = {
    "simulation": {
        "config_file": str(config),
        "seed": ffi_dict["rng_seed"],
        "ticks_executed": total_ticks,
        "duration_seconds": round(sim_duration, 3),
        "ticks_per_second": round(final_stats.get("ticks_per_second", 0), 2),
    },
    "metrics": {
        "total_arrivals": final_stats["total_arrivals"],
        "total_settlements": final_stats["total_settlements"],
        "total_lsm_releases": final_stats.get("total_lsm_releases", 0),
        "settlement_rate": final_stats.get("settlement_rate", 0),
    },
    "agents": agents,
    "costs": {
        "total_cost": final_stats.get("total_costs", 0),
    },
    "performance": {
        "ticks_per_second": round(final_stats.get("ticks_per_second", 0), 2),
    },
}

if persist and sim_id:
    output_data["simulation"]["simulation_id"] = sim_id
    output_data["simulation"]["database"] = db_path
```

### Recommendation

**Create Output Builder in `api/payment_simulator/cli/output.py`:**

```python
def build_simulation_output(
    *,
    config_file: Path | str,
    ffi_dict: dict,
    final_stats: dict,
    agents: list[dict],
    duration: float,
    simulation_id: str | None = None,
    db_path: str | None = None,
) -> dict:
    """Build standardized simulation output JSON.

    Args:
        config_file: Configuration file path
        ffi_dict: FFI configuration dictionary
        final_stats: Final statistics from runner
        agents: Agent state list
        duration: Simulation duration in seconds
        simulation_id: Optional simulation ID (if persisted)
        db_path: Optional database path (if persisted)

    Returns:
        Standardized output dictionary
    """
    output = {
        "simulation": {
            "config_file": str(config_file),
            "seed": ffi_dict["rng_seed"],
            "ticks_executed": ffi_dict["ticks_per_day"] * ffi_dict["num_days"],
            "duration_seconds": round(duration, 3),
            "ticks_per_second": round(final_stats.get("ticks_per_second", 0), 2),
        },
        "metrics": {
            "total_arrivals": final_stats["total_arrivals"],
            "total_settlements": final_stats["total_settlements"],
            "total_lsm_releases": final_stats.get("total_lsm_releases", 0),
            "settlement_rate": final_stats.get("settlement_rate", 0),
        },
        "agents": agents,
        "costs": {
            "total_cost": final_stats.get("total_costs", 0),
        },
        "performance": {
            "ticks_per_second": round(final_stats.get("ticks_per_second", 0), 2),
        },
    }

    # Add persistence info if available
    if simulation_id and db_path:
        output["simulation"]["simulation_id"] = simulation_id
        output["simulation"]["database"] = db_path

    return output
```

**Estimated Effort**: 1 hour

---

## 7. Simulation Metadata Persistence 🟠 HIGH

### Severity: HIGH
**Reason**: Complex metadata persistence logic (45+ lines) is called identically from 4 execution modes. Currently exists as a helper function but could be better encapsulated.

### Location
**`api/payment_simulator/cli/commands/run.py:130-249`** - `_persist_simulation_metadata()`

### Current State
The function `_persist_simulation_metadata()` exists but:
1. Has 12 parameters (too many)
2. Mixes responsibilities (config hashing, timestamp calculation, multiple table writes)
3. Called identically from 4 places in run.py (lines 656, 757, 819, 883)

### Recommendation

**Move to `api/payment_simulator/persistence/metadata.py` and refactor:**

```python
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import json

@dataclass
class SimulationMetadata:
    """Simulation metadata for persistence."""
    simulation_id: str
    config_path: Path
    config_dict: dict
    ffi_dict: dict
    agent_ids: list[str]
    total_arrivals: int
    total_settlements: int
    total_costs: int
    duration: float

    def persist(self, conn, orch):
        """Persist all metadata to database tables."""
        # Calculate derived values
        config_hash = hashlib.sha256(str(self.config_dict).encode()).hexdigest()
        config_json = json.dumps(self.config_dict)
        end_time = datetime.now()
        start_time = end_time - timedelta(seconds=self.duration)
        ticks_per_second = (
            (self.ffi_dict["ticks_per_day"] * self.ffi_dict["num_days"]) / self.duration
            if self.duration > 0 else 0
        )

        # Write simulation_runs table
        conn.execute("""
            INSERT INTO simulation_runs (
                simulation_id, config_name, config_hash, description,
                start_time, end_time,
                ticks_per_day, num_days, rng_seed,
                status, total_transactions
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            self.simulation_id,
            self.config_path.name,
            config_hash,
            f"Simulation run from {self.config_path.name}",
            start_time,
            end_time,
            self.ffi_dict["ticks_per_day"],
            self.ffi_dict["num_days"],
            self.ffi_dict["rng_seed"],
            "completed",
            self.total_arrivals,
        ])

        # Write simulations table
        conn.execute("""
            INSERT INTO simulations (
                simulation_id, config_file, config_hash, rng_seed,
                ticks_per_day, num_days, num_agents, config_json,
                status, started_at, completed_at,
                total_arrivals, total_settlements, total_cost_cents,
                duration_seconds, ticks_per_second
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            self.simulation_id,
            self.config_path.name,
            config_hash,
            self.ffi_dict["rng_seed"],
            self.ffi_dict["ticks_per_day"],
            self.ffi_dict["num_days"],
            len(self.agent_ids),
            config_json,
            "completed",
            start_time,
            end_time,
            self.total_arrivals,
            self.total_settlements,
            self.total_costs,
            self.duration,
            ticks_per_second,
        ])

        # Persist events
        from payment_simulator.persistence.event_writer import write_events_batch
        events = orch.get_all_events()
        if events:
            write_events_batch(
                conn=conn,
                simulation_id=self.simulation_id,
                events=events,
                ticks_per_day=self.ffi_dict["ticks_per_day"],
            )
```

**Usage in PersistenceManager:**
```python
# In persistence.py:
from payment_simulator.persistence.metadata import SimulationMetadata

def persist_final_metadata(self, **kwargs) -> None:
    metadata = SimulationMetadata(
        simulation_id=self.sim_id,
        **kwargs
    )
    metadata.persist(self.db_manager.conn, kwargs["orch"])
```

**Estimated Effort**: 2 hours

---

## 8. Transaction Cache Building 🟡 MEDIUM

### Severity: MEDIUM
**Reason**: Complex transaction cache building logic (~70 lines) in replay.py could be abstracted for reuse.

### Location
**`api/payment_simulator/cli/commands/replay.py:652-725`**

### Current Code
```python
# Build transaction cache for entire simulation from simulation_events
tx_cache = {}

# Get all Arrival events to populate initial transaction data (with pagination)
offset = 0
while True:
    arrival_events_result = get_simulation_events(
        conn=db_manager.conn,
        simulation_id=simulation_id,
        event_type="Arrival",
        sort="tick_asc",
        limit=1000,
        offset=offset,
    )

    # Build transaction cache from arrival events
    for event in arrival_events_result["events"]:
        details = event["details"]
        tx_id = event["tx_id"]
        if tx_id:
            tx_cache[tx_id] = {
                "tx_id": tx_id,
                "sender_id": details.get("sender_id"),
                # ... 10 more fields
            }

    if len(arrival_events_result["events"]) < 1000:
        break
    offset += 1000

# Update cache with settlement information (with pagination)
# ... similar loop for Settlement events
```

### Recommendation

**Move to `api/payment_simulator/persistence/queries.py`:**

```python
def build_transaction_cache(
    conn,
    simulation_id: str,
    *,
    progress_callback: Callable[[int, int], None] | None = None
) -> dict[str, dict]:
    """Build transaction cache from simulation_events table.

    Aggregates Arrival and Settlement events to create a complete
    transaction cache for replay. Uses pagination for memory efficiency.

    Args:
        conn: DuckDB connection
        simulation_id: Simulation identifier
        progress_callback: Optional callback(current, total) for progress reporting

    Returns:
        Dict mapping tx_id -> transaction details

    Examples:
        >>> cache = build_transaction_cache(conn, "sim-abc123")
        >>> len(cache)
        1532
        >>> cache["tx_00001"]["sender_id"]
        'BANK_A'
    """
    from .event_queries import get_simulation_events

    tx_cache = {}

    # Phase 1: Load arrivals
    offset = 0
    arrivals_processed = 0
    while True:
        result = get_simulation_events(
            conn=conn,
            simulation_id=simulation_id,
            event_type="Arrival",
            sort="tick_asc",
            limit=1000,
            offset=offset,
        )

        for event in result["events"]:
            details = event["details"]
            tx_id = event["tx_id"]
            if tx_id:
                tx_cache[tx_id] = {
                    "tx_id": tx_id,
                    "sender_id": details.get("sender_id"),
                    "receiver_id": details.get("receiver_id"),
                    "amount": details.get("amount", 0),
                    "amount_settled": 0,  # Will be updated in phase 2
                    "priority": details.get("priority", 0),
                    "is_divisible": details.get("is_divisible", False),
                    "arrival_tick": event["tick"],
                    "arrival_day": event["day"],
                    "deadline_tick": details.get("deadline") or details.get("deadline_tick", 0),
                    "settlement_tick": None,
                    "status": "pending",
                }

        arrivals_processed += len(result["events"])
        if progress_callback:
            progress_callback(arrivals_processed, None)  # Unknown total

        if len(result["events"]) < 1000:
            break
        offset += 1000

    # Phase 2: Update with settlements
    offset = 0
    settlements_processed = 0
    while True:
        result = get_simulation_events(
            conn=conn,
            simulation_id=simulation_id,
            event_type="Settlement",
            sort="tick_asc",
            limit=1000,
            offset=offset,
        )

        for event in result["events"]:
            details = event["details"]
            tx_id = event["tx_id"]
            if tx_id and tx_id in tx_cache:
                tx_cache[tx_id]["amount_settled"] = details.get("amount", 0)
                tx_cache[tx_id]["settlement_tick"] = event["tick"]
                tx_cache[tx_id]["status"] = "settled"

        settlements_processed += len(result["events"])
        if progress_callback:
            progress_callback(len(tx_cache), len(tx_cache))  # Total known now

        if len(result["events"]) < 1000:
            break
        offset += 1000

    return tx_cache
```

**Usage:**
```python
# In replay.py:
from payment_simulator.persistence.queries import build_transaction_cache

log_info("Loading transaction data from simulation_events...", False)

def progress(current, total):
    if total:
        log_info(f"  Loaded {current}/{total} transactions...", False)

tx_cache = build_transaction_cache(db_manager.conn, simulation_id, progress_callback=progress)
log_success(f"Loaded {len(tx_cache)} transactions", False)
```

**Estimated Effort**: 2 hours

---

## 9. Event Type String Literals 🟢 LOW

### Severity: LOW
**Reason**: Event type strings are repeated throughout the codebase. While this is a common pattern, it could benefit from centralization for type safety.

### Locations
Event type strings appear in:
- `replay.py`: "Arrival", "Settlement", "LsmBilateralOffset", "LsmCycleSettlement", etc.
- `strategies.py`: "PolicySubmit", "PolicyHold", "PolicyDrop", "PolicySplit"
- `runner.py`: Same policy event types
- Multiple display functions

### Recommendation

**Create Event Type Constants in `api/payment_simulator/core/event_types.py`:**

```python
from enum import Enum

class EventType(str, Enum):
    """Centralized event type definitions.

    Using str Enum allows direct comparison with strings while
    providing type safety and autocomplete in IDEs.
    """
    # Transaction lifecycle
    ARRIVAL = "Arrival"
    SETTLEMENT = "Settlement"

    # Policy decisions
    POLICY_SUBMIT = "PolicySubmit"
    POLICY_HOLD = "PolicyHold"
    POLICY_DROP = "PolicyDrop"
    POLICY_SPLIT = "PolicySplit"

    # LSM activity
    LSM_BILATERAL_OFFSET = "LsmBilateralOffset"
    LSM_CYCLE_SETTLEMENT = "LsmCycleSettlement"

    # Collateral management
    COLLATERAL_POST = "CollateralPost"
    COLLATERAL_WITHDRAW = "CollateralWithdraw"

    # Cost tracking
    COST_ACCRUAL = "CostAccrual"

    # End-of-day
    END_OF_DAY = "EndOfDay"

    # Scenario events
    SCENARIO_EVENT_EXECUTED = "ScenarioEventExecuted"

# Convenience groups
POLICY_EVENTS = {
    EventType.POLICY_SUBMIT,
    EventType.POLICY_HOLD,
    EventType.POLICY_DROP,
    EventType.POLICY_SPLIT,
}

LSM_EVENTS = {
    EventType.LSM_BILATERAL_OFFSET,
    EventType.LSM_CYCLE_SETTLEMENT,
}

COLLATERAL_EVENTS = {
    EventType.COLLATERAL_POST,
    EventType.COLLATERAL_WITHDRAW,
}
```

**Usage:**
```python
from payment_simulator.core.event_types import EventType, LSM_EVENTS

# Instead of:
if event_type in ["LsmBilateralOffset", "LsmCycleSettlement"]:

# Use:
if event_type in LSM_EVENTS:

# Type-safe comparisons:
if event["event_type"] == EventType.ARRIVAL:
```

**Estimated Effort**: 1 hour (low priority)

---

## 10. Cost Formatting & Display 🟢 LOW

### Severity: LOW
**Reason**: Cost formatting logic (`${amount / 100:,.2f}`) is repeated ~50 times across display functions. Minor duplication but could use a helper.

### Recommendation

**Add to `api/payment_simulator/cli/output.py`:**

```python
def format_cents_as_currency(cents: int) -> str:
    """Format cents as currency string.

    Args:
        cents: Amount in cents

    Returns:
        Formatted currency string (e.g., "$1,234.56")

    Examples:
        >>> format_cents_as_currency(123456)
        '$1,234.56'
        >>> format_cents_as_currency(-5000)
        '-$50.00'
    """
    return f"${cents / 100:,.2f}"

def format_cents_with_color(cents: int, *, negative_color: str = "red") -> str:
    """Format cents with Rich color coding.

    Args:
        cents: Amount in cents
        negative_color: Color for negative amounts (default: "red")

    Returns:
        Formatted string with Rich markup
    """
    formatted = format_cents_as_currency(cents)
    if cents < 0:
        return f"[{negative_color}]{formatted}[/{negative_color}]"
    return formatted
```

**Estimated Effort**: 30 minutes (low priority)

---

## 11. Summary Statistics Calculation 🟡 MEDIUM

### Severity: MEDIUM
**Reason**: Summary statistics are calculated in multiple ways, leading to the replay divergence issues mentioned in CLAUDE.md.

### Locations
1. **`replay.py:342-446`** - `_get_summary_statistics()` (DEPRECATED but still present)
2. **`runner.py`** - Uses `get_system_metrics()` from Rust
3. **Multiple manual count queries** scattered across commands

### Problem
The DEPRECATED `_get_summary_statistics()` function manually recalculates statistics from events, which can produce different results than the authoritative values from Rust's `get_system_metrics()`.

### Recommendation

**Action 1**: Remove the deprecated function and add clear warnings:

```python
# In replay.py - REMOVE _get_summary_statistics() entirely

# Add this comment where it was used:
# REMOVED: _get_summary_statistics() (Issue #XXX)
# Always use authoritative stats from simulations table via get_simulation_summary()
# Manual recalculation from events violates the Replay Identity principle
```

**Action 2**: Create statistics utilities in `api/payment_simulator/persistence/statistics.py`:

```python
def get_authoritative_statistics(conn, simulation_id: str) -> dict:
    """Get authoritative statistics from simulations table.

    These are the ONLY source of truth for final statistics.
    Never recalculate from events - this violates Replay Identity.

    Args:
        conn: Database connection
        simulation_id: Simulation identifier

    Returns:
        Dict with total_arrivals, total_settlements, total_cost_cents, etc.

    Raises:
        ValueError: If simulation not found
    """
    from .queries import get_simulation_summary

    summary = get_simulation_summary(conn, simulation_id)
    if not summary:
        raise ValueError(f"Simulation {simulation_id} not found")

    return {
        "total_arrivals": summary["total_arrivals"],
        "total_settlements": summary["total_settlements"],
        "total_cost_cents": summary["total_cost_cents"],
        "settlement_rate": (
            summary["total_settlements"] / summary["total_arrivals"]
            if summary["total_arrivals"] > 0 else 0
        ),
        "duration_seconds": summary.get("duration_seconds", 0),
        "ticks_per_second": summary.get("ticks_per_second", 0),
    }
```

**Estimated Effort**: 1 hour

---

## Refactoring Priority Matrix

### Immediate Action (Sprint 1)
1. **Credit Utilization** 🔴 - Already caused bugs, highest risk
2. **Configuration Loading** 🟠 - High duplication, affects all commands
3. **Database Initialization** 🟠 - Inconsistent patterns causing confusion

### Short-Term (Sprint 2)
4. **Event Reconstruction** 🟠 - High code volume, blocks schema evolution
5. **Simulation Metadata** 🟠 - Complex, called from multiple places
6. **Final Output JSON** 🟡 - Moderate duplication, straightforward refactor

### Medium-Term (Sprint 3)
7. **Agent State Display** 🟡 - Partially solved by StateProvider
8. **Transaction Cache** 🟡 - Complex but isolated to replay
9. **Summary Statistics** 🟡 - Remove deprecated function

### Low Priority (Backlog)
10. **Event Type Literals** 🟢 - Nice-to-have, low impact
11. **Cost Formatting** 🟢 - Minor duplication, purely cosmetic

---

## Anti-Patterns Observed

### 1. **Copy-Paste Inheritance**
Multiple commands copy-paste the same initialization logic rather than calling a shared function.

**Example**: Database initialization repeated in 4 commands.

### 2. **Inline Validation**
Configuration validation logic is inlined rather than using shared validation functions.

**Example**: run.py lines 497-501 vs replay.py lines 628-632

### 3. **God Functions**
Functions with 10+ parameters that mix multiple responsibilities.

**Example**: `_persist_simulation_metadata()` with 12 parameters

### 4. **String Literal Coupling**
Event types, database table names, and other constants are string literals scattered throughout code.

**Example**: Event type strings repeated 50+ times

### 5. **Implicit Contracts**
Functions rely on implicit contracts (e.g., "details field must be parsed JSON") rather than explicit types.

**Example**: Event reconstruction functions assume `event["details"]` is already parsed

---

## Testing Implications

### Current State
Most refactoring candidates lack comprehensive unit tests, making refactoring risky.

### Recommended Test Coverage Before Refactoring

```python
# Example: Credit utilization tests
def test_credit_utilization_positive_balance():
    """Positive balance should show 0% utilization."""
    assert calculate_credit_utilization(100000, 50000) == 0.0

def test_credit_utilization_negative_balance():
    """Negative balance should show utilization."""
    assert calculate_credit_utilization(-30000, 50000) == 60.0

def test_credit_utilization_overdraft_exceeds_limit():
    """Overdraft exceeding limit should show >100%."""
    assert calculate_credit_utilization(-60000, 50000) == 120.0

def test_credit_utilization_zero_limit():
    """Zero credit limit should return 0% (edge case)."""
    assert calculate_credit_utilization(-10000, 0) == 0.0
```

### Test-First Refactoring Workflow

For each refactoring:
1. **Extract existing behavior** into comprehensive tests
2. **Refactor** with confidence (tests catch regressions)
3. **Verify** all tests still pass
4. **Document** the new API

---

## Estimated Refactoring Effort

| Category | Effort (hours) | Risk | Impact |
|----------|----------------|------|--------|
| Credit Utilization | 2 | Low | High |
| Config Loading | 3 | Low | High |
| Database Init | 2 | Low | Medium |
| Event Reconstruction | 6 | Medium | High |
| Simulation Metadata | 2 | Low | Medium |
| Final Output JSON | 1 | Low | Low |
| Agent State Display | 3 | Low | Medium |
| Transaction Cache | 2 | Low | Low |
| Summary Statistics | 1 | Low | Medium |
| Event Type Literals | 1 | Low | Low |
| Cost Formatting | 0.5 | Low | Low |
| **Total** | **23.5** | | |

**Note**: Effort estimates assume:
- One developer working sequentially
- Includes writing tests
- Includes updating documentation
- Does NOT include code review time

**Recommended Approach**:
- Sprint 1 (7 hours): Items 1-3 (critical/high priority)
- Sprint 2 (11 hours): Items 4-6 (high/medium priority)
- Sprint 3 (5.5 hours): Items 7-11 (medium/low priority)

---

## Conclusion

The Python middleware has accumulated significant technical debt through code duplication. While the recent addition of `SimulationRunner`, `PersistenceManager`, and `StateProvider` patterns has improved the situation, several critical areas remain.

**Key Takeaways:**
1. **Immediate action required** on credit utilization (bug risk)
2. **High-value refactoring** in config loading and database initialization
3. **Long-term maintainability** will benefit from event reconstruction refactoring
4. **Test coverage** must improve before major refactoring

**Success Criteria:**
- Zero duplicate credit utilization calculations
- Single source of truth for configuration loading
- Consistent database initialization across all commands
- Reduced lines of code by ~500 (10% reduction)
- Improved test coverage from ~60% to >80%

---

**Next Steps:**
1. Review this report with the team
2. Prioritize refactoring items based on current sprint goals
3. Create GitHub issues for each refactoring item
4. Assign owners and begin Sprint 1 work
