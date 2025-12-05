"""Chart generation for castro experiments.

Provides matplotlib-based visualizations for experiment analysis.
All charts follow a consistent style with clear labeling.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import duckdb
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

if TYPE_CHECKING:
    from experiments.castro.castro.core.types import (
        AcceptanceData,
        CostRibbonData,
        PerAgentCostData,
        SettlementRateData,
    )


def _fetch_cost_ribbon_data(db_path: str) -> CostRibbonData | None:
    """Fetch data for cost ribbon chart from database."""
    conn = duckdb.connect(db_path, read_only=True)

    data = conn.execute(
        """
        SELECT
            iteration_number,
            total_cost_mean,
            best_seed_cost,
            worst_seed_cost
        FROM iteration_metrics
        ORDER BY iteration_number
    """
    ).fetchall()
    conn.close()

    if not data:
        return None

    # Deduplicate by taking last entry per iteration
    seen: dict[int, tuple[float, int, int]] = {}
    for row in data:
        iter_num, mean_cost, best_cost, worst_cost = row
        seen[iter_num] = (mean_cost, best_cost, worst_cost)

    iterations = sorted(seen.keys())
    return {
        "iterations": iterations,
        "mean_costs": [seen[i][0] for i in iterations],
        "best_costs": [seen[i][1] for i in iterations],
        "worst_costs": [seen[i][2] for i in iterations],
    }


def generate_cost_ribbon_chart(
    db_path: str,
    output_path: Path,
    experiment_name: str,
) -> None:
    """Generate a ribbon plot showing cost evolution over iterations.

    Creates a chart with:
    - Mean cost line (center)
    - Best cost line (lower bound)
    - Worst cost line (upper bound)
    - Filled ribbon between best and worst

    Args:
        db_path: Path to the experiment database
        output_path: Path where the chart should be saved
        experiment_name: Name of the experiment for the chart title
    """
    chart_data = _fetch_cost_ribbon_data(db_path)
    if not chart_data:
        print("  No iteration data found for chart generation")
        return

    iterations = chart_data["iterations"]
    mean_costs = chart_data["mean_costs"]
    best_costs = chart_data["best_costs"]
    worst_costs = chart_data["worst_costs"]

    # Create the figure
    fig, ax = plt.subplots(figsize=(12, 7))

    # Plot the ribbon (filled area between best and worst)
    ax.fill_between(
        iterations,
        best_costs,
        worst_costs,
        alpha=0.3,
        color="steelblue",
        label="Best-Worst Range",
    )

    # Plot the lines
    ax.plot(
        iterations,
        worst_costs,
        "o-",
        color="indianred",
        linewidth=1.5,
        markersize=5,
        label="Worst Cost",
        alpha=0.8,
    )
    ax.plot(
        iterations,
        mean_costs,
        "o-",
        color="steelblue",
        linewidth=2.5,
        markersize=7,
        label="Average Cost",
    )
    ax.plot(
        iterations,
        best_costs,
        "o-",
        color="seagreen",
        linewidth=1.5,
        markersize=5,
        label="Best Cost",
        alpha=0.8,
    )

    # Find and annotate the best iteration
    min_mean_cost = min(mean_costs)
    best_iter_idx = mean_costs.index(min_mean_cost)
    best_iter = iterations[best_iter_idx]

    ax.annotate(
        f"Best Avg: ${min_mean_cost:,.0f}",
        xy=(best_iter, min_mean_cost),
        xytext=(best_iter + 1, min_mean_cost * 1.15),
        arrowprops={"arrowstyle": "->", "color": "steelblue", "lw": 1.5},
        fontsize=11,
        fontweight="bold",
        color="steelblue",
    )

    # Formatting
    ax.set_xlabel("Iteration", fontsize=13)
    ax.set_ylabel("Total Cost ($)", fontsize=13)
    ax.set_title(f"Cost Over Iterations - {experiment_name}", fontsize=14, fontweight="bold")

    # Format y-axis with dollar amounts
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"${x:,.0f}"))

    # Legend
    ax.legend(loc="upper right", fontsize=11)

    # Grid
    ax.grid(True, alpha=0.3, linestyle="--")

    # Set axis limits with some padding
    ax.set_xlim(min(iterations) - 0.5, max(iterations) + 0.5)
    y_min = min(best_costs) * 0.9
    y_max = max(worst_costs) * 1.1
    ax.set_ylim(y_min, y_max)

    # Add summary statistics as text box
    final_mean = mean_costs[-1]
    final_best = best_costs[-1]
    final_worst = worst_costs[-1]
    improvement = (
        ((mean_costs[0] - min_mean_cost) / mean_costs[0] * 100) if mean_costs[0] > 0 else 0
    )

    stats_text = (
        f"Final (Iter {iterations[-1]}):\n"
        f"  Avg: ${final_mean:,.0f}\n"
        f"  Best: ${final_best:,.0f}\n"
        f"  Worst: ${final_worst:,.0f}\n"
        f"Improvement: {improvement:.1f}%"
    )
    ax.text(
        0.02,
        0.98,
        stats_text,
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment="top",
        fontfamily="monospace",
        bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.8, "edgecolor": "gray"},
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

    print(f"  Cost ribbon chart saved to: {output_path}")


def _fetch_settlement_rate_data(db_path: str) -> SettlementRateData | None:
    """Fetch data for settlement rate chart from database."""
    conn = duckdb.connect(db_path, read_only=True)

    data = conn.execute(
        """
        SELECT
            iteration_number,
            settlement_rate_mean,
            failure_rate
        FROM iteration_metrics
        ORDER BY iteration_number
    """
    ).fetchall()
    conn.close()

    if not data:
        return None

    # Deduplicate by taking last entry per iteration
    seen: dict[int, tuple[float, float]] = {}
    for row in data:
        iter_num, settlement_rate, failure_rate = row
        seen[iter_num] = (settlement_rate, failure_rate)

    iterations = sorted(seen.keys())
    return {
        "iterations": iterations,
        "settlement_rates": [seen[i][0] * 100 for i in iterations],  # Convert to percentage
        "failure_rates": [seen[i][1] * 100 for i in iterations],
    }


def generate_settlement_rate_chart(
    db_path: str,
    output_path: Path,
    experiment_name: str,
) -> None:
    """Generate a chart showing settlement rate over iterations.

    Args:
        db_path: Path to the experiment database
        output_path: Path where the chart should be saved
        experiment_name: Name of the experiment for the chart title
    """
    chart_data = _fetch_settlement_rate_data(db_path)
    if not chart_data:
        print("  No iteration data found for settlement rate chart")
        return

    iterations = chart_data["iterations"]
    settlement_rates = chart_data["settlement_rates"]
    failure_rates = chart_data["failure_rates"]

    # Create the figure
    fig, ax = plt.subplots(figsize=(12, 7))

    # Plot settlement rate
    ax.plot(
        iterations,
        settlement_rates,
        "o-",
        color="seagreen",
        linewidth=2.5,
        markersize=7,
        label="Settlement Rate",
    )

    # Plot failure rate if any failures exist
    if any(f > 0 for f in failure_rates):
        ax.plot(
            iterations,
            failure_rates,
            "s--",
            color="indianred",
            linewidth=1.5,
            markersize=5,
            label="Failure Rate",
            alpha=0.8,
        )

    # Formatting
    ax.set_xlabel("Iteration", fontsize=13)
    ax.set_ylabel("Rate (%)", fontsize=13)
    ax.set_title(
        f"Settlement Rate Over Iterations - {experiment_name}", fontsize=14, fontweight="bold"
    )

    # Legend
    ax.legend(loc="lower right", fontsize=11)

    # Grid
    ax.grid(True, alpha=0.3, linestyle="--")

    # Set axis limits
    ax.set_xlim(min(iterations) - 0.5, max(iterations) + 0.5)
    ax.set_ylim(0, 105)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

    print(f"  Settlement rate chart saved to: {output_path}")


def _fetch_per_agent_cost_data(db_path: str) -> PerAgentCostData | None:
    """Fetch data for per-agent cost chart from database."""
    conn = duckdb.connect(db_path, read_only=True)

    data = conn.execute(
        """
        SELECT
            iteration_number,
            AVG(bank_a_cost) as avg_bank_a_cost,
            AVG(bank_b_cost) as avg_bank_b_cost,
            AVG(total_cost) as avg_total_cost
        FROM simulation_runs
        GROUP BY iteration_number
        ORDER BY iteration_number
    """
    ).fetchall()
    conn.close()

    if not data:
        return None

    return {
        "iterations": [row[0] for row in data],
        "bank_a_costs": [row[1] for row in data],
        "bank_b_costs": [row[2] for row in data],
    }


def generate_per_agent_cost_chart(
    db_path: str,
    output_path: Path,
    experiment_name: str,
) -> None:
    """Generate a chart showing per-agent cost breakdown over iterations.

    Args:
        db_path: Path to the experiment database
        output_path: Path where the chart should be saved
        experiment_name: Name of the experiment for the chart title
    """
    chart_data = _fetch_per_agent_cost_data(db_path)
    if not chart_data:
        print("  No simulation run data found for per-agent cost chart")
        return

    iterations = chart_data["iterations"]
    bank_a_costs = chart_data["bank_a_costs"]
    bank_b_costs = chart_data["bank_b_costs"]

    # Create the figure
    fig, ax = plt.subplots(figsize=(12, 7))

    # Plot stacked area chart
    ax.stackplot(
        iterations,
        bank_a_costs,
        bank_b_costs,
        labels=["BANK_A", "BANK_B"],
        colors=["steelblue", "coral"],
        alpha=0.7,
    )

    # Formatting
    ax.set_xlabel("Iteration", fontsize=13)
    ax.set_ylabel("Cost ($)", fontsize=13)
    ax.set_title(f"Per-Agent Cost Breakdown - {experiment_name}", fontsize=14, fontweight="bold")

    # Format y-axis with dollar amounts
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"${x:,.0f}"))

    # Legend
    ax.legend(loc="upper right", fontsize=11)

    # Grid
    ax.grid(True, alpha=0.3, linestyle="--")

    # Set axis limits
    ax.set_xlim(min(iterations), max(iterations))

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

    print(f"  Per-agent cost chart saved to: {output_path}")


def _fetch_acceptance_data(db_path: str) -> AcceptanceData | None:
    """Fetch data for acceptance chart from database."""
    conn = duckdb.connect(db_path, read_only=True)

    data = conn.execute(
        """
        SELECT
            iteration_number,
            total_cost_mean,
            policy_was_accepted,
            is_best_iteration
        FROM iteration_metrics
        ORDER BY iteration_number
    """
    ).fetchall()
    conn.close()

    if not data:
        return None

    # Deduplicate by taking last entry per iteration
    seen: dict[int, tuple[float, bool, bool]] = {}
    for row in data:
        iter_num, mean_cost, accepted, is_best = row
        seen[iter_num] = (mean_cost, accepted, is_best)

    iterations = sorted(seen.keys())
    return {
        "iterations": iterations,
        "mean_costs": [seen[i][0] for i in iterations],
        "accepted": [seen[i][1] for i in iterations],
        "is_best": [seen[i][2] for i in iterations],
    }


def generate_acceptance_chart(
    db_path: str,
    output_path: Path,
    experiment_name: str,
) -> None:
    """Generate a chart showing accepted vs rejected iterations.

    Args:
        db_path: Path to the experiment database
        output_path: Path where the chart should be saved
        experiment_name: Name of the experiment for the chart title
    """
    chart_data = _fetch_acceptance_data(db_path)
    if not chart_data:
        print("  No iteration data found for acceptance chart")
        return

    iterations = chart_data["iterations"]
    mean_costs = chart_data["mean_costs"]
    accepted = chart_data["accepted"]
    is_best = chart_data["is_best"]

    # Create the figure
    fig, ax = plt.subplots(figsize=(12, 7))

    # Plot all points
    for i, iter_num in enumerate(iterations):
        color = "seagreen" if accepted[i] else "indianred"
        marker = "*" if is_best[i] else "o"
        size = 200 if is_best[i] else 80
        ax.scatter(iter_num, mean_costs[i], c=color, marker=marker, s=size, zorder=3)

    # Connect with line
    ax.plot(iterations, mean_costs, "-", color="gray", linewidth=1, alpha=0.5, zorder=1)

    # Add legend
    legend_elements = [
        Line2D(
            [0], [0], marker="o", color="w", markerfacecolor="seagreen", markersize=10,
            label="Accepted"
        ),
        Line2D(
            [0], [0], marker="o", color="w", markerfacecolor="indianred", markersize=10,
            label="Rejected"
        ),
        Line2D(
            [0], [0], marker="*", color="w", markerfacecolor="gold", markersize=15,
            label="Best"
        ),
    ]
    ax.legend(handles=legend_elements, loc="upper right", fontsize=11)

    # Formatting
    ax.set_xlabel("Iteration", fontsize=13)
    ax.set_ylabel("Mean Cost ($)", fontsize=13)
    ax.set_title(f"Iteration Acceptance - {experiment_name}", fontsize=14, fontweight="bold")

    # Format y-axis with dollar amounts
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"${x:,.0f}"))

    # Grid
    ax.grid(True, alpha=0.3, linestyle="--")

    # Count statistics
    num_accepted = sum(1 for a in accepted if a)
    num_rejected = sum(1 for a in accepted if not a)
    stats_text = f"Accepted: {num_accepted}\nRejected: {num_rejected}"
    ax.text(
        0.02,
        0.98,
        stats_text,
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment="top",
        fontfamily="monospace",
        bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.8, "edgecolor": "gray"},
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

    print(f"  Acceptance chart saved to: {output_path}")


def generate_all_charts(db_path: str, output_dir: Path | None = None) -> None:
    """Generate all charts from an existing experiment database.

    Args:
        db_path: Path to the experiment database
        output_dir: Directory to save charts (default: same directory as database)
    """
    db_path_obj = Path(db_path)

    if not db_path_obj.exists():
        print(f"Error: Database not found: {db_path}")
        return

    # Determine output directory
    if output_dir is None:
        output_dir = db_path_obj.parent

    output_dir.mkdir(parents=True, exist_ok=True)

    # Get experiment name from database
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        result = conn.execute("SELECT experiment_name FROM experiment_config LIMIT 1").fetchone()
        experiment_name = result[0] if result else "Unknown Experiment"
    except Exception:
        experiment_name = "Unknown Experiment"
    finally:
        conn.close()

    print(f"\nGenerating charts for: {experiment_name}")
    print(f"Output directory: {output_dir}")
    print("-" * 60)

    # Generate all charts
    generate_cost_ribbon_chart(
        db_path=str(db_path),
        output_path=output_dir / "cost_over_iterations.png",
        experiment_name=experiment_name,
    )

    generate_settlement_rate_chart(
        db_path=str(db_path),
        output_path=output_dir / "settlement_rate.png",
        experiment_name=experiment_name,
    )

    generate_per_agent_cost_chart(
        db_path=str(db_path),
        output_path=output_dir / "per_agent_costs.png",
        experiment_name=experiment_name,
    )

    generate_acceptance_chart(
        db_path=str(db_path),
        output_path=output_dir / "iteration_acceptance.png",
        experiment_name=experiment_name,
    )

    print("-" * 60)
    print(f"All charts generated in: {output_dir}")
