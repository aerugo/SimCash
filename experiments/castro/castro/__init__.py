"""Castro experiments using ai_cash_mgmt module.

Clean-slate implementation of Castro et al. (2025) experiments
for LLM-based policy optimization in payment systems.
"""

from __future__ import annotations

__all__ = [
    # Core exports
    "CASTRO_CONSTRAINTS",
    "ExperimentResult",
    "ExperimentRunner",
    # Experiment loading (preferred)
    "list_experiments",
    "load_experiment",
    "get_llm_config",
    # Configuration classes
    "CastroExperiment",
    "YamlExperimentConfig",
    "ExperimentConfigProtocol",
]


def __getattr__(name: str) -> object:
    """Lazy import to avoid circular dependencies."""
    if name == "CASTRO_CONSTRAINTS":
        from castro.constraints import CASTRO_CONSTRAINTS

        return CASTRO_CONSTRAINTS
    if name in ("list_experiments", "load_experiment", "get_llm_config"):
        from castro import experiment_loader

        return getattr(experiment_loader, name)
    if name in (
        "CastroExperiment",
        "YamlExperimentConfig",
        "ExperimentConfigProtocol",
    ):
        from castro import experiment_config

        return getattr(experiment_config, name)
    if name in ("ExperimentResult", "ExperimentRunner"):
        from castro import runner

        return getattr(runner, name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
