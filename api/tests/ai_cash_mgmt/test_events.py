"""TDD tests for LLM optimization event system.

Tests for event types and creation helpers moved from Castro to core.

Phase 12, Task 12.1: Move Event System to Core

Write these tests FIRST, then implement.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest


class TestEventTypeConstants:
    """Tests for event type constants."""

    def test_event_types_importable(self) -> None:
        """Event type constants should be importable from ai_cash_mgmt."""
        from payment_simulator.ai_cash_mgmt.events import (
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
        assert EVENT_ITERATION_START == "iteration_start"
        assert EVENT_BOOTSTRAP_EVALUATION == "bootstrap_evaluation"
        assert EVENT_LLM_CALL == "llm_call"
        assert EVENT_LLM_INTERACTION == "llm_interaction"
        assert EVENT_POLICY_CHANGE == "policy_change"
        assert EVENT_POLICY_REJECTED == "policy_rejected"
        assert EVENT_EXPERIMENT_END == "experiment_end"

    def test_all_event_types_list(self) -> None:
        """ALL_EVENT_TYPES should contain all event types."""
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

        assert EVENT_EXPERIMENT_START in ALL_EVENT_TYPES
        assert EVENT_ITERATION_START in ALL_EVENT_TYPES
        assert EVENT_BOOTSTRAP_EVALUATION in ALL_EVENT_TYPES
        assert EVENT_LLM_CALL in ALL_EVENT_TYPES
        assert EVENT_LLM_INTERACTION in ALL_EVENT_TYPES
        assert EVENT_POLICY_CHANGE in ALL_EVENT_TYPES
        assert EVENT_POLICY_REJECTED in ALL_EVENT_TYPES
        assert EVENT_EXPERIMENT_END in ALL_EVENT_TYPES
        assert len(ALL_EVENT_TYPES) == 8


class TestEventCreationHelpers:
    """Tests for event creation helpers."""

    def test_create_experiment_start_event(self) -> None:
        """Should create experiment start event."""
        from payment_simulator.ai_cash_mgmt.events import (
            EVENT_EXPERIMENT_START,
            create_experiment_start_event,
        )
        from payment_simulator.experiments.persistence import EventRecord

        event = create_experiment_start_event(
            run_id="test-run",
            experiment_name="exp1",
            description="Test experiment",
            model="claude-3",
            max_iterations=10,
            num_samples=5,
        )

        assert isinstance(event, EventRecord)
        assert event.event_type == EVENT_EXPERIMENT_START
        assert event.run_id == "test-run"
        assert event.iteration == 0
        assert event.event_data["experiment_name"] == "exp1"
        assert event.event_data["description"] == "Test experiment"
        assert event.event_data["model"] == "claude-3"
        assert event.event_data["max_iterations"] == 10
        assert event.event_data["num_samples"] == 5

    def test_create_iteration_start_event(self) -> None:
        """Should create iteration start event."""
        from payment_simulator.ai_cash_mgmt.events import (
            EVENT_ITERATION_START,
            create_iteration_start_event,
        )
        from payment_simulator.experiments.persistence import EventRecord

        event = create_iteration_start_event(
            run_id="test-run",
            iteration=5,
            total_cost=100000,  # Integer cents (INV-1)
        )

        assert isinstance(event, EventRecord)
        assert event.event_type == EVENT_ITERATION_START
        assert event.run_id == "test-run"
        assert event.iteration == 5
        assert event.event_data["total_cost"] == 100000

    def test_create_bootstrap_evaluation_event(self) -> None:
        """Should create bootstrap evaluation event."""
        from payment_simulator.ai_cash_mgmt.events import (
            EVENT_BOOTSTRAP_EVALUATION,
            create_bootstrap_evaluation_event,
        )
        from payment_simulator.experiments.persistence import EventRecord

        seed_results = [
            {"seed": 1, "cost": 1000, "settled": 95, "total": 100},
            {"seed": 2, "cost": 1100, "settled": 94, "total": 100},
        ]

        event = create_bootstrap_evaluation_event(
            run_id="test-run",
            iteration=0,
            seed_results=seed_results,
            mean_cost=1050,  # Integer cents
            std_cost=50,  # Integer cents
        )

        assert isinstance(event, EventRecord)
        assert event.event_type == EVENT_BOOTSTRAP_EVALUATION
        assert event.run_id == "test-run"
        assert event.iteration == 0
        assert event.event_data["mean_cost"] == 1050
        assert event.event_data["std_cost"] == 50
        assert len(event.event_data["seed_results"]) == 2

    def test_create_llm_call_event(self) -> None:
        """Should create LLM call event."""
        from payment_simulator.ai_cash_mgmt.events import (
            EVENT_LLM_CALL,
            create_llm_call_event,
        )
        from payment_simulator.experiments.persistence import EventRecord

        event = create_llm_call_event(
            run_id="test-run",
            iteration=1,
            agent_id="BANK_A",
            model="claude-3",
            prompt_tokens=100,
            completion_tokens=50,
            latency_seconds=1.5,
            context_summary={"best_seed": 42, "worst_seed": 13},
        )

        assert isinstance(event, EventRecord)
        assert event.event_type == EVENT_LLM_CALL
        assert event.event_data["agent_id"] == "BANK_A"
        assert event.event_data["model"] == "claude-3"
        assert event.event_data["prompt_tokens"] == 100
        assert event.event_data["completion_tokens"] == 50
        assert event.event_data["latency_seconds"] == 1.5
        assert event.event_data["context_summary"]["best_seed"] == 42

    def test_create_llm_call_event_default_context(self) -> None:
        """LLM call event should default to empty context_summary."""
        from payment_simulator.ai_cash_mgmt.events import create_llm_call_event

        event = create_llm_call_event(
            run_id="test-run",
            iteration=1,
            agent_id="BANK_A",
            model="claude-3",
            prompt_tokens=100,
            completion_tokens=50,
            latency_seconds=1.5,
        )

        assert event.event_data["context_summary"] == {}

    def test_create_llm_interaction_event(self) -> None:
        """Should create LLM interaction event with full audit data."""
        from payment_simulator.ai_cash_mgmt.events import (
            EVENT_LLM_INTERACTION,
            create_llm_interaction_event,
        )
        from payment_simulator.experiments.persistence import EventRecord

        event = create_llm_interaction_event(
            run_id="test-run",
            iteration=1,
            agent_id="BANK_A",
            system_prompt="You are a policy optimizer...",
            user_prompt="Current cost is 1000. Suggest improvement.",
            raw_response='```json\n{"type": "release"}\n```',
            parsed_policy={"type": "release"},
            parsing_error=None,
            model="claude-3",
            prompt_tokens=100,
            completion_tokens=50,
            latency_seconds=1.5,
        )

        assert isinstance(event, EventRecord)
        assert event.event_type == EVENT_LLM_INTERACTION
        assert event.event_data["agent_id"] == "BANK_A"
        assert event.event_data["system_prompt"] == "You are a policy optimizer..."
        assert event.event_data["user_prompt"] == "Current cost is 1000. Suggest improvement."
        assert event.event_data["raw_response"] == '```json\n{"type": "release"}\n```'
        assert event.event_data["parsed_policy"] == {"type": "release"}
        assert event.event_data["parsing_error"] is None
        assert event.event_data["model"] == "claude-3"
        assert event.event_data["prompt_tokens"] == 100
        assert event.event_data["completion_tokens"] == 50
        assert event.event_data["latency_seconds"] == 1.5

    def test_create_llm_interaction_event_with_error(self) -> None:
        """Should create LLM interaction event with parsing error."""
        from payment_simulator.ai_cash_mgmt.events import create_llm_interaction_event

        event = create_llm_interaction_event(
            run_id="test-run",
            iteration=1,
            agent_id="BANK_A",
            system_prompt="...",
            user_prompt="...",
            raw_response="invalid json",
            parsed_policy=None,
            parsing_error="JSON decode error",
            model="claude-3",
            prompt_tokens=100,
            completion_tokens=50,
            latency_seconds=1.5,
        )

        assert event.event_data["parsed_policy"] is None
        assert event.event_data["parsing_error"] == "JSON decode error"

    def test_create_policy_change_event(self) -> None:
        """Should create policy change event."""
        from payment_simulator.ai_cash_mgmt.events import (
            EVENT_POLICY_CHANGE,
            create_policy_change_event,
        )
        from payment_simulator.experiments.persistence import EventRecord

        event = create_policy_change_event(
            run_id="test-run",
            iteration=1,
            agent_id="BANK_A",
            old_policy={"type": "hold"},
            new_policy={"type": "release"},
            old_cost=1000,  # Integer cents
            new_cost=800,  # Integer cents
            accepted=True,
        )

        assert isinstance(event, EventRecord)
        assert event.event_type == EVENT_POLICY_CHANGE
        assert event.event_data["agent_id"] == "BANK_A"
        assert event.event_data["old_policy"] == {"type": "hold"}
        assert event.event_data["new_policy"] == {"type": "release"}
        assert event.event_data["old_cost"] == 1000
        assert event.event_data["new_cost"] == 800
        assert event.event_data["accepted"] is True

    def test_create_policy_rejected_event(self) -> None:
        """Should create policy rejected event."""
        from payment_simulator.ai_cash_mgmt.events import (
            EVENT_POLICY_REJECTED,
            create_policy_rejected_event,
        )
        from payment_simulator.experiments.persistence import EventRecord

        event = create_policy_rejected_event(
            run_id="test-run",
            iteration=1,
            agent_id="BANK_A",
            proposed_policy={"type": "invalid"},
            validation_errors=["Unknown policy type"],
            rejection_reason="validation_failed",
        )

        assert isinstance(event, EventRecord)
        assert event.event_type == EVENT_POLICY_REJECTED
        assert event.event_data["agent_id"] == "BANK_A"
        assert event.event_data["proposed_policy"] == {"type": "invalid"}
        assert "Unknown policy type" in event.event_data["validation_errors"]
        assert event.event_data["rejection_reason"] == "validation_failed"

    def test_create_policy_rejected_event_with_costs(self) -> None:
        """Should create policy rejected event with cost data."""
        from payment_simulator.ai_cash_mgmt.events import create_policy_rejected_event

        event = create_policy_rejected_event(
            run_id="test-run",
            iteration=1,
            agent_id="BANK_A",
            proposed_policy={"type": "release"},
            validation_errors=[],
            rejection_reason="cost_not_improved",
            old_cost=1000,
            new_cost=1100,
        )

        assert event.event_data["old_cost"] == 1000
        assert event.event_data["new_cost"] == 1100

    def test_create_experiment_end_event(self) -> None:
        """Should create experiment end event."""
        from payment_simulator.ai_cash_mgmt.events import (
            EVENT_EXPERIMENT_END,
            create_experiment_end_event,
        )
        from payment_simulator.experiments.persistence import EventRecord

        event = create_experiment_end_event(
            run_id="test-run",
            iteration=10,
            final_cost=800,  # Integer cents
            best_cost=750,  # Integer cents
            converged=True,
            convergence_reason="stability",
            duration_seconds=120.5,
        )

        assert isinstance(event, EventRecord)
        assert event.event_type == EVENT_EXPERIMENT_END
        assert event.event_data["final_cost"] == 800
        assert event.event_data["best_cost"] == 750
        assert event.event_data["converged"] is True
        assert event.event_data["convergence_reason"] == "stability"
        assert event.event_data["duration_seconds"] == 120.5


class TestCostsAreIntegerCents:
    """Tests ensuring all costs are integer cents (INV-1)."""

    def test_iteration_start_cost_is_integer(self) -> None:
        """Iteration start total_cost must be integer cents."""
        from payment_simulator.ai_cash_mgmt.events import create_iteration_start_event

        event = create_iteration_start_event(
            run_id="test",
            iteration=0,
            total_cost=100050,  # $1,000.50 in cents
        )

        assert isinstance(event.event_data["total_cost"], int)

    def test_bootstrap_costs_are_integers(self) -> None:
        """Bootstrap mean_cost and std_cost must be integer cents."""
        from payment_simulator.ai_cash_mgmt.events import create_bootstrap_evaluation_event

        event = create_bootstrap_evaluation_event(
            run_id="test",
            iteration=0,
            seed_results=[],
            mean_cost=100050,
            std_cost=5025,
        )

        assert isinstance(event.event_data["mean_cost"], int)
        assert isinstance(event.event_data["std_cost"], int)

    def test_policy_change_costs_are_integers(self) -> None:
        """Policy change old_cost and new_cost must be integer cents."""
        from payment_simulator.ai_cash_mgmt.events import create_policy_change_event

        event = create_policy_change_event(
            run_id="test",
            iteration=0,
            agent_id="BANK_A",
            old_policy={},
            new_policy={},
            old_cost=100050,
            new_cost=90025,
            accepted=True,
        )

        assert isinstance(event.event_data["old_cost"], int)
        assert isinstance(event.event_data["new_cost"], int)

    def test_experiment_end_costs_are_integers(self) -> None:
        """Experiment end final_cost and best_cost must be integer cents."""
        from payment_simulator.ai_cash_mgmt.events import create_experiment_end_event

        event = create_experiment_end_event(
            run_id="test",
            iteration=10,
            final_cost=80000,
            best_cost=75000,
            converged=True,
            convergence_reason="stability",
            duration_seconds=120.0,
        )

        assert isinstance(event.event_data["final_cost"], int)
        assert isinstance(event.event_data["best_cost"], int)


class TestEventTimestamps:
    """Tests for event timestamps."""

    def test_events_have_iso_timestamp(self) -> None:
        """All events should have ISO format timestamp."""
        from payment_simulator.ai_cash_mgmt.events import create_experiment_start_event

        event = create_experiment_start_event(
            run_id="test",
            experiment_name="exp1",
            description="Test",
            model="claude-3",
            max_iterations=10,
            num_samples=5,
        )

        # Should be ISO format string
        assert isinstance(event.timestamp, str)
        # Should be parseable
        parsed = datetime.fromisoformat(event.timestamp)
        assert parsed is not None

    def test_iteration_event_has_iso_timestamp(self) -> None:
        """Iteration event should have ISO format timestamp."""
        from payment_simulator.ai_cash_mgmt.events import create_iteration_start_event

        event = create_iteration_start_event(
            run_id="test",
            iteration=0,
            total_cost=1000,
        )

        assert isinstance(event.timestamp, str)
        parsed = datetime.fromisoformat(event.timestamp)
        assert parsed is not None

    def test_llm_interaction_event_has_iso_timestamp(self) -> None:
        """LLM interaction event should have ISO format timestamp."""
        from payment_simulator.ai_cash_mgmt.events import create_llm_interaction_event

        event = create_llm_interaction_event(
            run_id="test",
            iteration=0,
            agent_id="BANK_A",
            system_prompt="...",
            user_prompt="...",
            raw_response="...",
            parsed_policy=None,
            parsing_error=None,
            model="claude-3",
            prompt_tokens=100,
            completion_tokens=50,
            latency_seconds=1.0,
        )

        assert isinstance(event.timestamp, str)
        parsed = datetime.fromisoformat(event.timestamp)
        assert parsed is not None


class TestEventRecordImmutability:
    """Tests ensuring EventRecord is immutable (frozen dataclass)."""

    def test_event_record_is_frozen(self) -> None:
        """EventRecord should be a frozen dataclass."""
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

    def test_created_event_is_frozen(self) -> None:
        """Events created by helpers should be frozen."""
        from payment_simulator.ai_cash_mgmt.events import create_experiment_start_event

        event = create_experiment_start_event(
            run_id="test",
            experiment_name="exp1",
            description="Test",
            model="claude-3",
            max_iterations=10,
            num_samples=5,
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            event.run_id = "changed"  # type: ignore[misc]


class TestModuleExports:
    """Tests for module exports."""

    def test_events_importable_from_ai_cash_mgmt(self) -> None:
        """Event helpers should be importable from ai_cash_mgmt package."""
        from payment_simulator.ai_cash_mgmt import (
            ALL_EVENT_TYPES,
            EVENT_EXPERIMENT_START,
            EVENT_LLM_INTERACTION,
            EVENT_POLICY_CHANGE,
            create_experiment_start_event,
            create_llm_interaction_event,
            create_policy_change_event,
        )

        assert EVENT_EXPERIMENT_START == "experiment_start"
        assert callable(create_experiment_start_event)
        assert callable(create_llm_interaction_event)
        assert callable(create_policy_change_event)
