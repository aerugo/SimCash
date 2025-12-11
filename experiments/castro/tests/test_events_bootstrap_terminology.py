"""TDD tests for bootstrap terminology in events.py.

These tests verify the terminology migration from Monte Carlo to Bootstrap.
Write these tests FIRST, then implement changes to make them pass.
"""

from __future__ import annotations

import pytest
from datetime import datetime


class TestEventTypeConstants:
    """Tests for event type constant naming."""

    def test_bootstrap_evaluation_constant_exists(self) -> None:
        """EVENT_BOOTSTRAP_EVALUATION constant should exist."""
        from castro.events import EVENT_BOOTSTRAP_EVALUATION

        assert EVENT_BOOTSTRAP_EVALUATION == "bootstrap_evaluation"

    def test_monte_carlo_constant_removed(self) -> None:
        """EVENT_MONTE_CARLO_EVALUATION constant should NOT exist."""
        from castro import events

        assert not hasattr(events, "EVENT_MONTE_CARLO_EVALUATION")

    def test_all_event_types_contains_bootstrap(self) -> None:
        """ALL_EVENT_TYPES should contain bootstrap_evaluation."""
        from castro.events import ALL_EVENT_TYPES

        assert "bootstrap_evaluation" in ALL_EVENT_TYPES
        assert "monte_carlo_evaluation" not in ALL_EVENT_TYPES


class TestBootstrapEventCreation:
    """Tests for create_bootstrap_evaluation_event function."""

    def test_create_bootstrap_evaluation_event_exists(self) -> None:
        """create_bootstrap_evaluation_event function should exist."""
        from castro.events import create_bootstrap_evaluation_event

        assert callable(create_bootstrap_evaluation_event)

    def test_create_monte_carlo_event_removed(self) -> None:
        """create_monte_carlo_event function should NOT exist."""
        from castro import events

        assert not hasattr(events, "create_monte_carlo_event")

    def test_create_bootstrap_evaluation_event_returns_correct_type(self) -> None:
        """Event should have event_type='bootstrap_evaluation'."""
        from castro.events import (
            create_bootstrap_evaluation_event,
            EVENT_BOOTSTRAP_EVALUATION,
        )

        event = create_bootstrap_evaluation_event(
            run_id="test-run",
            iteration=1,
            seed_results=[{"seed": 42, "cost": 1000}],
            mean_cost=1000,
            std_cost=100,
        )
        assert event.event_type == EVENT_BOOTSTRAP_EVALUATION
        assert event.event_type == "bootstrap_evaluation"

    def test_create_bootstrap_evaluation_event_has_required_details(self) -> None:
        """Event details should contain seed_results, mean_cost, std_cost."""
        from castro.events import create_bootstrap_evaluation_event

        seed_results = [
            {"seed": 42, "cost": 1000, "settled": 5, "total": 6},
            {"seed": 43, "cost": 1200, "settled": 4, "total": 6},
        ]
        event = create_bootstrap_evaluation_event(
            run_id="test-run",
            iteration=2,
            seed_results=seed_results,
            mean_cost=1100,
            std_cost=141,
        )
        assert event.details["seed_results"] == seed_results
        assert event.details["mean_cost"] == 1100
        assert event.details["std_cost"] == 141
        assert event.iteration == 2

    def test_bootstrap_event_costs_are_integers(self) -> None:
        """Costs should be integers (INV-1 compliance)."""
        from castro.events import create_bootstrap_evaluation_event

        event = create_bootstrap_evaluation_event(
            run_id="test-run",
            iteration=1,
            seed_results=[{"seed": 42, "cost": 1000}],
            mean_cost=1000,
            std_cost=100,
        )
        assert isinstance(event.details["mean_cost"], int)
        assert isinstance(event.details["std_cost"], int)


class TestEventSerialization:
    """Tests for event serialization with new naming."""

    def test_bootstrap_event_to_dict_has_correct_type(self) -> None:
        """Serialized event should have event_type='bootstrap_evaluation'."""
        from castro.events import create_bootstrap_evaluation_event

        event = create_bootstrap_evaluation_event(
            run_id="test-run",
            iteration=1,
            seed_results=[],
            mean_cost=0,
            std_cost=0,
        )
        event_dict = event.to_dict()
        assert event_dict["event_type"] == "bootstrap_evaluation"

    def test_bootstrap_event_round_trip(self) -> None:
        """Event should survive serialization round-trip."""
        from castro.events import (
            create_bootstrap_evaluation_event,
            ExperimentEvent,
        )

        original = create_bootstrap_evaluation_event(
            run_id="test-run",
            iteration=5,
            seed_results=[{"seed": 99, "cost": 500}],
            mean_cost=500,
            std_cost=0,
        )
        event_dict = original.to_dict()
        restored = ExperimentEvent.from_dict(event_dict)
        assert restored.event_type == original.event_type
        assert restored.details == original.details
