"""Tests for experiment event types and persistence.

TDD: These tests are written BEFORE the implementation.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pytest


class TestExperimentEvent:
    """Test ExperimentEvent dataclass."""

    def test_event_creation(self) -> None:
        """ExperimentEvent can be created with required fields."""
        from castro.events import ExperimentEvent

        event = ExperimentEvent(
            event_type="iteration_start",
            run_id="exp1-20251209-143022-a1b2c3",
            iteration=1,
            timestamp=datetime.now(),
            details={"total_cost": 15000},
        )

        assert event.event_type == "iteration_start"
        assert event.run_id == "exp1-20251209-143022-a1b2c3"
        assert event.iteration == 1
        assert event.details["total_cost"] == 15000

    def test_event_details_defaults_to_empty_dict(self) -> None:
        """ExperimentEvent details defaults to empty dict."""
        from castro.events import ExperimentEvent

        event = ExperimentEvent(
            event_type="test",
            run_id="test-run",
            iteration=1,
            timestamp=datetime.now(),
        )

        assert event.details == {}

    def test_event_to_dict(self) -> None:
        """ExperimentEvent can be converted to dict."""
        from castro.events import ExperimentEvent

        ts = datetime(2025, 12, 9, 14, 30, 22)
        event = ExperimentEvent(
            event_type="iteration_start",
            run_id="exp1-20251209-143022-a1b2c3",
            iteration=1,
            timestamp=ts,
            details={"total_cost": 15000},
        )

        d = event.to_dict()

        assert d["event_type"] == "iteration_start"
        assert d["run_id"] == "exp1-20251209-143022-a1b2c3"
        assert d["iteration"] == 1
        assert d["timestamp"] == ts.isoformat()
        assert d["details"]["total_cost"] == 15000

    def test_event_from_dict(self) -> None:
        """ExperimentEvent can be created from dict."""
        from castro.events import ExperimentEvent

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
        assert event.timestamp == datetime(2025, 12, 9, 14, 30, 22)
        assert event.details["total_cost"] == 15000


class TestEventTypes:
    """Test event type constants are defined."""

    def test_experiment_start_event_type(self) -> None:
        """EVENT_EXPERIMENT_START is defined."""
        from castro.events import EVENT_EXPERIMENT_START

        assert EVENT_EXPERIMENT_START == "experiment_start"

    def test_iteration_start_event_type(self) -> None:
        """EVENT_ITERATION_START is defined."""
        from castro.events import EVENT_ITERATION_START

        assert EVENT_ITERATION_START == "iteration_start"

    def test_monte_carlo_evaluation_event_type(self) -> None:
        """EVENT_MONTE_CARLO_EVALUATION is defined."""
        from castro.events import EVENT_MONTE_CARLO_EVALUATION

        assert EVENT_MONTE_CARLO_EVALUATION == "monte_carlo_evaluation"

    def test_llm_call_event_type(self) -> None:
        """EVENT_LLM_CALL is defined."""
        from castro.events import EVENT_LLM_CALL

        assert EVENT_LLM_CALL == "llm_call"

    def test_policy_change_event_type(self) -> None:
        """EVENT_POLICY_CHANGE is defined."""
        from castro.events import EVENT_POLICY_CHANGE

        assert EVENT_POLICY_CHANGE == "policy_change"

    def test_policy_rejected_event_type(self) -> None:
        """EVENT_POLICY_REJECTED is defined."""
        from castro.events import EVENT_POLICY_REJECTED

        assert EVENT_POLICY_REJECTED == "policy_rejected"

    def test_experiment_end_event_type(self) -> None:
        """EVENT_EXPERIMENT_END is defined."""
        from castro.events import EVENT_EXPERIMENT_END

        assert EVENT_EXPERIMENT_END == "experiment_end"

    def test_all_event_types_list(self) -> None:
        """ALL_EVENT_TYPES contains all event types."""
        from castro.events import (
            ALL_EVENT_TYPES,
            EVENT_EXPERIMENT_END,
            EVENT_EXPERIMENT_START,
            EVENT_ITERATION_START,
            EVENT_LLM_CALL,
            EVENT_MONTE_CARLO_EVALUATION,
            EVENT_POLICY_CHANGE,
            EVENT_POLICY_REJECTED,
        )

        assert EVENT_EXPERIMENT_START in ALL_EVENT_TYPES
        assert EVENT_ITERATION_START in ALL_EVENT_TYPES
        assert EVENT_MONTE_CARLO_EVALUATION in ALL_EVENT_TYPES
        assert EVENT_LLM_CALL in ALL_EVENT_TYPES
        assert EVENT_POLICY_CHANGE in ALL_EVENT_TYPES
        assert EVENT_POLICY_REJECTED in ALL_EVENT_TYPES
        assert EVENT_EXPERIMENT_END in ALL_EVENT_TYPES


class TestEventCreationHelpers:
    """Test helper functions for creating specific event types."""

    def test_create_experiment_start_event(self) -> None:
        """create_experiment_start_event creates correct event."""
        from castro.events import EVENT_EXPERIMENT_START, create_experiment_start_event

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
        assert event.details["experiment_name"] == "exp1"
        assert event.details["description"] == "Test experiment"
        assert event.details["model"] == "anthropic:claude-sonnet-4-5"
        assert event.details["max_iterations"] == 25
        assert event.details["num_samples"] == 5

    def test_create_iteration_start_event(self) -> None:
        """create_iteration_start_event creates correct event."""
        from castro.events import EVENT_ITERATION_START, create_iteration_start_event

        event = create_iteration_start_event(
            run_id="exp1-20251209-143022-a1b2c3",
            iteration=3,
            total_cost=15000,
        )

        assert event.event_type == EVENT_ITERATION_START
        assert event.iteration == 3
        assert event.details["total_cost"] == 15000

    def test_create_monte_carlo_event(self) -> None:
        """create_monte_carlo_event creates correct event."""
        from castro.events import EVENT_MONTE_CARLO_EVALUATION, create_monte_carlo_event

        seed_results = [
            {"seed": 42, "cost": 15000, "settled": 10, "total": 10, "settlement_rate": 1.0},
            {"seed": 43, "cost": 16000, "settled": 9, "total": 10, "settlement_rate": 0.9},
        ]

        event = create_monte_carlo_event(
            run_id="exp1-20251209-143022-a1b2c3",
            iteration=1,
            seed_results=seed_results,
            mean_cost=15500,
            std_cost=500,
        )

        assert event.event_type == EVENT_MONTE_CARLO_EVALUATION
        assert event.details["seed_results"] == seed_results
        assert event.details["mean_cost"] == 15500
        assert event.details["std_cost"] == 500

    def test_create_llm_call_event(self) -> None:
        """create_llm_call_event creates correct event."""
        from castro.events import EVENT_LLM_CALL, create_llm_call_event

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
        assert event.details["agent_id"] == "BANK_A"
        assert event.details["model"] == "openai:gpt-5.1"
        assert event.details["prompt_tokens"] == 1000
        assert event.details["completion_tokens"] == 500
        assert event.details["latency_seconds"] == 2.5
        assert event.details["context_summary"]["current_cost"] == 7500

    def test_create_policy_change_event(self) -> None:
        """create_policy_change_event creates correct event."""
        from castro.events import EVENT_POLICY_CHANGE, create_policy_change_event

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
        assert event.details["agent_id"] == "BANK_A"
        assert event.details["old_policy"] == old_policy
        assert event.details["new_policy"] == new_policy
        assert event.details["old_cost"] == 8000
        assert event.details["new_cost"] == 7000
        assert event.details["accepted"] is True

    def test_create_policy_rejected_event(self) -> None:
        """create_policy_rejected_event creates correct event."""
        from castro.events import EVENT_POLICY_REJECTED, create_policy_rejected_event

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
        assert event.details["agent_id"] == "BANK_A"
        assert event.details["proposed_policy"] == proposed_policy
        assert event.details["validation_errors"] == ["threshold must be >= 0"]
        assert event.details["rejection_reason"] == "validation_failed"

    def test_create_experiment_end_event(self) -> None:
        """create_experiment_end_event creates correct event."""
        from castro.events import EVENT_EXPERIMENT_END, create_experiment_end_event

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
        assert event.details["final_cost"] == 12000
        assert event.details["best_cost"] == 11500
        assert event.details["converged"] is True
        assert event.details["convergence_reason"] == "stability_reached"
        assert event.details["duration_seconds"] == 120.5
