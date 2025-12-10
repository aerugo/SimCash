"""Tests for ExperimentRunnerProtocol.

These tests verify the ExperimentRunnerProtocol interface
defines the required methods for experiment runners.
"""

from __future__ import annotations

import pytest
from typing import Protocol


class TestExperimentRunnerProtocol:
    """Tests for ExperimentRunnerProtocol interface."""

    def test_protocol_has_run_method(self) -> None:
        """Protocol defines async run method."""
        from payment_simulator.experiments.runner.protocol import (
            ExperimentRunnerProtocol,
        )

        assert hasattr(ExperimentRunnerProtocol, "run")

    def test_protocol_has_get_state_method(self) -> None:
        """Protocol defines get_current_state method."""
        from payment_simulator.experiments.runner.protocol import (
            ExperimentRunnerProtocol,
        )

        assert hasattr(ExperimentRunnerProtocol, "get_current_state")

    def test_protocol_is_protocol_subclass(self) -> None:
        """Protocol is a Protocol subclass."""
        from payment_simulator.experiments.runner.protocol import (
            ExperimentRunnerProtocol,
        )

        assert issubclass(ExperimentRunnerProtocol, Protocol)

    def test_protocol_is_runtime_checkable(self) -> None:
        """Protocol can be used for isinstance checks."""
        from payment_simulator.experiments.runner.protocol import (
            ExperimentRunnerProtocol,
        )
        from payment_simulator.experiments.runner.result import (
            ExperimentResult,
            ExperimentState,
        )

        # Create a mock that satisfies the protocol
        class MockRunner:
            async def run(self) -> ExperimentResult:
                return ExperimentResult(
                    experiment_name="mock",
                    num_iterations=1,
                    converged=True,
                    convergence_reason="test",
                    final_costs={},
                    total_duration_seconds=0.0,
                )

            def get_current_state(self) -> ExperimentState:
                return ExperimentState(experiment_name="mock")

        # Should not raise - isinstance check works
        mock = MockRunner()
        assert isinstance(mock, ExperimentRunnerProtocol)

    def test_can_import_from_runner_module(self) -> None:
        """ExperimentRunnerProtocol can be imported from runner module."""
        from payment_simulator.experiments.runner import ExperimentRunnerProtocol

        assert ExperimentRunnerProtocol is not None
