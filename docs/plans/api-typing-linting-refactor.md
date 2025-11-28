# API Typing, Linting, and Static Type Checking Refactoring Plan

**Created**: 2025-11-28
**Status**: Planning
**Priority**: High
**Estimated Effort**: Medium (2-3 sessions)

---

## Overview

This plan outlines the comprehensive refactoring of the `/api` Python codebase to comply with company styleguide requirements for strict typing, linting, and static type checking.

### Goals

1. Add complete type annotations to all Python functions
2. Configure and enforce mypy static type checking
3. Configure and enforce ruff linting
4. Establish patterns for ongoing compliance

### Current State Analysis

**Well-Typed Modules (80%+ coverage):**
- `persistence/` - All files fully typed (exemplary patterns)
- `config/` - All files fully typed
- `cli/execution/` - All files fully typed
- `cli/output.py` - Fully typed
- `cli/filters.py` - Fully typed
- `cli/main.py` - Fully typed

**Modules Needing Work (< 50% coverage):**
- `cli/commands/run.py` - Helper functions lack types (~400 lines)
- `cli/commands/replay.py` - Reconstruction functions untyped (~300 lines)
- `cli/commands/db.py` - Typer commands need `Annotated` (~400 lines)
- `cli/commands/checkpoint.py` - Typer commands need `Annotated` (~360 lines)
- `cli/commands/policy_schema.py` - Minimal typing (~50 lines)
- `cli/commands/validate_policy.py` - Partially typed (~380 lines)
- `api/main.py` - Minimal, needs review (~30 lines)

---

## Phase 1: Configuration Setup

### 1.1 Add Tool Configuration to pyproject.toml

Add the following sections to `api/pyproject.toml`:

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

# Gradual migration: start permissive, tighten later
[[tool.mypy.overrides]]
module = "payment_simulator.cli.commands.*"
disallow_untyped_defs = false

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # pyflakes
    "I",      # isort
    "N",      # pep8-naming
    "UP",     # pyupgrade
    "B",      # flake8-bugbear
    "C4",     # flake8-comprehensions
    "ANN",    # flake8-annotations
    "S",      # flake8-bandit (security)
    "RUF",    # ruff-specific rules
]
ignore = [
    "ANN101",  # Missing type annotation for self
    "ANN102",  # Missing type annotation for cls
    "ANN401",  # Dynamically typed expressions (Any) - temporary
]

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["ANN", "S101"]  # Tests: no annotations required, allow assert

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
line-ending = "auto"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --tb=short"
markers = [
    "integration: integration tests",
    "unit: unit tests",
]
```

### 1.2 Add Dev Dependencies

Ensure `pyproject.toml` includes:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "mypy>=1.8.0",
    "ruff>=0.3.0",
    "types-PyYAML",      # Type stubs for PyYAML
    "types-requests",    # Type stubs for requests (if used)
]
```

### 1.3 Verification Commands

Add to development workflow:

```bash
# Install dev dependencies
cd api
uv sync --extra dev

# Run type checker
.venv/bin/python -m mypy payment_simulator/

# Run linter
.venv/bin/python -m ruff check payment_simulator/

# Auto-fix linting issues
.venv/bin/python -m ruff check --fix payment_simulator/

# Format code
.venv/bin/python -m ruff format payment_simulator/
```

---

## Phase 2: High-Priority Module Refactoring

### 2.1 `cli/commands/db.py` (~400 lines)

**Current Issues:**
- Typer commands use direct `typer.Option()` instead of `Annotated`
- Helper functions `_extract_policy_names`, `_collect_event_based_cost_data`, `_generate_cost_chart_png` need parameter and return types

**Required Changes:**

```python
# BEFORE
@db_app.command("init")
def db_init(
    db_path: str = typer.Option(
        "simulation_data.db",
        "--db-path",
        "-d",
        help="Path to database file",
    ),
):
    ...

# AFTER
from typing_extensions import Annotated

@db_app.command("init")
def db_init(
    db_path: Annotated[str, typer.Option(
        "--db-path",
        "-d",
        help="Path to database file",
    )] = "simulation_data.db",
) -> None:
    ...
```

**Helper Functions to Type:**

```python
def _extract_policy_names(config_json: str) -> dict[str, str]:
    """Extract policy names from simulation config JSON."""
    ...

def _collect_event_based_cost_data(
    conn: duckdb.DuckDBPyConnection,
    simulation_id: str,
    agent_ids: list[str],
    ticks_per_day: int,
    num_days: int,
) -> list[dict[str, Any]]:
    """Collect tick-level cost data from simulation events."""
    ...

def _generate_cost_chart_png(
    tick_costs: list[dict[str, Any]],
    agent_ids: list[str],
    simulation_id: str,
    ticks_per_day: int,
    output_path: str,
    show_per_tick: bool = False,
    quiet: bool = False,
    policy_names: dict[str, str] | None = None,
    max_y: int | None = None,
) -> None:
    """Generate a PNG cost chart from tick-level cost data."""
    ...
```

### 2.2 `cli/commands/checkpoint.py` (~360 lines)

**Current Issues:**
- Same Typer command pattern issues as db.py
- Helper function `get_database_manager()` needs return type

**Required Changes:**

```python
# Add return type to helper
def get_database_manager() -> DatabaseManager:
    """Get database manager with configured path."""
    ...

# Update all command signatures
@checkpoint_app.command(name="save")
def save_checkpoint(
    simulation_id: Annotated[str, typer.Option(
        "--simulation-id", "-s",
        help="Simulation ID for this checkpoint"
    )],
    state_file: Annotated[Path, typer.Option(
        "--state-file", "-f",
        help="Path to state JSON file"
    )],
    config_file: Annotated[Path, typer.Option(
        "--config", "-c",
        help="Path to simulation config YAML"
    )],
    description: Annotated[str | None, typer.Option(
        "--description", "-d",
        help="Human-readable description"
    )] = None,
    checkpoint_type: Annotated[str, typer.Option(
        "--type", "-t",
        help="Checkpoint type"
    )] = "manual",
) -> None:
    ...
```

### 2.3 `cli/commands/run.py` (~400 lines)

**Current Issues:**
- Large file with many helper functions
- Some functions have partial typing, need completion

**Functions Needing Types:**

```python
def _create_output_strategy(
    mode: str,
    event_filter: EventFilter | None,
    state_provider: StateProvider | None,
    persist: bool,
    full_replay: bool,
    quiet: bool,
    console: Console,
) -> OutputStrategy:
    """Factory function for output strategies."""
    ...

def _persist_final_metadata(
    persistence: PersistenceManager,
    config_path: Path | str,
    config_dict: dict[str, Any],
    ffi_dict: dict[str, Any],
    agent_ids: list[str],
    total_arrivals: int,
    total_settlements: int,
    total_costs: int,
    duration: float,
    orch: Orchestrator,
) -> None:
    """Persist final simulation metadata after run completes."""
    ...
```

### 2.4 `cli/commands/replay.py` (~300 lines)

**Current Issues:**
- Event reconstruction helper functions lack types
- Some database query results need type hints

**Functions Needing Types:**

```python
def _reconstruct_arrival_events_from_simulation_events(
    events: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Reconstruct arrival events from simulation events."""
    ...

def _get_tick_events_from_db(
    conn: duckdb.DuckDBPyConnection,
    simulation_id: str,
    tick: int,
) -> list[dict[str, Any]]:
    """Get events for a specific tick from database."""
    ...
```

### 2.5 `cli/commands/validate_policy.py` (~380 lines)

**Current State:**
- Already uses `Annotated` for main command (good!)
- Helper functions need typing

**Functions Needing Types:**

```python
def _output_error(
    format: OutputFormat,
    message: str,
    error_type: str
) -> None:
    """Output an error message."""
    ...

def _output_json(
    result: dict[str, Any],
    functional_test_result: dict[str, Any] | None = None
) -> None:
    """Output validation results as JSON."""
    ...

def _output_text(
    result: dict[str, Any],
    policy_file: Path,
    verbose: bool,
    functional_test_result: dict[str, Any] | None = None
) -> None:
    """Output validation results as human-readable text."""
    ...

def _show_policy_details(result: dict[str, Any]) -> None:
    """Show detailed policy information."""
    ...

def _run_functional_tests(
    policy_file: Path,
    policy_content: str,
    validation_result: dict[str, Any],
    scenario: Path | None,
    verbose: bool,
) -> dict[str, Any]:
    """Run functional tests against the policy."""
    ...

def _show_functional_test_results(result: dict[str, Any]) -> None:
    """Display functional test results."""
    ...
```

### 2.6 `cli/commands/policy_schema.py` (~50 lines)

**Current Issues:**
- Small file, but Typer command needs `Annotated`
- Likely a simple fix

**Required Changes:**

```python
from typing_extensions import Annotated

def policy_schema(
    output: Annotated[Path | None, typer.Option(
        "--output", "-o",
        help="Output file path"
    )] = None,
) -> None:
    """Generate policy JSON schema documentation."""
    ...
```

### 2.7 `api/main.py` (~30 lines)

**Current Issues:**
- FastAPI integration file, minimal code
- May need route return types

**Required Changes:**
- Add return types to any routes
- Ensure type safety for request/response models

---

## Phase 3: Fix `cli/execution/display.py`

**Known Issue (Line 25-26):**
```python
# Current
event_filter: Any = None

# Should be
event_filter: EventFilter | None = None
```

This is a quick fix in an otherwise well-typed module.

---

## Phase 4: Gradual Migration to Strict Mode

### 4.1 Initial Relaxed Overrides

Start with permissive mypy overrides in `pyproject.toml`:

```toml
[[tool.mypy.overrides]]
module = "payment_simulator.cli.commands.*"
disallow_untyped_defs = false
```

### 4.2 Module-by-Module Tightening

After fixing each module, remove it from the override list:

```toml
# After fixing db.py, checkpoint.py, etc:
[[tool.mypy.overrides]]
module = [
    "payment_simulator.cli.commands.policy_schema",  # Still needs work
]
disallow_untyped_defs = false
```

### 4.3 Final Strict Mode

Once all modules are typed, enable full strict mode:

```toml
[tool.mypy]
strict = true

# Remove all per-module overrides
```

---

## Phase 5: CI Integration

### 5.1 Pre-commit Hook (Optional)

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: mypy
        name: mypy
        entry: .venv/bin/python -m mypy
        language: system
        types: [python]
        files: ^api/payment_simulator/

      - id: ruff
        name: ruff
        entry: .venv/bin/python -m ruff check
        language: system
        types: [python]
        files: ^api/
```

### 5.2 CI Pipeline Integration

Add to CI workflow (GitHub Actions / GitLab CI):

```yaml
# Example GitHub Actions
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        uses: astral-sh/setup-uv@v4
      - name: Install dependencies
        run: cd api && uv sync --extra dev
      - name: Run mypy
        run: cd api && .venv/bin/python -m mypy payment_simulator/
      - name: Run ruff
        run: cd api && .venv/bin/python -m ruff check payment_simulator/
```

---

## Implementation Order

### Session 1: Foundation
1. Add tool configuration to `pyproject.toml`
2. Run initial mypy/ruff to baseline errors
3. Fix `cli/commands/policy_schema.py` (smallest file)
4. Fix `api/main.py` (minimal changes)

### Session 2: CLI Commands
1. Fix `cli/commands/db.py` (largest, many helpers)
2. Fix `cli/commands/checkpoint.py`
3. Fix `cli/commands/validate_policy.py`

### Session 3: Core Commands
1. Fix `cli/commands/run.py`
2. Fix `cli/commands/replay.py`
3. Fix `cli/execution/display.py` (quick fix)
4. Remove mypy overrides, enable strict mode
5. Run full test suite to verify no regressions

---

## Testing Strategy

### For Each Module:
1. Add types
2. Run `mypy payment_simulator/path/to/module.py`
3. Fix any type errors
4. Run `ruff check payment_simulator/path/to/module.py`
5. Fix any lint errors
6. Run existing tests: `.venv/bin/python -m pytest tests/`
7. Verify no regressions

### Integration Test:
After all changes:
```bash
# Full type check
.venv/bin/python -m mypy payment_simulator/

# Full lint check
.venv/bin/python -m ruff check payment_simulator/

# Full test suite
.venv/bin/python -m pytest

# Replay identity test (critical)
payment-sim run --config test.yaml --persist test.db --verbose > run.txt
payment-sim replay test.db --verbose > replay.txt
diff <(grep -v "Duration:" run.txt) <(grep -v "Duration:" replay.txt)
```

---

## Reference Patterns

### Pattern 1: Typer Command with Annotated

```python
from pathlib import Path
from typing import Any
from typing_extensions import Annotated
import typer

@app.command("example")
def example_command(
    required_arg: Annotated[str, typer.Argument(help="Required argument")],
    optional_path: Annotated[Path | None, typer.Option(
        "--path", "-p",
        help="Optional path",
    )] = None,
    verbose: Annotated[bool, typer.Option(
        "--verbose", "-v",
        help="Enable verbose output",
    )] = False,
    limit: Annotated[int, typer.Option(
        "--limit", "-n",
        help="Maximum items",
    )] = 100,
) -> None:
    """Example command demonstrating proper typing."""
    ...
```

### Pattern 2: Helper Function with Full Types

```python
from typing import Any
import duckdb
import polars as pl

def query_simulation_data(
    conn: duckdb.DuckDBPyConnection,
    simulation_id: str,
    agent_id: str | None = None,
    tick_min: int | None = None,
    tick_max: int | None = None,
) -> pl.DataFrame:
    """Query simulation data with optional filters.

    Args:
        conn: DuckDB connection
        simulation_id: Simulation identifier
        agent_id: Optional agent filter
        tick_min: Optional minimum tick (inclusive)
        tick_max: Optional maximum tick (inclusive)

    Returns:
        Polars DataFrame with query results
    """
    ...
```

### Pattern 3: Protocol for Duck Typing

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class StateProvider(Protocol):
    """Protocol for simulation state providers."""

    def get_agent_balance(self, agent_id: str) -> int:
        """Get current balance for agent."""
        ...

    def get_queue_size(self, agent_id: str) -> int:
        """Get queue size for agent."""
        ...
```

### Pattern 4: Dataclass for Configuration

```python
from dataclasses import dataclass

@dataclass
class ExecutionConfig:
    """Configuration for simulation execution."""
    total_ticks: int
    ticks_per_day: int
    num_days: int
    persist: bool = False
    full_replay: bool = False
    db_path: str | None = None
    quiet: bool = False
```

---

## Success Criteria

1. **mypy passes** with no errors on entire `payment_simulator/` directory
2. **ruff passes** with no errors on entire `payment_simulator/` directory
3. **All existing tests pass** with no regressions
4. **Replay identity maintained** (run vs replay output identical)
5. **No `Any` types** where specific types are knowable
6. **All Typer commands** use `Annotated` pattern
7. **Documentation updated** in `api/CLAUDE.md`

---

## Appendix: Module Inventory

| Module | Lines | Current Status | Priority |
|--------|-------|----------------|----------|
| `cli/commands/db.py` | ~400 | Partial | High |
| `cli/commands/run.py` | ~400 | Partial | High |
| `cli/commands/checkpoint.py` | ~360 | Weak | High |
| `cli/commands/replay.py` | ~300 | Weak | High |
| `cli/commands/validate_policy.py` | ~380 | Partial | Medium |
| `cli/commands/policy_schema.py` | ~50 | Weak | Low |
| `api/main.py` | ~30 | Minimal | Low |
| `cli/execution/display.py` | ~200 | Good (1 fix) | Low |

**Total Estimated Changes**: ~2000 lines across 8 files

---

## References

- [mypy documentation](https://mypy.readthedocs.io/)
- [ruff documentation](https://docs.astral.sh/ruff/)
- [Typer documentation - CLI Arguments](https://typer.tiangolo.com/tutorial/arguments/)
- [PEP 604 - Union Types](https://peps.python.org/pep-0604/)
- [PEP 585 - Type Hinting Generics](https://peps.python.org/pep-0585/)
