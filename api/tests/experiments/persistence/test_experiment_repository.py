"""TDD tests for unified ExperimentRepository.

Tests for the core experiment persistence layer.

Write these tests FIRST, then implement.

Phase 11, Task 11.2: Unified Persistence

All costs are integer cents (INV-1 compliance).
"""

from __future__ import annotations

import pytest
from pathlib import Path
from typing import Any


# =============================================================================
# Import Tests
# =============================================================================


class TestExperimentRepositoryImport:
    """Tests for importing ExperimentRepository."""

    def test_importable_from_persistence(self) -> None:
        """ExperimentRepository should be importable from experiments.persistence."""
        from payment_simulator.experiments.persistence import ExperimentRepository

        assert ExperimentRepository is not None

    def test_importable_from_repository_module(self) -> None:
        """ExperimentRepository should be importable from repository module."""
        from payment_simulator.experiments.persistence.repository import (
            ExperimentRepository,
        )

        assert ExperimentRepository is not None

    def test_record_classes_importable(self) -> None:
        """Record dataclasses should be importable."""
        from payment_simulator.experiments.persistence import (
            ExperimentRecord,
            IterationRecord,
        )

        assert ExperimentRecord is not None
        assert IterationRecord is not None

    def test_event_record_importable(self) -> None:
        """EventRecord should be importable."""
        from payment_simulator.experiments.persistence import EventRecord

        assert EventRecord is not None


# =============================================================================
# Record Class Tests
# =============================================================================


class TestExperimentRecord:
    """Tests for ExperimentRecord dataclass."""

    def test_is_frozen(self) -> None:
        """ExperimentRecord should be immutable."""
        from payment_simulator.experiments.persistence import ExperimentRecord

        record = ExperimentRecord(
            run_id="test-run",
            experiment_name="test",
            experiment_type="castro",
            config={},
            created_at="2025-12-11T10:00:00",
            completed_at=None,
            num_iterations=0,
            converged=False,
            convergence_reason=None,
        )

        with pytest.raises(AttributeError):
            record.run_id = "new-id"  # type: ignore

    def test_has_required_fields(self) -> None:
        """ExperimentRecord should have all required fields."""
        from payment_simulator.experiments.persistence import ExperimentRecord

        record = ExperimentRecord(
            run_id="test-run-001",
            experiment_name="test_exp",
            experiment_type="castro",
            config={"master_seed": 42, "num_samples": 10},
            created_at="2025-12-11T10:00:00",
            completed_at="2025-12-11T10:30:00",
            num_iterations=5,
            converged=True,
            convergence_reason="stability",
        )

        assert record.run_id == "test-run-001"
        assert record.experiment_name == "test_exp"
        assert record.experiment_type == "castro"
        assert record.config == {"master_seed": 42, "num_samples": 10}
        assert record.created_at == "2025-12-11T10:00:00"
        assert record.completed_at == "2025-12-11T10:30:00"
        assert record.num_iterations == 5
        assert record.converged is True
        assert record.convergence_reason == "stability"


class TestIterationRecord:
    """Tests for IterationRecord dataclass."""

    def test_is_frozen(self) -> None:
        """IterationRecord should be immutable."""
        from payment_simulator.experiments.persistence import IterationRecord

        record = IterationRecord(
            run_id="test-run",
            iteration=0,
            costs_per_agent={},
            accepted_changes={},
            policies={},
            timestamp="2025-12-11T10:00:00",
        )

        with pytest.raises(AttributeError):
            record.iteration = 1  # type: ignore

    def test_costs_field_for_integer_cents(self) -> None:
        """costs_per_agent should store integer cents (INV-1)."""
        from payment_simulator.experiments.persistence import IterationRecord

        record = IterationRecord(
            run_id="test-run",
            iteration=0,
            costs_per_agent={"BANK_A": 100050, "BANK_B": 200075},
            accepted_changes={"BANK_A": True, "BANK_B": False},
            policies={"BANK_A": {"type": "release"}, "BANK_B": {"type": "hold"}},
            timestamp="2025-12-11T10:00:00",
        )

        # Verify costs are integers
        for agent_id, cost in record.costs_per_agent.items():
            assert isinstance(cost, int), f"Cost for {agent_id} must be integer cents"


class TestEventRecord:
    """Tests for EventRecord dataclass."""

    def test_is_frozen(self) -> None:
        """EventRecord should be immutable."""
        from payment_simulator.experiments.persistence import EventRecord

        record = EventRecord(
            run_id="test-run",
            iteration=0,
            event_type="bootstrap_evaluation",
            event_data={"mean_cost": 1000},
            timestamp="2025-12-11T10:00:00",
        )

        with pytest.raises(AttributeError):
            record.event_type = "new_type"  # type: ignore


# =============================================================================
# Repository Creation Tests
# =============================================================================


class TestExperimentRepositoryCreation:
    """Tests for creating ExperimentRepository."""

    def test_creates_database_file(self, tmp_path: Path) -> None:
        """Repository should create database file."""
        from payment_simulator.experiments.persistence import ExperimentRepository

        db_path = tmp_path / "experiments.db"
        repo = ExperimentRepository(db_path)

        assert db_path.exists()
        repo.close()

    def test_creates_required_tables(self, tmp_path: Path) -> None:
        """Repository should create required tables."""
        from payment_simulator.experiments.persistence import ExperimentRepository
        import duckdb

        db_path = tmp_path / "experiments.db"
        repo = ExperimentRepository(db_path)
        repo.close()

        # Verify tables exist
        conn = duckdb.connect(str(db_path))
        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
        ).fetchall()
        table_names = [t[0] for t in tables]
        conn.close()

        assert "experiments" in table_names
        assert "experiment_iterations" in table_names
        assert "experiment_events" in table_names

    def test_idempotent_schema_creation(self, tmp_path: Path) -> None:
        """Creating repository twice should not error."""
        from payment_simulator.experiments.persistence import ExperimentRepository

        db_path = tmp_path / "experiments.db"

        # Create first time
        repo1 = ExperimentRepository(db_path)
        repo1.close()

        # Create second time (should not error)
        repo2 = ExperimentRepository(db_path)
        repo2.close()

    def test_context_manager_support(self, tmp_path: Path) -> None:
        """Repository should support context manager pattern."""
        from payment_simulator.experiments.persistence import ExperimentRepository

        db_path = tmp_path / "experiments.db"

        with ExperimentRepository(db_path) as repo:
            assert repo is not None


# =============================================================================
# Experiment Record Operations Tests
# =============================================================================


class TestExperimentRecordOperations:
    """Tests for experiment record CRUD operations."""

    @pytest.fixture
    def repo(self, tmp_path: Path) -> Any:
        """Create repository for testing."""
        from payment_simulator.experiments.persistence import ExperimentRepository

        db_path = tmp_path / "test.db"
        repository = ExperimentRepository(db_path)
        yield repository
        repository.close()

    def test_save_and_load_experiment(self, repo: Any) -> None:
        """Should save and load experiment record."""
        from payment_simulator.experiments.persistence import ExperimentRecord

        record = ExperimentRecord(
            run_id="test-run-001",
            experiment_name="test_experiment",
            experiment_type="castro",
            config={"num_samples": 10, "ticks": 12},
            created_at="2025-12-11T10:00:00",
            completed_at=None,
            num_iterations=0,
            converged=False,
            convergence_reason=None,
        )

        repo.save_experiment(record)
        loaded = repo.load_experiment("test-run-001")

        assert loaded is not None
        assert loaded.run_id == "test-run-001"
        assert loaded.experiment_name == "test_experiment"
        assert loaded.experiment_type == "castro"
        assert loaded.config == {"num_samples": 10, "ticks": 12}

    def test_load_nonexistent_experiment_returns_none(self, repo: Any) -> None:
        """Loading non-existent experiment should return None."""
        loaded = repo.load_experiment("nonexistent-run")
        assert loaded is None

    def test_update_experiment(self, repo: Any) -> None:
        """Should update existing experiment."""
        from payment_simulator.experiments.persistence import ExperimentRecord

        # Save initial record
        record = ExperimentRecord(
            run_id="test-run",
            experiment_name="test",
            experiment_type="castro",
            config={},
            created_at="2025-12-11T10:00:00",
            completed_at=None,
            num_iterations=0,
            converged=False,
            convergence_reason=None,
        )
        repo.save_experiment(record)

        # Update with new data
        updated = ExperimentRecord(
            run_id="test-run",
            experiment_name="test",
            experiment_type="castro",
            config={},
            created_at="2025-12-11T10:00:00",
            completed_at="2025-12-11T10:30:00",
            num_iterations=5,
            converged=True,
            convergence_reason="stability",
        )
        repo.save_experiment(updated)

        # Load and verify update
        loaded = repo.load_experiment("test-run")
        assert loaded is not None
        assert loaded.completed_at == "2025-12-11T10:30:00"
        assert loaded.num_iterations == 5
        assert loaded.converged is True
        assert loaded.convergence_reason == "stability"

    def test_list_experiments_by_type(self, repo: Any) -> None:
        """Should list experiments filtered by type."""
        from payment_simulator.experiments.persistence import ExperimentRecord

        # Save experiments of different types
        for i, exp_type in enumerate(["castro", "castro", "custom"]):
            record = ExperimentRecord(
                run_id=f"run-{i}",
                experiment_name=f"exp-{i}",
                experiment_type=exp_type,
                config={},
                created_at="2025-12-11T10:00:00",
                completed_at=None,
                num_iterations=0,
                converged=False,
                convergence_reason=None,
            )
            repo.save_experiment(record)

        castro_experiments = repo.list_experiments(experiment_type="castro")
        assert len(castro_experiments) == 2

        all_experiments = repo.list_experiments()
        assert len(all_experiments) == 3

    def test_list_experiments_empty_returns_empty_list(self, repo: Any) -> None:
        """Listing experiments when none exist should return empty list."""
        experiments = repo.list_experiments()
        assert experiments == []


# =============================================================================
# Iteration Record Operations Tests
# =============================================================================


class TestIterationRecordOperations:
    """Tests for iteration record operations."""

    @pytest.fixture
    def repo_with_experiment(self, tmp_path: Path) -> Any:
        """Create repository with a test experiment."""
        from payment_simulator.experiments.persistence import (
            ExperimentRepository,
            ExperimentRecord,
        )

        db_path = tmp_path / "test.db"
        repository = ExperimentRepository(db_path)

        record = ExperimentRecord(
            run_id="test-run",
            experiment_name="test",
            experiment_type="castro",
            config={},
            created_at="2025-12-11T10:00:00",
            completed_at=None,
            num_iterations=0,
            converged=False,
            convergence_reason=None,
        )
        repository.save_experiment(record)

        yield repository
        repository.close()

    def test_save_and_get_iterations(self, repo_with_experiment: Any) -> None:
        """Should save and retrieve iterations."""
        from payment_simulator.experiments.persistence import IterationRecord

        record = IterationRecord(
            run_id="test-run",
            iteration=0,
            costs_per_agent={"BANK_A": 1000, "BANK_B": 1500},
            accepted_changes={"BANK_A": True, "BANK_B": False},
            policies={"BANK_A": {"type": "release"}, "BANK_B": {"type": "hold"}},
            timestamp="2025-12-11T10:01:00",
        )

        repo_with_experiment.save_iteration(record)
        iterations = repo_with_experiment.get_iterations("test-run")

        assert len(iterations) == 1
        assert iterations[0].iteration == 0
        assert iterations[0].costs_per_agent == {"BANK_A": 1000, "BANK_B": 1500}

    def test_get_iterations_ordered_by_iteration(
        self, repo_with_experiment: Any
    ) -> None:
        """Iterations should be returned in order."""
        from payment_simulator.experiments.persistence import IterationRecord

        # Save iterations out of order
        for i in [2, 0, 1]:
            record = IterationRecord(
                run_id="test-run",
                iteration=i,
                costs_per_agent={"BANK_A": 1000 - i * 100},
                accepted_changes={},
                policies={},
                timestamp=f"2025-12-11T10:{i:02d}:00",
            )
            repo_with_experiment.save_iteration(record)

        iterations = repo_with_experiment.get_iterations("test-run")

        assert len(iterations) == 3
        assert iterations[0].iteration == 0
        assert iterations[1].iteration == 1
        assert iterations[2].iteration == 2

    def test_costs_are_integer_cents(self, repo_with_experiment: Any) -> None:
        """All costs must be integer cents (INV-1 compliance)."""
        from payment_simulator.experiments.persistence import IterationRecord

        record = IterationRecord(
            run_id="test-run",
            iteration=0,
            costs_per_agent={"BANK_A": 100050, "BANK_B": 200075},  # Integer cents
            accepted_changes={},
            policies={},
            timestamp="2025-12-11T10:01:00",
        )

        repo_with_experiment.save_iteration(record)
        iterations = repo_with_experiment.get_iterations("test-run")

        for agent_id, cost in iterations[0].costs_per_agent.items():
            assert isinstance(cost, int), f"Cost for {agent_id} must be integer cents"

    def test_get_iterations_nonexistent_run_returns_empty(
        self, repo_with_experiment: Any
    ) -> None:
        """Getting iterations for non-existent run returns empty list."""
        iterations = repo_with_experiment.get_iterations("nonexistent-run")
        assert iterations == []


# =============================================================================
# Event Operations Tests
# =============================================================================


class TestEventOperations:
    """Tests for event operations."""

    @pytest.fixture
    def repo_with_experiment(self, tmp_path: Path) -> Any:
        """Create repository with a test experiment."""
        from payment_simulator.experiments.persistence import (
            ExperimentRepository,
            ExperimentRecord,
        )

        db_path = tmp_path / "test.db"
        repository = ExperimentRepository(db_path)

        record = ExperimentRecord(
            run_id="test-run",
            experiment_name="test",
            experiment_type="castro",
            config={},
            created_at="2025-12-11T10:00:00",
            completed_at=None,
            num_iterations=0,
            converged=False,
            convergence_reason=None,
        )
        repository.save_experiment(record)

        yield repository
        repository.close()

    def test_save_and_get_events(self, repo_with_experiment: Any) -> None:
        """Should save and retrieve events."""
        from payment_simulator.experiments.persistence import EventRecord

        event = EventRecord(
            run_id="test-run",
            iteration=0,
            event_type="bootstrap_evaluation",
            event_data={"mean_cost": 1000, "std_cost": 100},
            timestamp="2025-12-11T10:01:00",
        )

        repo_with_experiment.save_event(event)
        events = repo_with_experiment.get_events("test-run", 0)

        assert len(events) == 1
        assert events[0].event_type == "bootstrap_evaluation"
        assert events[0].event_data["mean_cost"] == 1000

    def test_get_events_filtered_by_iteration(self, repo_with_experiment: Any) -> None:
        """Events should be filtered by iteration."""
        from payment_simulator.experiments.persistence import EventRecord

        # Save events for different iterations
        for i in range(3):
            event = EventRecord(
                run_id="test-run",
                iteration=i,
                event_type=f"event_{i}",
                event_data={"iteration": i},
                timestamp=f"2025-12-11T10:{i:02d}:00",
            )
            repo_with_experiment.save_event(event)

        events_iter_1 = repo_with_experiment.get_events("test-run", 1)
        assert len(events_iter_1) == 1
        assert events_iter_1[0].event_data["iteration"] == 1

    def test_get_all_events_for_run(self, repo_with_experiment: Any) -> None:
        """Should get all events for a run."""
        from payment_simulator.experiments.persistence import EventRecord

        # Save events for different iterations
        for i in range(3):
            event = EventRecord(
                run_id="test-run",
                iteration=i,
                event_type=f"event_{i}",
                event_data={},
                timestamp=f"2025-12-11T10:{i:02d}:00",
            )
            repo_with_experiment.save_event(event)

        all_events = repo_with_experiment.get_all_events("test-run")
        assert len(all_events) == 3


# =============================================================================
# StateProvider Integration Tests
# =============================================================================


class TestStateProviderIntegration:
    """Tests for creating StateProvider from repository."""

    @pytest.fixture
    def repo_with_data(self, tmp_path: Path) -> Any:
        """Create repository with test data."""
        from payment_simulator.experiments.persistence import (
            ExperimentRepository,
            ExperimentRecord,
            IterationRecord,
            EventRecord,
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

            # Add event for each iteration
            event = EventRecord(
                run_id="test-run",
                iteration=i,
                event_type="bootstrap_evaluation",
                event_data={"mean_cost": 1000 - i * 100},
                timestamp=f"2025-12-11T10:{i:02d}:30",
            )
            repository.save_event(event)

        yield repository
        repository.close()

    def test_as_state_provider_returns_protocol_impl(self, repo_with_data: Any) -> None:
        """as_state_provider should return ExperimentStateProviderProtocol."""
        from payment_simulator.experiments.runner import (
            ExperimentStateProviderProtocol,
        )

        provider = repo_with_data.as_state_provider("test-run")
        assert isinstance(provider, ExperimentStateProviderProtocol)

    def test_state_provider_get_total_iterations(self, repo_with_data: Any) -> None:
        """StateProvider should return correct iteration count."""
        provider = repo_with_data.as_state_provider("test-run")
        assert provider.get_total_iterations() == 3

    def test_state_provider_get_experiment_info(self, repo_with_data: Any) -> None:
        """StateProvider should return experiment info."""
        provider = repo_with_data.as_state_provider("test-run")
        info = provider.get_experiment_info()

        assert info["experiment_name"] == "test_experiment"
        assert info["experiment_type"] == "castro"
        assert info["converged"] is True

    def test_state_provider_get_iteration_costs(self, repo_with_data: Any) -> None:
        """StateProvider should return iteration costs."""
        provider = repo_with_data.as_state_provider("test-run")
        costs = provider.get_iteration_costs(0)

        assert costs["BANK_A"] == 1000
        assert costs["BANK_B"] == 1500
        assert isinstance(costs["BANK_A"], int)  # INV-1

    def test_state_provider_get_iteration_events(self, repo_with_data: Any) -> None:
        """StateProvider should return iteration events."""
        provider = repo_with_data.as_state_provider("test-run")
        events = provider.get_iteration_events(0)

        assert len(events) == 1
        assert events[0]["event_type"] == "bootstrap_evaluation"

    def test_state_provider_get_iteration_policies(self, repo_with_data: Any) -> None:
        """StateProvider should return iteration policies."""
        provider = repo_with_data.as_state_provider("test-run")
        policies = provider.get_iteration_policies(1)

        assert policies["BANK_A"]["iter"] == 1

    def test_state_provider_get_iteration_accepted_changes(
        self, repo_with_data: Any
    ) -> None:
        """StateProvider should return accepted changes."""
        provider = repo_with_data.as_state_provider("test-run")
        changes = provider.get_iteration_accepted_changes(1)

        assert changes["BANK_A"] is True
        assert changes["BANK_B"] is False


# =============================================================================
# Castro Backward Compatibility Tests
# =============================================================================


def _castro_available() -> bool:
    """Check if castro module is available."""
    try:
        import castro  # noqa: F401

        return True
    except ImportError:
        return False


class TestCastroMigration:
    """Tests for Castro migration to unified repository."""

    @pytest.mark.skipif(
        not _castro_available(),
        reason="Castro module not available in this environment",
    )
    def test_castro_can_use_core_repository(self) -> None:
        """Castro should be able to use ExperimentRepository."""
        from payment_simulator.experiments.persistence import ExperimentRepository

        assert ExperimentRepository is not None

    @pytest.mark.skipif(
        not _castro_available(),
        reason="Castro module not available in this environment",
    )
    def test_castro_persistence_still_works(self, tmp_path: Path) -> None:
        """Castro's existing persistence should remain functional."""
        from castro.persistence import ExperimentEventRepository

        # Castro's repository should still work
        import duckdb

        conn = duckdb.connect(str(tmp_path / "castro.db"))
        repo = ExperimentEventRepository(conn)
        repo.initialize_schema()
        conn.close()
