"""Experiment runner protocol.

This module defines the ExperimentRunnerProtocol interface
that all experiment runners must implement.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from payment_simulator.experiments.runner.result import (
        ExperimentResult,
        ExperimentState,
    )


@runtime_checkable
class ExperimentRunnerProtocol(Protocol):
    """Protocol for experiment runners.

    Defines the interface for experiment execution. Implementations
    handle the optimization loop, convergence detection, and
    policy updates.

    Example:
        >>> class MyRunner:
        ...     async def run(self) -> ExperimentResult:
        ...         # Run experiment...
        ...         return result
        ...     def get_current_state(self) -> ExperimentState:
        ...         return self._state
        >>>
        >>> runner = MyRunner()
        >>> assert isinstance(runner, ExperimentRunnerProtocol)

    The typical optimization loop:
        1. Evaluate current policies
        2. Check convergence criteria
        3. For each agent, generate new policy via LLM
        4. Accept/reject based on paired comparison
        5. Repeat until convergence or max iterations
    """

    async def run(self) -> ExperimentResult:
        """Run experiment to completion.

        Executes the full optimization loop until convergence
        or max iterations is reached.

        Returns:
            ExperimentResult with final state and metrics.
        """
        ...

    def get_current_state(self) -> ExperimentState:
        """Get current experiment state.

        Returns:
            ExperimentState snapshot of current progress.
        """
        ...
