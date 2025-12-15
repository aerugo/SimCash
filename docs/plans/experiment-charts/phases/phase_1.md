# Phase 1: Chart Data Extraction

**Status**: Pending
**Started**: -

---

## Objective

Create a service that extracts chart-ready data from the experiment database, including iteration costs, acceptance status, and policy parameters.

---

## Invariants Enforced in This Phase

- INV-1: Costs stored as integer cents, service converts to float dollars for chart display
- Data comes from `experiment_iterations` table, same source as replay (INV-5)

---

## TDD Steps

### Step 1.1: Write Failing Tests (RED)

Create `api/tests/experiments/analysis/test_charting.py`:

**Test Cases**:
1. `test_extract_chart_data_basic` - Extract costs for all iterations
2. `test_extract_chart_data_separates_accepted` - Accepted vs all policies distinguished
3. `test_extract_chart_data_agent_filter` - Filter to single agent
4. `test_extract_chart_data_parameter_extraction` - Extract parameter values from policies
5. `test_extract_chart_data_empty_run` - Handle run with no iterations
6. `test_extract_chart_data_run_not_found` - Error on invalid run_id

```python
class TestExperimentChartService:
    def test_extract_chart_data_basic(self) -> None:
        """Extract costs for all iterations."""
        # Setup mock repository with sample iterations
        # Call service.extract_chart_data(run_id)
        # Verify data points have correct iteration numbers and costs

    def test_extract_chart_data_separates_accepted(self) -> None:
        """Accepted vs all policies are distinguished."""
        # Setup iterations where some are accepted, some rejected
        # Verify accepted_costs and all_costs are different

    def test_extract_chart_data_agent_filter(self) -> None:
        """Filter to single agent's costs."""
        # Setup multi-agent iterations
        # Call with agent_filter="BANK_A"
        # Verify only BANK_A costs returned

    def test_extract_chart_data_parameter_extraction(self) -> None:
        """Extract parameter values from policies."""
        # Setup iterations with policies containing initial_liquidity_fraction
        # Call with parameter_name="initial_liquidity_fraction"
        # Verify parameter values extracted correctly

    def test_extract_chart_data_empty_run(self) -> None:
        """Handle run with no iterations gracefully."""
        # Setup empty iterations list
        # Verify returns empty ChartData

    def test_extract_chart_data_run_not_found(self) -> None:
        """Error on invalid run_id."""
        # Call with non-existent run_id
        # Verify raises ValueError
```

### Step 1.2: Implement to Pass Tests (GREEN)

Create `api/payment_simulator/experiments/analysis/charting.py`:

```python
"""Chart data extraction for experiment visualization.

Provides service layer for extracting chart-ready data from experiment runs.
All costs are converted from integer cents (INV-1) to dollars for display.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from payment_simulator.experiments.persistence import ExperimentRepository


@dataclass(frozen=True)
class ChartDataPoint:
    """Single data point for chart visualization.

    Attributes:
        iteration: Iteration number (1-indexed for display).
        cost_dollars: Cost in dollars (converted from cents).
        accepted: Whether this policy was accepted.
        parameter_value: Optional parameter value (when --parameter used).
    """

    iteration: int
    cost_dollars: float
    accepted: bool
    parameter_value: float | None = None


@dataclass(frozen=True)
class ChartData:
    """Complete data for rendering experiment chart.

    Attributes:
        run_id: Experiment run identifier.
        experiment_name: Name of the experiment.
        evaluation_mode: "deterministic" or "bootstrap".
        agent_id: Agent ID if filtered, None for system total.
        parameter_name: Parameter being tracked, if any.
        data_points: List of data points for all iterations.
    """

    run_id: str
    experiment_name: str
    evaluation_mode: str
    agent_id: str | None
    parameter_name: str | None
    data_points: list[ChartDataPoint]


class ExperimentChartService:
    """Service for extracting chart data from experiments.

    Example:
        >>> service = ExperimentChartService(repo)
        >>> data = service.extract_chart_data(
        ...     run_id="exp1-20251215-084901-866d63",
        ...     agent_filter="BANK_A",
        ...     parameter_name="initial_liquidity_fraction",
        ... )
    """

    def __init__(self, repository: ExperimentRepository) -> None:
        """Initialize with experiment repository."""
        self._repo = repository

    def extract_chart_data(
        self,
        run_id: str,
        agent_filter: str | None = None,
        parameter_name: str | None = None,
    ) -> ChartData:
        """Extract chart data from experiment run.

        Args:
            run_id: Experiment run ID.
            agent_filter: Optional agent ID to filter costs.
            parameter_name: Optional parameter to extract from policies.

        Returns:
            ChartData ready for rendering.

        Raises:
            ValueError: If run_id not found.
        """
        ...
```

### Step 1.3: Refactor

- Ensure type safety (no bare `Any` where avoidable)
- Add docstrings with examples
- Optimize for readability

---

## Implementation Details

### Cost Calculation

For **deterministic** mode:
- System total: `sum(costs_per_agent.values())` converted to dollars

For **bootstrap** mode:
- Same calculation - costs stored are already the evaluation costs

### Accepted vs All

For each iteration:
- **All**: Include all data points regardless of `accepted_changes`
- **Accepted**: Only include iteration if `all(accepted_changes.values()) == True` OR track cumulative accepted state

Actually, for the "accepted policies" line, we want to show the cost trajectory of the policy that was ultimately kept at each iteration. This means:
- Iteration 1: Always show (initial policy)
- Iteration N: Show cost if this iteration's policy was accepted, otherwise show previous accepted cost

### Parameter Extraction

For `--parameter initial_liquidity_fraction`:
- Access `policies[agent_id]["parameters"]["initial_liquidity_fraction"]`
- Handle missing keys gracefully (None)

---

## Files

| File | Action |
|------|--------|
| `api/payment_simulator/experiments/analysis/charting.py` | CREATE |
| `api/tests/experiments/analysis/test_charting.py` | CREATE |
| `api/payment_simulator/experiments/analysis/__init__.py` | MODIFY (add export) |

---

## Verification

```bash
# Run tests
cd api
.venv/bin/python -m pytest tests/experiments/analysis/test_charting.py -v

# Type check
.venv/bin/python -m mypy payment_simulator/experiments/analysis/charting.py

# Lint
.venv/bin/python -m ruff check payment_simulator/experiments/analysis/charting.py
```

---

## Completion Criteria

- [ ] All test cases pass
- [ ] Type check passes
- [ ] Lint passes
- [ ] Docstrings added with examples
- [ ] Handles edge cases (empty run, missing agent, missing parameter)
- [ ] INV-1 verified: costs converted from cents to dollars
