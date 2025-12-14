# Experiment Runner

> Runner protocols, GenericExperimentRunner, and result dataclasses

**Version**: 2.0 (YAML-only experiments)

## Overview

The experiment runner module provides:
- `GenericExperimentRunner`: Works with any YAML configuration
- `OptimizationLoop`: Core loop with sophisticated LLM context building
- `VerboseConfig`: Structured verbose logging control
- `ExperimentResult`: Final experiment results
- `ExperimentState`: Runtime state snapshot

> **Sophisticated Prompt System**: The runner integrates with the optimizer prompt architecture to provide rich 50k+ token LLM context including best/worst seed analysis, cost breakdowns, and iteration history. See **[Optimizer Prompt Architecture](../ai_cash_mgmt/optimizer-prompt.md)** for details.

## GenericExperimentRunner

The primary runner for YAML-only experiments. No experiment-specific Python code required.

### Bootstrap Evaluation (Default)

In bootstrap mode, the runner:
1. **Runs an initial simulation** once to collect transaction history
2. **Generates bootstrap samples** by resampling from observed transactions
3. **Evaluates policies** on isolated 3-agent sandboxes (AGENT, SOURCE, SINK)
4. **Computes paired deltas** by evaluating both old and new policies on the SAME samples

This provides statistically valid policy comparison without confounding from other agents.

### Import

```python
from payment_simulator.experiments.runner import GenericExperimentRunner
from payment_simulator.experiments.config import ExperimentConfig
```

### Basic Usage

```python
from pathlib import Path
from payment_simulator.experiments.config import ExperimentConfig
from payment_simulator.experiments.runner import GenericExperimentRunner

# Load config from YAML
config = ExperimentConfig.from_yaml(Path("experiments/exp1.yaml"))

# Create and run
runner = GenericExperimentRunner(config)
result = await runner.run()

print(f"Converged: {result.converged}")
print(f"Final cost: ${result.final_costs['total'] / 100:.2f}")
```

### With Verbose Logging

```python
from payment_simulator.experiments.runner import GenericExperimentRunner, VerboseConfig

# Enable all verbose output
verbose_config = VerboseConfig.all_enabled()

runner = GenericExperimentRunner(config, verbose_config=verbose_config)
result = await runner.run()
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `run_id` | `str` | Unique run identifier |
| `experiment_name` | `str` | Name from config |
| `scenario_path` | `Path` | Path to scenario YAML |
| `system_prompt` | `str \| None` | System prompt from config.llm |
| `constraints` | `ScenarioConstraints \| None` | Policy constraints from config |

## VerboseConfig

Controls verbose output categories. Each flag enables a category of output.

### Import

```python
from payment_simulator.experiments.runner import VerboseConfig
```

### Definition

```python
@dataclass
class VerboseConfig:
    iterations: bool = False   # Iteration start messages
    policy: bool = False       # Before/after policy parameters
    bootstrap: bool = False    # Per-sample bootstrap results
    llm: bool = False          # LLM call metadata (model, tokens)
    rejections: bool = False   # Policy rejection reasons
    debug: bool = False        # Debug info (validation errors, retries)
    simulations: bool = True   # Show simulation IDs when simulations start
```

> **Note**: The `simulations` flag defaults to `True` for transparency. When enabled, simulation IDs are logged to the terminal each time a simulation runs.

### Factory Methods

```python
# Enable all main flags (not debug)
config = VerboseConfig.all_enabled()

# Create from CLI flags
config = VerboseConfig.from_cli_flags(
    verbose=True,            # Enable all
    verbose_policy=False,    # Override: disable policy
    debug=True,              # Enable debug
)
```

### Example Output

With `VerboseConfig(iterations=True, policy=True, bootstrap=True)`:

```
Iteration 1
  Total cost: $1,250.00

Bootstrap Baseline (10 samples):
┏━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━┳━━━━━━━┓
┃ Seed       ┃ Cost       ┃ Settled  ┃ Rate  ┃ Note  ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━╇━━━━━━━┩
│ 0x12345678 │ $1,250.00  │ 8/10     │ 80.0% │       │
│ 0x23456789 │ $1,180.00  │ 9/10     │ 90.0% │       │
└────────────┴────────────┴──────────┴───────┴───────┘
  Mean: $1,215.00 (std: $35.00)

Policy Change: BANK_A
┏━━━━━━━━━━━━━━━━━━┳━━━━━━┳━━━━━━┳━━━━━━━━┓
┃ Parameter        ┃ Old  ┃ New  ┃ Delta  ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━╇━━━━━━╇━━━━━━━━┩
│ urgency_threshold│ 5    │ 3    │ -40%   │
└──────────────────┴──────┴──────┴────────┘
  Evaluation: $1,250.00 → $1,100.00 (-12.0%)
  Decision: ACCEPTED
```

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

## SimulationResult (Internal)

Unified result type for all simulation execution within `OptimizationLoop`. This dataclass consolidates the output from the internal `_run_simulation()` method.

> **Note**: This is an internal dataclass used by `OptimizationLoop`. External callers typically interact with `ExperimentResult` or `EnrichedEvaluationResult` instead.

### Import

```python
from payment_simulator.experiments.runner.bootstrap_support import SimulationResult
```

### Definition

```python
@dataclass(frozen=True)
class SimulationResult:
    """Complete simulation output. Callers transform to their specific needs.

    All costs are integer cents (INV-1).
    """
    seed: int                           # RNG seed used
    simulation_id: str                  # Unique identifier (e.g., "init-42-abc123")
    total_cost: int                     # Sum of all agent costs (integer cents)
    per_agent_costs: dict[str, int]     # Cost per optimized agent
    events: tuple[dict[str, Any], ...]  # Immutable event trace
    cost_breakdown: CostBreakdown       # Itemized costs
    settlement_rate: float              # Ratio of settled/total transactions
    avg_delay: float                    # Average settlement delay in ticks
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `seed` | `int` | RNG seed used for determinism |
| `simulation_id` | `str` | Unique identifier with purpose prefix |
| `total_cost` | `int` | Total cost (integer cents) |
| `per_agent_costs` | `dict[str, int]` | Per-agent costs (integer cents) |
| `events` | `tuple[dict, ...]` | Immutable event trace for replay |
| `cost_breakdown` | `CostBreakdown` | Itemized costs (delay, overdraft, etc.) |
| `settlement_rate` | `float` | Settlement success ratio |
| `avg_delay` | `float` | Average delay in ticks |

### Usage

The `SimulationResult` is returned by the internal `_run_simulation()` method and transformed by callers:

```python
# Internal: _run_initial_simulation() transforms to InitialSimulationResult
result = self._run_simulation(seed=master_seed, purpose="init")
collector = TransactionHistoryCollector()
collector.process_events(list(result.events))
# ... build InitialSimulationResult from result + collector

# Internal: _run_simulation_with_events() transforms to EnrichedEvaluationResult
result = self._run_simulation(seed=seed, purpose="bootstrap", sample_idx=idx)
bootstrap_events = [BootstrapEvent(tick=e["tick"], ...) for e in result.events]
# ... build EnrichedEvaluationResult from result + bootstrap_events
```

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
import asyncio
from pathlib import Path
from payment_simulator.experiments.config import ExperimentConfig
from payment_simulator.experiments.runner import GenericExperimentRunner, VerboseConfig

async def run_experiment():
    # Load config from YAML (all settings included)
    config = ExperimentConfig.from_yaml(Path("experiments/exp1.yaml"))

    # Optionally override seed
    config = config.with_seed(12345)

    # Configure verbose output
    verbose_config = VerboseConfig(
        iterations=True,
        bootstrap=True,
        policy=True,
    )

    # Create runner (no manual LLM client setup needed)
    runner = GenericExperimentRunner(
        config=config,
        verbose_config=verbose_config,
    )

    # Run experiment
    result = await runner.run()

    # Process results
    print(f"Experiment: {result.experiment_name}")
    print(f"Iterations: {result.num_iterations}")
    print(f"Converged: {result.converged} ({result.convergence_reason})")

    # Per-agent costs (integer cents)
    for agent_id, cost in result.final_costs.items():
        if agent_id != "total":
            print(f"  {agent_id}: ${cost / 100:.2f}")

    return result

# Run
result = asyncio.run(run_experiment())
```

## CLI Usage

The recommended way to run experiments is via the CLI:

```bash
# Run experiment (uses GenericExperimentRunner internally)
payment-sim experiment run experiments/exp1.yaml

# With verbose output
payment-sim experiment run experiments/exp1.yaml --verbose

# Override seed
payment-sim experiment run experiments/exp1.yaml --seed 12345

# Dry run (validate without LLM calls)
payment-sim experiment run experiments/exp1.yaml --dry-run
```

## Related Documentation

- [Experiment Configuration](configuration.md) - YAML config reference
- [Experiment CLI](../cli/commands/experiment.md) - CLI commands
- [Castro Experiments](../castro/index.md) - Example YAML experiments

---

*Last updated: 2025-12-14*
