# Python API Layer - Style Guide & Architecture

## Overview

This is the **Python middleware layer** for the payment simulator. It provides CLI tools, FastAPI endpoints, configuration validation, and persistence.

**Key Principle**: Python orchestrates; Rust computes. Keep FFI minimal, validate early, and maintain strict type safety throughout.

---

## Python Style Guide

### Type System Philosophy

This codebase uses **strict, complete typing**. Every function signature must be fully annotated with no ambiguity.

**Core Rules:**
1. Every parameter has a type annotation
2. Every function has a return type (use `-> None` for void)
3. No partially unknown types (avoid `Any` unless truly necessary)
4. All generic classes specify type arguments

### Use Native Python Types

Use Python 3.11+ built-in generics. Never import from `typing` for basic types.

```python
# Correct - native types
def process(items: list[str], lookup: dict[str, int]) -> list[int]:
    return [lookup[item] for item in items]

def find_user(user_id: str) -> User | None:
    return users.get(user_id)

# Wrong - legacy typing imports
from typing import List, Dict, Optional, Union
def process(items: List[str], lookup: Dict[str, int]) -> List[int]: ...
def find_user(user_id: str) -> Optional[User]: ...
```

### Specify Type Arguments for Generics

Never use bare generic types. Always specify what they contain.

```python
# Correct - fully specified
def get_events(tick: int) -> list[dict[str, str | int | float]]:
    ...

def aggregate(data: dict[str, list[int]]) -> dict[str, int]:
    ...

# Wrong - bare generics
def get_events(tick: int) -> list[dict]:  # What's in the dict?
    ...

def aggregate(data: dict) -> dict:  # Useless type info
    ...
```

### Avoid Partial Unknown Types

When a return type would be `Any` or unknown, define a proper type.

```python
# Wrong - leaks unknown type
def get_tick_result(self) -> dict[str, Any]:  # Any is a code smell
    return self._orchestrator.tick()

# Better - define the shape
class TickResult(TypedDict):
    tick: int
    arrivals: int
    settlements: int
    events: list[EventDict]

def get_tick_result(self) -> TickResult:
    return self._orchestrator.tick()

# Alternative - use a Protocol or dataclass if TypedDict doesn't fit
@dataclass
class TickResult:
    tick: int
    arrivals: int
    settlements: int
    events: list[dict[str, str | int | float]]
```

### Use Union Syntax, Not Optional

```python
# Correct
def find(id: str) -> User | None:
    ...

def parse(value: str) -> int | float | str:
    ...

# Wrong
from typing import Optional, Union
def find(id: str) -> Optional[User]: ...
def parse(value: str) -> Union[int, float, str]: ...
```

---

## Composition Over Inheritance

Prefer composition and protocols over class hierarchies.

### Use Protocols for Interfaces

Protocols define behavior contracts without requiring inheritance.

```python
from typing import Protocol, runtime_checkable


@runtime_checkable
class StateProvider(Protocol):
    """Abstraction for accessing simulation state."""

    def get_agent_balance(self, agent_id: str) -> int:
        """Return agent's current balance in cents."""
        ...

    def get_pending_transactions(self, agent_id: str) -> list[dict[str, str | int]]:
        """Return pending outgoing transactions."""
        ...

    def get_events_for_tick(self, tick: int) -> list[dict[str, str | int | float]]:
        """Return events that occurred in the given tick."""
        ...


# Implementation via composition, not inheritance
class OrchestratorStateProvider:
    """StateProvider backed by live Rust FFI."""

    def __init__(self, orchestrator: Orchestrator) -> None:
        self._orch = orchestrator

    def get_agent_balance(self, agent_id: str) -> int:
        return self._orch.get_agent_balance(agent_id)

    def get_pending_transactions(self, agent_id: str) -> list[dict[str, str | int]]:
        return self._orch.get_pending_transactions(agent_id)

    def get_events_for_tick(self, tick: int) -> list[dict[str, str | int | float]]:
        return self._orch.get_tick_events(tick)


class DatabaseStateProvider:
    """StateProvider backed by persisted database."""

    def __init__(self, conn: duckdb.DuckDBPyConnection, sim_id: str) -> None:
        self._conn = conn
        self._sim_id = sim_id

    def get_agent_balance(self, agent_id: str) -> int:
        result = self._conn.execute(
            "SELECT balance FROM agent_snapshots WHERE simulation_id = ? AND agent_id = ? ORDER BY tick DESC LIMIT 1",
            [self._sim_id, agent_id]
        ).fetchone()
        return result[0] if result else 0

    # ... implement other methods
```

### Use Dataclasses for Value Objects

Prefer dataclasses over plain dicts for structured data.

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class SimulationConfig:
    """Immutable simulation configuration."""
    total_ticks: int
    ticks_per_day: int
    num_days: int
    persist: bool
    db_path: str | None = None


@dataclass
class TickResult:
    """Result of a single tick execution."""
    tick: int
    day: int
    arrivals: int
    settlements: int
    queue_depth: int
    events: list[dict[str, str | int | float]]


# Use dataclass in function signatures
def run_tick(config: SimulationConfig, provider: StateProvider) -> TickResult:
    ...
```

### Strategy Pattern via Protocols

```python
from typing import Protocol


class OutputStrategy(Protocol):
    """Strategy for handling simulation output."""

    def on_tick_complete(self, result: TickResult, provider: StateProvider) -> None:
        """Called after each tick completes."""
        ...

    def on_simulation_complete(self, stats: SimulationStats) -> None:
        """Called when simulation ends."""
        ...


# Implementations are plain classes, not subclasses
class VerboseOutput:
    """Rich console output for verbose mode."""

    def __init__(self, console: Console, event_filter: EventFilter | None = None) -> None:
        self._console = console
        self._filter = event_filter

    def on_tick_complete(self, result: TickResult, provider: StateProvider) -> None:
        self._console.print(f"Tick {result.tick}: {result.settlements} settlements")
        for event in self._filter_events(result.events):
            self._console.print(f"  {event['event_type']}")

    def on_simulation_complete(self, stats: SimulationStats) -> None:
        self._console.print(f"Complete: {stats.total_settlements} total settlements")

    def _filter_events(self, events: list[dict[str, str | int | float]]) -> list[dict[str, str | int | float]]:
        if self._filter is None:
            return events
        return [e for e in events if self._filter.matches(e)]


class JsonStreamOutput:
    """JSONL output for streaming mode."""

    def on_tick_complete(self, result: TickResult, provider: StateProvider) -> None:
        print(json.dumps({"type": "tick", "data": result.__dict__}))

    def on_simulation_complete(self, stats: SimulationStats) -> None:
        print(json.dumps({"type": "complete", "data": stats.__dict__}))
```

---

## Typer CLI Commands

Use the `Annotated` pattern for all CLI commands.

```python
from typing import Annotated
from pathlib import Path
import typer


def run_command(
    config: Annotated[Path, typer.Argument(help="Path to YAML config file")],
    persist: Annotated[Path | None, typer.Option("--persist", "-p", help="Database path for persistence")] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose output")] = False,
    days: Annotated[int | None, typer.Option("--days", "-d", help="Override number of days")] = None,
    seed: Annotated[int | None, typer.Option("--seed", "-s", help="Override RNG seed")] = None,
) -> None:
    """Run a payment simulation from configuration file."""
    ...
```

---

## Pydantic Models

Use Pydantic v2 patterns with Field descriptions.

```python
from pydantic import BaseModel, ConfigDict, Field


class AgentConfig(BaseModel):
    """Configuration for a single agent (bank)."""

    model_config = ConfigDict(strict=True)

    id: str = Field(..., pattern=r"^[A-Z0-9_]+$", description="Agent identifier (uppercase)")
    balance: int = Field(..., ge=0, description="Opening balance in cents")
    credit_limit: int = Field(0, ge=0, description="Credit limit in cents")


class TransactionConfig(BaseModel):
    """Initial transaction configuration."""

    model_config = ConfigDict(strict=True)

    tx_id: str = Field(..., description="Unique transaction ID")
    sender_id: str = Field(..., description="Sender agent ID")
    receiver_id: str = Field(..., description="Receiver agent ID")
    amount: int = Field(..., gt=0, description="Amount in cents")
    arrival_tick: int = Field(0, ge=0, description="Tick when transaction arrives")
    deadline_tick: int | None = Field(None, ge=0, description="Settlement deadline tick")


class SimulationConfigSchema(BaseModel):
    """Top-level simulation configuration schema."""

    model_config = ConfigDict(strict=True)

    ticks_per_day: int = Field(..., ge=1, le=1000, description="Ticks per simulated day")
    num_days: int = Field(1, ge=1, description="Number of days to simulate")
    seed: int = Field(..., description="RNG seed for determinism")
    agents: list[AgentConfig] = Field(..., min_length=2, description="Agent configurations")
    initial_transactions: list[TransactionConfig] = Field(default_factory=list)
```

---

## FFI Safety Patterns

### Validate Before Crossing FFI

```python
def create_orchestrator(config: SimulationConfigSchema) -> Orchestrator:
    """Create Rust orchestrator from validated config."""
    # Config is already validated by Pydantic
    config_dict = config.model_dump()

    try:
        return Orchestrator.new(config_dict)
    except ValueError as e:
        raise ConfigurationError(f"Rust rejected configuration: {e}") from e
    except Exception as e:
        raise RuntimeError(f"FFI initialization failed: {e}") from e
```

### Wrap FFI Calls with Proper Error Handling

```python
class OrchestratorWrapper:
    """Safe wrapper around Rust FFI."""

    def __init__(self, orchestrator: Orchestrator) -> None:
        self._orch = orchestrator

    def tick(self) -> TickResult:
        """Execute one simulation tick."""
        try:
            raw = self._orch.tick()
            return TickResult(
                tick=raw["tick"],
                day=raw["day"],
                arrivals=raw["arrivals"],
                settlements=raw["settlements"],
                queue_depth=raw["queue_depth"],
                events=raw["events"],
            )
        except Exception as e:
            raise SimulationError(f"Tick execution failed: {e}") from e

    def get_state(self) -> SimulationState:
        """Get current simulation state snapshot."""
        try:
            raw = self._orch.get_state()
            return SimulationState(
                current_tick=raw["current_tick"],
                agents=[AgentState(**a) for a in raw["agents"]],
            )
        except Exception as e:
            raise SimulationError(f"Failed to get state: {e}") from e
```

### Never Cache Rust State

```python
# Wrong - stale data
class BadManager:
    def __init__(self, orch: Orchestrator) -> None:
        self._state = orch.get_state()  # Cached once, stale forever

    def get_balance(self, agent_id: str) -> int:
        return self._state["agents"][agent_id]["balance"]  # STALE!


# Correct - always query fresh
class GoodManager:
    def __init__(self, orch: Orchestrator) -> None:
        self._orch = orch

    def get_balance(self, agent_id: str) -> int:
        state = self._orch.get_state()  # Fresh each time
        return state["agents"][agent_id]["balance"]
```

---

## Project Structure

```
api/
├── payment_simulator/
│   ├── __init__.py
│   ├── _core.py                  # Rust FFI re-exports
│   ├── backends.py               # Rust backend wrapper
│   │
│   ├── api/                      # FastAPI routes
│   │   └── main.py
│   │
│   ├── cli/                      # CLI layer
│   │   ├── main.py               # Typer app entry point
│   │   ├── output.py             # Rich console utilities
│   │   ├── filters.py            # EventFilter
│   │   │
│   │   ├── commands/             # CLI commands
│   │   │   ├── run.py
│   │   │   ├── replay.py
│   │   │   ├── checkpoint.py
│   │   │   └── db.py
│   │   │
│   │   └── execution/            # Simulation execution
│   │       ├── runner.py         # SimulationRunner
│   │       ├── strategies.py     # OutputStrategy implementations
│   │       ├── persistence.py    # PersistenceManager
│   │       ├── stats.py          # TickResult, SimulationStats
│   │       ├── state_provider.py # StateProvider protocol
│   │       └── display.py        # Shared display logic
│   │
│   ├── config/                   # Configuration
│   │   ├── schemas.py            # Pydantic models
│   │   └── loader.py             # YAML loading
│   │
│   └── persistence/              # Database layer
│       ├── models.py             # Pydantic models (schema source)
│       ├── connection.py         # DatabaseManager
│       ├── writers.py            # Batch write functions
│       ├── queries.py            # Query functions
│       └── migrations.py         # MigrationManager
│
├── tests/
│   ├── unit/                     # Pure Python tests
│   └── integration/              # FFI boundary tests
│
└── pyproject.toml
```

---

## Tool Configuration

### mypy (pyproject.toml)

```toml
[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
```

### ruff (pyproject.toml)

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = [
    "E", "W",   # pycodestyle
    "F",        # pyflakes
    "I",        # isort
    "UP",       # pyupgrade
    "B",        # bugbear
    "ANN",      # annotations
    "C4",       # comprehensions
    "RUF",      # ruff-specific
]
ignore = ["ANN101", "ANN102"]  # self/cls annotations
```

---

## Development Commands

```bash
# Setup (builds Rust + installs deps)
uv sync --extra dev

# After Rust changes
uv sync --extra dev --reinstall-package payment-simulator

# Type checking (MUST pass)
.venv/bin/python -m mypy payment_simulator/

# Linting (MUST pass)
.venv/bin/python -m ruff check payment_simulator/

# Format
.venv/bin/python -m ruff format payment_simulator/

# Tests
.venv/bin/python -m pytest

# Coverage
.venv/bin/python -m pytest --cov=payment_simulator --cov-report=html
```

---

## Anti-Patterns

### Using `Any` When Type Is Known

```python
# Wrong
def tick(self) -> Any:
    return self._orch.tick()

# Correct - define the return type
def tick(self) -> TickResult:
    return TickResult(**self._orch.tick())
```

### Bare Generic Types

```python
# Wrong
def get_agents(self) -> list:
    ...

def get_config(self) -> dict:
    ...

# Correct
def get_agents(self) -> list[AgentState]:
    ...

def get_config(self) -> dict[str, str | int | bool]:
    ...
```

### Deep Inheritance Hierarchies

```python
# Wrong - inheritance chain
class BaseHandler:
    def handle(self) -> None: ...

class ExtendedHandler(BaseHandler):
    def handle(self) -> None: ...

class SpecialHandler(ExtendedHandler):
    def handle(self) -> None: ...


# Correct - protocol + composition
class Handler(Protocol):
    def handle(self) -> None: ...

class SpecialHandler:
    def __init__(self, helper: Helper) -> None:
        self._helper = helper

    def handle(self) -> None:
        self._helper.do_work()
```

### Float Money

```python
# Wrong - NEVER use float for money
balance: float = 1000.50

# Correct - always integer cents
balance: int = 100050  # $1,000.50
```

---

## Checklist Before Committing

- [ ] All functions have complete type annotations (params + return)
- [ ] No bare `list`, `dict`, `set` without type arguments
- [ ] No `Any` where a specific type is known
- [ ] Using `str | None` not `Optional[str]`
- [ ] Using `list[str]` not `List[str]`
- [ ] Typer commands use `Annotated` pattern
- [ ] mypy passes: `.venv/bin/python -m mypy payment_simulator/`
- [ ] ruff passes: `.venv/bin/python -m ruff check payment_simulator/`
- [ ] Tests pass: `.venv/bin/python -m pytest`
- [ ] All money values are `int` (cents, never floats)

---

*Last updated: 2025-11-28*
*For Rust patterns, see `/backend/CLAUDE.md`*
*For project overview, see root `/CLAUDE.md`*
