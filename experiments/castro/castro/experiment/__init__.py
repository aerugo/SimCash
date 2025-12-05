"""Experiment execution layer for castro experiments.

Provides the main experiment runner and supporting classes.

Main components:
- EXPERIMENTS: Registry of experiment definitions
- ExperimentDefinition: Dataclass for experiment configuration
- LLMOptimizer: LLM-based policy optimizer
- ReproducibleExperiment: Main experiment runner
"""

from experiments.castro.castro.experiment.definitions import (
    EXPERIMENTS,
    get_experiment,
)
from experiments.castro.castro.experiment.optimizer import LLMOptimizer
from experiments.castro.castro.experiment.runner import ReproducibleExperiment

__all__ = [
    "EXPERIMENTS",
    "get_experiment",
    "LLMOptimizer",
    "ReproducibleExperiment",
]
