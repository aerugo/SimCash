# Phase 2: Chart Rendering

**Status**: Pending
**Started**: -

---

## Objective

Implement matplotlib-based chart rendering with proper styling, dual-line visualization, and parameter annotation support.

---

## TDD Steps

### Step 2.1: Write Failing Tests (RED)

Add to `api/tests/experiments/analysis/test_charting.py`:

**Test Cases**:
1. `test_render_chart_creates_file` - Output file is created
2. `test_render_chart_with_parameter_annotations` - Parameter values shown on chart
3. `test_render_chart_styling` - Verify chart has expected elements (title, labels)
4. `test_render_chart_dual_lines` - Both accepted and all policy lines present

```python
class TestChartRendering:
    def test_render_chart_creates_file(self, tmp_path: Path) -> None:
        """Chart file is created at specified path."""
        # Create sample ChartData
        # Call render_convergence_chart(data, output_path)
        # Verify file exists

    def test_render_chart_with_parameter_annotations(self, tmp_path: Path) -> None:
        """Parameter values are annotated on data points."""
        # Create ChartData with parameter_values
        # Render chart
        # Verify file created (visual inspection for now)

    def test_render_chart_styling(self, tmp_path: Path) -> None:
        """Chart has title, axis labels, legend."""
        # Render chart
        # Read back with matplotlib and verify elements exist

    def test_render_chart_dual_lines(self, tmp_path: Path) -> None:
        """Both accepted and all policy lines are rendered."""
        # Create data with mix of accepted/rejected
        # Verify chart file created
```

### Step 2.2: Implement to Pass Tests (GREEN)

Add to `api/payment_simulator/experiments/analysis/charting.py`:

```python
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker


# Color palette for pleasant appearance
COLORS = {
    "accepted": "#2563eb",      # Blue - prominent
    "all": "#94a3b8",           # Gray - subtle
    "band": "#dbeafe",          # Light blue - uncertainty band
    "grid": "#e2e8f0",          # Light gray - gridlines
    "text": "#334155",          # Dark gray - text
}


def render_convergence_chart(
    data: ChartData,
    output_path: Path,
    show_all_policies: bool = True,
    figsize: tuple[float, float] = (10, 6),
    dpi: int = 150,
) -> None:
    """Render experiment convergence chart to file.

    Creates a line plot showing cost convergence over iterations with:
    - Primary line: Cost trajectory following accepted policies
    - Secondary line: Cost of all tested policies (subtle, dashed)
    - Optional: Parameter value annotations at each point

    Args:
        data: ChartData extracted from experiment.
        output_path: Path to save chart image (PNG, PDF, SVG supported).
        show_all_policies: Whether to show the "all policies" line.
        figsize: Figure size in inches (width, height).
        dpi: Resolution for raster output.

    Example:
        >>> render_convergence_chart(data, Path("chart.png"))
    """
    # Set up figure with clean style
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=figsize)

    # Extract data series
    iterations = [p.iteration for p in data.data_points]
    all_costs = [p.cost_dollars for p in data.data_points]

    # Build accepted cost trajectory (carry forward last accepted)
    accepted_costs = _build_accepted_trajectory(data.data_points)

    # Plot all policies line (subtle, behind)
    if show_all_policies:
        ax.plot(
            iterations,
            all_costs,
            color=COLORS["all"],
            linestyle="--",
            linewidth=1.5,
            alpha=0.7,
            label="All Policies",
            marker=".",
            markersize=4,
        )

    # Plot accepted policies line (prominent, front)
    ax.plot(
        iterations,
        accepted_costs,
        color=COLORS["accepted"],
        linewidth=2.5,
        label="Accepted Policies",
        marker="o",
        markersize=6,
    )

    # Add parameter annotations if present
    if data.parameter_name:
        _add_parameter_annotations(ax, data)

    # Styling
    title = f"Cost Convergence - {data.run_id}"
    if data.agent_id:
        title += f" ({data.agent_id})"
    ax.set_title(title, fontsize=14, fontweight="medium", color=COLORS["text"])

    ax.set_xlabel("Iteration", fontsize=12, color=COLORS["text"])
    ax.set_ylabel("Cost ($)", fontsize=12, color=COLORS["text"])

    # Format y-axis as currency
    ax.yaxis.set_major_formatter(ticker.FormatStrFormatter('$%.2f'))

    # Integer x-axis ticks
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))

    # Legend
    ax.legend(loc="upper right", framealpha=0.9)

    # Clean up spines
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Grid styling
    ax.grid(True, alpha=0.3, color=COLORS["grid"])

    # Tight layout and save
    plt.tight_layout()
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def _build_accepted_trajectory(data_points: list[ChartDataPoint]) -> list[float]:
    """Build cost trajectory following accepted policies.

    For accepted iterations, use the cost.
    For rejected iterations, carry forward the previous accepted cost.

    Args:
        data_points: List of ChartDataPoint with accepted flags.

    Returns:
        List of costs representing the accepted trajectory.
    """
    trajectory: list[float] = []
    last_accepted_cost = 0.0

    for point in data_points:
        if point.accepted:
            last_accepted_cost = point.cost_dollars
        trajectory.append(last_accepted_cost)

    return trajectory


def _add_parameter_annotations(ax: plt.Axes, data: ChartData) -> None:
    """Add parameter value annotations to chart.

    Places text annotations above accepted data points showing
    the parameter value at that iteration.

    Args:
        ax: Matplotlib axes object.
        data: ChartData with parameter values.
    """
    for point in data.data_points:
        if point.accepted and point.parameter_value is not None:
            ax.annotate(
                f"{point.parameter_value:.2f}",
                xy=(point.iteration, point.cost_dollars),
                xytext=(0, 10),
                textcoords="offset points",
                ha="center",
                fontsize=9,
                color=COLORS["text"],
                alpha=0.8,
            )
```

### Step 2.3: Refactor

- Extract color palette to module constant
- Ensure consistent styling
- Add support for uncertainty bands (bootstrap mode enhancement)

---

## Implementation Details

### Styling Guidelines

- **Clean, minimal**: Remove unnecessary chart chrome
- **Publication quality**: Suitable for papers/reports
- **Accessible colors**: Distinct for colorblind users
- **Readable text**: Large enough fonts, good contrast

### Accepted Trajectory Logic

The "accepted" line shows what cost would be achieved if you only took accepted policy changes:
- Start with iteration 1 cost (baseline)
- Each time a policy is accepted, update the trajectory cost
- Each time a policy is rejected, carry forward previous cost

This creates a non-decreasing improvement line (assuming optimization works).

### Output Formats

Support based on file extension:
- `.png` - Raster, good for web/docs
- `.pdf` - Vector, good for papers
- `.svg` - Vector, good for web

---

## Files

| File | Action |
|------|--------|
| `api/payment_simulator/experiments/analysis/charting.py` | MODIFY (add rendering) |
| `api/tests/experiments/analysis/test_charting.py` | MODIFY (add rendering tests) |

---

## Verification

```bash
# Run tests
cd api
.venv/bin/python -m pytest tests/experiments/analysis/test_charting.py -v

# Manual verification - generate sample chart
.venv/bin/python -c "
from pathlib import Path
from payment_simulator.experiments.analysis.charting import (
    ChartData, ChartDataPoint, render_convergence_chart
)
data = ChartData(
    run_id='test-run',
    experiment_name='test',
    evaluation_mode='deterministic',
    agent_id=None,
    parameter_name=None,
    data_points=[
        ChartDataPoint(1, 80.0, True),
        ChartDataPoint(2, 75.0, False),
        ChartDataPoint(3, 70.0, True),
        ChartDataPoint(4, 65.0, True),
        ChartDataPoint(5, 60.0, False),
        ChartDataPoint(6, 55.0, True),
    ]
)
render_convergence_chart(data, Path('test_chart.png'))
print('Chart saved to test_chart.png')
"
```

---

## Completion Criteria

- [ ] Chart renders to PNG/PDF/SVG
- [ ] Dual-line visualization works
- [ ] Parameter annotations display correctly
- [ ] Styling is clean and professional
- [ ] All tests pass
- [ ] Type check passes
