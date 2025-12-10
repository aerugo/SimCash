"""Output handler protocol and implementations.

This module provides the OutputHandlerProtocol for experiment
output handling and implementations like SilentOutput.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class OutputHandlerProtocol(Protocol):
    """Protocol for experiment output handling.

    Defines callbacks for experiment lifecycle events.
    Implementations can render to console, log to file, etc.

    All callbacks receive relevant information about the event
    and can choose to display, log, or ignore it.

    Example:
        >>> class MyOutput(OutputHandlerProtocol):
        ...     def on_experiment_start(self, experiment_name: str) -> None:
        ...         print(f"Starting: {experiment_name}")
        ...     # ... other methods ...
    """

    def on_experiment_start(self, experiment_name: str) -> None:
        """Called when experiment starts.

        Args:
            experiment_name: Name of the experiment being run.
        """
        ...

    def on_iteration_start(self, iteration: int) -> None:
        """Called at the start of each iteration.

        Args:
            iteration: Current iteration number (1-indexed).
        """
        ...

    def on_iteration_complete(
        self,
        iteration: int,
        metrics: dict[str, Any],
    ) -> None:
        """Called after iteration completes.

        Args:
            iteration: Completed iteration number.
            metrics: Iteration metrics (costs, timings, etc.).
        """
        ...

    def on_agent_optimized(
        self,
        agent_id: str,
        accepted: bool,
        delta: int | None = None,
    ) -> None:
        """Called after agent optimization attempt.

        Args:
            agent_id: ID of the optimized agent.
            accepted: Whether the new policy was accepted.
            delta: Cost delta (negative = improvement) in cents.
        """
        ...

    def on_convergence(self, reason: str) -> None:
        """Called when convergence detected.

        Args:
            reason: Reason for convergence (stability, max_iterations, etc.).
        """
        ...

    def on_experiment_complete(self, result: Any) -> None:
        """Called when experiment finishes.

        Args:
            result: ExperimentResult or None if aborted.
        """
        ...


class SilentOutput:
    """Silent output handler for testing.

    All callbacks are no-ops. Useful for testing where
    console output would be distracting.

    Example:
        >>> from payment_simulator.experiments.runner import SilentOutput
        >>> output = SilentOutput()
        >>> output.on_experiment_start("test")  # No output
    """

    def on_experiment_start(self, experiment_name: str) -> None:
        """No-op for experiment start."""
        pass

    def on_iteration_start(self, iteration: int) -> None:
        """No-op for iteration start."""
        pass

    def on_iteration_complete(
        self,
        iteration: int,
        metrics: dict[str, Any],
    ) -> None:
        """No-op for iteration complete."""
        pass

    def on_agent_optimized(
        self,
        agent_id: str,
        accepted: bool,
        delta: int | None = None,
    ) -> None:
        """No-op for agent optimized."""
        pass

    def on_convergence(self, reason: str) -> None:
        """No-op for convergence."""
        pass

    def on_experiment_complete(self, result: Any) -> None:
        """No-op for experiment complete."""
        pass
