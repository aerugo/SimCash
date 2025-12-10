"""Tests for output handler implementations.

These tests verify the OutputHandlerProtocol interface and
the SilentOutput implementation for testing.
"""

from __future__ import annotations

import pytest


class TestOutputHandlerProtocol:
    """Tests for OutputHandlerProtocol interface."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """Protocol can be used for isinstance checks."""
        from payment_simulator.experiments.runner.output import (
            OutputHandlerProtocol,
            SilentOutput,
        )

        output = SilentOutput()
        assert isinstance(output, OutputHandlerProtocol)

    def test_protocol_has_required_methods(self) -> None:
        """Protocol defines required callback methods."""
        from payment_simulator.experiments.runner.output import OutputHandlerProtocol

        assert hasattr(OutputHandlerProtocol, "on_experiment_start")
        assert hasattr(OutputHandlerProtocol, "on_iteration_start")
        assert hasattr(OutputHandlerProtocol, "on_iteration_complete")
        assert hasattr(OutputHandlerProtocol, "on_agent_optimized")
        assert hasattr(OutputHandlerProtocol, "on_convergence")
        assert hasattr(OutputHandlerProtocol, "on_experiment_complete")


class TestSilentOutput:
    """Tests for SilentOutput handler."""

    def test_on_experiment_start_is_noop(self) -> None:
        """on_experiment_start does nothing (silent)."""
        from payment_simulator.experiments.runner.output import SilentOutput

        output = SilentOutput()
        # Should not raise
        output.on_experiment_start("test_experiment")

    def test_on_iteration_start_is_noop(self) -> None:
        """on_iteration_start does nothing."""
        from payment_simulator.experiments.runner.output import SilentOutput

        output = SilentOutput()
        output.on_iteration_start(1)

    def test_on_iteration_complete_is_noop(self) -> None:
        """on_iteration_complete does nothing."""
        from payment_simulator.experiments.runner.output import SilentOutput

        output = SilentOutput()
        output.on_iteration_complete(1, {"total_cost": 1000})

    def test_on_agent_optimized_is_noop(self) -> None:
        """on_agent_optimized does nothing."""
        from payment_simulator.experiments.runner.output import SilentOutput

        output = SilentOutput()
        output.on_agent_optimized("BANK_A", accepted=True, delta=-100)

    def test_on_convergence_is_noop(self) -> None:
        """on_convergence does nothing."""
        from payment_simulator.experiments.runner.output import SilentOutput

        output = SilentOutput()
        output.on_convergence("stability_reached")

    def test_on_experiment_complete_is_noop(self) -> None:
        """on_experiment_complete does nothing."""
        from payment_simulator.experiments.runner.output import SilentOutput

        output = SilentOutput()
        output.on_experiment_complete(None)

    def test_can_import_from_runner_module(self) -> None:
        """SilentOutput can be imported from runner module."""
        from payment_simulator.experiments.runner import SilentOutput

        assert SilentOutput is not None

    def test_output_handler_protocol_can_import_from_runner_module(self) -> None:
        """OutputHandlerProtocol can be imported from runner module."""
        from payment_simulator.experiments.runner import OutputHandlerProtocol

        assert OutputHandlerProtocol is not None
