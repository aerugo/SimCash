"""Chart data extraction and rendering for experiment visualization.

Provides service layer for extracting chart-ready data from experiment runs
and rendering convergence charts with matplotlib.

All costs are converted from integer cents (INV-1) to dollars for display.

Example:
    >>> from pathlib import Path
    >>> from payment_simulator.experiments.persistence import ExperimentRepository
    >>> from payment_simulator.experiments.analysis.charting import (
    ...     ExperimentChartService,
    ...     render_convergence_chart,
    ... )
    >>> repo = ExperimentRepository(Path("experiments.db"))
    >>> service = ExperimentChartService(repo)
    >>> data = service.extract_chart_data("exp1-20251215-084901-866d63")
    >>> render_convergence_chart(data, Path("chart.png"))
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

from payment_simulator.experiments.persistence import ExperimentRepository

# Color palette for pleasant appearance
COLORS = {
    "accepted": "#2563eb",  # Blue - prominent
    "all": "#94a3b8",  # Gray - subtle
    "band": "#dbeafe",  # Light blue - uncertainty band
    "grid": "#e2e8f0",  # Light gray - gridlines
    "text": "#334155",  # Dark gray - text
}


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

    Queries the repository for iteration data and builds chart-ready
    data structures with costs converted to dollars.

    Example:
        >>> service = ExperimentChartService(repo)
        >>> data = service.extract_chart_data(
        ...     run_id="exp1-20251215-084901-866d63",
        ...     agent_filter="BANK_A",
        ...     parameter_name="initial_liquidity_fraction",
        ... )
    """

    def __init__(self, repository: ExperimentRepository) -> None:
        """Initialize with experiment repository.

        Args:
            repository: ExperimentRepository for database access.
        """
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
        # Verify experiment exists
        experiment = self._repo.load_experiment(run_id)
        if experiment is None:
            raise ValueError(f"Experiment run not found: {run_id}")

        # Get evaluation mode from config
        evaluation_mode = experiment.config.get("evaluation", {}).get(
            "mode", "deterministic"
        )

        # Get all iterations
        iterations = self._repo.get_iterations(run_id)

        if not iterations:
            return ChartData(
                run_id=run_id,
                experiment_name=experiment.experiment_name,
                evaluation_mode=evaluation_mode,
                agent_id=agent_filter,
                parameter_name=parameter_name,
                data_points=[],
            )

        # Build data points
        data_points: list[ChartDataPoint] = []

        for iteration in iterations:
            iter_num = iteration.iteration + 1  # 1-indexed for display

            # Calculate cost
            if agent_filter is not None:
                # Single agent cost
                cost_cents = iteration.costs_per_agent.get(agent_filter, 0)
            else:
                # Sum all agent costs for system total
                cost_cents = sum(iteration.costs_per_agent.values())

            # Convert cents to dollars (INV-1 compliance)
            cost_dollars = cost_cents / 100.0

            # Determine if this iteration was accepted
            # For single agent filter, check that agent's acceptance
            # For system total, check if all agents accepted
            if agent_filter is not None:
                accepted = iteration.accepted_changes.get(agent_filter, False)
            else:
                # System-wide: accepted if any agent accepted
                # (This represents that optimization made progress)
                accepted = any(iteration.accepted_changes.values())

            # Extract parameter value if requested
            parameter_value: float | None = None
            if parameter_name is not None and agent_filter is not None:
                parameter_value = self._extract_parameter(
                    iteration.policies.get(agent_filter, {}),
                    parameter_name,
                )

            data_points.append(
                ChartDataPoint(
                    iteration=iter_num,
                    cost_dollars=cost_dollars,
                    accepted=accepted,
                    parameter_value=parameter_value,
                )
            )

        return ChartData(
            run_id=run_id,
            experiment_name=experiment.experiment_name,
            evaluation_mode=evaluation_mode,
            agent_id=agent_filter,
            parameter_name=parameter_name,
            data_points=data_points,
        )

    def _extract_parameter(
        self,
        policy: dict[str, Any],
        parameter_name: str,
    ) -> float | None:
        """Extract a parameter value from a policy dict.

        Looks in policy["parameters"][parameter_name].

        Args:
            policy: Policy dictionary.
            parameter_name: Name of parameter to extract.

        Returns:
            Parameter value as float, or None if not found.
        """
        if not policy:
            return None

        parameters = policy.get("parameters", {})
        value = parameters.get(parameter_name)

        if value is None:
            return None

        try:
            return float(value)
        except (ValueError, TypeError):
            return None


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
    if not data.data_points:
        raise ValueError("Cannot render chart with no data points")

    # Set up figure with clean style
    plt.style.use("seaborn-v0_8-whitegrid")
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
        _add_parameter_annotations(ax, data, accepted_costs)

    # Styling
    title = f"Cost Convergence - {data.run_id}"
    if data.agent_id:
        title += f" ({data.agent_id})"
    ax.set_title(title, fontsize=14, fontweight="medium", color=COLORS["text"])

    ax.set_xlabel("Iteration", fontsize=12, color=COLORS["text"])
    ax.set_ylabel("Cost ($)", fontsize=12, color=COLORS["text"])

    # Format y-axis as currency
    ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("$%.2f"))

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
    last_accepted_cost: float | None = None

    for point in data_points:
        if point.accepted:
            last_accepted_cost = point.cost_dollars
        # Use last accepted cost, or current cost if none accepted yet
        trajectory.append(
            last_accepted_cost if last_accepted_cost is not None else point.cost_dollars
        )

    return trajectory


def _add_parameter_annotations(
    ax: plt.Axes,
    data: ChartData,
    accepted_costs: list[float],
) -> None:
    """Add parameter value annotations to chart.

    Places text annotations above accepted data points showing
    the parameter value at that iteration.

    Args:
        ax: Matplotlib axes object.
        data: ChartData with parameter values.
        accepted_costs: Y-coordinates for the accepted line.
    """
    for i, point in enumerate(data.data_points):
        if point.accepted and point.parameter_value is not None:
            ax.annotate(
                f"{point.parameter_value:.2f}",
                xy=(point.iteration, accepted_costs[i]),
                xytext=(0, 10),
                textcoords="offset points",
                ha="center",
                fontsize=9,
                color=COLORS["text"],
                alpha=0.8,
            )
