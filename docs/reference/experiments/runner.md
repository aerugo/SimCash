# Experiment Runner

> Runner protocols and result dataclasses

## ExperimentRunnerProtocol

Protocol defining the interface for experiment runners.

### Import

```python
from payment_simulator.experiments.runner import ExperimentRunnerProtocol
```

### Definition

```python
from typing import Protocol

class ExperimentRunnerProtocol(Protocol):
    """Protocol for experiment runners."""

    async def run(self) -> ExperimentResult:
        """Run the experiment to completion.

        Returns:
            ExperimentResult with final metrics and iteration records.
        """
        ...

    def get_current_state(self) -> ExperimentState:
        """Get current experiment state.

        Returns:
            Current ExperimentState snapshot.
        """
        ...
```

## ExperimentResult

Result returned when an experiment completes.

### Import

```python
from payment_simulator.experiments.runner import ExperimentResult
```

### Definition

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class ExperimentResult:
    """Final result of an experiment run."""

    run_id: str
    experiment_name: str
    started_at: datetime
    completed_at: datetime
    duration_seconds: float
    num_iterations: int
    converged: bool
    convergence_reason: str
    final_cost: int
    best_cost: int
    per_agent_costs: dict[str, int]
    iteration_records: list[IterationRecord]
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | `str` | Unique run identifier |
| `experiment_name` | `str` | Name from config |
| `started_at` | `datetime` | Start timestamp |
| `completed_at` | `datetime` | Completion timestamp |
| `duration_seconds` | `float` | Total duration |
| `num_iterations` | `int` | Iterations executed |
| `converged` | `bool` | Whether convergence was achieved |
| `convergence_reason` | `str` | Why experiment stopped |
| `final_cost` | `int` | Final cost (integer cents) |
| `best_cost` | `int` | Best cost achieved (integer cents) |
| `per_agent_costs` | `dict[str, int]` | Cost per agent (integer cents) |
| `iteration_records` | `list[IterationRecord]` | Per-iteration details |

### Usage

```python
result = await runner.run()

print(f"Run ID: {result.run_id}")
print(f"Iterations: {result.num_iterations}")
print(f"Final Cost: ${result.final_cost / 100:.2f}")
print(f"Best Cost: ${result.best_cost / 100:.2f}")
print(f"Converged: {result.converged}")
print(f"Reason: {result.convergence_reason}")

for agent_id, cost in result.per_agent_costs.items():
    print(f"  {agent_id}: ${cost / 100:.2f}")
```

## ExperimentState

Current state of a running experiment.

### Import

```python
from payment_simulator.experiments.runner import ExperimentState
```

### Definition

```python
@dataclass(frozen=True)
class ExperimentState:
    """Current state of an experiment."""

    iteration: int
    total_cost: int
    per_agent_costs: dict[str, int]
    policies: dict[str, dict]
    converged: bool
    convergence_reason: str | None
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `iteration` | `int` | Current iteration number |
| `total_cost` | `int` | Current total cost (integer cents) |
| `per_agent_costs` | `dict[str, int]` | Cost per agent (integer cents) |
| `policies` | `dict[str, dict]` | Current policies per agent |
| `converged` | `bool` | Whether converged |
| `convergence_reason` | `str \| None` | Reason if converged |

## IterationRecord

Record of a single optimization iteration.

### Import

```python
from payment_simulator.experiments.runner import IterationRecord
```

### Definition

```python
@dataclass(frozen=True)
class IterationRecord:
    """Record of a single iteration."""

    iteration: int
    total_cost: int
    per_agent_costs: dict[str, int]
    policy_accepted: bool
    mean_delta: float | None
    agent_updated: str | None
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `iteration` | `int` | Iteration number (0-indexed) |
| `total_cost` | `int` | Total cost after iteration (integer cents) |
| `per_agent_costs` | `dict[str, int]` | Cost per agent (integer cents) |
| `policy_accepted` | `bool` | Whether a policy update was accepted |
| `mean_delta` | `float \| None` | Mean delta if policy evaluated |
| `agent_updated` | `str \| None` | Agent ID if policy accepted |

## OutputHandlerProtocol

Protocol for handling experiment output.

### Import

```python
from payment_simulator.experiments.runner import OutputHandlerProtocol
```

### Definition

```python
from typing import Protocol

class OutputHandlerProtocol(Protocol):
    """Protocol for experiment output handlers."""

    def on_iteration_start(self, iteration: int) -> None:
        """Called when an iteration starts."""
        ...

    def on_iteration_end(
        self,
        iteration: int,
        total_cost: int,
        per_agent_costs: dict[str, int],
    ) -> None:
        """Called when an iteration ends."""
        ...

    def on_policy_evaluation(
        self,
        agent_id: str,
        old_cost: int,
        new_cost: int,
        delta: float,
        accepted: bool,
    ) -> None:
        """Called after policy evaluation."""
        ...

    def on_experiment_complete(self, result: ExperimentResult) -> None:
        """Called when experiment completes."""
        ...
```

### Implementations

#### SilentOutput

No output - for automated/testing use:

```python
from payment_simulator.experiments.runner import SilentOutput

output = SilentOutput()
```

## Convergence Reasons

| Reason | Description |
|--------|-------------|
| `"max_iterations"` | Reached maximum iteration limit |
| `"cost_stable"` | Cost stable for stability_window iterations |
| `"no_improvement"` | Improvement below threshold |
| `"manual_stop"` | Stopped by user/signal |

## Integer Cents Invariant

**CRITICAL**: All cost values are **integer cents** (INV-1).

```python
# Correct: Integer cents
result.final_cost = 125000  # $1,250.00

# Display conversion
print(f"${result.final_cost / 100:.2f}")  # "$1250.00"
```

Never use floats for money values.

## Example: Full Workflow

```python
from pathlib import Path
from payment_simulator.experiments.config import ExperimentConfig
from payment_simulator.experiments.runner import SilentOutput
from payment_simulator.llm import LLMConfig, PydanticAILLMClient

# Load config
config = ExperimentConfig.from_yaml(Path("experiments/exp1.yaml"))

# Create components
llm_client = PydanticAILLMClient(config.llm)
output = SilentOutput()

# Create runner (implementation-specific)
runner = create_experiment_runner(
    config=config,
    llm_client=llm_client,
    output=output,
)

# Run experiment
result = await runner.run()

# Process results
print(f"Experiment: {result.experiment_name}")
print(f"Iterations: {result.num_iterations}")
print(f"Final Cost: ${result.final_cost / 100:.2f}")
print(f"Converged: {result.converged} ({result.convergence_reason})")

# Analyze iterations
for record in result.iteration_records:
    status = "ACCEPT" if record.policy_accepted else "reject"
    print(f"  Iter {record.iteration}: ${record.total_cost / 100:.2f} [{status}]")
```

## Related Documentation

- [Experiment Configuration](configuration.md) - YAML config reference
- [Experiment CLI](../cli/commands/experiment.md) - CLI commands

---

*Last updated: 2025-12-10*
