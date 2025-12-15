# Experiment Analysis

> Tools for analyzing and visualizing experiment results

The `payment_simulator.experiments.analysis` module provides tools for extracting, analyzing, and visualizing experiment data from the persistence layer.

## Overview

| Component | Description |
|-----------|-------------|
| `ExperimentChartService` | Extract chart-ready data from experiments |
| `PolicyEvolutionService` | Extract policy evolution across iterations |
| `render_convergence_chart` | Generate matplotlib convergence charts |
| `compute_policy_diff` | Calculate differences between policies |

## Charting

### ExperimentChartService

Extracts chart-ready data from experiment runs stored in the database.

```python
from pathlib import Path
from payment_simulator.experiments.persistence import ExperimentRepository
from payment_simulator.experiments.analysis import (
    ExperimentChartService,
    render_convergence_chart,
)

# Open repository
repo = ExperimentRepository(Path("results/experiments.db"))

# Create service
service = ExperimentChartService(repo)

# Extract data for all agents (system total)
data = service.extract_chart_data("exp1-20251215-084901-866d63")

# Extract data for specific agent with parameter tracking
data = service.extract_chart_data(
    run_id="exp1-20251215-084901-866d63",
    agent_filter="BANK_A",
    parameter_name="initial_liquidity_fraction",
)

# Render chart
render_convergence_chart(data, Path("convergence.png"))
```

### ChartData Structure

```python
@dataclass(frozen=True)
class ChartDataPoint:
    iteration: int           # 1-indexed iteration number
    cost_dollars: float      # Cost in dollars (converted from cents)
    accepted: bool           # Whether policy was accepted
    parameter_value: float | None  # Optional parameter value

@dataclass(frozen=True)
class ChartData:
    run_id: str              # Experiment run identifier
    experiment_name: str     # Name from config
    evaluation_mode: str     # "deterministic" or "bootstrap"
    agent_id: str | None     # Agent if filtered, None for system total
    parameter_name: str | None  # Parameter being tracked
    data_points: list[ChartDataPoint]
```

### render_convergence_chart

Renders a publication-quality convergence chart using matplotlib.

```python
def render_convergence_chart(
    data: ChartData,
    output_path: Path,
    show_all_policies: bool = True,
    figsize: tuple[float, float] = (10, 6),
    dpi: int = 150,
) -> None:
    """Render experiment convergence chart to file.

    Args:
        data: ChartData extracted from experiment.
        output_path: Path to save chart (supports .png, .pdf, .svg).
        show_all_policies: Whether to show the "all policies" line.
        figsize: Figure size in inches (width, height).
        dpi: Resolution for raster output.
    """
```

**Chart Features:**

- **Primary Line (Accepted)**: Bold blue line showing the cost trajectory when following only accepted policy changes. This represents the optimization convergence path.

- **Secondary Line (All)**: Subtle gray dashed line showing the cost of every tested policy, including rejected ones. This visualizes the exploration space.

- **Parameter Annotations**: When `parameter_name` is specified, accepted data points are annotated with the parameter value at that iteration.

**Supported Output Formats:**

| Extension | Format | Best For |
|-----------|--------|----------|
| `.png` | Raster | Web, documentation |
| `.pdf` | Vector | Papers, publications |
| `.svg` | Vector | Web, scalable graphics |

### CLI Usage

```bash
# Basic chart (system total cost)
payment-sim experiment chart exp1-20251215-084901-866d63

# Agent-specific chart
payment-sim experiment chart exp1-20251215-084901-866d63 --agent BANK_A

# With parameter annotations
payment-sim experiment chart exp1-20251215-084901-866d63 \
    --agent BANK_A --parameter initial_liquidity_fraction

# Custom output
payment-sim experiment chart exp1-20251215-084901-866d63 --output results/fig1.pdf
```

## Policy Evolution

### PolicyEvolutionService

Extracts the complete policy evolution history across iterations.

```python
from payment_simulator.experiments.analysis import PolicyEvolutionService

service = PolicyEvolutionService(repo)
evolutions = service.get_evolution(
    run_id="exp1-20251215-084901-866d63",
    include_llm=True,       # Include LLM prompts/responses
    agent_filter="BANK_A",  # Filter to specific agent
    start_iteration=1,      # Start iteration (1-indexed)
    end_iteration=10,       # End iteration (1-indexed)
)
```

### CLI Usage

```bash
# Full evolution for all agents
payment-sim experiment policy-evolution exp1-20251215-084901-866d63

# Filter by agent
payment-sim experiment policy-evolution exp1-20251215-084901-866d63 --agent BANK_A

# Include LLM prompts/responses
payment-sim experiment policy-evolution exp1-20251215-084901-866d63 --llm

# Compact JSON for piping
payment-sim experiment policy-evolution exp1-20251215-084901-866d63 --compact | jq .
```

## Policy Diff

### compute_policy_diff

Calculates a human-readable diff between two policies.

```python
from payment_simulator.experiments.analysis import compute_policy_diff

old_policy = {"parameters": {"threshold": 10}}
new_policy = {"parameters": {"threshold": 15}}

diff = compute_policy_diff(old_policy, new_policy)
# Returns: "parameters.threshold: 10 → 15"
```

### extract_parameter_changes

Extracts structured parameter changes between policies.

```python
from payment_simulator.experiments.analysis import extract_parameter_changes

changes = extract_parameter_changes(old_policy, new_policy)
# Returns: [{"path": "parameters.threshold", "old": 10, "new": 15}]
```

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Experiment Database                       │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  experiment_iterations                               │    │
│  │  ├── iteration (0-indexed)                          │    │
│  │  ├── costs_per_agent (JSON)                         │    │
│  │  ├── accepted_changes (JSON)                        │    │
│  │  └── policies (JSON)                                │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   ExperimentChartService                     │
│  ├── extract_chart_data(run_id, agent_filter, parameter)   │
│  └── Returns: ChartData with ChartDataPoints               │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                render_convergence_chart                      │
│  ├── Builds accepted trajectory (carry-forward)            │
│  ├── Plots dual lines (accepted + all)                     │
│  ├── Adds parameter annotations                            │
│  └── Saves to PNG/PDF/SVG                                  │
└─────────────────────────────────────────────────────────────┘
```

## INV-1 Compliance

All costs in the database are stored as **integer cents** (per INV-1). The analysis module converts to dollars for display:

```python
# Database stores cents
costs_per_agent = {"BANK_A": 8000}  # $80.00 in cents

# ChartData converts to dollars
data_point.cost_dollars = 80.0  # Displayed as $80.00
```

## Module Structure

```
payment_simulator/experiments/analysis/
├── __init__.py              # Public API exports
├── charting.py              # ChartData, ExperimentChartService, render_convergence_chart
├── evolution_model.py       # AgentEvolution, IterationEvolution
├── evolution_service.py     # PolicyEvolutionService
└── policy_diff.py           # compute_policy_diff, extract_parameter_changes
```

## Related Documentation

- [CLI Commands](../cli/commands/experiment.md) - Command-line interface
- [Experiment Runner](runner.md) - How experiments are executed
- [Experiment Configuration](configuration.md) - YAML configuration reference

---

*Last updated: 2025-12-15*
