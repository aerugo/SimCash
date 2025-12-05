"""Castro experiments library for payment system optimization.

This library provides a reproducible experiment framework for replicating
and extending Castro et al. (2025) "Strategic Payment Timing" using
LLM-based policy optimization.

Main modules:
- castro.core: Core types, protocols, and domain models
- castro.db: Database layer for experiment persistence
- castro.simulation: Simulation execution and replay
- castro.experiment: Experiment runner and definitions
- castro.visualization: Chart generation for analysis
"""

from experiments.castro.castro.core.types import (
    ExperimentConfigRecord,
    IterationMetricsRecord,
    PolicyIterationRecord,
    SimulationResult,
    SimulationRunRecord,
    ValidationErrorRecord,
)

__all__ = [
    "ExperimentConfigRecord",
    "IterationMetricsRecord",
    "PolicyIterationRecord",
    "SimulationResult",
    "SimulationRunRecord",
    "ValidationErrorRecord",
]
