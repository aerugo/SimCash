"""TDD tests for core StateProvider protocol.

Tests for generalizing StateProvider pattern for experiment replay.

Write these tests FIRST, then implement.

Phase 11, Task 11.1: StateProvider Protocol
"""

from __future__ import annotations

import pytest
from pathlib import Path
from typing import Any, Iterator


# =============================================================================
# Protocol Definition Tests
# =============================================================================


class TestExperimentStateProviderProtocol:
    """Tests for ExperimentStateProviderProtocol definition."""

    def test_protocol_importable_from_runner(self) -> None:
        """Protocol should be importable from experiments.runner."""
        from payment_simulator.experiments.runner import (
            ExperimentStateProviderProtocol,
        )

        assert ExperimentStateProviderProtocol is not None

    def test_protocol_importable_from_state_provider(self) -> None:
        """Protocol should be importable from state_provider module."""
        from payment_simulator.experiments.runner.state_provider import (
            ExperimentStateProviderProtocol,
        )

        assert ExperimentStateProviderProtocol is not None

    def test_protocol_is_runtime_checkable(self) -> None:
        """Protocol should be @runtime_checkable for isinstance checks."""
        from typing import Iterator

        from payment_simulator.experiments.runner import (
            ExperimentStateProviderProtocol,
        )

        # Create a mock implementation with all required methods
        class MockProvider:
            def get_experiment_info(self) -> dict[str, Any]:
                return {}

            def get_total_iterations(self) -> int:
                return 0

            def get_iteration_events(self, iteration: int) -> list[dict[str, Any]]:
                return []

            def get_iteration_policies(self, iteration: int) -> dict[str, Any]:
                return {}

            def get_iteration_costs(self, iteration: int) -> dict[str, int]:
                return {}

            def get_iteration_accepted_changes(
                self, iteration: int
            ) -> dict[str, bool]:
                return {}

            # Audit methods (Phase 13)
            @property
            def run_id(self) -> str | None:
                return None

            def get_run_metadata(self) -> dict[str, Any] | None:
                return None

            def get_all_events(self) -> Iterator[dict[str, Any]]:
                return iter([])

            def get_final_result(self) -> dict[str, Any] | None:
                return None

        provider = MockProvider()
        assert isinstance(provider, ExperimentStateProviderProtocol)

    def test_protocol_requires_get_experiment_info(self) -> None:
        """Protocol should require get_experiment_info method."""
        from payment_simulator.experiments.runner import (
            ExperimentStateProviderProtocol,
        )

        assert hasattr(ExperimentStateProviderProtocol, "get_experiment_info")

    def test_protocol_requires_get_total_iterations(self) -> None:
        """Protocol should require get_total_iterations method."""
        from payment_simulator.experiments.runner import (
            ExperimentStateProviderProtocol,
        )

        assert hasattr(ExperimentStateProviderProtocol, "get_total_iterations")

    def test_protocol_requires_get_iteration_events(self) -> None:
        """Protocol should require get_iteration_events method."""
        from payment_simulator.experiments.runner import (
            ExperimentStateProviderProtocol,
        )

        assert hasattr(ExperimentStateProviderProtocol, "get_iteration_events")

    def test_protocol_requires_get_iteration_policies(self) -> None:
        """Protocol should require get_iteration_policies method."""
        from payment_simulator.experiments.runner import (
            ExperimentStateProviderProtocol,
        )

        assert hasattr(ExperimentStateProviderProtocol, "get_iteration_policies")

    def test_protocol_requires_get_iteration_costs(self) -> None:
        """Protocol should require get_iteration_costs method."""
        from payment_simulator.experiments.runner import (
            ExperimentStateProviderProtocol,
        )

        assert hasattr(ExperimentStateProviderProtocol, "get_iteration_costs")

    def test_protocol_requires_get_iteration_accepted_changes(self) -> None:
        """Protocol should require get_iteration_accepted_changes method."""
        from payment_simulator.experiments.runner import (
            ExperimentStateProviderProtocol,
        )

        assert hasattr(
            ExperimentStateProviderProtocol, "get_iteration_accepted_changes"
        )


# =============================================================================
# LiveStateProvider Tests
# =============================================================================


class TestLiveStateProvider:
    """Tests for LiveStateProvider implementation."""

    def test_importable_from_runner(self) -> None:
        """LiveStateProvider should be importable from experiments.runner."""
        from payment_simulator.experiments.runner import LiveStateProvider

        assert LiveStateProvider is not None

    def test_importable_from_state_provider(self) -> None:
        """LiveStateProvider should be importable from state_provider module."""
        from payment_simulator.experiments.runner.state_provider import (
            LiveStateProvider,
        )

        assert LiveStateProvider is not None

    def test_implements_protocol(self) -> None:
        """LiveStateProvider should implement the protocol."""
        from payment_simulator.experiments.runner import (
            LiveStateProvider,
            ExperimentStateProviderProtocol,
        )

        # Check it has required methods
        assert hasattr(LiveStateProvider, "get_experiment_info")
        assert hasattr(LiveStateProvider, "get_total_iterations")
        assert hasattr(LiveStateProvider, "get_iteration_events")
        assert hasattr(LiveStateProvider, "get_iteration_policies")
        assert hasattr(LiveStateProvider, "get_iteration_costs")
        assert hasattr(LiveStateProvider, "get_iteration_accepted_changes")

    def test_is_instance_of_protocol(self) -> None:
        """LiveStateProvider instance should satisfy isinstance check."""
        from payment_simulator.experiments.runner import (
            LiveStateProvider,
            ExperimentStateProviderProtocol,
        )

        provider = LiveStateProvider(
            experiment_name="test",
            experiment_type="castro",
            config={"master_seed": 42},
        )
        assert isinstance(provider, ExperimentStateProviderProtocol)

    def test_get_experiment_info_returns_dict(self) -> None:
        """get_experiment_info should return experiment metadata."""
        from payment_simulator.experiments.runner import LiveStateProvider

        provider = LiveStateProvider(
            experiment_name="test_exp",
            experiment_type="castro",
            config={"master_seed": 42, "num_samples": 10},
        )

        info = provider.get_experiment_info()
        assert isinstance(info, dict)
        assert info["experiment_name"] == "test_exp"
        assert info["experiment_type"] == "castro"
        assert info["config"]["master_seed"] == 42

    def test_get_total_iterations_initially_zero(self) -> None:
        """get_total_iterations should return 0 for new provider."""
        from payment_simulator.experiments.runner import LiveStateProvider

        provider = LiveStateProvider(
            experiment_name="test",
            experiment_type="castro",
            config={},
        )

        assert provider.get_total_iterations() == 0

    def test_record_iteration_increments_count(self) -> None:
        """Recording iteration should increment iteration count."""
        from payment_simulator.experiments.runner import LiveStateProvider

        provider = LiveStateProvider(
            experiment_name="test",
            experiment_type="castro",
            config={},
        )

        # Record an iteration
        provider.record_iteration(
            iteration=0,
            costs_per_agent={"BANK_A": 1000, "BANK_B": 1500},
            accepted_changes={"BANK_A": True, "BANK_B": False},
            policies={"BANK_A": {"type": "release"}, "BANK_B": {"type": "hold"}},
        )

        assert provider.get_total_iterations() == 1

    def test_get_iteration_costs_returns_recorded_costs(self) -> None:
        """get_iteration_costs should return previously recorded costs."""
        from payment_simulator.experiments.runner import LiveStateProvider

        provider = LiveStateProvider(
            experiment_name="test",
            experiment_type="castro",
            config={},
        )

        # Record an iteration with specific costs
        provider.record_iteration(
            iteration=0,
            costs_per_agent={"BANK_A": 1000, "BANK_B": 1500},
            accepted_changes={"BANK_A": True, "BANK_B": False},
            policies={},
        )

        costs = provider.get_iteration_costs(0)
        assert costs["BANK_A"] == 1000
        assert costs["BANK_B"] == 1500

    def test_costs_are_integer_cents(self) -> None:
        """All costs must be integer cents (INV-1 compliance)."""
        from payment_simulator.experiments.runner import LiveStateProvider

        provider = LiveStateProvider(
            experiment_name="test",
            experiment_type="castro",
            config={},
        )

        # Record iteration with integer cents
        provider.record_iteration(
            iteration=0,
            costs_per_agent={"BANK_A": 100050, "BANK_B": 200075},
            accepted_changes={},
            policies={},
        )

        costs = provider.get_iteration_costs(0)
        for agent_id, cost in costs.items():
            assert isinstance(cost, int), f"Cost for {agent_id} must be integer cents"

    def test_record_event_stores_event(self) -> None:
        """record_event should store events for retrieval."""
        from payment_simulator.experiments.runner import LiveStateProvider

        provider = LiveStateProvider(
            experiment_name="test",
            experiment_type="castro",
            config={},
        )

        # Record an event
        provider.record_event(
            iteration=0,
            event_type="bootstrap_evaluation",
            event_data={"mean_cost": 1000, "std_cost": 100},
        )

        events = provider.get_iteration_events(0)
        assert len(events) == 1
        assert events[0]["event_type"] == "bootstrap_evaluation"
        assert events[0]["mean_cost"] == 1000


# =============================================================================
# DatabaseStateProvider Tests
# =============================================================================


class TestDatabaseStateProvider:
    """Tests for DatabaseStateProvider implementation."""

    def test_importable_from_runner(self) -> None:
        """DatabaseStateProvider should be importable from experiments.runner."""
        from payment_simulator.experiments.runner import DatabaseStateProvider

        assert DatabaseStateProvider is not None

    def test_importable_from_state_provider(self) -> None:
        """DatabaseStateProvider should be importable from state_provider module."""
        from payment_simulator.experiments.runner.state_provider import (
            DatabaseStateProvider,
        )

        assert DatabaseStateProvider is not None

    def test_implements_protocol(self) -> None:
        """DatabaseStateProvider should implement the protocol."""
        from payment_simulator.experiments.runner import (
            DatabaseStateProvider,
        )

        # Check it has required methods
        assert hasattr(DatabaseStateProvider, "get_experiment_info")
        assert hasattr(DatabaseStateProvider, "get_total_iterations")
        assert hasattr(DatabaseStateProvider, "get_iteration_events")
        assert hasattr(DatabaseStateProvider, "get_iteration_policies")
        assert hasattr(DatabaseStateProvider, "get_iteration_costs")
        assert hasattr(DatabaseStateProvider, "get_iteration_accepted_changes")

    def test_requires_repository_and_run_id(self) -> None:
        """DatabaseStateProvider should require repository and run_id."""
        from payment_simulator.experiments.runner.state_provider import (
            DatabaseStateProvider,
        )
        import inspect

        sig = inspect.signature(DatabaseStateProvider.__init__)
        params = list(sig.parameters.keys())
        assert "repository" in params or "repo" in params
        assert "run_id" in params


class TestDatabaseStateProviderWithData:
    """Integration tests for DatabaseStateProvider with actual database."""

    @pytest.fixture
    def repo_with_data(self, tmp_path: Path) -> Any:
        """Create repository with test data."""
        from payment_simulator.experiments.persistence import (
            ExperimentRepository,
            ExperimentRecord,
            IterationRecord,
        )

        db_path = tmp_path / "test.db"
        repository = ExperimentRepository(db_path)

        # Add experiment
        exp_record = ExperimentRecord(
            run_id="test-run",
            experiment_name="test_experiment",
            experiment_type="castro",
            config={"master_seed": 42},
            created_at="2025-12-11T10:00:00",
            completed_at="2025-12-11T10:30:00",
            num_iterations=3,
            converged=True,
            convergence_reason="stability",
        )
        repository.save_experiment(exp_record)

        # Add iterations
        for i in range(3):
            iter_record = IterationRecord(
                run_id="test-run",
                iteration=i,
                costs_per_agent={"BANK_A": 1000 - i * 100, "BANK_B": 1500 - i * 50},
                accepted_changes={"BANK_A": i > 0, "BANK_B": False},
                policies={"BANK_A": {"iter": i}, "BANK_B": {"iter": i}},
                timestamp=f"2025-12-11T10:{i:02d}:00",
            )
            repository.save_iteration(iter_record)

        yield repository
        repository.close()

    def test_get_experiment_info(self, repo_with_data: Any) -> None:
        """Should return experiment info from database."""
        from payment_simulator.experiments.runner import DatabaseStateProvider

        provider = DatabaseStateProvider(repo_with_data, "test-run")
        info = provider.get_experiment_info()

        assert info["experiment_name"] == "test_experiment"
        assert info["experiment_type"] == "castro"
        assert info["converged"] is True

    def test_get_total_iterations(self, repo_with_data: Any) -> None:
        """Should return correct iteration count."""
        from payment_simulator.experiments.runner import DatabaseStateProvider

        provider = DatabaseStateProvider(repo_with_data, "test-run")
        assert provider.get_total_iterations() == 3

    def test_get_iteration_costs(self, repo_with_data: Any) -> None:
        """Should return iteration costs."""
        from payment_simulator.experiments.runner import DatabaseStateProvider

        provider = DatabaseStateProvider(repo_with_data, "test-run")
        costs = provider.get_iteration_costs(0)

        assert costs["BANK_A"] == 1000
        assert costs["BANK_B"] == 1500

    def test_costs_are_integer_cents(self, repo_with_data: Any) -> None:
        """All costs must be integer cents (INV-1)."""
        from payment_simulator.experiments.runner import DatabaseStateProvider

        provider = DatabaseStateProvider(repo_with_data, "test-run")
        costs = provider.get_iteration_costs(0)

        for agent_id, cost in costs.items():
            assert isinstance(cost, int), f"Cost for {agent_id} must be integer cents"

    def test_get_iteration_policies(self, repo_with_data: Any) -> None:
        """Should return iteration policies."""
        from payment_simulator.experiments.runner import DatabaseStateProvider

        provider = DatabaseStateProvider(repo_with_data, "test-run")
        policies = provider.get_iteration_policies(1)

        assert policies["BANK_A"]["iter"] == 1

    def test_get_iteration_accepted_changes(self, repo_with_data: Any) -> None:
        """Should return accepted changes."""
        from payment_simulator.experiments.runner import DatabaseStateProvider

        provider = DatabaseStateProvider(repo_with_data, "test-run")
        changes = provider.get_iteration_accepted_changes(1)

        assert changes["BANK_A"] is True
        assert changes["BANK_B"] is False


# =============================================================================
# Castro Backward Compatibility Tests
# =============================================================================


def _castro_available() -> bool:
    """Check if castro module with state_provider is available.

    Note: A test 'castro' directory exists in tests/castro but that's not
    the real castro package. We need to check for the actual submodule.
    """
    try:
        from castro.state_provider import ExperimentStateProvider  # noqa: F401

        return True
    except ImportError:
        return False


class TestCastroBackwardCompatibility:
    """Tests ensuring Castro can use core StateProvider."""

    @pytest.mark.skipif(
        not _castro_available(),
        reason="Castro module not available in this environment",
    )
    def test_castro_can_import_core_protocol(self) -> None:
        """Castro should be able to import core protocol."""
        from payment_simulator.experiments.runner import (
            ExperimentStateProviderProtocol,
        )

        assert ExperimentStateProviderProtocol is not None

    @pytest.mark.skipif(
        not _castro_available(),
        reason="Castro module not available in this environment",
    )
    def test_castro_provider_method_signatures_compatible(self) -> None:
        """Castro's provider should have compatible method signatures."""
        from castro.state_provider import ExperimentStateProvider

        # Castro provider should have methods compatible with core protocol
        assert hasattr(ExperimentStateProvider, "get_run_metadata")
        # Note: Castro uses get_run_metadata instead of get_experiment_info
        # and get_events_for_iteration instead of get_iteration_events

    @pytest.mark.skipif(
        not _castro_available(),
        reason="Castro module not available in this environment",
    )
    def test_castro_live_provider_exists(self) -> None:
        """Castro's LiveExperimentProvider should exist."""
        from castro.state_provider import LiveExperimentProvider

        assert LiveExperimentProvider is not None

    @pytest.mark.skipif(
        not _castro_available(),
        reason="Castro module not available in this environment",
    )
    def test_castro_database_provider_exists(self) -> None:
        """Castro's DatabaseExperimentProvider should exist."""
        from castro.state_provider import DatabaseExperimentProvider

        assert DatabaseExperimentProvider is not None
