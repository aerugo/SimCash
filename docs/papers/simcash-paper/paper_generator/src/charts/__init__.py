"""Chart path resolution and generation for paper figures."""

from __future__ import annotations

from pathlib import Path

from src.charts.generators import (
    generate_all_paper_charts,
    generate_combined_convergence_chart,
    generate_convergence_chart,
    generate_experiment_charts,
)

__all__ = [
    "get_convergence_chart_path",
    "generate_convergence_chart",
    "generate_combined_convergence_chart",
    "generate_experiment_charts",
    "generate_all_paper_charts",
]

# Charts directory relative to v5 root
CHARTS_DIR = Path(__file__).parent.parent.parent / "output" / "charts"


def get_convergence_chart_path(exp_id: str, pass_num: int) -> Path:
    """Get path to convergence chart for an experiment pass.

    Args:
        exp_id: Experiment identifier (exp1, exp2, exp3)
        pass_num: Pass number (1, 2, or 3)

    Returns:
        Path to the convergence chart PNG
    """
    return CHARTS_DIR / f"{exp_id}_pass{pass_num}_convergence.png"
