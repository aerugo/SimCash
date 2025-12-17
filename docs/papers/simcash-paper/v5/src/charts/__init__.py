"""Chart path resolution for paper figures."""

from __future__ import annotations

from pathlib import Path

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


def get_bootstrap_chart_path(exp_id: str, pass_num: int) -> Path:
    """Get path to bootstrap evaluation chart for an experiment pass.

    Args:
        exp_id: Experiment identifier (exp1, exp2, exp3)
        pass_num: Pass number (1, 2, or 3)

    Returns:
        Path to the bootstrap chart PNG
    """
    return CHARTS_DIR / f"{exp_id}_pass{pass_num}_bootstrap.png"
