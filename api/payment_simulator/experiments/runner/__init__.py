"""Experiment runner module.

Provides the framework for executing policy optimization experiments.

Components:
    - ExperimentRunnerProtocol: Protocol for experiment runners
    - OutputHandlerProtocol: Protocol for output handling
    - SilentOutput: Silent output for testing
    - ExperimentResult: Final experiment result
    - ExperimentState: Current experiment state
    - IterationRecord: Record of a single iteration
    - ExperimentStateProviderProtocol: Protocol for experiment state access
    - LiveStateProvider: State provider for live experiments
    - DatabaseStateProvider: State provider for database replay

Example:
    >>> from payment_simulator.experiments.runner import (
    ...     ExperimentResult,
    ...     ExperimentState,
    ...     SilentOutput,
    ...     LiveStateProvider,
    ... )
    >>> state = ExperimentState(experiment_name="test")
    >>> output = SilentOutput()
    >>> provider = LiveStateProvider(
    ...     experiment_name="test",
    ...     experiment_type="castro",
    ...     config={},
    ... )
"""

from payment_simulator.experiments.runner.output import (
    OutputHandlerProtocol,
    SilentOutput,
)
from payment_simulator.experiments.runner.protocol import ExperimentRunnerProtocol
from payment_simulator.experiments.runner.result import (
    ExperimentResult,
    ExperimentState,
    IterationRecord,
)
from payment_simulator.experiments.runner.state_provider import (
    DatabaseStateProvider,
    ExperimentStateProviderProtocol,
    LiveStateProvider,
)

__all__ = [
    # Output handling
    "OutputHandlerProtocol",
    "SilentOutput",
    # Runner protocol
    "ExperimentRunnerProtocol",
    # Result types
    "ExperimentResult",
    "ExperimentState",
    "IterationRecord",
    # State provider (Phase 11)
    "ExperimentStateProviderProtocol",
    "LiveStateProvider",
    "DatabaseStateProvider",
]
