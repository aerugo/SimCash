"""Chart generators for paper figures.

Uses existing SimCash charting infrastructure for convergence charts.
All functions take explicit paths and return the output path for verification.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# Add api directory to path for SimCash imports
API_PATH = Path(__file__).parent.parent.parent.parent.parent.parent / "api"
if str(API_PATH) not in sys.path:
    sys.path.insert(0, str(API_PATH))

from payment_simulator.experiments.persistence import ExperimentRepository  # noqa: E402
from payment_simulator.experiments.analysis.charting import (  # noqa: E402
    ExperimentChartService,
    render_convergence_chart,
)


# Color palette matching SimCash style
COLORS = {
    "bank_a": "#2563eb",  # Blue
    "bank_b": "#dc2626",  # Red
    "combined": "#059669",  # Green
    "grid": "#e2e8f0",
    "text": "#334155",
    "ci_band": "#dbeafe",
}


def _get_run_id_for_pass(
    db_path: Path,
    exp_id: str,
    pass_num: int,
    config: dict,
) -> str:
    """Get run_id for a specific experiment pass from config.

    Args:
        db_path: Path to experiment database (unused, kept for API compatibility)
        exp_id: Experiment identifier (exp1, exp2, exp3)
        pass_num: Pass number (1, 2, or 3)
        config: Paper config with explicit run_id mappings (required)

    Returns:
        Run ID string

    Raises:
        KeyError: If exp_id or pass_num not in config
    """
    # db_path kept for API compatibility but not used
    _ = db_path

    from src.config import get_run_id as config_get_run_id

    return config_get_run_id(config, exp_id, pass_num)


def generate_convergence_chart(
    db_path: Path,
    exp_id: str,
    pass_num: int,
    agent_id: str,
    output_path: Path,
    config: dict,
) -> Path:
    """Generate convergence chart for a single agent.

    Uses SimCash's ExperimentChartService for rendering.

    Args:
        db_path: Path to experiment database
        exp_id: Experiment identifier
        pass_num: Pass number (1, 2, or 3)
        agent_id: Agent to chart ("BANK_A" or "BANK_B")
        output_path: Where to save the chart
        config: Paper config with explicit run_id mappings (required)

    Returns:
        Path to generated chart
    """
    run_id = _get_run_id_for_pass(db_path, exp_id, pass_num, config)

    repo = ExperimentRepository(db_path)
    service = ExperimentChartService(repo)

    data = service.extract_chart_data(
        run_id=run_id,
        agent_filter=agent_id,
        parameter_name="initial_liquidity_fraction",
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    render_convergence_chart(data, output_path)

    return output_path


def generate_combined_convergence_chart(
    db_path: Path,
    exp_id: str,
    pass_num: int,
    output_path: Path,
    config: dict,
) -> Path:
    """Generate combined convergence chart showing both agents.

    Creates a side-by-side chart with:
    - Left: Cost convergence for both BANK_A and BANK_B
    - Right: Liquidity fraction convergence for both agents

    Args:
        db_path: Path to experiment database
        exp_id: Experiment identifier
        pass_num: Pass number
        output_path: Where to save the chart
        config: Paper config with explicit run_id mappings (required)

    Returns:
        Path to generated chart
    """
    run_id = _get_run_id_for_pass(db_path, exp_id, pass_num, config)

    repo = ExperimentRepository(db_path)
    service = ExperimentChartService(repo)

    # Extract cost data for both agents
    data_a = service.extract_chart_data(run_id=run_id, agent_filter="BANK_A")
    data_b = service.extract_chart_data(run_id=run_id, agent_filter="BANK_B")

    # Extract liquidity fraction data for both agents
    data_a_liq = service.extract_chart_data(
        run_id=run_id,
        agent_filter="BANK_A",
        parameter_name="initial_liquidity_fraction",
    )
    data_b_liq = service.extract_chart_data(
        run_id=run_id,
        agent_filter="BANK_B",
        parameter_name="initial_liquidity_fraction",
    )

    # Create side-by-side subplots
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, (ax_cost, ax_liq) = plt.subplots(1, 2, figsize=(14, 5))

    # === Left subplot: Cost Convergence ===
    iterations_a = [p.iteration for p in data_a.data_points]
    costs_a = [p.cost_dollars for p in data_a.data_points]
    ax_cost.plot(
        iterations_a,
        costs_a,
        color=COLORS["bank_a"],
        linewidth=2,
        label="BANK_A",
        marker="o",
        markersize=5,
    )

    iterations_b = [p.iteration for p in data_b.data_points]
    costs_b = [p.cost_dollars for p in data_b.data_points]
    ax_cost.plot(
        iterations_b,
        costs_b,
        color=COLORS["bank_b"],
        linewidth=2,
        label="BANK_B",
        marker="s",
        markersize=5,
    )

    ax_cost.set_title("Cost Convergence", fontsize=12, fontweight="medium", color=COLORS["text"])
    ax_cost.set_xlabel("Iteration", fontsize=11, color=COLORS["text"])
    ax_cost.set_ylabel("Cost ($)", fontsize=11, color=COLORS["text"])
    ax_cost.yaxis.set_major_formatter(ticker.FormatStrFormatter("$%.2f"))
    ax_cost.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax_cost.legend(loc="upper right", framealpha=0.9)
    ax_cost.spines["top"].set_visible(False)
    ax_cost.spines["right"].set_visible(False)
    ax_cost.grid(True, alpha=0.3, color=COLORS["grid"])

    # === Right subplot: Liquidity Fraction Convergence ===
    iterations_a_liq = [p.iteration for p in data_a_liq.data_points]
    liq_a = [p.parameter_value if p.parameter_value is not None else 0.5 for p in data_a_liq.data_points]
    ax_liq.plot(
        iterations_a_liq,
        liq_a,
        color=COLORS["bank_a"],
        linewidth=2,
        label="BANK_A",
        marker="o",
        markersize=5,
    )

    iterations_b_liq = [p.iteration for p in data_b_liq.data_points]
    liq_b = [p.parameter_value if p.parameter_value is not None else 0.5 for p in data_b_liq.data_points]
    ax_liq.plot(
        iterations_b_liq,
        liq_b,
        color=COLORS["bank_b"],
        linewidth=2,
        label="BANK_B",
        marker="s",
        markersize=5,
    )

    ax_liq.set_title("Liquidity Fraction Convergence", fontsize=12, fontweight="medium", color=COLORS["text"])
    ax_liq.set_xlabel("Iteration", fontsize=11, color=COLORS["text"])
    ax_liq.set_ylabel("Liquidity Fraction", fontsize=11, color=COLORS["text"])
    ax_liq.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.2f"))
    ax_liq.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax_liq.set_ylim(0, 1)  # Liquidity fraction is always 0-1
    ax_liq.legend(loc="upper right", framealpha=0.9)
    ax_liq.spines["top"].set_visible(False)
    ax_liq.spines["right"].set_visible(False)
    ax_liq.grid(True, alpha=0.3, color=COLORS["grid"])

    # Overall figure title
    fig.suptitle(
        f"{exp_id.upper()} Pass {pass_num}",
        fontsize=14,
        fontweight="medium",
        color=COLORS["text"],
        y=1.02,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return output_path


def generate_experiment_charts(
    db_path: Path,
    exp_id: str,
    pass_num: int,
    output_dir: Path,
    config: dict,
) -> dict[str, Path]:
    """Generate all charts for an experiment pass.

    Creates BANK_A, BANK_B, combined, and variance charts with flat naming scheme.
    Files are named: {exp_id}_pass{pass_num}_{type}.png

    For bootstrap experiments (exp2), also generates variance charts showing
    cost with confidence interval bands.

    Args:
        db_path: Path to experiment database
        exp_id: Experiment identifier
        pass_num: Pass number
        output_dir: Directory for output files (flat structure)
        config: Paper config with explicit run_id mappings (required)

    Returns:
        Dict mapping chart type to path
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}

    # Individual agent charts with flat naming
    paths["BANK_A"] = generate_convergence_chart(
        db_path=db_path,
        exp_id=exp_id,
        pass_num=pass_num,
        agent_id="BANK_A",
        output_path=output_dir / f"{exp_id}_pass{pass_num}_bankA.png",
        config=config,
    )

    paths["BANK_B"] = generate_convergence_chart(
        db_path=db_path,
        exp_id=exp_id,
        pass_num=pass_num,
        agent_id="BANK_B",
        output_path=output_dir / f"{exp_id}_pass{pass_num}_bankB.png",
        config=config,
    )

    # Combined chart
    paths["combined"] = generate_combined_convergence_chart(
        db_path=db_path,
        exp_id=exp_id,
        pass_num=pass_num,
        output_path=output_dir / f"{exp_id}_pass{pass_num}_combined.png",
        config=config,
    )

    # Bootstrap variance chart (for experiments with bootstrap evaluation)
    try:
        paths["variance"] = generate_bootstrap_variance_chart(
            db_path=db_path,
            exp_id=exp_id,
            pass_num=pass_num,
            output_path=output_dir / f"{exp_id}_pass{pass_num}_variance.png",
            config=config,
        )
    except ValueError:
        # No policy evaluations available, skip variance chart
        pass

    return paths


# =============================================================================
# Bootstrap Variance Charts
# =============================================================================


def generate_bootstrap_variance_chart(
    db_path: Path,
    exp_id: str,
    pass_num: int,
    output_path: Path,
    config: dict,
) -> Path:
    """Generate bootstrap variance chart with Gaussian Process-style visualization.

    Creates a side-by-side chart with:
    - Left: BANK_A cost trajectory with smooth 95% CI band
    - Right: BANK_B cost trajectory with smooth 95% CI band

    Styled like Gaussian Process regression plots with:
    - Smooth mean prediction line
    - Shaded confidence interval band
    - Distinct markers for observed data points

    This illustrates how risk (variance) may change as agents optimize for lower costs.
    Requires bootstrap evaluation data in the policy_evaluations table.

    Args:
        db_path: Path to experiment database
        exp_id: Experiment identifier
        pass_num: Pass number
        output_path: Where to save the chart
        config: Paper config with explicit run_id mappings (required)

    Returns:
        Path to generated chart
    """
    import numpy as np

    run_id = _get_run_id_for_pass(db_path, exp_id, pass_num, config)

    repo = ExperimentRepository(db_path)

    # Get policy evaluations for both agents
    evals_a = repo.get_policy_evaluations(run_id, "BANK_A")
    evals_b = repo.get_policy_evaluations(run_id, "BANK_B")

    if not evals_a or not evals_b:
        raise ValueError(f"No policy evaluations found for {exp_id} pass {pass_num}")

    # Create side-by-side subplots with white background
    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(14, 5), facecolor="white")

    # GP-style colors
    GP_COLORS = {
        "bank_a": {
            "line": "#1f77b4",  # Blue line
            "band": "#aec7e8",  # Light blue band
            "points": "#d62728",  # Red observed points
        },
        "bank_b": {
            "line": "#1f77b4",  # Blue line
            "band": "#aec7e8",  # Light blue band
            "points": "#d62728",  # Red observed points
        },
    }

    def plot_gp_style(
        ax: plt.Axes, evals: list, agent_id: str, colors: dict
    ) -> None:
        """Plot agent data in Gaussian Process regression style."""
        iterations = []
        costs = []
        ci_lower = []
        ci_upper = []

        for e in evals:
            iterations.append(e.iteration)
            # Convert cents to dollars
            costs.append(e.new_cost / 100.0)

            # Get CI from agent_stats if available, otherwise use confidence_interval_95
            if e.agent_stats and agent_id in e.agent_stats:
                agent_stat = e.agent_stats[agent_id]
                ci_lower.append(agent_stat.get("ci_95_lower", e.new_cost) / 100.0)
                ci_upper.append(agent_stat.get("ci_95_upper", e.new_cost) / 100.0)
            elif e.confidence_interval_95:
                ci_lower.append(e.confidence_interval_95[0] / 100.0)
                ci_upper.append(e.confidence_interval_95[1] / 100.0)
            else:
                # No CI data, use cost as both bounds
                ci_lower.append(e.new_cost / 100.0)
                ci_upper.append(e.new_cost / 100.0)

        # Convert to numpy arrays
        x = np.array(iterations)
        y_mean = np.array(costs)
        y_lower = np.array(ci_lower)
        y_upper = np.array(ci_upper)

        # Create smooth interpolation for GP-like appearance
        if len(x) > 2:
            # Create fine-grained x values for smooth curves
            x_smooth = np.linspace(x.min(), x.max(), 200)

            # Linear interpolation using numpy (sufficient for GP aesthetic)
            y_mean_smooth = np.interp(x_smooth, x, y_mean)
            y_lower_smooth = np.interp(x_smooth, x, y_lower)
            y_upper_smooth = np.interp(x_smooth, x, y_upper)
        else:
            # Not enough points for interpolation, use original
            x_smooth = x
            y_mean_smooth = y_mean
            y_lower_smooth = y_lower
            y_upper_smooth = y_upper

        # Plot 95% CI band (prominent, GP-style)
        ax.fill_between(
            x_smooth,
            y_lower_smooth,
            y_upper_smooth,
            alpha=0.4,
            color=colors["band"],
            label="95% Confidence Interval",
            edgecolor="none",
        )

        # Plot smooth mean prediction line
        ax.plot(
            x_smooth,
            y_mean_smooth,
            color=colors["line"],
            linewidth=2,
            label="Mean Prediction",
        )

        # Plot observed data points (red dots like GP chart)
        ax.scatter(
            x,
            y_mean,
            color=colors["points"],
            s=80,
            zorder=5,
            label="Observed Data",
            edgecolors="white",
            linewidths=1.5,
        )

        # Styling - clean, minimal like GP plots
        ax.set_title(agent_id, fontsize=14, fontweight="medium", color=COLORS["text"])
        ax.set_xlabel("Iteration", fontsize=12, color=COLORS["text"])
        ax.set_ylabel("Cost ($)", fontsize=12, color=COLORS["text"])
        ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("$%.2f"))
        ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))

        # Clean legend
        ax.legend(loc="upper right", framealpha=0.95, fontsize=10)

        # Minimal spines
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#cccccc")
        ax.spines["bottom"].set_color("#cccccc")

        # Subtle grid
        ax.grid(True, alpha=0.3, color="#e0e0e0", linestyle="-")
        ax.set_facecolor("white")

    # Plot both agents in GP style
    plot_gp_style(ax_a, evals_a, "BANK_A", GP_COLORS["bank_a"])
    plot_gp_style(ax_b, evals_b, "BANK_B", GP_COLORS["bank_b"])

    # Overall figure title
    fig.suptitle(
        f"Cost Variance - {exp_id.upper()} Pass {pass_num}",
        fontsize=14,
        fontweight="medium",
        color=COLORS["text"],
        y=1.02,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    return output_path


# =============================================================================
# Batch Generation
# =============================================================================


def generate_all_paper_charts(
    data_dir: Path,
    output_dir: Path,
    config: dict,
) -> dict[str, dict[int, dict[str, Path]]]:
    """Generate all charts needed for the paper.

    Creates convergence charts for all experiments and passes.

    Chart files are generated with flat naming scheme to match
    what the LaTeX section generators expect:
    - {exp_id}_pass{pass_num}_combined.png
    - {exp_id}_pass{pass_num}_bankA.png
    - {exp_id}_pass{pass_num}_bankB.png

    Args:
        data_dir: Directory containing exp{1,2,3}.db
        output_dir: Directory for output charts
        config: Paper config with explicit run_id mappings (required)

    Returns:
        Nested dict: {exp_id: {pass_num: {chart_type: path}}}
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    result: dict[str, dict[int, dict[str, Path]]] = {}

    from src.config import get_experiment_ids, get_pass_numbers

    exp_ids = get_experiment_ids(config)

    for exp_id in exp_ids:
        db_path = data_dir / f"{exp_id}.db"
        if not db_path.exists():
            continue

        result[exp_id] = {}
        pass_nums = get_pass_numbers(config, exp_id)

        for pass_num in pass_nums:
            try:
                # Generate convergence charts with flat naming (directly in output_dir)
                paths = generate_experiment_charts(
                    db_path=db_path,
                    exp_id=exp_id,
                    pass_num=pass_num,
                    output_dir=output_dir,  # Flat structure
                    config=config,
                )
                result[exp_id][pass_num] = paths

            except ValueError:
                # Pass doesn't exist, skip
                continue

    return result
