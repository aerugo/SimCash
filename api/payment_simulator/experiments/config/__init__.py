"""Experiment configuration module.

Handles loading and validating experiment configurations from YAML files.

Components:
    - ExperimentConfig: Main configuration loaded from YAML
    - EvaluationConfig: Evaluation mode settings
    - ConvergenceConfig: Convergence criteria
    - OutputConfig: Output settings

Example:
    >>> from payment_simulator.experiments.config import ExperimentConfig
    >>> config = ExperimentConfig.from_yaml(Path("experiment.yaml"))
    >>> config.name
    'my_experiment'
"""

from payment_simulator.experiments.config.experiment_config import (
    ConvergenceConfig,
    EvaluationConfig,
    ExperimentConfig,
    OutputConfig,
)

__all__ = [
    "ExperimentConfig",
    "EvaluationConfig",
    "ConvergenceConfig",
    "OutputConfig",
]
