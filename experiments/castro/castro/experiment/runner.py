"""Experiment runner for castro experiments.

This module re-exports the ReproducibleExperiment class from the
original scripts module. The runner is being incrementally refactored
to use the new modular structure.

Future refactoring will fully migrate this class to use:
- Repository protocol for database operations
- SimulationExecutor protocol for simulation execution
- Proper dependency injection
"""

from __future__ import annotations

# Re-export from original module while preserving backward compatibility
# This allows gradual migration to the new structure
from experiments.castro.scripts.reproducible_experiment import ReproducibleExperiment

__all__ = ["ReproducibleExperiment"]


# Type annotation stubs for IDE support
# These will be used by the full implementation after migration

# from experiments.castro.castro.core.protocols import Repository, SimulationExecutor
# from experiments.castro.castro.experiment.optimizer import LLMOptimizer
# from experiments.castro.castro.experiment.definitions import ExperimentDefinition
#
# class ReproducibleExperiment:
#     """Main experiment runner with full reproducibility.
#
#     IMPORTANT: This runner NEVER modifies the seed policy files.
#     """
#
#     def __init__(
#         self,
#         experiment_key: str,
#         db_path: str,
#         simcash_root: str | None = None,
#         model: str = "gpt-4o",
#         reasoning_effort: str = "high",
#         master_seed: int | None = None,
#         verbose: bool = False,
#         thinking_budget: int | None = None,
#         # Dependency injection (future)
#         # repository: Repository | None = None,
#         # executor: SimulationExecutor | None = None,
#     ) -> None:
#         ...
