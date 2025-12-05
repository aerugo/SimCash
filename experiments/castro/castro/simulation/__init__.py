"""Simulation execution layer for castro experiments.

Provides parallel simulation execution and filtered replay functionality.

Main components:
- ParallelSimulationExecutor: Runs simulations in parallel
- compute_metrics: Aggregates simulation results
"""

from experiments.castro.castro.simulation.executor import ParallelSimulationExecutor
from experiments.castro.castro.simulation.metrics import compute_metrics

__all__ = [
    "ParallelSimulationExecutor",
    "compute_metrics",
]
