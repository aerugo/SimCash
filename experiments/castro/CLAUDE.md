# Castro Experiments - Style Guide & Architecture

## Overview

This is the **Castro experiments module** implementing Castro et al. (2025) LLM-based policy optimization experiments. It uses the `ai_cash_mgmt` module from the main payment-simulator package.

**Key Principle**: This module MUST follow the same strict typing and linting conventions as the main `api/` codebase. All code must pass mypy, pyright, and ruff checks.

> **Essential Reading**: See the root `/CLAUDE.md` for project-wide invariants (i64 money, determinism, FFI safety).

---

## 🔴 Critical Rules

### 1. Always Use UV for Package Management

**NEVER use pip directly. Always use Astral UV.**

```bash
# Correct - use UV
cd experiments/castro
uv sync
uv sync --extra dev

# Wrong - NEVER do this
pip install -e .
pip install -r requirements.txt
```

### 2. Strict Typing is MANDATORY

All Python code MUST have complete type annotations. This matches the `api/` codebase requirements.

```python
# Correct - complete types
def process(items: list[str], lookup: dict[str, int]) -> list[int]:
    return [lookup[item] for item in items]

def find_user(user_id: str) -> User | None:
    return users.get(user_id)

# Wrong - missing or incomplete types
def process(items, lookup):  # NO!
    return [lookup[item] for item in items]

def get_data() -> dict:  # NO! Bare dict
    return {}
```

### 3. Money is Always i64 (Integer Cents)

All costs, amounts, and financial values are `int` representing cents. NEVER use float for money.

```python
# Correct
total_cost: int = 150000  # $1,500.00

# Wrong
total_cost: float = 1500.00  # NEVER floats for money
```

---

## Python Style Guide

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

### Avoid `Any` When Type Is Known

When a return type would be `Any` or unknown, define a proper type.

```python
# Wrong - leaks unknown type
def get_result(self) -> dict[str, Any]:  # Any is a code smell
    return self._orch.tick()

# Better - define the shape
class TickResult(TypedDict):
    tick: int
    arrivals: int
    settlements: int

def get_result(self) -> TickResult:
    return self._orch.tick()
```

### Use Union Syntax, Not Optional

```python
# Correct
def find(id: str) -> User | None:
    ...

# Wrong
from typing import Optional
def find(id: str) -> Optional[User]: ...
```

### Private Methods Need Return Types Too

**All methods** need explicit return types, including private/internal methods.

```python
# Wrong - missing return type
def _convert_to_dict(self, model: SomeModel) -> dict:
    return {"type": model.type, "value": model.value}

# Correct - explicit type arguments
def _convert_to_dict(self, model: SomeModel) -> dict[str, str | int]:
    return {"type": model.type, "value": model.value}
```

---

## Typer CLI Pattern

Use the `Annotated` pattern for all CLI commands (as in `cli.py`).

```python
from typing import Annotated
from pathlib import Path
import typer


def run(
    config: Annotated[Path, typer.Argument(help="Config file path")],
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Output path")] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Verbose output")] = False,
) -> None:
    """Run the experiment."""
    ...
```

---

## Dataclasses for Value Objects

Use dataclasses instead of dicts for structured data.

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class SimulationConfig:
    """Immutable simulation configuration."""
    total_ticks: int
    ticks_per_day: int
    num_days: int


@dataclass
class ExperimentResult:
    """Result of running an experiment."""
    experiment_name: str
    final_cost: int  # Always int cents!
    best_cost: int
    num_iterations: int
    converged: bool
```

---

## Verbose Logging Module

The `verbose_logging.py` module provides structured verbose output for experiment runs. It uses dataclasses for type-safe data transfer and Rich for formatted console output.

### Configuration

```python
from castro.verbose_logging import VerboseConfig, VerboseLogger

# Enable all verbose output
config = VerboseConfig.all()

# Enable specific flags
config = VerboseConfig(policy=True, monte_carlo=True)

# Create from CLI flags (--verbose enables all)
config = VerboseConfig.from_flags(
    verbose=True,           # Enables all if no individual flags
    verbose_policy=None,    # Individual override
    verbose_monte_carlo=None,
    verbose_llm=None,
    verbose_rejections=None,
)
```

### Data Types

```python
from castro.verbose_logging import (
    MonteCarloSeedResult,
    LLMCallMetadata,
    RejectionDetail,
)

# Monte Carlo result per seed
result = MonteCarloSeedResult(
    seed=12345,
    cost=150000,  # cents!
    settled=95,
    total=100,
    settlement_rate=0.95,
)

# LLM call metadata
metadata = LLMCallMetadata(
    agent_id="BANK_A",
    model="claude-sonnet-4-5-20250929",
    prompt_tokens=1500,
    completion_tokens=200,
    latency_seconds=2.3,
    context_summary={"current_cost": 150000, "iteration": 5},
)

# Rejection details
rejection = RejectionDetail(
    agent_id="BANK_A",
    proposed_policy={"parameters": {"threshold": -1.0}},  # Invalid
    validation_errors=["threshold must be >= 0"],
    rejection_reason="validation_failed",
)
```

### Usage in Runner

```python
from castro.verbose_logging import VerboseConfig, VerboseLogger

class ExperimentRunner:
    def __init__(self, experiment, verbose_config: VerboseConfig | None = None):
        self._verbose = VerboseLogger(verbose_config or VerboseConfig())

    async def run(self) -> ExperimentResult:
        # Log iteration start
        self._verbose.log_iteration_start(iteration, total_cost)

        # Log Monte Carlo results
        self._verbose.log_monte_carlo_evaluation(seed_results, mean, std)

        # Log LLM call
        self._verbose.log_llm_call(metadata)

        # Log policy change
        self._verbose.log_policy_change(
            agent_id, old_policy, new_policy, old_cost, new_cost, accepted
        )

        # Log rejection
        self._verbose.log_rejection(rejection_detail)
```

---

## Project Structure

```
experiments/castro/
├── CLAUDE.md                    # You are here
├── pyproject.toml               # Build config with strict typing
├── cli.py                       # Typer CLI entry point
├── castro/
│   ├── __init__.py              # Package exports
│   ├── constraints.py           # Castro-aligned constraints
│   ├── experiments.py           # Experiment definitions
│   ├── llm_client.py            # LLM client implementation
│   ├── runner.py                # Experiment runner
│   ├── simulation.py            # Simulation wrapper
│   └── verbose_logging.py       # Verbose output logging
├── configs/                     # YAML scenario configs
│   ├── exp1_2period.yaml
│   ├── exp2_12period.yaml
│   └── exp3_joint.yaml
├── tests/
│   ├── test_experiments.py
│   └── test_verbose_logging.py  # Verbose logging tests
└── results/                     # Output directory
```

---

## Development Commands

```bash
# Setup environment (ALWAYS use UV, never pip!)
cd experiments/castro
uv sync --extra dev

# Type checking with mypy (MUST pass)
uv run mypy castro/ cli.py

# Type checking with pyright (matches VS Code Pylance)
uv run pyright castro/ cli.py

# Linting (MUST pass)
uv run ruff check castro/ cli.py

# Format
uv run ruff format castro/ cli.py

# Run tests
uv run pytest

# Run experiments
uv run castro run exp1
uv run castro list
```

---

## Tool Configuration

### mypy

Configured in `pyproject.toml` with strict mode:

```toml
[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_ignores = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
no_implicit_optional = true
```

### pyright

Configured to match VS Code Pylance:

```toml
[tool.pyright]
pythonVersion = "3.11"
include = ["castro", "cli.py"]
typeCheckingMode = "standard"
```

### ruff

Includes ANN rules for annotation enforcement:

```toml
[tool.ruff.lint]
select = ["E", "W", "F", "I", "N", "UP", "B", "C4", "ANN", "S", "RUF"]
ignore = ["ANN101", "ANN102"]  # self/cls don't need annotations
```

---

## Anti-Patterns (Don't Do These)

### Using pip Instead of UV

```bash
# WRONG
pip install -e .
pip install anthropic

# CORRECT
uv sync
uv add anthropic
```

### Float for Money

```python
# WRONG
cost: float = 1500.00

# CORRECT
cost: int = 150000  # cents
```

### Bare Generic Types

```python
# WRONG
def get_agents(self) -> list:
    ...

def get_config(self) -> dict:
    ...

# CORRECT
def get_agents(self) -> list[AgentState]:
    ...

def get_config(self) -> dict[str, str | int | bool]:
    ...
```

### Legacy typing Imports

```python
# WRONG
from typing import List, Dict, Optional, Union

# CORRECT
# Just use list[str], dict[str, int], str | None directly
```

---

## Checklist Before Committing

### Type Safety
- [ ] All functions have complete type annotations (params + return)
- [ ] No bare `list`, `dict`, `set` without type arguments
- [ ] No `Any` where a specific type is known
- [ ] Using `str | None` not `Optional[str]`
- [ ] Using `list[str]` not `List[str]`
- [ ] Typer commands use `Annotated` pattern

### Verification
- [ ] mypy passes: `uv run mypy castro/ cli.py`
- [ ] pyright passes: `uv run pyright castro/ cli.py`
- [ ] ruff passes: `uv run ruff check castro/ cli.py`
- [ ] Tests pass: `uv run pytest`
- [ ] All money values are `int` (cents, never floats)

---

*Last updated: 2025-12-09*
*For project-wide patterns, see root `/CLAUDE.md`*
*For main API patterns, see `/api/CLAUDE.md`*
