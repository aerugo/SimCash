# Policy Evolution Tracking CLI Command

## Overview

Add a new CLI subcommand `payment-sim experiment policy-evolution` that extracts and displays how policies evolved across experiment iterations for all bank agents.

## Output Format

```json
{
  "BANK_A": {
    "iteration_1": {
      "policy": {...},
      "explanation": "...",      // optional
      "diff": "...",             // optional: what changed from previous
      "llm": {                   // optional: only with --llm flag
        "system_prompt": "...",
        "user_prompt": "...",
        "raw_response": "..."
      }
    },
    "iteration_2": {...}
  },
  "BANK_B": {...}
}
```

## CLI Interface

```bash
payment-sim experiment policy-evolution <run_id> [OPTIONS]
```

### Arguments

- `run_id` (required): Experiment run ID (e.g., `exp1-20251209-143022-a1b2c3`)

### Options

| Flag | Type | Description |
|------|------|-------------|
| `--llm` | bool | Include LLM prompts and responses |
| `--agent <ID>` | string | Filter output to specific agent ID (e.g., BANK_A) |
| `--start <N>` | int | Start from iteration N (1-indexed, inclusive) |
| `--end <N>` | int | End at iteration N (1-indexed, inclusive) |
| `--db <path>` | Path | Database path (default: `results/experiments.db`) |
| `--pretty` | bool | Pretty-print JSON output (default: compact) |

### Examples

```bash
# Basic usage - all agents, all iterations
payment-sim experiment policy-evolution exp1-20251209-143022-a1b2c3

# Filter by agent
payment-sim experiment policy-evolution exp1-20251209-143022-a1b2c3 --agent BANK_A

# Include LLM prompts/responses
payment-sim experiment policy-evolution exp1-20251209-143022-a1b2c3 --llm

# Iteration range (1-indexed for user-facing)
payment-sim experiment policy-evolution exp1-20251209-143022-a1b2c3 --start 2 --end 5

# Combined filters
payment-sim experiment policy-evolution exp1-20251209-143022-a1b2c3 \
  --agent BANK_A --llm --start 1 --end 10 --pretty
```

---

## Data Model Analysis

### Source Tables (Generic Experiment Framework)

#### `experiment_iterations` table
```sql
run_id VARCHAR NOT NULL,
iteration INTEGER NOT NULL,           -- 0-indexed internally
costs_per_agent JSON NOT NULL,        -- {"BANK_A": 15000, "BANK_B": 12000}
accepted_changes JSON NOT NULL,       -- {"BANK_A": true, "BANK_B": false}
policies JSON NOT NULL,               -- {"BANK_A": {...}, "BANK_B": {...}}
timestamp VARCHAR NOT NULL,
PRIMARY KEY (run_id, iteration)
```

#### `experiment_events` table
```sql
id INTEGER PRIMARY KEY,
run_id VARCHAR NOT NULL,
iteration INTEGER NOT NULL,
event_type VARCHAR NOT NULL,          -- 'llm_call_complete', 'policy_accepted', etc.
event_data JSON NOT NULL,             -- Event-specific payload
timestamp VARCHAR NOT NULL
```

### Event Types for LLM Data

From `optimization.py`, LLM interaction data is stored in events with:
- `event_type`: `'llm_call_complete'` or similar
- `event_data`: Contains `LLMInteraction` fields serialized:
  - `system_prompt`
  - `user_prompt`
  - `raw_response`
  - `parsed_policy`
  - `parsing_error`
  - `latency_seconds`
  - `prompt_tokens`
  - `completion_tokens`

---

## Implementation Plan (TDD)

### Phase 1: Data Access Layer (Tests First)

#### Task 1.1: Create Query Functions Module

**File**: `api/payment_simulator/experiments/persistence/queries.py`

Add functions to extract policy evolution data:

```python
def get_policy_evolution(
    repo: ExperimentRepository,
    run_id: str,
    agent_id: str | None = None,
    start_iteration: int | None = None,
    end_iteration: int | None = None,
) -> list[IterationRecord]:
    """Get iteration records filtered by agent and iteration range."""
    ...

def get_llm_events_for_iteration(
    repo: ExperimentRepository,
    run_id: str,
    iteration: int,
    agent_id: str | None = None,
) -> list[EventRecord]:
    """Get LLM-related events for a specific iteration."""
    ...
```

**Test File**: `api/tests/unit/experiments/persistence/test_policy_evolution_queries.py`

```python
def test_get_policy_evolution_returns_all_iterations():
    """Verify all iterations are returned when no filters applied."""
    ...

def test_get_policy_evolution_filters_by_agent():
    """Verify agent filter returns only that agent's policies."""
    ...

def test_get_policy_evolution_filters_by_iteration_range():
    """Verify start/end filters work correctly."""
    ...

def test_get_llm_events_returns_prompts_and_responses():
    """Verify LLM event data is correctly extracted."""
    ...
```

---

#### Task 1.2: Create Policy Diff Calculator

**File**: `api/payment_simulator/experiments/analysis/policy_diff.py`

```python
from typing import Any

def compute_policy_diff(
    old_policy: dict[str, Any],
    new_policy: dict[str, Any],
) -> str:
    """Compute human-readable diff between two policies.

    Returns a summary of what changed:
    - Parameter changes (with before/after values)
    - Tree structure changes (payment_tree, collateral_tree)

    Args:
        old_policy: Previous iteration's policy.
        new_policy: Current iteration's policy.

    Returns:
        Human-readable diff summary string.
    """
    ...

def extract_parameter_changes(
    old_policy: dict[str, Any],
    new_policy: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Extract structured parameter changes.

    Returns dict like:
    {
        "parameters.liquidity_threshold": {
            "before": 5000,
            "after": 3000
        },
        "payment_tree.on_true.threshold": {
            "before": 0.5,
            "after": 0.7
        }
    }
    """
    ...
```

**Test File**: `api/tests/unit/experiments/analysis/test_policy_diff.py`

```python
def test_compute_policy_diff_detects_parameter_change():
    """Verify parameter changes are detected and formatted."""
    old = {"parameters": {"threshold": 100}}
    new = {"parameters": {"threshold": 200}}
    diff = compute_policy_diff(old, new)
    assert "threshold" in diff
    assert "100" in diff or "200" in diff

def test_compute_policy_diff_handles_nested_tree_changes():
    """Verify tree structure changes are detected."""
    ...

def test_compute_policy_diff_handles_added_fields():
    """Verify new fields are reported."""
    ...

def test_compute_policy_diff_handles_removed_fields():
    """Verify removed fields are reported."""
    ...

def test_compute_policy_diff_returns_empty_for_identical():
    """Verify no diff for identical policies."""
    ...
```

---

### Phase 2: Domain Model

#### Task 2.1: Create Output Model

**File**: `api/payment_simulator/experiments/analysis/evolution_model.py`

```python
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LLMInteractionData:
    """LLM interaction data for a single iteration.

    Attributes:
        system_prompt: Full system prompt sent to LLM.
        user_prompt: Full user prompt with policy and context.
        raw_response: Raw LLM response before parsing.
    """
    system_prompt: str
    user_prompt: str
    raw_response: str


@dataclass(frozen=True)
class IterationEvolution:
    """Policy evolution data for a single iteration.

    Attributes:
        policy: The policy dict at this iteration.
        explanation: Optional explanation (from LLM reasoning).
        diff: Optional diff from previous iteration.
        llm: Optional LLM interaction data (when --llm flag used).
        cost: Cost in integer cents (INV-1).
        accepted: Whether the policy change was accepted.
    """
    policy: dict[str, Any]
    explanation: str | None = None
    diff: str | None = None
    llm: LLMInteractionData | None = None
    cost: int | None = None
    accepted: bool | None = None


@dataclass(frozen=True)
class AgentEvolution:
    """Policy evolution history for a single agent.

    Attributes:
        agent_id: The agent identifier (e.g., "BANK_A").
        iterations: Mapping of iteration number (1-indexed) to evolution data.
    """
    agent_id: str
    iterations: dict[str, IterationEvolution]  # "iteration_1", "iteration_2", etc.


def build_evolution_output(
    evolutions: list[AgentEvolution],
) -> dict[str, dict[str, dict[str, Any]]]:
    """Convert evolution data to output JSON structure.

    Returns:
        Dict with structure: {agent_id: {iteration_N: {...}}}
    """
    ...
```

**Test File**: `api/tests/unit/experiments/analysis/test_evolution_model.py`

```python
def test_iteration_evolution_is_immutable():
    """Verify frozen dataclass."""
    ...

def test_build_evolution_output_formats_correctly():
    """Verify output matches expected JSON structure."""
    ...

def test_build_evolution_output_handles_optional_fields():
    """Verify None fields are excluded from output."""
    ...
```

---

### Phase 3: Service Layer

#### Task 3.1: Create Policy Evolution Service

**File**: `api/payment_simulator/experiments/analysis/evolution_service.py`

```python
from pathlib import Path
from typing import Any

from payment_simulator.experiments.persistence import ExperimentRepository
from payment_simulator.experiments.analysis.evolution_model import (
    AgentEvolution,
    IterationEvolution,
    LLMInteractionData,
)
from payment_simulator.experiments.analysis.policy_diff import compute_policy_diff


class PolicyEvolutionService:
    """Service for extracting policy evolution data from experiments.

    Example:
        >>> service = PolicyEvolutionService(repo)
        >>> evolution = service.get_evolution(
        ...     run_id="exp1-20251209-143022-a1b2c3",
        ...     include_llm=True,
        ...     agent_filter="BANK_A",
        ...     start_iteration=1,
        ...     end_iteration=10,
        ... )
    """

    def __init__(self, repository: ExperimentRepository) -> None:
        """Initialize with experiment repository.

        Args:
            repository: ExperimentRepository for database access.
        """
        self._repo = repository

    def get_evolution(
        self,
        run_id: str,
        include_llm: bool = False,
        agent_filter: str | None = None,
        start_iteration: int | None = None,
        end_iteration: int | None = None,
    ) -> list[AgentEvolution]:
        """Extract policy evolution for an experiment.

        Args:
            run_id: Experiment run ID.
            include_llm: Whether to include LLM prompts/responses.
            agent_filter: Optional agent ID to filter by.
            start_iteration: Start iteration (1-indexed, inclusive).
            end_iteration: End iteration (1-indexed, inclusive).

        Returns:
            List of AgentEvolution objects.

        Raises:
            ValueError: If run_id not found.
        """
        ...

    def _extract_llm_data(
        self,
        run_id: str,
        iteration: int,
        agent_id: str,
    ) -> LLMInteractionData | None:
        """Extract LLM interaction data from events.

        Args:
            run_id: Experiment run ID.
            iteration: Iteration number (0-indexed internally).
            agent_id: Agent identifier.

        Returns:
            LLMInteractionData if found, None otherwise.
        """
        ...
```

**Test File**: `api/tests/unit/experiments/analysis/test_evolution_service.py`

```python
def test_get_evolution_returns_all_agents():
    """Verify all agents are returned when no filter."""
    ...

def test_get_evolution_filters_by_agent():
    """Verify agent_filter works correctly."""
    ...

def test_get_evolution_filters_by_iteration_range():
    """Verify start/end iteration filtering."""
    ...

def test_get_evolution_includes_llm_when_requested():
    """Verify LLM data is included with --llm flag."""
    ...

def test_get_evolution_excludes_llm_by_default():
    """Verify LLM data is NOT included by default."""
    ...

def test_get_evolution_computes_diffs():
    """Verify diffs are computed between iterations."""
    ...

def test_get_evolution_handles_first_iteration_no_diff():
    """Verify first iteration has no diff (nothing to compare)."""
    ...

def test_get_evolution_raises_for_invalid_run_id():
    """Verify ValueError for non-existent run."""
    ...

def test_get_evolution_iteration_numbers_are_1_indexed():
    """Verify output uses 1-indexed iteration numbers."""
    ...
```

---

### Phase 4: CLI Command

#### Task 4.1: Implement CLI Command

**File**: `api/payment_simulator/experiments/cli/commands.py` (add to existing)

```python
@experiment_app.command("policy-evolution")
def policy_evolution(
    run_id: Annotated[
        str,
        typer.Argument(help="Experiment run ID (e.g., exp1-20251209-143022-a1b2c3)"),
    ],
    db: Annotated[
        Path,
        typer.Option("--db", "-d", help="Path to database file"),
    ] = DEFAULT_DB_PATH,
    llm: Annotated[
        bool,
        typer.Option("--llm", help="Include LLM prompts and responses"),
    ] = False,
    agent: Annotated[
        str | None,
        typer.Option("--agent", "-a", help="Filter by agent ID (e.g., BANK_A)"),
    ] = None,
    start: Annotated[
        int | None,
        typer.Option("--start", help="Start iteration (1-indexed, inclusive)"),
    ] = None,
    end: Annotated[
        int | None,
        typer.Option("--end", help="End iteration (1-indexed, inclusive)"),
    ] = None,
    pretty: Annotated[
        bool,
        typer.Option("--pretty", "-p", help="Pretty-print JSON output"),
    ] = False,
) -> None:
    """Extract policy evolution across experiment iterations.

    Returns JSON showing how policies evolved for each agent across iterations.
    Useful for analyzing optimization trajectories and understanding what the LLM
    changed at each step.

    Examples:
        # All agents, all iterations
        experiment policy-evolution exp1-20251209-143022-a1b2c3

        # Filter by agent
        experiment policy-evolution exp1-20251209-143022-a1b2c3 --agent BANK_A

        # Include LLM prompts/responses
        experiment policy-evolution exp1-20251209-143022-a1b2c3 --llm

        # Specific iteration range
        experiment policy-evolution exp1-20251209-143022-a1b2c3 --start 2 --end 5
    """
    ...
```

**Test File**: `api/tests/unit/experiments/cli/test_policy_evolution_command.py`

```python
def test_policy_evolution_command_exists():
    """Verify command is registered."""
    from typer.testing import CliRunner
    from payment_simulator.cli.main import app

    runner = CliRunner()
    result = runner.invoke(app, ["experiment", "policy-evolution", "--help"])
    assert result.exit_code == 0
    assert "policy-evolution" in result.output

def test_policy_evolution_requires_run_id():
    """Verify run_id is required."""
    ...

def test_policy_evolution_validates_iteration_range():
    """Verify start <= end validation."""
    ...

def test_policy_evolution_outputs_valid_json():
    """Verify output is valid JSON."""
    ...

def test_policy_evolution_pretty_flag_formats_output():
    """Verify --pretty flag indents JSON."""
    ...
```

---

### Phase 5: Integration Tests

**File**: `api/tests/integration/experiments/test_policy_evolution_integration.py`

```python
"""Integration tests for policy-evolution command.

Tests the full flow from CLI to database to JSON output.
Uses a real experiment database fixture.
"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from payment_simulator.cli.main import app


@pytest.fixture
def experiment_db(tmp_path: Path) -> Path:
    """Create a test experiment database with sample data."""
    from payment_simulator.experiments.persistence import (
        ExperimentRepository,
        ExperimentRecord,
        IterationRecord,
        EventRecord,
    )
    from datetime import datetime

    db_path = tmp_path / "test_experiments.db"
    repo = ExperimentRepository(db_path)

    # Create experiment
    repo.save_experiment(ExperimentRecord(
        run_id="test-run-123",
        experiment_name="test_exp",
        experiment_type="generic",
        config={},
        created_at=datetime.now().isoformat(),
        completed_at=datetime.now().isoformat(),
        num_iterations=3,
        converged=True,
        convergence_reason="stability_reached",
    ))

    # Create iterations with policies
    for i in range(3):
        repo.save_iteration(IterationRecord(
            run_id="test-run-123",
            iteration=i,
            costs_per_agent={"BANK_A": 10000 - i * 1000, "BANK_B": 8000 - i * 500},
            accepted_changes={"BANK_A": True, "BANK_B": i > 0},
            policies={
                "BANK_A": {"version": "2.0", "threshold": 100 + i * 10},
                "BANK_B": {"version": "2.0", "threshold": 200 + i * 5},
            },
            timestamp=datetime.now().isoformat(),
        ))

    # Create LLM events
    for i in range(3):
        repo.save_event(EventRecord(
            run_id="test-run-123",
            iteration=i,
            event_type="llm_call_complete",
            event_data={
                "agent_id": "BANK_A",
                "system_prompt": f"System prompt for iteration {i}",
                "user_prompt": f"User prompt for iteration {i}",
                "raw_response": f'{{"threshold": {100 + i * 10}}}',
            },
            timestamp=datetime.now().isoformat(),
        ))

    repo.close()
    return db_path


class TestPolicyEvolutionIntegration:
    """Integration tests for policy-evolution command."""

    def test_basic_output_structure(self, experiment_db: Path) -> None:
        """Verify basic JSON output structure."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["experiment", "policy-evolution", "test-run-123", "--db", str(experiment_db)],
        )

        assert result.exit_code == 0
        output = json.loads(result.output)

        # Check structure
        assert "BANK_A" in output
        assert "BANK_B" in output
        assert "iteration_1" in output["BANK_A"]
        assert "policy" in output["BANK_A"]["iteration_1"]

    def test_agent_filter(self, experiment_db: Path) -> None:
        """Verify --agent filter works."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "experiment", "policy-evolution", "test-run-123",
                "--db", str(experiment_db),
                "--agent", "BANK_A",
            ],
        )

        assert result.exit_code == 0
        output = json.loads(result.output)

        assert "BANK_A" in output
        assert "BANK_B" not in output

    def test_iteration_range_filter(self, experiment_db: Path) -> None:
        """Verify --start and --end filters work."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "experiment", "policy-evolution", "test-run-123",
                "--db", str(experiment_db),
                "--start", "2",
                "--end", "2",
            ],
        )

        assert result.exit_code == 0
        output = json.loads(result.output)

        # Should only have iteration_2
        assert "iteration_1" not in output.get("BANK_A", {})
        assert "iteration_2" in output.get("BANK_A", {})
        assert "iteration_3" not in output.get("BANK_A", {})

    def test_llm_flag_includes_prompts(self, experiment_db: Path) -> None:
        """Verify --llm flag includes LLM data."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "experiment", "policy-evolution", "test-run-123",
                "--db", str(experiment_db),
                "--llm",
            ],
        )

        assert result.exit_code == 0
        output = json.loads(result.output)

        # Check LLM data is present
        iteration_1 = output["BANK_A"]["iteration_1"]
        assert "llm" in iteration_1
        assert "system_prompt" in iteration_1["llm"]
        assert "user_prompt" in iteration_1["llm"]
        assert "raw_response" in iteration_1["llm"]

    def test_llm_flag_absent_excludes_prompts(self, experiment_db: Path) -> None:
        """Verify LLM data is excluded without --llm flag."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["experiment", "policy-evolution", "test-run-123", "--db", str(experiment_db)],
        )

        assert result.exit_code == 0
        output = json.loads(result.output)

        # LLM data should NOT be present
        iteration_1 = output["BANK_A"]["iteration_1"]
        assert "llm" not in iteration_1

    def test_diff_computed_between_iterations(self, experiment_db: Path) -> None:
        """Verify diff is computed between consecutive iterations."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["experiment", "policy-evolution", "test-run-123", "--db", str(experiment_db)],
        )

        assert result.exit_code == 0
        output = json.loads(result.output)

        # First iteration should have no diff
        iteration_1 = output["BANK_A"]["iteration_1"]
        assert iteration_1.get("diff") is None or iteration_1.get("diff") == ""

        # Subsequent iterations should have diff
        iteration_2 = output["BANK_A"]["iteration_2"]
        assert iteration_2.get("diff") is not None
        assert "threshold" in iteration_2["diff"]

    def test_invalid_run_id_returns_error(self, experiment_db: Path) -> None:
        """Verify error for non-existent run ID."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "experiment", "policy-evolution", "nonexistent-run",
                "--db", str(experiment_db),
            ],
        )

        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_invalid_iteration_range_returns_error(self, experiment_db: Path) -> None:
        """Verify error when start > end."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "experiment", "policy-evolution", "test-run-123",
                "--db", str(experiment_db),
                "--start", "5",
                "--end", "2",
            ],
        )

        assert result.exit_code != 0
        assert "start" in result.output.lower() and "end" in result.output.lower()
```

---

## File Structure

```
api/payment_simulator/experiments/
├── analysis/                              # NEW directory
│   ├── __init__.py                        # NEW
│   ├── evolution_model.py                 # NEW: Output models
│   ├── evolution_service.py               # NEW: Service layer
│   └── policy_diff.py                     # NEW: Diff calculator
├── cli/
│   └── commands.py                        # ADD: policy-evolution command
└── persistence/
    └── repository.py                      # (existing, may add helper methods)

api/tests/
├── unit/experiments/
│   ├── analysis/                          # NEW directory
│   │   ├── test_evolution_model.py        # NEW
│   │   ├── test_evolution_service.py      # NEW
│   │   └── test_policy_diff.py            # NEW
│   ├── cli/
│   │   └── test_policy_evolution_command.py  # NEW
│   └── persistence/
│       └── test_policy_evolution_queries.py  # NEW
└── integration/experiments/
    └── test_policy_evolution_integration.py  # NEW
```

---

## Implementation Order (TDD)

### Step 1: Red - Write Failing Tests First

1. Create `api/tests/unit/experiments/analysis/test_policy_diff.py`
2. Create `api/tests/unit/experiments/analysis/test_evolution_model.py`
3. Create `api/tests/unit/experiments/analysis/test_evolution_service.py`
4. Create `api/tests/unit/experiments/cli/test_policy_evolution_command.py`
5. Create `api/tests/integration/experiments/test_policy_evolution_integration.py`

### Step 2: Green - Implement to Pass Tests

1. Create `api/payment_simulator/experiments/analysis/__init__.py`
2. Implement `policy_diff.py` - make diff tests pass
3. Implement `evolution_model.py` - make model tests pass
4. Implement `evolution_service.py` - make service tests pass
5. Add `policy-evolution` command to `commands.py` - make CLI tests pass
6. Run integration tests - should all pass

### Step 3: Refactor

1. Review for type completeness (mypy/pyright)
2. Check ruff compliance
3. Ensure no `Any` types where specific types are known
4. Add docstrings where missing
5. Update reference documentation

---

## Validation Checklist

### Type Safety
- [ ] All functions have complete type annotations (params + return)
- [ ] No bare `list`, `dict` without type arguments
- [ ] Using `str | None` not `Optional[str]`
- [ ] Typer commands use `Annotated` pattern

### Project Invariants
- [ ] All costs are `int` (cents, never floats) - INV-1
- [ ] Iteration numbers are 1-indexed in output (user-facing)
- [ ] Iteration numbers are 0-indexed internally (database)

### Tests
- [ ] Unit tests for each new module
- [ ] Integration test for full CLI flow
- [ ] Tests verify JSON output structure
- [ ] Tests verify filter combinations

### Documentation
- [ ] Update `docs/reference/cli/commands/` with new command
- [ ] Add to experiment CLI help text
- [ ] Example usage in docstrings

---

## Edge Cases to Handle

1. **Empty iterations**: Run has no iterations (just started)
2. **Single agent**: Only one agent being optimized
3. **No LLM events**: Events table doesn't have LLM data for some iterations
4. **Missing diff**: First iteration has nothing to diff against
5. **Large policies**: Policies with deeply nested trees
6. **Unicode in prompts**: LLM prompts/responses may contain special characters
7. **Agent not found**: Filter by agent that doesn't exist in experiment

---

## Notes

- Iteration numbers are **1-indexed in output** (user-facing) but **0-indexed in database** (internal)
- The `diff` field is computed at query time, not stored in database
- LLM data may be large (50k+ tokens for system prompt); consider streaming for very large outputs
- The command outputs to stdout as JSON for piping to other tools (e.g., `jq`)
