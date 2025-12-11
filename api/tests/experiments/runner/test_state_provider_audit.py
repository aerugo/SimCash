"""TDD tests for audit methods in ExperimentStateProviderProtocol.

Phase 13, Task 13.1: Extend core protocol with audit methods.

Write these tests FIRST, then implement to make them pass.

All costs must be integer cents (INV-1 compliance).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator

import pytest

if TYPE_CHECKING:
    pass


class TestProtocolHasAuditMethods:
    """Tests verifying protocol includes audit methods."""

    def test_protocol_has_run_id_property(self) -> None:
        """Protocol should include run_id property."""
        from payment_simulator.experiments.runner.state_provider import (
            ExperimentStateProviderProtocol,
        )

        # Check that run_id is defined in protocol annotations
        assert hasattr(ExperimentStateProviderProtocol, "run_id")

    def test_protocol_has_get_run_metadata(self) -> None:
        """Protocol should include get_run_metadata method."""
        from payment_simulator.experiments.runner.state_provider import (
            ExperimentStateProviderProtocol,
        )

        assert hasattr(ExperimentStateProviderProtocol, "get_run_metadata")

    def test_protocol_has_get_all_events(self) -> None:
        """Protocol should include get_all_events method."""
        from payment_simulator.experiments.runner.state_provider import (
            ExperimentStateProviderProtocol,
        )

        assert hasattr(ExperimentStateProviderProtocol, "get_all_events")

    def test_protocol_has_get_final_result(self) -> None:
        """Protocol should include get_final_result method."""
        from payment_simulator.experiments.runner.state_provider import (
            ExperimentStateProviderProtocol,
        )

        assert hasattr(ExperimentStateProviderProtocol, "get_final_result")


class TestLiveStateProviderAuditMethods:
    """Tests for LiveStateProvider audit method implementations."""

    def test_run_id_returns_identifier(self) -> None:
        """run_id property should return the run identifier."""
        from payment_simulator.experiments.runner.state_provider import (
            LiveStateProvider,
        )

        provider = LiveStateProvider(
            experiment_name="exp1",
            experiment_type="castro",
            config={"master_seed": 42},
            run_id="exp1-20251211-100000-abc123",
        )

        assert provider.run_id == "exp1-20251211-100000-abc123"

    def test_run_id_returns_none_when_not_set(self) -> None:
        """run_id should return None if not provided."""
        from payment_simulator.experiments.runner.state_provider import (
            LiveStateProvider,
        )

        provider = LiveStateProvider(
            experiment_name="exp1",
            experiment_type="castro",
            config={},
        )

        assert provider.run_id is None

    def test_get_run_metadata_returns_dict(self) -> None:
        """get_run_metadata should return experiment metadata dict."""
        from payment_simulator.experiments.runner.state_provider import (
            LiveStateProvider,
        )

        provider = LiveStateProvider(
            experiment_name="exp1",
            experiment_type="castro",
            config={"model": "anthropic:claude-sonnet-4-5"},
            run_id="exp1-123",
        )

        metadata = provider.get_run_metadata()

        assert metadata is not None
        assert metadata["experiment_name"] == "exp1"
        assert metadata["experiment_type"] == "castro"
        assert metadata["run_id"] == "exp1-123"
        assert "config" in metadata

    def test_get_all_events_returns_iterator(self) -> None:
        """get_all_events should return an iterator over all events."""
        from payment_simulator.experiments.runner.state_provider import (
            LiveStateProvider,
        )

        provider = LiveStateProvider(
            experiment_name="exp1",
            experiment_type="castro",
            config={},
            run_id="exp1-123",
        )

        # Record events across iterations
        provider.record_event(0, "llm_interaction", {"agent_id": "BANK_A"})
        provider.record_event(0, "policy_change", {"agent_id": "BANK_A"})
        provider.record_event(1, "llm_interaction", {"agent_id": "BANK_B"})

        events = list(provider.get_all_events())

        assert len(events) == 3
        assert events[0]["event_type"] == "llm_interaction"
        assert events[0]["agent_id"] == "BANK_A"
        assert events[1]["event_type"] == "policy_change"
        assert events[2]["agent_id"] == "BANK_B"

    def test_get_all_events_empty_when_no_events(self) -> None:
        """get_all_events should return empty iterator when no events."""
        from payment_simulator.experiments.runner.state_provider import (
            LiveStateProvider,
        )

        provider = LiveStateProvider(
            experiment_name="exp1",
            experiment_type="castro",
            config={},
        )

        events = list(provider.get_all_events())
        assert len(events) == 0

    def test_get_final_result_before_set(self) -> None:
        """get_final_result should return None before set_final_result called."""
        from payment_simulator.experiments.runner.state_provider import (
            LiveStateProvider,
        )

        provider = LiveStateProvider(
            experiment_name="exp1",
            experiment_type="castro",
            config={},
        )

        result = provider.get_final_result()
        assert result is None

    def test_get_final_result_after_set(self) -> None:
        """get_final_result should return result dict after set_final_result."""
        from payment_simulator.experiments.runner.state_provider import (
            LiveStateProvider,
        )

        provider = LiveStateProvider(
            experiment_name="exp1",
            experiment_type="castro",
            config={},
        )

        provider.set_final_result(
            final_cost=15000,  # Integer cents
            best_cost=14000,  # Integer cents
            converged=True,
            convergence_reason="stability",
        )

        result = provider.get_final_result()

        assert result is not None
        assert result["final_cost"] == 15000
        assert result["best_cost"] == 14000
        assert result["converged"] is True
        assert result["convergence_reason"] == "stability"

    def test_final_result_costs_are_integer_cents(self) -> None:
        """Final result costs must be integer cents (INV-1)."""
        from payment_simulator.experiments.runner.state_provider import (
            LiveStateProvider,
        )

        provider = LiveStateProvider(
            experiment_name="exp1",
            experiment_type="castro",
            config={},
        )

        provider.set_final_result(
            final_cost=150000,  # $1,500.00 in cents
            best_cost=140000,  # $1,400.00 in cents
            converged=True,
            convergence_reason="stability",
        )

        result = provider.get_final_result()

        assert isinstance(result["final_cost"], int)
        assert isinstance(result["best_cost"], int)


class TestDatabaseStateProviderAuditMethods:
    """Tests for DatabaseStateProvider audit method implementations."""

    def test_run_id_returns_identifier(self, tmp_path: Path) -> None:
        """run_id property should return the run identifier."""
        from payment_simulator.experiments.persistence import (
            ExperimentRecord,
            ExperimentRepository,
        )
        from payment_simulator.experiments.runner.state_provider import (
            DatabaseStateProvider,
        )

        # Create database with experiment
        db_path = tmp_path / "test.db"
        repo = ExperimentRepository(db_path)

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

        provider = DatabaseStateProvider(repo, "test-run-001")

        assert provider.run_id == "test-run-001"

        repo.close()

    def test_get_run_metadata_from_database(self, tmp_path: Path) -> None:
        """get_run_metadata should return metadata from database."""
        from payment_simulator.experiments.persistence import (
            ExperimentRecord,
            ExperimentRepository,
        )
        from payment_simulator.experiments.runner.state_provider import (
            DatabaseStateProvider,
        )

        db_path = tmp_path / "test.db"
        repo = ExperimentRepository(db_path)

        record = ExperimentRecord(
            run_id="test-run-001",
            experiment_name="exp1",
            experiment_type="castro",
            config={"model": "anthropic:claude-sonnet-4-5"},
            created_at="2025-12-11T10:00:00",
            completed_at="2025-12-11T10:30:00",
            num_iterations=10,
            converged=True,
            convergence_reason="stability",
        )
        repo.save_experiment(record)

        provider = DatabaseStateProvider(repo, "test-run-001")
        metadata = provider.get_run_metadata()

        assert metadata is not None
        assert metadata["experiment_name"] == "exp1"
        assert metadata["experiment_type"] == "castro"
        assert metadata["run_id"] == "test-run-001"
        assert metadata["config"]["model"] == "anthropic:claude-sonnet-4-5"

        repo.close()

    def test_get_all_events_from_database(self, tmp_path: Path) -> None:
        """get_all_events should return iterator over all events from database."""
        from payment_simulator.experiments.persistence import (
            EventRecord,
            ExperimentRecord,
            ExperimentRepository,
        )
        from payment_simulator.experiments.runner.state_provider import (
            DatabaseStateProvider,
        )

        db_path = tmp_path / "test.db"
        repo = ExperimentRepository(db_path)

        # Save experiment
        exp_record = ExperimentRecord(
            run_id="test-run-001",
            experiment_name="exp1",
            experiment_type="castro",
            config={},
            created_at="2025-12-11T10:00:00",
            completed_at=None,
            num_iterations=2,
            converged=False,
            convergence_reason=None,
        )
        repo.save_experiment(exp_record)

        # Save events across iterations
        events_to_save = [
            EventRecord(
                run_id="test-run-001",
                iteration=0,
                event_type="llm_interaction",
                event_data={"agent_id": "BANK_A"},
                timestamp="2025-12-11T10:01:00",
            ),
            EventRecord(
                run_id="test-run-001",
                iteration=0,
                event_type="policy_change",
                event_data={"agent_id": "BANK_A"},
                timestamp="2025-12-11T10:02:00",
            ),
            EventRecord(
                run_id="test-run-001",
                iteration=1,
                event_type="llm_interaction",
                event_data={"agent_id": "BANK_B"},
                timestamp="2025-12-11T10:03:00",
            ),
        ]
        for event in events_to_save:
            repo.save_event(event)

        provider = DatabaseStateProvider(repo, "test-run-001")
        events = list(provider.get_all_events())

        assert len(events) == 3
        assert events[0]["event_type"] == "llm_interaction"
        assert events[0]["agent_id"] == "BANK_A"
        assert events[1]["event_type"] == "policy_change"
        assert events[2]["agent_id"] == "BANK_B"

        repo.close()

    def test_get_final_result_from_database(self, tmp_path: Path) -> None:
        """get_final_result should return final result from database config."""
        from payment_simulator.experiments.persistence import (
            ExperimentRecord,
            ExperimentRepository,
        )
        from payment_simulator.experiments.runner.state_provider import (
            DatabaseStateProvider,
        )

        db_path = tmp_path / "test.db"
        repo = ExperimentRepository(db_path)

        # Save completed experiment with final result in config
        record = ExperimentRecord(
            run_id="test-run-001",
            experiment_name="exp1",
            experiment_type="castro",
            config={
                "model": "anthropic:claude-sonnet-4-5",
                "final_cost": 150000,  # Integer cents
                "best_cost": 140000,  # Integer cents
            },
            created_at="2025-12-11T10:00:00",
            completed_at="2025-12-11T10:30:00",
            num_iterations=10,
            converged=True,
            convergence_reason="stability",
        )
        repo.save_experiment(record)

        provider = DatabaseStateProvider(repo, "test-run-001")
        result = provider.get_final_result()

        assert result is not None
        assert result["converged"] is True
        assert result["convergence_reason"] == "stability"
        assert result["final_cost"] == 150000
        assert result["best_cost"] == 140000

        repo.close()

    def test_final_result_costs_are_integer_cents(self, tmp_path: Path) -> None:
        """Final result costs from database must be integer cents (INV-1)."""
        from payment_simulator.experiments.persistence import (
            ExperimentRecord,
            ExperimentRepository,
        )
        from payment_simulator.experiments.runner.state_provider import (
            DatabaseStateProvider,
        )

        db_path = tmp_path / "test.db"
        repo = ExperimentRepository(db_path)

        record = ExperimentRecord(
            run_id="test-run-001",
            experiment_name="exp1",
            experiment_type="castro",
            config={
                "final_cost": 150000,  # $1,500.00 in cents
                "best_cost": 140000,  # $1,400.00 in cents
            },
            created_at="2025-12-11T10:00:00",
            completed_at="2025-12-11T10:30:00",
            num_iterations=10,
            converged=True,
            convergence_reason="stability",
        )
        repo.save_experiment(record)

        provider = DatabaseStateProvider(repo, "test-run-001")
        result = provider.get_final_result()

        assert isinstance(result["final_cost"], int)
        assert isinstance(result["best_cost"], int)

        repo.close()

    def test_get_final_result_returns_none_for_incomplete(
        self, tmp_path: Path
    ) -> None:
        """get_final_result should return None for incomplete experiments."""
        from payment_simulator.experiments.persistence import (
            ExperimentRecord,
            ExperimentRepository,
        )
        from payment_simulator.experiments.runner.state_provider import (
            DatabaseStateProvider,
        )

        db_path = tmp_path / "test.db"
        repo = ExperimentRepository(db_path)

        # Save incomplete experiment (no completed_at, no final_cost)
        record = ExperimentRecord(
            run_id="test-run-001",
            experiment_name="exp1",
            experiment_type="castro",
            config={},
            created_at="2025-12-11T10:00:00",
            completed_at=None,  # Not completed
            num_iterations=5,
            converged=False,
            convergence_reason=None,
        )
        repo.save_experiment(record)

        provider = DatabaseStateProvider(repo, "test-run-001")
        result = provider.get_final_result()

        assert result is None

        repo.close()


class TestStateProviderProtocolCompliance:
    """Tests verifying implementations satisfy the protocol."""

    def test_live_provider_is_protocol_compliant(self) -> None:
        """LiveStateProvider should satisfy ExperimentStateProviderProtocol."""
        from payment_simulator.experiments.runner.state_provider import (
            ExperimentStateProviderProtocol,
            LiveStateProvider,
        )

        provider = LiveStateProvider(
            experiment_name="exp1",
            experiment_type="castro",
            config={},
        )

        # Protocol is @runtime_checkable, so isinstance should work
        assert isinstance(provider, ExperimentStateProviderProtocol)

    def test_database_provider_is_protocol_compliant(self, tmp_path: Path) -> None:
        """DatabaseStateProvider should satisfy ExperimentStateProviderProtocol."""
        from payment_simulator.experiments.persistence import (
            ExperimentRecord,
            ExperimentRepository,
        )
        from payment_simulator.experiments.runner.state_provider import (
            DatabaseStateProvider,
            ExperimentStateProviderProtocol,
        )

        db_path = tmp_path / "test.db"
        repo = ExperimentRepository(db_path)

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

        provider = DatabaseStateProvider(repo, "test-run-001")

        assert isinstance(provider, ExperimentStateProviderProtocol)

        repo.close()
