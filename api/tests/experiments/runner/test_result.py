"""Tests for ExperimentResult and ExperimentState.

These tests verify the experiment result and state dataclasses
used to track experiment progress and final outcomes.
"""

from __future__ import annotations

import pytest


class TestIterationRecord:
    """Tests for IterationRecord dataclass."""

    def test_creates_with_required_fields(self) -> None:
        """IterationRecord creates with iteration and costs."""
        from payment_simulator.experiments.runner.result import IterationRecord

        record = IterationRecord(
            iteration=1,
            costs_per_agent={"BANK_A": 1000, "BANK_B": 2000},
            accepted_changes={"BANK_A": True},
        )
        assert record.iteration == 1
        assert record.costs_per_agent["BANK_A"] == 1000
        assert record.accepted_changes["BANK_A"] is True

    def test_is_frozen(self) -> None:
        """IterationRecord is immutable."""
        from payment_simulator.experiments.runner.result import IterationRecord

        record = IterationRecord(
            iteration=1,
            costs_per_agent={"BANK_A": 1000},
            accepted_changes={},
        )
        with pytest.raises(AttributeError):
            record.iteration = 2  # type: ignore

    def test_costs_are_integers(self) -> None:
        """Costs are integer cents (INV-1)."""
        from payment_simulator.experiments.runner.result import IterationRecord

        record = IterationRecord(
            iteration=1,
            costs_per_agent={"BANK_A": 100000, "BANK_B": 200000},
            accepted_changes={},
        )
        for cost in record.costs_per_agent.values():
            assert isinstance(cost, int)


class TestExperimentState:
    """Tests for ExperimentState dataclass."""

    def test_creates_with_defaults(self) -> None:
        """ExperimentState creates with sensible defaults."""
        from payment_simulator.experiments.runner.result import ExperimentState

        state = ExperimentState(experiment_name="test")
        assert state.experiment_name == "test"
        assert state.current_iteration == 0
        assert state.is_converged is False
        assert state.convergence_reason is None

    def test_is_frozen(self) -> None:
        """ExperimentState is immutable."""
        from payment_simulator.experiments.runner.result import ExperimentState

        state = ExperimentState(experiment_name="test")
        with pytest.raises(AttributeError):
            state.current_iteration = 5  # type: ignore

    def test_with_iteration_creates_new_state(self) -> None:
        """with_iteration returns new state with updated iteration."""
        from payment_simulator.experiments.runner.result import ExperimentState

        state = ExperimentState(experiment_name="test")
        new_state = state.with_iteration(5)
        assert new_state.current_iteration == 5
        assert state.current_iteration == 0  # Original unchanged

    def test_with_converged_creates_new_state(self) -> None:
        """with_converged returns new state with convergence info."""
        from payment_simulator.experiments.runner.result import ExperimentState

        state = ExperimentState(experiment_name="test", current_iteration=10)
        new_state = state.with_converged("stability_reached")
        assert new_state.is_converged is True
        assert new_state.convergence_reason == "stability_reached"
        assert new_state.current_iteration == 10
        assert state.is_converged is False  # Original unchanged

    def test_policies_default_empty(self) -> None:
        """Policies default to empty dict."""
        from payment_simulator.experiments.runner.result import ExperimentState

        state = ExperimentState(experiment_name="test")
        assert state.policies == {}


class TestExperimentResult:
    """Tests for ExperimentResult dataclass."""

    def test_creates_with_required_fields(self) -> None:
        """ExperimentResult creates with required fields."""
        from payment_simulator.experiments.runner.result import ExperimentResult

        result = ExperimentResult(
            experiment_name="test",
            num_iterations=10,
            converged=True,
            convergence_reason="stability_reached",
            final_costs={"BANK_A": 500},
            total_duration_seconds=120.5,
        )
        assert result.experiment_name == "test"
        assert result.num_iterations == 10
        assert result.converged is True

    def test_is_frozen(self) -> None:
        """ExperimentResult is immutable."""
        from payment_simulator.experiments.runner.result import ExperimentResult

        result = ExperimentResult(
            experiment_name="test",
            num_iterations=10,
            converged=False,
            convergence_reason="max_iterations",
            final_costs={},
            total_duration_seconds=60.0,
        )
        with pytest.raises(AttributeError):
            result.num_iterations = 20  # type: ignore

    def test_final_costs_are_integers(self) -> None:
        """Final costs are integer cents (INV-1)."""
        from payment_simulator.experiments.runner.result import ExperimentResult

        result = ExperimentResult(
            experiment_name="test",
            num_iterations=5,
            converged=True,
            convergence_reason="improvement_threshold",
            final_costs={"BANK_A": 100000, "BANK_B": 200000},
            total_duration_seconds=30.0,
        )
        for cost in result.final_costs.values():
            assert isinstance(cost, int)

    def test_iteration_history_defaults_empty(self) -> None:
        """iteration_history defaults to empty tuple."""
        from payment_simulator.experiments.runner.result import ExperimentResult

        result = ExperimentResult(
            experiment_name="test",
            num_iterations=5,
            converged=True,
            convergence_reason="converged",
            final_costs={},
            total_duration_seconds=10.0,
        )
        assert result.iteration_history == ()

    def test_final_policies_defaults_empty(self) -> None:
        """final_policies defaults to empty dict."""
        from payment_simulator.experiments.runner.result import ExperimentResult

        result = ExperimentResult(
            experiment_name="test",
            num_iterations=5,
            converged=True,
            convergence_reason="converged",
            final_costs={},
            total_duration_seconds=10.0,
        )
        assert result.final_policies == {}

    def test_can_import_from_runner_module(self) -> None:
        """ExperimentResult can be imported from runner module."""
        from payment_simulator.experiments.runner import ExperimentResult

        assert ExperimentResult is not None

    def test_experiment_state_can_import_from_runner_module(self) -> None:
        """ExperimentState can be imported from runner module."""
        from payment_simulator.experiments.runner import ExperimentState

        assert ExperimentState is not None

    def test_iteration_record_can_import_from_runner_module(self) -> None:
        """IterationRecord can be imported from runner module."""
        from payment_simulator.experiments.runner import IterationRecord

        assert IterationRecord is not None
