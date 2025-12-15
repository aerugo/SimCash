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

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

from payment_simulator.experiments.persistence import ExperimentRepository


@dataclass(frozen=True)
class ParsedIterationData:
    """Iteration data parsed from LLM user_prompt.

    Attributes:
        iteration: Iteration number (1-indexed).
        cost_cents: Cost in integer cents.
        is_best: True if this is the best policy so far.
        is_accepted: True if policy was accepted (BEST or KEPT).
        parameter_value: Parameter value if extractable.
    """

    iteration: int
    cost_cents: int
    is_best: bool
    is_accepted: bool
    parameter_value: float | None = None


def _parse_iteration_history_from_llm_prompt(
    user_prompt: str,
    parameter_name: str | None = None,
) -> list[ParsedIterationData]:
    """Parse iteration history from LLM user_prompt.

    Extracts cost and acceptance status from the Metrics Summary Table
    in the LLM user_prompt. Also extracts parameter values from the
    Detailed Changes Per Iteration section if parameter_name is provided.

    Args:
        user_prompt: The user_prompt from LLM interaction event.
        parameter_name: Optional parameter name to extract values for.

    Returns:
        List of ParsedIterationData, one per iteration.
    """
    results: list[ParsedIterationData] = []

    # Pattern to match metrics table rows:
    # | 1 | ⭐ BEST | $39,840 | ... or
    # | 1 | ✅ KEPT | $15,127 | ... or
    # | 1 | ❌ REJECTED | $15,643 | ...
    metrics_pattern = r"\|\s*(\d+)\s*\|\s*(⭐ BEST|✅ KEPT|❌ REJECTED)\s*\|\s*\$([0-9,]+)\s*\|"
    metrics_matches = re.findall(metrics_pattern, user_prompt)

    # Build parameter value lookup from Detailed Changes section
    param_values: dict[int, float] = {}
    if parameter_name:
        # Pattern to find parameter values in the iterations
        # Looking for: "initial_liquidity_fraction": 0.15
        # in the Iteration X section
        iter_sections = re.findall(
            r"####\s*[⭐✅❌]\s*Iteration\s+(\d+).*?```json\s*\{([^}]+)\}",
            user_prompt,
            re.DOTALL,
        )
        for iter_str, json_content in iter_sections:
            iter_num = int(iter_str)
            # Look for the parameter value
            param_pattern = rf'"{re.escape(parameter_name)}"\s*:\s*([0-9.]+)'
            param_match = re.search(param_pattern, json_content)
            if param_match:
                try:
                    param_values[iter_num] = float(param_match.group(1))
                except ValueError:
                    pass

    # Build ParsedIterationData for each match
    for match in metrics_matches:
        iter_num = int(match[0])
        status = match[1]
        cost_str = match[2].replace(",", "")
        cost_cents = int(cost_str) * 100  # Convert dollars to cents

        is_best = status == "⭐ BEST"
        is_accepted = status != "❌ REJECTED"

        results.append(
            ParsedIterationData(
                iteration=iter_num,
                cost_cents=cost_cents,
                is_best=is_best,
                is_accepted=is_accepted,
                parameter_value=param_values.get(iter_num),
            )
        )

    return results


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

        For bootstrap mode experiments with an agent filter, extracts data
        from LLM events (which contain proposed policy costs and acceptance
        status). Falls back to experiment_iterations table for deterministic
        mode or system total views.

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

        # Try to extract from LLM events for bootstrap mode with agent filter
        # LLM events contain the full iteration history with proposed costs
        if evaluation_mode == "bootstrap" and agent_filter is not None:
            data_points = self._extract_from_llm_events(
                run_id, agent_filter, parameter_name
            )
            if data_points:
                return ChartData(
                    run_id=run_id,
                    experiment_name=experiment.experiment_name,
                    evaluation_mode=evaluation_mode,
                    agent_id=agent_filter,
                    parameter_name=parameter_name,
                    data_points=data_points,
                )

        # Fall back to experiment_iterations table
        return self._extract_from_iterations_table(
            run_id=run_id,
            experiment=experiment,
            evaluation_mode=evaluation_mode,
            agent_filter=agent_filter,
            parameter_name=parameter_name,
        )

    def _extract_from_llm_events(
        self,
        run_id: str,
        agent_filter: str,
        parameter_name: str | None,
    ) -> list[ChartDataPoint]:
        """Extract chart data from LLM interaction events.

        Parses the iteration history from the latest LLM user_prompt
        for the specified agent. This provides accurate costs for
        both accepted and rejected policies.

        Args:
            run_id: Experiment run ID.
            agent_filter: Agent ID to extract data for.
            parameter_name: Optional parameter name to extract.

        Returns:
            List of ChartDataPoints, empty if no LLM events found.
        """
        # Get all events for this run
        all_events = self._repo.get_all_events(run_id)

        # Find the latest LLM interaction for this agent
        latest_llm_event = None
        latest_iteration = -1

        for event in all_events:
            if event.event_type != "llm_interaction":
                continue
            agent_id = event.event_data.get("agent_id", "")
            if agent_id != agent_filter:
                continue
            if event.iteration > latest_iteration:
                latest_iteration = event.iteration
                latest_llm_event = event

        if latest_llm_event is None:
            return []

        # Get user_prompt from event
        user_prompt = latest_llm_event.event_data.get("user_prompt", "")
        if not user_prompt:
            return []

        # Parse iteration history from the prompt
        parsed_data = _parse_iteration_history_from_llm_prompt(
            user_prompt, parameter_name
        )

        if not parsed_data:
            return []

        # Convert to ChartDataPoints
        data_points: list[ChartDataPoint] = []
        for parsed in parsed_data:
            data_points.append(
                ChartDataPoint(
                    iteration=parsed.iteration,
                    cost_dollars=parsed.cost_cents / 100.0,
                    accepted=parsed.is_accepted,
                    parameter_value=parsed.parameter_value,
                )
            )

        return data_points

    def _extract_from_iterations_table(
        self,
        run_id: str,
        experiment: Any,
        evaluation_mode: str,
        agent_filter: str | None,
        parameter_name: str | None,
    ) -> ChartData:
        """Extract chart data from experiment_iterations table.

        Falls back method when LLM events are not available.

        Args:
            run_id: Experiment run ID.
            experiment: Experiment record.
            evaluation_mode: "deterministic" or "bootstrap".
            agent_filter: Optional agent ID to filter costs.
            parameter_name: Optional parameter to extract.

        Returns:
            ChartData with data from iterations table.
        """
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

        data_points: list[ChartDataPoint] = []

        for iteration in iterations:
            iter_num = iteration.iteration + 1  # 1-indexed for display

            # Calculate cost
            if agent_filter is not None:
                cost_cents = iteration.costs_per_agent.get(agent_filter, 0)
            else:
                cost_cents = sum(iteration.costs_per_agent.values())

            cost_dollars = cost_cents / 100.0

            # Determine acceptance status
            if agent_filter is not None:
                accepted = iteration.accepted_changes.get(agent_filter, False)
            else:
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
    the parameter name and value at that iteration.

    Args:
        ax: Matplotlib axes object.
        data: ChartData with parameter values.
        accepted_costs: Y-coordinates for the accepted line.
    """
    for i, point in enumerate(data.data_points):
        if point.accepted and point.parameter_value is not None:
            # Include parameter name in annotation for clarity
            if data.parameter_name:
                label = f"{data.parameter_name}: {point.parameter_value:.2f}"
            else:
                label = f"{point.parameter_value:.2f}"
            ax.annotate(
                label,
                xy=(point.iteration, accepted_costs[i]),
                xytext=(0, 10),
                textcoords="offset points",
                ha="center",
                fontsize=8,  # Slightly smaller to fit longer text
                color=COLORS["text"],
                alpha=0.8,
            )
