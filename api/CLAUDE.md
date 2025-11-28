# Python API Middleware - Payment Simulator

## You Are Here: `/api`

This is the **Python FastAPI middleware** layer that sits between the Rust core and external clients. It provides HTTP/WebSocket endpoints, configuration management, CLI tools, and orchestration.

**Your role**: You're an expert Python developer who understands async programming, API design, strict type safety, and how to safely interface with native code via FFI.

---

## 🎯 Quick Reference

### Project Structure
```
api/
├── payment_simulator/
│   ├── __init__.py
│   ├── _core.py                ← Rust FFI re-exports
│   ├── backends.py             ← Rust backend wrapper
│   │
│   ├── api/                    ← FastAPI routes and models
│   │   ├── __init__.py
│   │   └── main.py             ← FastAPI app entry point
│   │
│   ├── cli/                    ← CLI tool layer
│   │   ├── __init__.py
│   │   ├── main.py             ← Typer CLI entry point
│   │   ├── output.py           ← Rich console output utilities
│   │   ├── filters.py          ← Event filtering (EventFilter class)
│   │   │
│   │   ├── commands/           ← CLI command implementations
│   │   │   ├── __init__.py
│   │   │   ├── run.py          ← Run simulation command
│   │   │   ├── replay.py       ← Replay from database command
│   │   │   ├── checkpoint.py   ← Save/load checkpoints
│   │   │   ├── db.py           ← Database management commands
│   │   │   ├── policy_schema.py      ← Policy schema docs
│   │   │   └── validate_policy.py    ← Policy validation
│   │   │
│   │   └── execution/          ← Simulation execution engine
│   │       ├── __init__.py
│   │       ├── runner.py       ← SimulationRunner (template method)
│   │       ├── strategies.py   ← OutputStrategy implementations
│   │       ├── persistence.py  ← PersistenceManager
│   │       ├── stats.py        ← TickResult, SimulationStats
│   │       ├── state_provider.py  ← StateProvider protocol
│   │       └── display.py      ← Shared verbose output logic
│   │
│   ├── config/                 ← Configuration schemas
│   │   ├── __init__.py
│   │   ├── schemas.py          ← Pydantic models for YAML
│   │   └── loader.py           ← Configuration loading
│   │
│   └── persistence/            ← Database persistence layer
│       ├── __init__.py
│       ├── models.py           ← Pydantic models (schema source of truth)
│       ├── connection.py       ← DatabaseManager
│       ├── writers.py          ← Batch write functions
│       ├── queries.py          ← Query functions
│       ├── event_writer.py     ← Event persistence
│       ├── event_queries.py    ← Event query functions
│       ├── checkpoint.py       ← CheckpointManager
│       ├── migrations.py       ← MigrationManager
│       ├── policy_tracking.py  ← Policy helper functions
│       └── schema_generator.py ← DDL generation from Pydantic
│
├── migrations/                 ← Database schema migrations
│   └── *.sql
│
├── tests/
│   └── integration/            ← FFI and persistence tests
│       ├── test_replay_identity*.py
│       ├── test_queries.py
│       └── ...
│
└── pyproject.toml              ← Build config + tool settings
```

---

## 🔴 CRITICAL: Type Safety Requirements

### Strict Typing is MANDATORY

All Python code in this project MUST have complete type annotations. This is a **company styleguide requirement** and is enforced via static type checking.

### Type Annotation Rules

1. **ALL function signatures must have type hints**:
   - Every parameter must have a type annotation
   - Every function must have a return type annotation (use `-> None` for void functions)

2. **Use modern Python type syntax** (Python 3.11+):
   - Use `list[str]` instead of `List[str]`
   - Use `dict[str, int]` instead of `Dict[str, int]`
   - Use `str | None` instead of `Optional[str]`
   - Use `X | Y` instead of `Union[X, Y]`

3. **Typer commands use `Annotated`**:
   ```python
   from typing_extensions import Annotated

   def my_command(
       path: Annotated[Path, typer.Option("--path", help="File path")],
       verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
   ) -> None:
       ...
   ```

4. **Protocol for duck typing**:
   ```python
   from typing import Protocol, runtime_checkable

   @runtime_checkable
   class OutputStrategy(Protocol):
       def on_tick_complete(self, result: TickResult, orch: Orchestrator) -> None:
           ...
   ```

### ✅ Good Typing Examples

**From persistence/models.py (EXEMPLARY - follow this pattern):**
```python
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class TransactionStatus(str, Enum):
    """Transaction status enumeration."""
    PENDING = "pending"
    SETTLED = "settled"
    DROPPED = "dropped"


class TransactionRecord(BaseModel):
    """Transaction record for persistence."""

    model_config = ConfigDict(
        table_name="transactions",
        primary_key=["simulation_id", "tx_id"],
    )

    simulation_id: str = Field(..., description="Foreign key")
    tx_id: str = Field(..., description="Unique identifier")
    sender_id: str = Field(..., description="Sender agent ID")
    amount: int = Field(..., description="Amount in cents", ge=0)
    status: TransactionStatus = Field(..., description="Current status")
    settlement_tick: int | None = Field(None, description="When settled")
```

**From cli/execution/runner.py (Protocol + dataclass pattern):**
```python
from dataclasses import dataclass
from typing import Protocol, Any


@dataclass
class SimulationConfig:
    """Configuration for simulation execution."""
    total_ticks: int
    ticks_per_day: int
    num_days: int
    persist: bool
    full_replay: bool
    db_path: str | None = None
    event_filter: EventFilter | None = None


class OutputStrategy(Protocol):
    """Protocol for mode-specific output handling."""

    def on_simulation_start(self, config: SimulationConfig) -> None:
        """Called before simulation starts."""
        ...

    def on_tick_complete(self, result: TickResult, orch: Orchestrator) -> None:
        """Called after tick execution."""
        ...
```

**From persistence/queries.py (return types + Optional parameters):**
```python
import polars as pl
from typing import Any


def get_agent_performance(
    conn: duckdb.DuckDBPyConnection,
    simulation_id: str,
    agent_id: str
) -> pl.DataFrame:
    """Get agent performance metrics over time."""
    ...


def get_simulation_events(
    conn: duckdb.DuckDBPyConnection,
    simulation_id: str,
    tick: int | None = None,
    agent_id: str | None = None,
    event_type: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Query simulation events with filtering."""
    ...
```

### ❌ Bad Typing Examples (DO NOT DO THIS)

```python
# ❌ BAD: Missing parameter types
def process_data(data, config):
    return data

# ❌ BAD: Missing return type
def get_balance(agent_id: str):
    return self.balances[agent_id]

# ❌ BAD: Using Any when specific type is known
def tick(self) -> Any:
    return self._orchestrator.tick()

# ❌ BAD: Not using Annotated for Typer
def command(db_path: str = typer.Option("db.sqlite")):
    pass

# ❌ BAD: Old-style typing imports
from typing import List, Dict, Optional, Union
def func(items: List[str]) -> Dict[str, Optional[int]]:
    pass
```

```python
# ✅ GOOD: Full type annotations
def process_data(data: list[dict[str, Any]], config: SimConfig) -> ProcessedResult:
    return ProcessedResult(data)

# ✅ GOOD: Explicit return type
def get_balance(self, agent_id: str) -> int:
    return self.balances[agent_id]

# ✅ GOOD: Specific return type
def tick(self) -> dict[str, Any]:
    return self._orchestrator.tick()

# ✅ GOOD: Using Annotated for Typer
def command(
    db_path: Annotated[str, typer.Option("--db-path")] = "db.sqlite"
) -> None:
    pass

# ✅ GOOD: Modern type syntax
def func(items: list[str]) -> dict[str, int | None]:
    pass
```

---

## 🔴 Linting and Static Type Checking

### Required Tools

The following tools are REQUIRED for all Python code:

1. **mypy** - Static type checker
2. **ruff** - Fast Python linter (replaces flake8, isort, etc.)

### Running Checks

```bash
# Type checking (MUST pass before committing)
.venv/bin/python -m mypy payment_simulator/

# Linting (MUST pass before committing)
.venv/bin/python -m ruff check payment_simulator/

# Auto-fix linting issues
.venv/bin/python -m ruff check --fix payment_simulator/

# Format code
.venv/bin/python -m ruff format payment_simulator/
```

### Configuration (pyproject.toml)

The project uses the following tool configuration:

```toml
[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
strict_optional = true

# Per-module overrides (for gradual migration)
[[tool.mypy.overrides]]
module = "payment_simulator.cli.commands.*"
disallow_untyped_defs = false  # Being migrated

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "N",    # pep8-naming
    "UP",   # pyupgrade
    "B",    # flake8-bugbear
    "C4",   # flake8-comprehensions
    "ANN",  # flake8-annotations
]
ignore = [
    "ANN101",  # Missing type annotation for self
    "ANN102",  # Missing type annotation for cls
]

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["ANN"]  # Tests don't require full annotations

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-v --tb=short"
```

---

## 🔴 Python-Specific Critical Rules

### 1. Configuration Validation with Pydantic

```python
from pydantic import BaseModel, Field, field_validator
from typing import Dict, List, Optional

class ArrivalConfig(BaseModel):
    """Per-agent transaction arrival configuration."""
    agent_id: str
    rate_per_tick: float = Field(gt=0, description="Expected transactions per tick (Poisson λ)")
    distribution_type: str = Field(pattern="^(normal|lognormal|uniform|exponential)$")
    amount_mean: int = Field(gt=0, description="Mean amount in cents (i64)")
    amount_std_dev: Optional[int] = Field(None, gt=0, description="Std deviation in cents")
    counterparty_weights: Optional[Dict[str, float]] = None
    time_windows: Optional[List[TimeWindow]] = None
    
    @field_validator('amount_mean', 'amount_std_dev')
    @classmethod
    def validate_money_is_int(cls, v):
        """Ensure money amounts are integers (cents)."""
        if not isinstance(v, int):
            raise ValueError(f"Money must be integer cents, got {type(v)}")
        return v
    
    @field_validator('distribution_type')
    @classmethod
    def validate_distribution_params(cls, v, values):
        """Ensure required params present for distribution type."""
        if v in ['normal', 'lognormal']:
            if 'amount_std_dev' not in values or values['amount_std_dev'] is None:
                raise ValueError(f"{v} distribution requires amount_std_dev")
        return v


class AgentConfig(BaseModel):
    """Agent (bank) configuration."""
    id: str = Field(pattern="^[A-Z0-9_]+$")  # Uppercase IDs only
    balance: int = Field(ge=0, description="Opening balance in cents")
    credit_limit: int = Field(ge=0, description="Overdraft/credit limit in cents")
    arrival_config: Optional[ArrivalConfig] = None
    
    @field_validator('balance', 'credit_limit')
    @classmethod
    def validate_money(cls, v):
        if not isinstance(v, int):
            raise ValueError(f"Money must be integer cents, got {type(v)}")
        return v


class SimulationConfig(BaseModel):
    """Top-level simulation configuration."""
    ticks_per_day: int = Field(ge=1, le=1000)
    seed: int = Field(description="RNG seed for determinism")
    agents: List[AgentConfig] = Field(min_length=2)
    rails: List[RailConfig]
    costs: CostConfig
    initial_transactions: Optional[List[TransactionConfig]] = None
    
    @field_validator('agents')
    @classmethod
    def validate_unique_agent_ids(cls, v):
        ids = [agent.id for agent in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Agent IDs must be unique")
        return v
```

**Why Pydantic?**
- Validates early (fail fast at config load time)
- Self-documenting (Field descriptions)
- Type-safe (catches type errors before FFI)
- Easy to convert to Rust-compatible dicts

### 2. FFI Safety Patterns

#### Wrapper Layer (`backends/rust_backend.py`)
```python
from typing import Dict, Any, List
from payment_simulator_core_rs import Orchestrator as RustOrchestrator
import logging

logger = logging.getLogger(__name__)


class RustBackend:
    """Safe wrapper around Rust FFI."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Rust orchestrator with validated config.
        
        Args:
            config: Pre-validated configuration dict (from Pydantic)
        
        Raises:
            ValueError: If Rust rejects configuration
            RuntimeError: If Rust panics (should never happen in production)
        """
        # Convert config to Rust-compatible format
        rust_config = self._convert_config(config)
        
        try:
            self._orchestrator = RustOrchestrator.new(rust_config)
            logger.info("Rust orchestrator initialized successfully")
        except ValueError as e:
            logger.error(f"Invalid configuration: {e}")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error initializing Rust: {e}")
            raise RuntimeError(f"Rust initialization failed: {e}")
    
    def tick(self) -> Dict[str, Any]:
        """Advance simulation by one tick.
        
        Returns:
            Dictionary with tick events (arrivals, settlements, etc.)
        
        Raises:
            RuntimeError: If Rust simulation encounters error
        """
        try:
            result = self._orchestrator.tick()
            return result
        except Exception as e:
            logger.error(f"Tick failed: {e}")
            raise RuntimeError(f"Simulation error: {e}")
    
    def get_state(self) -> Dict[str, Any]:
        """Get current simulation state snapshot.
        
        Returns:
            Dictionary with agent balances, transaction queues, etc.
        """
        try:
            return self._orchestrator.get_state()
        except Exception as e:
            logger.error(f"Failed to get state: {e}")
            raise RuntimeError(f"State retrieval failed: {e}")
    
    @staticmethod
    def _convert_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Python config to Rust-compatible format.
        
        Ensures:
        - All money values are integers
        - All agent/transaction IDs are strings
        - No None values (convert to appropriate defaults or omit)
        """
        # Remove None values
        rust_config = {k: v for k, v in config.items() if v is not None}
        
        # Convert nested arrival configs
        if "agents" in rust_config:
            for agent in rust_config["agents"]:
                if agent.get("arrival_config"):
                    # Rust expects snake_case
                    arrival = agent["arrival_config"]
                    agent["arrival_config"] = {
                        "agent_id": arrival["agent_id"],
                        "rate_per_tick": arrival["rate_per_tick"],
                        "distribution_type": arrival["distribution_type"],
                        "amount_mean": arrival["amount_mean"],
                        "amount_std_dev": arrival.get("amount_std_dev"),
                    }
        
        return rust_config
```

**Critical FFI Rules**:
- ✅ Always validate config in Python before passing to Rust
- ✅ Convert Python types to Rust-compatible primitives
- ✅ Catch and wrap all Rust exceptions
- ✅ Log all FFI calls for debugging
- ❌ Never hold references to Rust objects across await points
- ❌ Never pass mutable Python objects to Rust
- ❌ Never cache Rust state in Python (always query fresh)

### 3. Async API Patterns (FastAPI)

```python
from fastapi import FastAPI, HTTPException, WebSocket, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Dict
import asyncio
import uuid

app = FastAPI(title="Payment Simulator API")

# In-memory simulation registry (use Redis in production)
simulations: Dict[str, RustBackend] = {}


@app.post("/api/simulations", status_code=201)
async def create_simulation(config: SimulationConfig) -> Dict[str, str]:
    """Create a new simulation instance.
    
    Args:
        config: Validated simulation configuration
    
    Returns:
        {'simulation_id': '<uuid>'}
    """
    sim_id = str(uuid.uuid4())
    
    try:
        # Convert Pydantic model to dict
        config_dict = config.model_dump()
        
        # Create Rust backend (this crosses FFI)
        backend = RustBackend(config_dict)
        
        # Store in registry
        simulations[sim_id] = backend
        
        logger.info(f"Created simulation {sim_id}")
        return {"simulation_id": sim_id}
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to create simulation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/simulations/{sim_id}/tick")
async def advance_tick(sim_id: str) -> Dict[str, Any]:
    """Advance simulation by one tick.
    
    Note: This is I/O bound (Rust call), so we use run_in_executor
    to avoid blocking the event loop for long simulations.
    """
    if sim_id not in simulations:
        raise HTTPException(status_code=404, detail="Simulation not found")
    
    backend = simulations[sim_id]
    
    try:
        # Run Rust tick in executor to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, backend.tick)
        
        return result
        
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/simulations/{sim_id}")
async def simulation_websocket(websocket: WebSocket, sim_id: str):
    """WebSocket for real-time simulation updates."""
    await websocket.accept()
    
    if sim_id not in simulations:
        await websocket.close(code=4004, reason="Simulation not found")
        return
    
    backend = simulations[sim_id]
    
    try:
        while True:
            # Wait for client message (e.g., "tick" command)
            message = await websocket.receive_json()
            
            if message.get("action") == "tick":
                # Run tick in executor
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, backend.tick)
                
                # Send result back to client
                await websocket.send_json({
                    "type": "tick_result",
                    "data": result
                })
            
            elif message.get("action") == "get_state":
                state = await loop.run_in_executor(None, backend.get_state)
                await websocket.send_json({
                    "type": "state",
                    "data": state
                })
                
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close(code=1011, reason="Internal error")


@app.delete("/api/simulations/{sim_id}")
async def delete_simulation(sim_id: str):
    """Delete simulation instance."""
    if sim_id not in simulations:
        raise HTTPException(status_code=404, detail="Simulation not found")
    
    del simulations[sim_id]
    return {"status": "deleted"}
```

**Key Patterns**:
- Use `run_in_executor()` for CPU-bound Rust calls
- WebSockets for real-time updates
- In-memory registry (replace with Redis for production)
- Proper HTTP status codes
- Comprehensive error handling

---

## Testing Patterns

### Unit Tests (Pure Python)

```python
# tests/unit/test_config_validation.py
import pytest
from pydantic import ValidationError
from payment_simulator.config.schema import AgentConfig, ArrivalConfig


def test_agent_config_validates_money_as_int():
    """Money values must be integers."""
    with pytest.raises(ValidationError) as exc_info:
        AgentConfig(
            id="BANK_A",
            balance=1000.50,  # Float not allowed!
            credit_limit=500,
        )
    assert "integer" in str(exc_info.value).lower()


def test_arrival_config_requires_std_dev_for_normal():
    """Normal distribution requires std_dev parameter."""
    with pytest.raises(ValidationError):
        ArrivalConfig(
            agent_id="BANK_A",
            rate_per_tick=5.0,
            distribution_type="normal",
            amount_mean=100000,
            # Missing amount_std_dev!
        )


def test_agent_ids_must_be_uppercase():
    """Agent IDs follow naming convention."""
    with pytest.raises(ValidationError):
        AgentConfig(
            id="bank_a",  # Lowercase not allowed
            balance=100000,
            credit_limit=50000,
        )
```

### Integration Tests (FFI Boundary)

```python
# tests/integration/test_rust_ffi_determinism.py
import pytest
from payment_simulator.backends.rust_backend import RustBackend


def test_deterministic_replay():
    """Same seed produces identical results."""
    config = {
        "ticks_per_day": 100,
        "seed": 12345,
        "agents": [
            {"id": "A", "balance": 100000, "credit_limit": 50000},
            {"id": "B", "balance": 150000, "credit_limit": 75000},
        ],
        "rails": [{"id": "RTGS", "settlement_type": "immediate"}],
        "costs": {
            "overdraft_rate": 0.0001,
            "delay_penalty_per_tick": 10,
        },
    }
    
    backend1 = RustBackend(config)
    backend2 = RustBackend(config)
    
    results1 = []
    results2 = []
    
    for _ in range(50):
        results1.append(backend1.tick())
        results2.append(backend2.tick())
    
    # Results must be identical
    assert results1 == results2


def test_ffi_error_handling():
    """Rust errors propagate as Python exceptions."""
    config = {
        "ticks_per_day": 100,
        "seed": 12345,
        "agents": [],  # No agents - should fail
        "rails": [],
        "costs": {},
    }
    
    with pytest.raises((ValueError, RuntimeError)):
        RustBackend(config)


def test_no_float_contamination():
    """Money values stay as integers across FFI."""
    config = create_test_config()
    backend = RustBackend(config)
    
    for _ in range(10):
        backend.tick()
    
    state = backend.get_state()
    
    for agent in state["agents"]:
        balance = agent["balance"]
        assert isinstance(balance, int), f"Balance is {type(balance)}, not int"
```

### E2E Tests (Full API)

```python
# tests/e2e/test_simulation_lifecycle.py
import pytest
from fastapi.testclient import TestClient
from payment_simulator.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_simulation_lifecycle(client):
    """Complete simulation lifecycle via API."""
    # 1. Create simulation
    config = {
        "ticks_per_day": 100,
        "seed": 12345,
        "agents": [
            {
                "id": "BANK_A",
                "balance": 1000000,
                "credit_limit": 500000,
                "arrival_config": {
                    "agent_id": "BANK_A",
                    "rate_per_tick": 5.0,
                    "distribution_type": "normal",
                    "amount_mean": 100000,
                    "amount_std_dev": 30000,
                }
            },
            {
                "id": "BANK_B",
                "balance": 1500000,
                "credit_limit": 750000,
            }
        ],
        "rails": [{"id": "RTGS", "settlement_type": "immediate"}],
        "costs": {
            "overdraft_rate": 0.0001,
            "delay_penalty_per_tick": 10,
            "split_fee": 50,
            "eod_penalty": 100000,
        }
    }
    
    response = client.post("/api/simulations", json=config)
    assert response.status_code == 201
    sim_id = response.json()["simulation_id"]
    
    # 2. Run some ticks
    for _ in range(10):
        response = client.post(f"/api/simulations/{sim_id}/tick")
        assert response.status_code == 200
        result = response.json()
        assert "tick" in result
    
    # 3. Get state
    response = client.get(f"/api/simulations/{sim_id}/state")
    assert response.status_code == 200
    state = response.json()
    assert len(state["agents"]) == 2
    
    # 4. Delete simulation
    response = client.delete(f"/api/simulations/{sim_id}")
    assert response.status_code == 200
    
    # 5. Verify deleted
    response = client.get(f"/api/simulations/{sim_id}/state")
    assert response.status_code == 404
```

---

## Common Python Patterns

### Pattern 1: Configuration Loading

```python
import yaml
from pathlib import Path
from payment_simulator.config.schema import SimulationConfig


def load_config(path: str) -> SimulationConfig:
    """Load and validate configuration from YAML file.
    
    Args:
        path: Path to YAML configuration file
    
    Returns:
        Validated SimulationConfig
    
    Raises:
        FileNotFoundError: If file doesn't exist
        ValidationError: If config is invalid
    """
    config_path = Path(path)
    
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    
    with open(config_path) as f:
        raw_config = yaml.safe_load(f)
    
    # Pydantic validates automatically
    config = SimulationConfig(**raw_config)
    
    return config
```

### Pattern 2: Metrics Aggregation

```python
from typing import List, Dict
from dataclasses import dataclass
import statistics


@dataclass
class SimulationMetrics:
    """Aggregated metrics from simulation run."""
    total_ticks: int
    total_arrivals: int
    total_settlements: int
    total_dropped: int
    settlement_rate: float
    average_delay: float
    max_queue_depth: int
    agent_metrics: Dict[str, Dict[str, float]]


def aggregate_metrics(tick_results: List[Dict]) -> SimulationMetrics:
    """Compute aggregate metrics from tick results.
    
    Args:
        tick_results: List of tick result dicts from Rust
    
    Returns:
        Aggregated metrics
    """
    total_arrivals = sum(r["arrivals"] for r in tick_results)
    total_settlements = sum(r["settlements"] for r in tick_results)
    total_dropped = sum(r["dropped"] for r in tick_results)
    
    settlement_rate = total_settlements / total_arrivals if total_arrivals > 0 else 0.0
    
    # Compute per-agent metrics
    agent_metrics = {}
    for agent_id in get_agent_ids(tick_results[0]):
        agent_data = extract_agent_data(tick_results, agent_id)
        agent_metrics[agent_id] = {
            "avg_balance": statistics.mean(agent_data["balances"]),
            "min_balance": min(agent_data["balances"]),
            "total_sent": sum(agent_data["sent"]),
            "total_received": sum(agent_data["received"]),
        }
    
    return SimulationMetrics(
        total_ticks=len(tick_results),
        total_arrivals=total_arrivals,
        total_settlements=total_settlements,
        total_dropped=total_dropped,
        settlement_rate=settlement_rate,
        average_delay=compute_average_delay(tick_results),
        max_queue_depth=max(r["queue_depth"] for r in tick_results),
        agent_metrics=agent_metrics,
    )
```

---

## Debugging Tips

### Logging Best Practices

```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Use structured logging for important events
logger.info(
    "Simulation created",
    extra={
        "simulation_id": sim_id,
        "ticks_per_day": config.ticks_per_day,
        "num_agents": len(config.agents),
        "seed": config.seed,
    }
)
```

### FFI Debugging

```python
# Enable Rust tracing
import os
os.environ["RUST_LOG"] = "debug"

# Capture Rust panics
import sys
sys.stderr = open("rust_errors.log", "w")

# Test FFI calls in isolation
def test_ffi_call():
    try:
        result = rust_orchestrator.tick()
        print(f"Success: {result}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
```

---

## Common Mistakes

### ❌ Mistake 1: Caching Rust State
```python
# BAD: Stale cached data
class SimulationManager:
    def __init__(self, backend):
        self.backend = backend
        self.cached_state = backend.get_state()  # DON'T CACHE!
    
    def get_balance(self, agent_id):
        return self.cached_state["agents"][agent_id]["balance"]  # WRONG!


# GOOD: Always query fresh
class SimulationManager:
    def __init__(self, backend):
        self.backend = backend
    
    def get_balance(self, agent_id):
        state = self.backend.get_state()  # Fresh every time
        return state["agents"][agent_id]["balance"]
```

### ❌ Mistake 2: Async/FFI Mixing Without Executor
```python
# BAD: Blocking async function
async def run_simulation():
    backend = RustBackend(config)
    for _ in range(1000):
        result = backend.tick()  # BLOCKS EVENT LOOP!


# GOOD: Use executor for CPU-bound work
async def run_simulation():
    backend = RustBackend(config)
    loop = asyncio.get_event_loop()
    for _ in range(1000):
        result = await loop.run_in_executor(None, backend.tick)
```

### ❌ Mistake 3: Float Money in Config
```python
# BAD: Float amounts
config = {
    "agents": [
        {"id": "A", "balance": 1000.00, "credit_limit": 500.00}  # FLOATS!
    ]
}

# GOOD: Integer cents
config = {
    "agents": [
        {"id": "A", "balance": 100000, "credit_limit": 50000}  # CENTS!
    ]
}
```

---

## Development Commands

```bash
# Setup: Build Rust module and install everything (ONE command!)
uv sync --extra dev

# Run tests (use .venv/bin/python to ensure correct environment)
.venv/bin/python -m pytest

# Run tests with coverage
.venv/bin/python -m pytest --cov=payment_simulator --cov-report=html

# Run specific test file
.venv/bin/python -m pytest tests/integration/test_rust_ffi_determinism.py

# Run with verbose output
.venv/bin/python -m pytest -v -s

# After Rust code changes, rebuild with:
uv sync --extra dev --reinstall-package payment-simulator

# Type checking
mypy payment_simulator/

# Linting
ruff check payment_simulator/
black --check payment_simulator/

# Format code
black payment_simulator/
ruff check --fix payment_simulator/

# Start API server (dev)
uvicorn payment_simulator.api.main:app --reload

# Start API server (prod)
gunicorn payment_simulator.api.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

---

## CLI Execution Architecture (SimulationRunner)

### Overview

The CLI execution layer uses the **Template Method** and **Strategy** patterns to eliminate code duplication across 4 execution modes (normal, verbose, stream, event_stream).

**Key Components:**
- `SimulationRunner`: Core execution engine (template method)
- `OutputStrategy` (Protocol): Mode-specific output behavior
- `PersistenceManager`: Centralized database persistence
- `SimulationStats`: Statistics tracking and aggregation

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│  run_simulation() - CLI Entry Point                     │
│  (/cli/commands/run.py)                                 │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  _create_output_strategy()                              │
│  Factory: mode → OutputStrategy                         │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  SimulationRunner                                       │
│  (/cli/execution/runner.py)                            │
│                                                         │
│  - Common execution flow (tick loop, EOD detection)    │
│  - Calls output strategy hooks at lifecycle events     │
│  - Manages persistence and statistics                  │
└───────┬────────────────────────────────────┬───────────┘
        │                                    │
        ▼                                    ▼
┌──────────────────────┐         ┌─────────────────────────┐
│  OutputStrategy      │         │  PersistenceManager     │
│  (Protocol)          │         │  (/cli/execution/       │
│                      │         │   persistence.py)       │
│  Implementations:    │         │                         │
│  - VerboseModeOutput │         │  - EOD data persistence │
│  - NormalModeOutput  │         │  - Full replay buffers  │
│  - StreamModeOutput  │         │  - Metadata persistence │
│  - EventStreamOutput │         └─────────────────────────┘
└──────────────────────┘
```

### OutputStrategy Protocol

Each execution mode implements this protocol:

```python
class OutputStrategy(Protocol):
    def on_simulation_start(self, config: SimulationConfig) -> None:
        """Called once before simulation starts."""
        ...

    def on_tick_start(self, tick: int) -> None:
        """Called at start of each tick."""
        ...

    def on_tick_complete(self, result: TickResult, orch: Orchestrator) -> None:
        """Called after tick execution completes."""
        ...

    def on_day_complete(self, day: int, day_stats: dict, orch: Orchestrator) -> None:
        """Called at end of each day."""
        ...

    def on_simulation_complete(self, final_stats: dict) -> None:
        """Called once after simulation completes."""
        ...
```

### Execution Flow

```python
# 1. CLI parses arguments
run_simulation(config, verbose=True, persist=True, ...)

# 2. Create output strategy for mode
output = _create_output_strategy(mode="verbose", ...)

# 3. Create persistence manager (if enabled)
persistence = PersistenceManager(db_manager, sim_id, full_replay)

# 4. Create runner config
runner_config = SimulationConfig(
    total_ticks=100,
    ticks_per_day=10,
    num_days=10,
    persist=True,
    full_replay=False,
)

# 5. Run simulation
runner = SimulationRunner(orch, runner_config, output, persistence)
final_stats = runner.run()  # Returns statistics dict

# 6. Persist final metadata (caller's responsibility)
if persist:
    persistence.persist_final_metadata(config_path, config_dict, ...)
```

### Adding a New Execution Mode

To add a new execution mode:

1. **Create OutputStrategy implementation** (`/cli/execution/strategies.py`):
```python
class MyNewModeOutput:
    def on_simulation_start(self, config):
        print("Starting my new mode!")

    def on_tick_complete(self, result, orch):
        # Custom output for each tick
        print(f"Tick {result.tick}: {result.num_settlements} settlements")

    # ... implement other hooks
```

2. **Add to factory** (`/cli/commands/run.py`):
```python
def _create_output_strategy(mode, ...):
    if mode == "my_new_mode":
        return MyNewModeOutput(...)
    # ... existing modes
```

3. **Add CLI flag** (if needed):
```python
def run_simulation(..., my_new_mode: bool = False):
    if my_new_mode:
        output = _create_output_strategy("my_new_mode", ...)
```

### Persistence Pattern

**Separation of Concerns:**
- `SimulationRunner.run()`: Executes simulation, returns statistics
- **Caller** (run.py): Handles metadata persistence after run() completes

```python
# SimulationRunner returns stats WITHOUT persisting metadata
final_stats = runner.run()

# Caller persists metadata using returned stats
persistence.persist_final_metadata(
    config_path=config,
    config_dict=config_dict,
    total_arrivals=final_stats["total_arrivals"],
    ...
)
```

**Why this pattern?**
- SimulationRunner focuses on execution logic
- Caller has access to config paths and other metadata
- Clear separation prevents circular dependencies

### Migration Notes

**Feature Flag (Temporary):**
```bash
# Default (new runner)
payment-sim run config.yaml

# Legacy mode (for comparison testing)
USE_NEW_RUNNER=false payment-sim run config.yaml
```

The `USE_NEW_RUNNER` flag enables A/B testing. Once fully validated, the old implementation will be removed entirely.

**File Locations:**
- Runner: `/cli/execution/runner.py`
- Strategies: `/cli/execution/strategies.py`
- Persistence: `/cli/execution/persistence.py`
- Stats: `/cli/execution/stats.py`
- Integration: `/cli/commands/run.py`

---

## Checklist Before Committing

### Type Safety (REQUIRED)
- [ ] **ALL functions have type annotations** (parameters AND return types)
- [ ] **mypy passes**: `.venv/bin/python -m mypy payment_simulator/`
- [ ] **ruff passes**: `.venv/bin/python -m ruff check payment_simulator/`
- [ ] Using modern type syntax (`str | None`, not `Optional[str]`)
- [ ] Typer commands use `Annotated` pattern
- [ ] No `Any` where specific types are known

### Money Safety
- [ ] All money values are `int` (never `float`)
- [ ] Amounts in cents, not dollars

### FFI Safety
- [ ] Pydantic models validate config early
- [ ] FFI calls wrapped in try/except
- [ ] Async functions use `run_in_executor` for Rust calls
- [ ] No stale state cached from Rust

### Testing
- [ ] Tests pass: `.venv/bin/python -m pytest`
- [ ] Integration tests cover FFI boundary
- [ ] New code has test coverage

### Code Quality
- [ ] Code formatted: `.venv/bin/python -m ruff format payment_simulator/`
- [ ] Logging added for important operations
- [ ] Docstrings present for public functions

---

## Typing Migration Status

The following modules have complete type coverage:
- ✅ `persistence/` - All files fully typed
- ✅ `config/` - All files fully typed
- ✅ `cli/execution/` - All files fully typed
- ✅ `cli/output.py` - Fully typed
- ✅ `cli/filters.py` - Fully typed
- ✅ `cli/main.py` - Fully typed

The following modules need typing improvements (in progress):
- ⚠️ `cli/commands/run.py` - Helper functions need types
- ⚠️ `cli/commands/replay.py` - Reconstruction functions need types
- ⚠️ `cli/commands/db.py` - Typer commands need `Annotated`
- ⚠️ `cli/commands/checkpoint.py` - Typer commands need `Annotated`
- ⚠️ `cli/commands/policy_schema.py` - Needs typing improvements
- ⚠️ `cli/commands/validate_policy.py` - Partially typed
- ⚠️ `api/main.py` - Minimal, needs review

See `docs/plans/api-typing-linting-refactor.md` for the full migration plan.

---

*Last updated: 2025-11-28*
*For Rust core guidance, see `/backend/CLAUDE.md`*
*For general patterns, see root `/CLAUDE.md`*