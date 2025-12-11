"""State provider protocol for experiment replay identity.

Defines a common interface for accessing experiment state, implemented by:
- LiveStateProvider (wraps live execution)
- DatabaseStateProvider (wraps database for replay)

This enables unified display functions that work identically in both modes.

Phase 11, Task 11.1: StateProvider Protocol

All costs are integer cents (INV-1 compliance).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from payment_simulator.experiments.persistence.repository import (
        ExperimentRepository,
    )


# =============================================================================
# Protocol Definition
# =============================================================================


@runtime_checkable
class ExperimentStateProviderProtocol(Protocol):
    """Protocol for accessing experiment state.

    This interface is implemented by both:
    - LiveStateProvider (live execution)
    - DatabaseStateProvider (replay from database)

    Enables unified display functions that work identically in both modes.

    All costs are integer cents (INV-1 compliance).
    """

    def get_experiment_info(self) -> dict[str, Any]:
        """Get experiment metadata.

        Returns:
            Dict with keys: experiment_name, experiment_type, config,
            and optional keys: run_id, converged, convergence_reason, etc.
        """
        ...

    def get_total_iterations(self) -> int:
        """Get total number of completed iterations."""
        ...

    def get_iteration_events(self, iteration: int) -> list[dict[str, Any]]:
        """Get all events for a specific iteration.

        Args:
            iteration: Iteration number (0-indexed)

        Returns:
            List of event dicts with at least 'event_type' key
        """
        ...

    def get_iteration_policies(self, iteration: int) -> dict[str, Any]:
        """Get policy state at end of iteration.

        Args:
            iteration: Iteration number (0-indexed)

        Returns:
            Dict mapping agent_id to policy dict
        """
        ...

    def get_iteration_costs(self, iteration: int) -> dict[str, int]:
        """Get per-agent costs for iteration.

        All costs are integer cents (INV-1 compliance).

        Args:
            iteration: Iteration number (0-indexed)

        Returns:
            Dict mapping agent_id to cost in integer cents
        """
        ...

    def get_iteration_accepted_changes(self, iteration: int) -> dict[str, bool]:
        """Get which agents had policy changes accepted.

        Args:
            iteration: Iteration number (0-indexed)

        Returns:
            Dict mapping agent_id to whether change was accepted
        """
        ...


# =============================================================================
# Iteration Record (for internal storage)
# =============================================================================


@dataclass
class IterationData:
    """Data for a single iteration.

    All costs are integer cents (INV-1).
    """

    iteration: int
    costs_per_agent: dict[str, int]
    accepted_changes: dict[str, bool]
    policies: dict[str, Any]
    events: list[dict[str, Any]] = field(default_factory=list)


# =============================================================================
# Live Implementation
# =============================================================================


class LiveStateProvider:
    """StateProvider wrapping live experiment execution.

    Captures events during execution for both:
    - Live display (immediate feedback)
    - Database persistence (for replay)

    All costs are integer cents (INV-1 compliance).
    """

    def __init__(
        self,
        experiment_name: str,
        experiment_type: str,
        config: dict[str, Any],
        run_id: str | None = None,
    ) -> None:
        """Initialize live provider.

        Args:
            experiment_name: Name of experiment
            experiment_type: Type of experiment (e.g., "castro")
            config: Experiment configuration dict
            run_id: Optional run identifier
        """
        self._experiment_name = experiment_name
        self._experiment_type = experiment_type
        self._config = config
        self._run_id = run_id
        self._iterations: list[IterationData] = []
        self._converged: bool = False
        self._convergence_reason: str | None = None

    def get_experiment_info(self) -> dict[str, Any]:
        """Get experiment metadata."""
        return {
            "experiment_name": self._experiment_name,
            "experiment_type": self._experiment_type,
            "config": self._config,
            "run_id": self._run_id,
            "converged": self._converged,
            "convergence_reason": self._convergence_reason,
        }

    def get_total_iterations(self) -> int:
        """Get total number of completed iterations."""
        return len(self._iterations)

    def get_iteration_events(self, iteration: int) -> list[dict[str, Any]]:
        """Get all events for a specific iteration."""
        if iteration < 0 or iteration >= len(self._iterations):
            return []
        return self._iterations[iteration].events

    def get_iteration_policies(self, iteration: int) -> dict[str, Any]:
        """Get policy state at end of iteration."""
        if iteration < 0 or iteration >= len(self._iterations):
            return {}
        return self._iterations[iteration].policies

    def get_iteration_costs(self, iteration: int) -> dict[str, int]:
        """Get per-agent costs for iteration (integer cents)."""
        if iteration < 0 or iteration >= len(self._iterations):
            return {}
        return self._iterations[iteration].costs_per_agent

    def get_iteration_accepted_changes(self, iteration: int) -> dict[str, bool]:
        """Get which agents had policy changes accepted."""
        if iteration < 0 or iteration >= len(self._iterations):
            return {}
        return self._iterations[iteration].accepted_changes

    # =========================================================================
    # Methods for recording data during live execution
    # =========================================================================

    def record_iteration(
        self,
        iteration: int,
        costs_per_agent: dict[str, int],
        accepted_changes: dict[str, bool],
        policies: dict[str, Any],
    ) -> None:
        """Record results for an iteration.

        All costs must be integer cents (INV-1).

        Args:
            iteration: Iteration number
            costs_per_agent: Dict mapping agent_id to cost in cents
            accepted_changes: Dict mapping agent_id to acceptance status
            policies: Dict mapping agent_id to policy dict
        """
        # Ensure we have space for this iteration
        while len(self._iterations) <= iteration:
            self._iterations.append(
                IterationData(
                    iteration=len(self._iterations),
                    costs_per_agent={},
                    accepted_changes={},
                    policies={},
                )
            )

        self._iterations[iteration] = IterationData(
            iteration=iteration,
            costs_per_agent=costs_per_agent,
            accepted_changes=accepted_changes,
            policies=policies,
            events=self._iterations[iteration].events,
        )

    def record_event(
        self,
        iteration: int,
        event_type: str,
        event_data: dict[str, Any],
    ) -> None:
        """Record an event during execution.

        Args:
            iteration: Iteration number
            event_type: Type of event
            event_data: Event-specific data
        """
        # Ensure we have space for this iteration
        while len(self._iterations) <= iteration:
            self._iterations.append(
                IterationData(
                    iteration=len(self._iterations),
                    costs_per_agent={},
                    accepted_changes={},
                    policies={},
                )
            )

        event = {"event_type": event_type, **event_data}
        self._iterations[iteration].events.append(event)

    def set_converged(self, converged: bool, reason: str | None = None) -> None:
        """Set convergence status.

        Args:
            converged: Whether experiment converged
            reason: Reason for convergence/stopping
        """
        self._converged = converged
        self._convergence_reason = reason


# =============================================================================
# Database Implementation
# =============================================================================


class DatabaseStateProvider:
    """StateProvider wrapping database queries for replay.

    Reads from pre-persisted experiment data to provide the same
    interface as LiveStateProvider.

    All costs are integer cents (INV-1 compliance).
    """

    def __init__(
        self,
        repository: ExperimentRepository,
        run_id: str,
    ) -> None:
        """Initialize database provider.

        Args:
            repository: ExperimentRepository instance
            run_id: Run identifier to load
        """
        self._repository = repository
        self._run_id = run_id
        self._experiment_record: Any | None = None
        self._iterations: list[Any] | None = None
        self._load_data()

    def _load_data(self) -> None:
        """Load experiment data from database."""
        self._experiment_record = self._repository.load_experiment(self._run_id)
        if self._experiment_record is not None:
            self._iterations = self._repository.get_iterations(self._run_id)

    def get_experiment_info(self) -> dict[str, Any]:
        """Get experiment metadata from database."""
        if self._experiment_record is None:
            return {}

        return {
            "experiment_name": self._experiment_record.experiment_name,
            "experiment_type": self._experiment_record.experiment_type,
            "config": self._experiment_record.config,
            "run_id": self._experiment_record.run_id,
            "converged": self._experiment_record.converged,
            "convergence_reason": self._experiment_record.convergence_reason,
            "created_at": self._experiment_record.created_at,
            "completed_at": self._experiment_record.completed_at,
            "num_iterations": self._experiment_record.num_iterations,
        }

    def get_total_iterations(self) -> int:
        """Get total number of iterations from database."""
        if self._iterations is None:
            return 0
        return len(self._iterations)

    def get_iteration_events(self, iteration: int) -> list[dict[str, Any]]:
        """Get events for iteration from database."""
        events = self._repository.get_events(self._run_id, iteration)
        # Include event_type in the returned dict for consistency
        return [{"event_type": e.event_type, **e.event_data} for e in events]

    def get_iteration_policies(self, iteration: int) -> dict[str, Any]:
        """Get policy state at end of iteration."""
        if self._iterations is None or iteration >= len(self._iterations):
            return {}
        return self._iterations[iteration].policies

    def get_iteration_costs(self, iteration: int) -> dict[str, int]:
        """Get per-agent costs for iteration (integer cents)."""
        if self._iterations is None or iteration >= len(self._iterations):
            return {}
        return self._iterations[iteration].costs_per_agent

    def get_iteration_accepted_changes(self, iteration: int) -> dict[str, bool]:
        """Get which agents had policy changes accepted."""
        if self._iterations is None or iteration >= len(self._iterations):
            return {}
        return self._iterations[iteration].accepted_changes
