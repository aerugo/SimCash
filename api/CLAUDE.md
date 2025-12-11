# Python API Layer - Style Guide & Architecture

## Overview

This is the **Python middleware layer** for the payment simulator. It provides CLI tools, FastAPI endpoints, configuration validation, and persistence.

**Key Principle**: Python orchestrates; Rust computes. Keep FFI minimal, validate early, and maintain strict type safety throughout.

> 📖 **Essential Reading**: Before working on this codebase, read [`docs/reference/patterns-and-conventions.md`](/docs/reference/patterns-and-conventions.md) for all critical invariants and patterns.

---

## 🔴 Documentation Requirements

### Reference Documentation is Mandatory

The `docs/reference/` directory contains the authoritative documentation for this project. **You MUST consult and maintain this documentation.**

**Reference Structure:**
```
docs/reference/
├── architecture/     # System architecture docs
├── cli/              # CLI command documentation
│   ├── commands/     # Per-command reference (run, replay, db, etc.)
│   ├── exit-codes.md
│   └── output-modes.md
├── orchestrator/     # Rust orchestrator internals
├── policy/           # Policy system reference
│   ├── index.md      # Policy overview
│   ├── nodes.md      # Node types
│   ├── actions.md    # Available actions
│   └── ...
└── scenario/         # Scenario configuration docs
```

### Before Starting Any Work

**ALWAYS read the relevant reference docs first:**

1. **Adding/modifying a CLI command?** → Read `docs/reference/cli/commands/<command>.md`
2. **Working on policies?** → Read `docs/reference/policy/index.md` and related files
3. **Changing orchestrator behavior?** → Read `docs/reference/orchestrator/`
4. **Modifying configuration?** → Read `docs/reference/scenario/`

### After Completing Any Work

**ALWAYS update the relevant reference docs:**

1. **Changed function signatures?** → Update the reference doc
2. **Added new CLI options?** → Update `docs/reference/cli/commands/<command>.md`
3. **Modified event types?** → Update orchestrator docs
4. **Changed config schema?** → Update scenario docs

### Documentation Update Workflow

```bash
# 1. Before starting work, read relevant docs
cat docs/reference/cli/commands/run.md

# 2. Make your code changes
# ...

# 3. Update the reference documentation
# Edit docs/reference/... to reflect your changes

# 4. Commit both code AND docs together
git add api/payment_simulator/cli/commands/run.py docs/reference/cli/commands/run.md
git commit -m "feat: Add --foo option to run command"
```

### Documentation Principles

- **Reference docs are the source of truth** for behavior, not code comments
- **Keep docs in sync with code** - stale docs are worse than no docs
- **Document the "what" and "why"**, not implementation details
- **Include examples** for non-obvious features

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

### Private Methods Need Return Types Too

**All methods** need explicit return types, including private/internal methods. Pylance catches missing return types that mypy may miss.

```python
# Wrong - Pylance reports dict[Unknown, Unknown]
def _to_ffi_dict(self, obj: SomeModel) -> dict:
    return {"type": obj.type, "value": obj.value}

# Correct - explicit return type
def _to_ffi_dict(self, obj: SomeModel) -> dict[str, str | int]:
    return {"type": obj.type, "value": obj.value}

# Better - use TypedDict for complex shapes
class FfiDict(TypedDict):
    type: str
    value: int

def _to_ffi_dict(self, obj: SomeModel) -> FfiDict:
    return {"type": obj.type, "value": obj.value}
```

### Use Match Statements for Union Type Dispatch

When converting union types, prefer `match` statements over `isinstance` chains. This provides exhaustiveness checking and cleaner code.

```python
# Acceptable but verbose - isinstance chains
def _policy_to_dict(self, policy: PolicyConfig) -> dict[str, str | int]:
    if isinstance(policy, FifoPolicy):
        return {"type": "Fifo"}
    elif isinstance(policy, DeadlinePolicy):
        return {"type": "Deadline", "threshold": policy.urgency_threshold}
    else:
        raise ValueError(f"Unknown policy: {type(policy)}")

# Better - match statement with exhaustiveness
def _policy_to_dict(self, policy: PolicyConfig) -> dict[str, str | int]:
    match policy:
        case FifoPolicy():
            return {"type": "Fifo"}
        case DeadlinePolicy(urgency_threshold=threshold):
            return {"type": "Deadline", "threshold": threshold}
        case _:
            # This catches any unhandled types at runtime
            raise ValueError(f"Unknown policy: {type(policy)}")
```

**Note**: When using isinstance for type narrowing that Pylance already infers, consider if the check is necessary. Unnecessary isinstance calls indicate the type is already narrowed.

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

## 🎯 Replay Identity Pattern

**Critical Invariant**: `payment-sim replay` output MUST be byte-for-byte identical to `payment-sim run` output (modulo timing).

### StateProvider Pattern

Both run and replay modes use the same display code through the `StateProvider` abstraction:

```python
# Display code uses StateProvider - works for BOTH run and replay
def display_tick_verbose_output(provider: StateProvider, tick: int) -> None:
    events = provider.get_events_for_tick(tick)
    for event in events:
        display_event(event)

# Run mode: uses OrchestratorStateProvider (live FFI)
# Replay mode: uses DatabaseStateProvider (persisted data)
```

### When Adding New Display Logic

1. **ALWAYS use StateProvider** - never access FFI or database directly from display code
2. **Add methods to StateProvider protocol** if you need new data access patterns
3. **Implement in BOTH providers** - OrchestratorStateProvider and DatabaseStateProvider
4. **Test with both run and replay** - verify identical output

### What NOT To Do

```python
# ❌ WRONG - Only works in run mode, bypasses abstraction
def display_balance(orch: Orchestrator, agent_id: str) -> None:
    balance = orch.get_agent_balance(agent_id)  # Direct FFI access!
    print(f"Balance: {balance}")

# ✅ CORRECT - Works in both modes
def display_balance(provider: StateProvider, agent_id: str) -> None:
    balance = provider.get_agent_balance(agent_id)  # Abstracted
    print(f"Balance: {balance}")
```

See `docs/reference/patterns-and-conventions.md` for the complete event workflow.

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

### pyright / Pylance (pyproject.toml)

```toml
[tool.pyright]
pythonVersion = "3.11"
pythonPlatform = "Linux"
include = ["payment_simulator"]
exclude = ["**/node_modules", "**/__pycache__", ".venv", "build", "dist"]
typeCheckingMode = "standard"
# Suppress noisy errors for Rust FFI module
reportMissingTypeStubs = false
reportUnknownMemberType = false
reportUnknownVariableType = false
reportUnknownArgumentType = false
# Useful warnings
reportPrivateUsage = "warning"
reportUnnecessaryTypeIgnoreComment = "warning"
reportUnusedImport = "warning"
reportUnusedVariable = "warning"
```

**Note**: VS Code Pylance also reads `pyrightconfig.json` if present. Both are provided in this project.

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

# Type checking with mypy (MUST pass)
.venv/bin/python -m mypy payment_simulator/

# Type checking with pyright (matches VS Code Pylance)
.venv/bin/python -m pyright payment_simulator/

# Linting (MUST pass)
.venv/bin/python -m ruff check payment_simulator/

# Format
.venv/bin/python -m ruff format payment_simulator/

# Tests
.venv/bin/python -m pytest

# Coverage
.venv/bin/python -m pytest --cov=payment_simulator --cov-report=html
```

### Type Checking: mypy vs pyright

This project uses **both** mypy and pyright for type checking:

| Tool | Purpose | When to Use |
|------|---------|-------------|
| **mypy** | Traditional Python type checker | CI/CD, pre-commit hooks |
| **pyright** | Pylance's underlying engine | Match VS Code Pylance errors |

**Why both?** VS Code's Pylance extension uses pyright internally. If you see errors in VS Code that mypy doesn't catch, run pyright to reproduce them in the terminal.

```bash
# See the same errors as VS Code Pylance
.venv/bin/python -m pyright payment_simulator/

# Pyright with watch mode (re-checks on file changes)
.venv/bin/python -m pyright --watch payment_simulator/
```

**Configuration**: Both tools read from `pyproject.toml`:
- mypy: `[tool.mypy]` section
- pyright: `[tool.pyright]` section (also used by Pylance)

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

### Documentation (REQUIRED)
- [ ] Read relevant `docs/reference/` docs before starting
- [ ] Updated `docs/reference/` to reflect any changes
- [ ] Code and docs committed together

### Type Safety
- [ ] All functions have complete type annotations (params + return)
- [ ] No bare `list`, `dict`, `set` without type arguments
- [ ] No `Any` where a specific type is known
- [ ] Using `str | None` not `Optional[str]`
- [ ] Using `list[str]` not `List[str]`
- [ ] Typer commands use `Annotated` pattern

### Verification
- [ ] mypy passes: `.venv/bin/python -m mypy payment_simulator/`
- [ ] pyright passes: `.venv/bin/python -m pyright payment_simulator/`
- [ ] ruff passes: `.venv/bin/python -m ruff check payment_simulator/`
- [ ] Tests pass: `.venv/bin/python -m pytest`
- [ ] All money values are `int` (cents, never floats)

---

## 🎯 Proactive Agent Delegation

**IMPORTANT**: Before answering questions directly, check if a specialized agent should handle the task.

### docs-navigator — DELEGATE FIRST for Documentation Questions

**Trigger immediately when user asks:**
- "Where is X documented?" or "How do I use X?"
- Questions about CLI commands, configuration, or workflows
- Finding reference docs in `docs/reference/`
- Understanding the documentation structure

**Agent file**: `.claude/agents/docs-navigator.md`

### Python-Specific Agents

| Agent | Trigger When | File |
|-------|--------------|------|
| **python-stylist** | Type annotations, Pydantic patterns, modern Python idioms | `.claude/agents/python-stylist.md` |
| **ffi-specialist** | PyO3 patterns, Rust↔Python boundary issues | `.claude/agents/ffi-specialist.md` |
| **test-engineer** | Writing pytest tests, test strategy, mocking | `.claude/agents/test-engineer.md` |

### How to Use

Read the agent file for specialized context before answering:
```bash
.claude/agents/docs-navigator.md  # For documentation questions
.claude/agents/python-stylist.md  # For Python typing questions
```

---

*Last updated: 2025-12-11*
*For consolidated patterns and invariants, see `docs/reference/patterns-and-conventions.md`*
*For Rust patterns, see `/simulator/CLAUDE.md`*
*For project overview, see root `/CLAUDE.md`*
