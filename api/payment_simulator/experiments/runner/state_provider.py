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
from typing import TYPE_CHECKING, Any, Iterator, Protocol, runtime_checkable

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

    # =========================================================================
    # Audit Methods (Phase 13)
    # =========================================================================

    @property
    def run_id(self) -> str | None:
        """Get the run identifier.

        Returns:
            Run ID string, or None if not set
        """
        ...

    def get_run_metadata(self) -> dict[str, Any] | None:
        """Get run metadata for display.

        Returns:
            Dict with experiment_name, experiment_type, run_id, config,
            or None if not available
        """
        ...

    def get_all_events(self) -> Iterator[dict[str, Any]]:
        """Iterate over all events across all iterations.

        Returns:
            Iterator yielding event dicts with 'event_type' key
        """
        ...

    def get_final_result(self) -> dict[str, Any] | None:
        """Get final experiment result.

        Returns:
            Dict with final_cost, best_cost, converged, convergence_reason,
            or None if experiment not completed
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
        self._final_result: dict[str, Any] | None = None

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

    # =========================================================================
    # Audit Methods (Phase 13)
    # =========================================================================

    @property
    def run_id(self) -> str | None:
        """Get the run identifier."""
        return self._run_id

    def get_run_metadata(self) -> dict[str, Any] | None:
        """Get run metadata for display."""
        return {
            "experiment_name": self._experiment_name,
            "experiment_type": self._experiment_type,
            "run_id": self._run_id,
            "config": self._config,
            "converged": self._converged,
            "convergence_reason": self._convergence_reason,
        }

    def get_all_events(self) -> Iterator[dict[str, Any]]:
        """Iterate over all events across all iterations."""
        for iteration_data in self._iterations:
            yield from iteration_data.events

    def get_final_result(self) -> dict[str, Any] | None:
        """Get final experiment result."""
        return self._final_result

    def set_final_result(
        self,
        final_cost: int,
        best_cost: int,
        converged: bool,
        convergence_reason: str | None = None,
    ) -> None:
        """Set final experiment result.

        All costs must be integer cents (INV-1 compliance).

        Args:
            final_cost: Final cost at end of experiment (integer cents)
            best_cost: Best cost achieved during experiment (integer cents)
            converged: Whether experiment converged
            convergence_reason: Reason for convergence/stopping
        """
        self._final_result = {
            "final_cost": final_cost,
            "best_cost": best_cost,
            "converged": converged,
            "convergence_reason": convergence_reason,
        }
        # Also update convergence status
        self._converged = converged
        self._convergence_reason = convergence_reason


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

    # =========================================================================
    # Audit Methods (Phase 13)
    # =========================================================================

    @property
    def run_id(self) -> str:
        """Get the run identifier."""
        return self._run_id

    def get_run_metadata(self) -> dict[str, Any] | None:
        """Get run metadata for display."""
        if self._experiment_record is None:
            return None

        return {
            "experiment_name": self._experiment_record.experiment_name,
            "experiment_type": self._experiment_record.experiment_type,
            "run_id": self._experiment_record.run_id,
            "config": self._experiment_record.config,
            "converged": self._experiment_record.converged,
            "convergence_reason": self._experiment_record.convergence_reason,
            "created_at": self._experiment_record.created_at,
            "completed_at": self._experiment_record.completed_at,
            "num_iterations": self._experiment_record.num_iterations,
        }

    def get_all_events(self) -> Iterator[dict[str, Any]]:
        """Iterate over all events across all iterations."""
        events = self._repository.get_all_events(self._run_id)
        for event in events:
            yield {"event_type": event.event_type, **event.event_data}

    def get_final_result(self) -> dict[str, Any] | None:
        """Get final experiment result."""
        if self._experiment_record is None:
            return None

        # Check if experiment is completed
        if self._experiment_record.completed_at is None:
            return None

        # Get costs from config (stored there by runner)
        config = self._experiment_record.config
        final_cost = config.get("final_cost")
        best_cost = config.get("best_cost")

        # Return None if no cost data
        if final_cost is None:
            return None

        return {
            "final_cost": int(final_cost),  # Ensure integer (INV-1)
            "best_cost": int(best_cost) if best_cost is not None else int(final_cost),
            "converged": self._experiment_record.converged,
            "convergence_reason": self._experiment_record.convergence_reason,
        }
