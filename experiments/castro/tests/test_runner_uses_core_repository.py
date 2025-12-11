"""TDD tests for Castro runner using core ExperimentRepository.

Phase 12, Task 12.2a: Migrate runner.py to use core persistence.

Write these tests FIRST, then update runner.py to make them pass.

All costs must be integer cents (INV-1 compliance).
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    pass


def _get_runner_source() -> str:
    """Get runner.py source without importing (avoids pydantic_ai dependency)."""
    runner_path = Path(__file__).parent.parent / "castro" / "runner.py"
    return runner_path.read_text()


class TestRunnerImportsFromCore:
    """Tests verifying runner.py imports from core, not castro.persistence."""

    def test_runner_imports_experiment_repository_from_core(self) -> None:
        """Runner should import ExperimentRepository from core."""
        source = _get_runner_source()

        # Should import from core
        assert "from payment_simulator.experiments.persistence import" in source
        assert "ExperimentRepository" in source

    def test_runner_imports_experiment_record_from_core(self) -> None:
        """Runner should import ExperimentRecord from core."""
        source = _get_runner_source()

        # Should import ExperimentRecord from core
        assert "ExperimentRecord" in source
        assert "from payment_simulator.experiments.persistence import" in source

    def test_runner_does_not_import_castro_persistence(self) -> None:
        """Runner should NOT import from castro.persistence."""
        source = _get_runner_source()

        # Should NOT import from castro.persistence
        assert "from castro.persistence import" not in source
        assert "from castro.persistence." not in source

    def test_runner_imports_event_record_from_core(self) -> None:
        """Runner should import EventRecord from core persistence."""
        source = _get_runner_source()

        # Should import EventRecord from core
        assert "EventRecord" in source


class TestRunnerUsesCorePersistence:
    """Tests verifying runner uses core persistence correctly."""

    def test_runner_saves_experiment_with_core_record(self, tmp_path: Path) -> None:
        """Runner should create ExperimentRecord from core."""
        from payment_simulator.experiments.persistence import (
            ExperimentRecord,
            ExperimentRepository,
        )

        # Create repository
        db_path = tmp_path / "test.db"
        repo = ExperimentRepository(db_path)

        # Create record like runner would
        record = ExperimentRecord(
            run_id="test-run-001",
            experiment_name="exp1",
            experiment_type="castro",
            config={"model": "anthropic:claude-sonnet-4-5", "master_seed": 42},
            created_at="2025-12-11T10:00:00",
            completed_at=None,
            num_iterations=0,
            converged=False,
            convergence_reason=None,
        )

        # Save
        repo.save_experiment(record)

        # Verify
        loaded = repo.load_experiment("test-run-001")
        assert loaded is not None
        assert loaded.experiment_name == "exp1"
        assert loaded.experiment_type == "castro"

        repo.close()

    def test_runner_saves_events_with_core_record(self, tmp_path: Path) -> None:
        """Runner should save events using core EventRecord."""
        from payment_simulator.experiments.persistence import (
            EventRecord,
            ExperimentRecord,
            ExperimentRepository,
        )

        # Create repository and experiment
        db_path = tmp_path / "test.db"
        repo = ExperimentRepository(db_path)

        exp_record = ExperimentRecord(
            run_id="test-run-001",
            experiment_name="exp1",
            experiment_type="castro",
            config={},
            created_at="2025-12-11T10:00:00",
            completed_at=None,
            num_iterations=0,
            converged=False,
            convergence_reason=None,
        )
        repo.save_experiment(exp_record)

        # Save event like runner would
        event = EventRecord(
            run_id="test-run-001",
            iteration=0,
            event_type="llm_interaction",
            event_data={
                "agent_id": "BANK_A",
                "model": "anthropic:claude-sonnet-4-5",
                "prompt_tokens": 1000,
                "completion_tokens": 500,
            },
            timestamp="2025-12-11T10:01:00",
        )
        repo.save_event(event)

        # Verify
        events = repo.get_events("test-run-001", iteration=0)
        assert len(events) == 1
        assert events[0].event_type == "llm_interaction"
        assert events[0].event_data["agent_id"] == "BANK_A"

        repo.close()

    def test_runner_updates_experiment_completion(self, tmp_path: Path) -> None:
        """Runner should update experiment on completion via save_experiment."""
        from payment_simulator.experiments.persistence import (
            ExperimentRecord,
            ExperimentRepository,
        )

        # Create repository
        db_path = tmp_path / "test.db"
        repo = ExperimentRepository(db_path)

        # Create initial record
        record = ExperimentRecord(
            run_id="test-run-001",
            experiment_name="exp1",
            experiment_type="castro",
            config={},
            created_at="2025-12-11T10:00:00",
            completed_at=None,
            num_iterations=0,
            converged=False,
            convergence_reason=None,
        )
        repo.save_experiment(record)

        # Update with completion (runner would do this)
        updated_record = ExperimentRecord(
            run_id="test-run-001",
            experiment_name="exp1",
            experiment_type="castro",
            config={},
            created_at="2025-12-11T10:00:00",
            completed_at="2025-12-11T10:30:00",
            num_iterations=10,
            converged=True,
            convergence_reason="stability_reached",
        )
        repo.save_experiment(updated_record)

        # Verify
        loaded = repo.load_experiment("test-run-001")
        assert loaded is not None
        assert loaded.completed_at == "2025-12-11T10:30:00"
        assert loaded.num_iterations == 10
        assert loaded.converged is True
        assert loaded.convergence_reason == "stability_reached"

        repo.close()


class TestRunnerNoLegacyPersistence:
    """Tests ensuring runner doesn't use legacy Castro persistence."""

    def test_no_experiment_run_record_in_runner(self) -> None:
        """Runner should NOT use ExperimentRunRecord (castro legacy)."""
        source = _get_runner_source()

        # Should NOT use castro's ExperimentRunRecord
        assert "ExperimentRunRecord" not in source

    def test_no_experiment_event_repository_in_runner(self) -> None:
        """Runner should NOT use ExperimentEventRepository (castro legacy)."""
        source = _get_runner_source()

        # Should NOT use castro's ExperimentEventRepository
        assert "ExperimentEventRepository" not in source


class TestCostInvariant:
    """Tests for INV-1: All costs must be integer cents."""

    def test_event_costs_are_integer_cents(self, tmp_path: Path) -> None:
        """Event cost data must be stored as integer cents."""
        from payment_simulator.experiments.persistence import (
            EventRecord,
            ExperimentRecord,
            ExperimentRepository,
        )

        # Create repository
        db_path = tmp_path / "test.db"
        repo = ExperimentRepository(db_path)

        exp_record = ExperimentRecord(
            run_id="test-run-001",
            experiment_name="exp1",
            experiment_type="castro",
            config={},
            created_at="2025-12-11T10:00:00",
            completed_at=None,
            num_iterations=0,
            converged=False,
            convergence_reason=None,
        )
        repo.save_experiment(exp_record)

        # Save event with integer costs (INV-1)
        event = EventRecord(
            run_id="test-run-001",
            iteration=0,
            event_type="policy_change",
            event_data={
                "agent_id": "BANK_A",
                "old_cost": 150000,  # Integer cents: $1,500.00
                "new_cost": 120000,  # Integer cents: $1,200.00
            },
            timestamp="2025-12-11T10:01:00",
        )
        repo.save_event(event)

        # Verify costs are integers
        events = repo.get_events("test-run-001", iteration=0)
        assert len(events) == 1
        assert isinstance(events[0].event_data["old_cost"], int)
        assert isinstance(events[0].event_data["new_cost"], int)
        assert events[0].event_data["old_cost"] == 150000
        assert events[0].event_data["new_cost"] == 120000

        repo.close()


class TestIterationRecordUsage:
    """Tests for iteration data persistence."""

    def test_runner_can_save_iteration_data(self, tmp_path: Path) -> None:
        """Runner should save iteration data via core IterationRecord."""
        from payment_simulator.experiments.persistence import (
            ExperimentRecord,
            ExperimentRepository,
            IterationRecord,
        )

        # Create repository
        db_path = tmp_path / "test.db"
        repo = ExperimentRepository(db_path)

        exp_record = ExperimentRecord(
            run_id="test-run-001",
            experiment_name="exp1",
            experiment_type="castro",
            config={},
            created_at="2025-12-11T10:00:00",
            completed_at=None,
            num_iterations=0,
            converged=False,
            convergence_reason=None,
        )
        repo.save_experiment(exp_record)

        # Save iteration data
        iter_record = IterationRecord(
            run_id="test-run-001",
            iteration=0,
            costs_per_agent={
                "BANK_A": 150000,  # Integer cents
                "BANK_B": 175000,  # Integer cents
            },
            accepted_changes={"BANK_A": True, "BANK_B": False},
            policies={"BANK_A": {"type": "release"}, "BANK_B": {"type": "hold"}},
            timestamp="2025-12-11T10:01:00",
        )
        repo.save_iteration(iter_record)

        # Verify
        iterations = repo.get_iterations("test-run-001")
        assert len(iterations) == 1
        assert iterations[0].iteration == 0
        assert iterations[0].costs_per_agent["BANK_A"] == 150000
        assert isinstance(iterations[0].costs_per_agent["BANK_A"], int)

        repo.close()
