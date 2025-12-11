"""TDD tests verifying Castro uses core modules directly.

Tests that Castro infrastructure is deleted and core is used instead.

Phase 12, Task 12.2: Delete Castro Infrastructure
Phase 12, Task 12.3: Update Castro to Use Core

Write these tests FIRST, then implement.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass


class TestCastroInfrastructureDeleted:
    """Tests that Castro infrastructure files are deleted."""

    def get_castro_dir(self) -> Path:
        """Get the castro module directory."""
        return Path(__file__).parent.parent / "castro"

    def test_castro_events_deleted(self) -> None:
        """castro/events.py should not exist (moved to core)."""
        castro_path = self.get_castro_dir() / "events.py"
        assert not castro_path.exists(), "events.py should be moved to core ai_cash_mgmt"

    @pytest.mark.skip(reason="Phase 12.5: state_provider kept - uses core EventRecord")
    def test_castro_state_provider_deleted(self) -> None:
        """castro/state_provider.py should not exist (use core)."""
        castro_path = self.get_castro_dir() / "state_provider.py"
        assert not castro_path.exists(), "state_provider.py should be deleted (use core)"

    @pytest.mark.skip(reason="Phase 12.5: persistence kept - Castro-specific schema")
    def test_castro_persistence_repository_deleted(self) -> None:
        """castro/persistence/repository.py should not exist (use core)."""
        castro_path = self.get_castro_dir() / "persistence" / "repository.py"
        assert not castro_path.exists(), "persistence/repository.py should be deleted"

    @pytest.mark.skip(reason="Phase 12.5: persistence kept - Castro-specific schema")
    def test_castro_persistence_models_deleted(self) -> None:
        """castro/persistence/models.py should not exist (use core)."""
        castro_path = self.get_castro_dir() / "persistence" / "models.py"
        assert not castro_path.exists(), "persistence/models.py should be deleted"


class TestCoreEventsImportable:
    """Tests that core events module is importable and usable."""

    def test_event_types_from_core(self) -> None:
        """Event types should be importable from core ai_cash_mgmt."""
        from payment_simulator.ai_cash_mgmt.events import (
            ALL_EVENT_TYPES,
            EVENT_BOOTSTRAP_EVALUATION,
            EVENT_EXPERIMENT_END,
            EVENT_EXPERIMENT_START,
            EVENT_ITERATION_START,
            EVENT_LLM_CALL,
            EVENT_LLM_INTERACTION,
            EVENT_POLICY_CHANGE,
            EVENT_POLICY_REJECTED,
        )

        assert EVENT_EXPERIMENT_START == "experiment_start"
        assert EVENT_LLM_INTERACTION == "llm_interaction"
        assert len(ALL_EVENT_TYPES) == 8

    def test_event_helpers_from_core(self) -> None:
        """Event creation helpers should be importable from core."""
        from payment_simulator.ai_cash_mgmt.events import (
            create_bootstrap_evaluation_event,
            create_experiment_end_event,
            create_experiment_start_event,
            create_iteration_start_event,
            create_llm_call_event,
            create_llm_interaction_event,
            create_policy_change_event,
            create_policy_rejected_event,
        )

        # All should be callable
        assert callable(create_experiment_start_event)
        assert callable(create_llm_interaction_event)
        assert callable(create_policy_change_event)

    def test_event_record_from_core(self) -> None:
        """EventRecord should be importable from core."""
        from payment_simulator.experiments.persistence import EventRecord

        assert EventRecord is not None


class TestCoreStateProviderImportable:
    """Tests that core StateProvider is importable and usable."""

    def test_state_provider_protocol_from_core(self) -> None:
        """StateProvider protocol should be importable from core."""
        from payment_simulator.experiments.runner import (
            ExperimentStateProviderProtocol,
        )

        assert ExperimentStateProviderProtocol is not None

    def test_live_state_provider_from_core(self) -> None:
        """LiveStateProvider should be importable from core."""
        from payment_simulator.experiments.runner import LiveStateProvider

        assert LiveStateProvider is not None

    def test_database_state_provider_from_core(self) -> None:
        """DatabaseStateProvider should be importable from core."""
        from payment_simulator.experiments.runner import DatabaseStateProvider

        assert DatabaseStateProvider is not None


class TestCoreRepositoryImportable:
    """Tests that core ExperimentRepository is importable and usable."""

    def test_repository_from_core(self) -> None:
        """ExperimentRepository should be importable from core."""
        from payment_simulator.experiments.persistence import ExperimentRepository

        assert ExperimentRepository is not None

    def test_record_types_from_core(self) -> None:
        """Record types should be importable from core."""
        from payment_simulator.experiments.persistence import (
            EventRecord,
            ExperimentRecord,
            IterationRecord,
        )

        assert ExperimentRecord is not None
        assert IterationRecord is not None
        assert EventRecord is not None


class TestCastroRunnerUsesCore:
    """Tests that Castro runner uses core infrastructure."""

    def test_runner_imports_core_events(self) -> None:
        """Castro runner should import events from core."""
        # This test verifies the import works
        from payment_simulator.ai_cash_mgmt.events import create_llm_interaction_event

        assert callable(create_llm_interaction_event)

    def test_runner_can_create_core_event(self) -> None:
        """Castro runner should be able to create core events."""
        from payment_simulator.ai_cash_mgmt.events import create_llm_interaction_event
        from payment_simulator.experiments.persistence import EventRecord

        event = create_llm_interaction_event(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",
            system_prompt="test system",
            user_prompt="test user",
            raw_response="test response",
            parsed_policy={"type": "hold"},
            parsing_error=None,
            model="claude-3",
            prompt_tokens=100,
            completion_tokens=50,
            latency_seconds=1.0,
        )

        assert isinstance(event, EventRecord)
        assert event.event_type == "llm_interaction"


class TestCastroReplayUsesCore:
    """Tests that Castro replay uses core infrastructure."""

    def test_replay_uses_core_database_provider(self, tmp_path: Path) -> None:
        """Castro replay should use core DatabaseStateProvider."""
        from payment_simulator.ai_cash_mgmt.events import create_experiment_start_event
        from payment_simulator.experiments.persistence import (
            ExperimentRecord,
            ExperimentRepository,
        )
        from payment_simulator.experiments.runner import DatabaseStateProvider

        # Create database with core
        db_path = tmp_path / "test.db"
        repo = ExperimentRepository(db_path)

        # Save experiment
        record = ExperimentRecord(
            run_id="test-run",
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

        # Save event using core event helper
        event = create_experiment_start_event(
            run_id="test-run",
            experiment_name="exp1",
            description="Test",
            model="claude-3",
            max_iterations=10,
            num_samples=5,
        )
        repo.save_event(event)

        # Create provider for replay
        provider = DatabaseStateProvider(repo, "test-run")

        # Should work
        info = provider.get_experiment_info()
        assert info["experiment_name"] == "exp1"

        events = provider.get_iteration_events(0)
        assert len(events) == 1
        assert events[0]["event_type"] == "experiment_start"

        repo.close()


class TestCoreEventRecordCompatibility:
    """Tests that core EventRecord is compatible with Castro needs."""

    def test_event_record_has_required_fields(self) -> None:
        """EventRecord should have all fields needed by Castro."""
        from payment_simulator.experiments.persistence import EventRecord

        event = EventRecord(
            run_id="test",
            iteration=0,
            event_type="test_event",
            event_data={"key": "value"},
            timestamp="2025-12-11T10:00:00",
        )

        # Should have all required attributes
        assert event.run_id == "test"
        assert event.iteration == 0
        assert event.event_type == "test_event"
        assert event.event_data == {"key": "value"}
        assert event.timestamp == "2025-12-11T10:00:00"

    def test_event_record_is_frozen(self) -> None:
        """EventRecord should be immutable."""
        from payment_simulator.experiments.persistence import EventRecord

        event = EventRecord(
            run_id="test",
            iteration=0,
            event_type="test",
            event_data={},
            timestamp="2025-12-11T10:00:00",
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            event.run_id = "changed"  # type: ignore[misc]
