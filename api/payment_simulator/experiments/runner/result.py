"""Experiment result and state dataclasses.

This module provides immutable dataclasses for tracking
experiment progress and final outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class IterationRecord:
    """Record of a single iteration.

    Captures the state and outcomes of one optimization iteration.
    All cost values are integer cents per INV-1.

    Attributes:
        iteration: Iteration number (1-indexed).
        costs_per_agent: Total cost per agent in integer cents.
        accepted_changes: Whether each agent accepted a policy change.
    """

    iteration: int
    costs_per_agent: dict[str, int]
    accepted_changes: dict[str, bool]


@dataclass(frozen=True)
class ExperimentState:
    """Current state of an experiment.

    Immutable snapshot of experiment progress. Use with_* methods
    to create new states with updated values.

    Attributes:
        experiment_name: Name of the experiment.
        current_iteration: Current iteration number (0 = not started).
        is_converged: Whether convergence has been reached.
        convergence_reason: Why convergence occurred (if converged).
        policies: Current policies per agent.

    Example:
        >>> state = ExperimentState(experiment_name="test")
        >>> new_state = state.with_iteration(5)
        >>> new_state.current_iteration
        5
        >>> state.current_iteration  # Original unchanged
        0
    """

    experiment_name: str
    current_iteration: int = 0
    is_converged: bool = False
    convergence_reason: str | None = None
    policies: dict[str, dict[str, Any]] = field(default_factory=dict)

    def with_iteration(self, iteration: int) -> ExperimentState:
        """Return new state with updated iteration.

        Args:
            iteration: New iteration number.

        Returns:
            New ExperimentState with updated iteration.
        """
        return ExperimentState(
            experiment_name=self.experiment_name,
            current_iteration=iteration,
            is_converged=self.is_converged,
            convergence_reason=self.convergence_reason,
            policies=self.policies,
        )

    def with_converged(self, reason: str) -> ExperimentState:
        """Return new state marked as converged.

        Args:
            reason: Reason for convergence.

        Returns:
            New ExperimentState with convergence info.
        """
        return ExperimentState(
            experiment_name=self.experiment_name,
            current_iteration=self.current_iteration,
            is_converged=True,
            convergence_reason=reason,
            policies=self.policies,
        )


@dataclass(frozen=True)
class ExperimentResult:
    """Final result of an experiment run.

    Immutable record of experiment outcome. Contains all
    information needed to analyze and compare experiment runs.
    All cost values are integer cents per INV-1.

    Attributes:
        experiment_name: Name of the experiment.
        num_iterations: Total iterations run.
        converged: Whether experiment converged naturally.
        convergence_reason: Reason for termination.
        final_costs: Final costs per agent in integer cents.
        total_duration_seconds: Total runtime in seconds.
        iteration_history: History of all iterations.
        final_policies: Final policies per agent.

    Example:
        >>> result = ExperimentResult(
        ...     experiment_name="test",
        ...     num_iterations=10,
        ...     converged=True,
        ...     convergence_reason="stability_reached",
        ...     final_costs={"BANK_A": 100000},  # $1000.00
        ...     total_duration_seconds=120.5,
        ... )
    """

    experiment_name: str
    num_iterations: int
    converged: bool
    convergence_reason: str
    final_costs: dict[str, int]
    total_duration_seconds: float
    iteration_history: tuple[IterationRecord, ...] = ()
    final_policies: dict[str, dict[str, Any]] = field(default_factory=dict)
