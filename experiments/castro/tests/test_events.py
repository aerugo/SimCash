"""Tests for experiment event types and persistence.

TDD: These tests are written BEFORE the implementation.

Phase 12: Updated to use CastroEvent from event_compat.py
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pytest


class TestExperimentEvent:
    """Test CastroEvent dataclass (ExperimentEvent compatibility)."""

    def test_event_creation(self) -> None:
        """CastroEvent can be created with required fields."""
        from castro.event_compat import CastroEvent

        event = CastroEvent(
            event_type="iteration_start",
            run_id="exp1-20251209-143022-a1b2c3",
            iteration=1,
            timestamp=datetime.now().isoformat(),
            event_data={"total_cost": 15000},
        )

        assert event.event_type == "iteration_start"
        assert event.run_id == "exp1-20251209-143022-a1b2c3"
        assert event.iteration == 1
        assert event.details["total_cost"] == 15000
        assert event.event_data["total_cost"] == 15000

    def test_event_details_alias(self) -> None:
        """CastroEvent.details is an alias for event_data."""
        from castro.event_compat import CastroEvent

        event = CastroEvent(
            event_type="test",
            run_id="test-run",
            iteration=1,
            timestamp=datetime.now().isoformat(),
            event_data={},
        )

        assert event.details == {}
        assert event.event_data == {}
        assert event.details is event.event_data

    def test_event_to_dict(self) -> None:
        """CastroEvent can be converted to dict."""
        from castro.event_compat import CastroEvent

        ts = datetime(2025, 12, 9, 14, 30, 22).isoformat()
        event = CastroEvent(
            event_type="iteration_start",
            run_id="exp1-20251209-143022-a1b2c3",
            iteration=1,
            timestamp=ts,
            event_data={"total_cost": 15000},
        )

        d = event.to_dict()

        assert d["event_type"] == "iteration_start"
        assert d["run_id"] == "exp1-20251209-143022-a1b2c3"
        assert d["iteration"] == 1
        assert d["timestamp"] == ts  # ts is already a string
        assert d["details"]["total_cost"] == 15000

    def test_event_from_dict(self) -> None:
        """ExperimentEvent can be created from dict."""
        from castro.event_compat import CastroEvent as ExperimentEvent

        d = {
            "event_type": "iteration_start",
            "run_id": "exp1-20251209-143022-a1b2c3",
            "iteration": 1,
            "timestamp": "2025-12-09T14:30:22",
            "details": {"total_cost": 15000},
        }

        event = ExperimentEvent.from_dict(d)

        assert event.event_type == "iteration_start"
        assert event.run_id == "exp1-20251209-143022-a1b2c3"
        assert event.iteration == 1
        assert event.timestamp == "2025-12-09T14:30:22"  # Stored as string
        assert event.details["total_cost"] == 15000


class TestEventTypes:
    """Test event type constants are defined."""

    def test_experiment_start_event_type(self) -> None:
        """EVENT_EXPERIMENT_START is defined."""
        from payment_simulator.ai_cash_mgmt.events import EVENT_EXPERIMENT_START

        assert EVENT_EXPERIMENT_START == "experiment_start"

    def test_iteration_start_event_type(self) -> None:
        """EVENT_ITERATION_START is defined."""
        from payment_simulator.ai_cash_mgmt.events import EVENT_ITERATION_START

        assert EVENT_ITERATION_START == "iteration_start"

    def test_bootstrap_evaluation_event_type(self) -> None:
        """EVENT_BOOTSTRAP_EVALUATION is defined."""
        from payment_simulator.ai_cash_mgmt.events import EVENT_BOOTSTRAP_EVALUATION

        assert EVENT_BOOTSTRAP_EVALUATION == "bootstrap_evaluation"

    def test_llm_call_event_type(self) -> None:
        """EVENT_LLM_CALL is defined."""
        from payment_simulator.ai_cash_mgmt.events import EVENT_LLM_CALL

        assert EVENT_LLM_CALL == "llm_call"

    def test_policy_change_event_type(self) -> None:
        """EVENT_POLICY_CHANGE is defined."""
        from payment_simulator.ai_cash_mgmt.events import EVENT_POLICY_CHANGE

        assert EVENT_POLICY_CHANGE == "policy_change"

    def test_policy_rejected_event_type(self) -> None:
        """EVENT_POLICY_REJECTED is defined."""
        from payment_simulator.ai_cash_mgmt.events import EVENT_POLICY_REJECTED

        assert EVENT_POLICY_REJECTED == "policy_rejected"

    def test_experiment_end_event_type(self) -> None:
        """EVENT_EXPERIMENT_END is defined."""
        from payment_simulator.ai_cash_mgmt.events import EVENT_EXPERIMENT_END

        assert EVENT_EXPERIMENT_END == "experiment_end"

    def test_all_event_types_list(self) -> None:
        """ALL_EVENT_TYPES contains all event types."""
        from payment_simulator.ai_cash_mgmt.events import (
            ALL_EVENT_TYPES,
            EVENT_BOOTSTRAP_EVALUATION,
            EVENT_EXPERIMENT_END,
            EVENT_EXPERIMENT_START,
            EVENT_ITERATION_START,
            EVENT_LLM_CALL,
            EVENT_POLICY_CHANGE,
            EVENT_POLICY_REJECTED,
        )

        assert EVENT_EXPERIMENT_START in ALL_EVENT_TYPES
        assert EVENT_ITERATION_START in ALL_EVENT_TYPES
        assert EVENT_BOOTSTRAP_EVALUATION in ALL_EVENT_TYPES
        assert EVENT_LLM_CALL in ALL_EVENT_TYPES
        assert EVENT_POLICY_CHANGE in ALL_EVENT_TYPES
        assert EVENT_POLICY_REJECTED in ALL_EVENT_TYPES
        assert EVENT_EXPERIMENT_END in ALL_EVENT_TYPES


class TestEventCreationHelpers:
    """Test helper functions for creating specific event types.

    Note: Core create_*_event functions return EventRecord which uses
    'event_data' not 'details'. Tests use event_data accordingly.
    """

    def test_create_experiment_start_event(self) -> None:
        """create_experiment_start_event creates correct event."""
        from payment_simulator.ai_cash_mgmt.events import EVENT_EXPERIMENT_START, create_experiment_start_event

        event = create_experiment_start_event(
            run_id="exp1-20251209-143022-a1b2c3",
            experiment_name="exp1",
            description="Test experiment",
            model="anthropic:claude-sonnet-4-5",
            max_iterations=25,
            num_samples=5,
        )

        assert event.event_type == EVENT_EXPERIMENT_START
        assert event.run_id == "exp1-20251209-143022-a1b2c3"
        assert event.iteration == 0  # Start is before first iteration
        assert event.event_data["experiment_name"] == "exp1"
        assert event.event_data["description"] == "Test experiment"
        assert event.event_data["model"] == "anthropic:claude-sonnet-4-5"
        assert event.event_data["max_iterations"] == 25
        assert event.event_data["num_samples"] == 5

    def test_create_iteration_start_event(self) -> None:
        """create_iteration_start_event creates correct event."""
        from payment_simulator.ai_cash_mgmt.events import EVENT_ITERATION_START, create_iteration_start_event

        event = create_iteration_start_event(
            run_id="exp1-20251209-143022-a1b2c3",
            iteration=3,
            total_cost=15000,
        )

        assert event.event_type == EVENT_ITERATION_START
        assert event.iteration == 3
        assert event.event_data["total_cost"] == 15000

    def test_create_bootstrap_evaluation_event(self) -> None:
        """create_bootstrap_evaluation_event creates correct event."""
        from payment_simulator.ai_cash_mgmt.events import (
            EVENT_BOOTSTRAP_EVALUATION,
            create_bootstrap_evaluation_event,
        )

        seed_results = [
            {"seed": 42, "cost": 15000, "settled": 10, "total": 10, "settlement_rate": 1.0},
            {"seed": 43, "cost": 16000, "settled": 9, "total": 10, "settlement_rate": 0.9},
        ]

        event = create_bootstrap_evaluation_event(
            run_id="exp1-20251209-143022-a1b2c3",
            iteration=1,
            seed_results=seed_results,
            mean_cost=15500,
            std_cost=500,
        )

        assert event.event_type == EVENT_BOOTSTRAP_EVALUATION
        assert event.event_data["seed_results"] == seed_results
        assert event.event_data["mean_cost"] == 15500
        assert event.event_data["std_cost"] == 500

    def test_create_llm_call_event(self) -> None:
        """create_llm_call_event creates correct event."""
        from payment_simulator.ai_cash_mgmt.events import EVENT_LLM_CALL, create_llm_call_event

        event = create_llm_call_event(
            run_id="exp1-20251209-143022-a1b2c3",
            iteration=1,
            agent_id="BANK_A",
            model="openai:gpt-5.1",
            prompt_tokens=1000,
            completion_tokens=500,
            latency_seconds=2.5,
            context_summary={"current_cost": 7500},
        )

        assert event.event_type == EVENT_LLM_CALL
        assert event.event_data["agent_id"] == "BANK_A"
        assert event.event_data["model"] == "openai:gpt-5.1"
        assert event.event_data["prompt_tokens"] == 1000
        assert event.event_data["completion_tokens"] == 500
        assert event.event_data["latency_seconds"] == 2.5
        assert event.event_data["context_summary"]["current_cost"] == 7500

    def test_create_policy_change_event(self) -> None:
        """create_policy_change_event creates correct event."""
        from payment_simulator.ai_cash_mgmt.events import EVENT_POLICY_CHANGE, create_policy_change_event

        old_policy = {"parameters": {"threshold": 3.0}}
        new_policy = {"parameters": {"threshold": 2.0}}

        event = create_policy_change_event(
            run_id="exp1-20251209-143022-a1b2c3",
            iteration=1,
            agent_id="BANK_A",
            old_policy=old_policy,
            new_policy=new_policy,
            old_cost=8000,
            new_cost=7000,
            accepted=True,
        )

        assert event.event_type == EVENT_POLICY_CHANGE
        assert event.event_data["agent_id"] == "BANK_A"
        assert event.event_data["old_policy"] == old_policy
        assert event.event_data["new_policy"] == new_policy
        assert event.event_data["old_cost"] == 8000
        assert event.event_data["new_cost"] == 7000
        assert event.event_data["accepted"] is True

    def test_create_policy_rejected_event(self) -> None:
        """create_policy_rejected_event creates correct event."""
        from payment_simulator.ai_cash_mgmt.events import EVENT_POLICY_REJECTED, create_policy_rejected_event

        proposed_policy = {"parameters": {"threshold": -1.0}}  # Invalid

        event = create_policy_rejected_event(
            run_id="exp1-20251209-143022-a1b2c3",
            iteration=1,
            agent_id="BANK_A",
            proposed_policy=proposed_policy,
            validation_errors=["threshold must be >= 0"],
            rejection_reason="validation_failed",
            old_cost=8000,
            new_cost=None,
        )

        assert event.event_type == EVENT_POLICY_REJECTED
        assert event.event_data["agent_id"] == "BANK_A"
        assert event.event_data["proposed_policy"] == proposed_policy
        assert event.event_data["validation_errors"] == ["threshold must be >= 0"]
        assert event.event_data["rejection_reason"] == "validation_failed"

    def test_create_experiment_end_event(self) -> None:
        """create_experiment_end_event creates correct event."""
        from payment_simulator.ai_cash_mgmt.events import EVENT_EXPERIMENT_END, create_experiment_end_event

        event = create_experiment_end_event(
            run_id="exp1-20251209-143022-a1b2c3",
            iteration=10,
            final_cost=12000,
            best_cost=11500,
            converged=True,
            convergence_reason="stability_reached",
            duration_seconds=120.5,
        )

        assert event.event_type == EVENT_EXPERIMENT_END
        assert event.event_data["final_cost"] == 12000
        assert event.event_data["best_cost"] == 11500
        assert event.event_data["converged"] is True
        assert event.event_data["convergence_reason"] == "stability_reached"
        assert event.event_data["duration_seconds"] == 120.5
