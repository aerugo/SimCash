"""Core types and protocols for castro experiments.

This module provides:
- TypedDicts for database records and API responses
- Protocol definitions for dependency injection
- Dataclasses for domain models
"""

from experiments.castro.castro.core.protocols import Repository, SimulationExecutor
from experiments.castro.castro.core.types import (
    CostBreakdown,
    ExperimentConfigRecord,
    IterationMetricsRecord,
    PolicyIterationRecord,
    SimulationResult,
    SimulationRunRecord,
    ValidationErrorRecord,
)

__all__ = [
    # Types
    "CostBreakdown",
    "ExperimentConfigRecord",
    "IterationMetricsRecord",
    "PolicyIterationRecord",
    "SimulationResult",
    "SimulationRunRecord",
    "ValidationErrorRecord",
    # Protocols
    "Repository",
    "SimulationExecutor",
]
