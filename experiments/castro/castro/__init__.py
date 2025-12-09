"""Castro experiments using ai_cash_mgmt module.

Clean-slate implementation of Castro et al. (2025) experiments
for LLM-based policy optimization in payment systems.
"""

from __future__ import annotations

__all__ = [
    "CASTRO_CONSTRAINTS",
    "EXPERIMENTS",
    "CastroExperiment",
    "ExperimentResult",
    "ExperimentRunner",
    "create_exp1",
    "create_exp2",
    "create_exp3",
]


def __getattr__(name: str) -> object:
    """Lazy import to avoid circular dependencies."""
    if name == "CASTRO_CONSTRAINTS":
        from castro.constraints import CASTRO_CONSTRAINTS

        return CASTRO_CONSTRAINTS
    if name in ("EXPERIMENTS", "CastroExperiment", "create_exp1", "create_exp2", "create_exp3"):
        from castro import experiments

        return getattr(experiments, name)
    if name in ("ExperimentResult", "ExperimentRunner"):
        from castro import runner

        return getattr(runner, name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
