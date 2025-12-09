"""Tests for context_types module.

Tests for the data structures used in building optimization context.
"""

from __future__ import annotations

import pytest


class TestSingleAgentIterationRecord:
    """Tests for SingleAgentIterationRecord dataclass."""

    def test_required_fields(self) -> None:
        """Required fields must be provided."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentIterationRecord,
        )

        record = SingleAgentIterationRecord(
            iteration=1,
            metrics={"total_cost_mean": 1000},
            policy={"parameters": {"threshold": 5.0}},
        )

        assert record.iteration == 1
        assert record.metrics == {"total_cost_mean": 1000}
        assert record.policy == {"parameters": {"threshold": 5.0}}

    def test_default_values(self) -> None:
        """Default values are set correctly."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentIterationRecord,
        )

        record = SingleAgentIterationRecord(
            iteration=1,
            metrics={"total_cost_mean": 1000},
            policy={"parameters": {"threshold": 5.0}},
        )

        assert record.was_accepted is True
        assert record.is_best_so_far is False
        assert record.comparison_to_best == ""
        assert record.policy_changes == []

    def test_custom_values_override_defaults(self) -> None:
        """Custom values override defaults."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentIterationRecord,
        )

        record = SingleAgentIterationRecord(
            iteration=2,
            metrics={"total_cost_mean": 800},
            policy={"parameters": {"threshold": 4.0}},
            was_accepted=False,
            is_best_so_far=True,
            comparison_to_best="Cost improved by 20%",
            policy_changes=["Changed 'threshold': 5.0 → 4.0 (↓1.0)"],
        )

        assert record.was_accepted is False
        assert record.is_best_so_far is True
        assert record.comparison_to_best == "Cost improved by 20%"
        assert len(record.policy_changes) == 1

    def test_policy_changes_list_independent(self) -> None:
        """Each instance has independent policy_changes list."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentIterationRecord,
        )

        record1 = SingleAgentIterationRecord(
            iteration=1, metrics={}, policy={},
        )
        record2 = SingleAgentIterationRecord(
            iteration=2, metrics={}, policy={},
        )

        record1.policy_changes.append("change1")

        assert record1.policy_changes == ["change1"]
        assert record2.policy_changes == []


class TestSingleAgentContext:
    """Tests for SingleAgentContext dataclass."""

    def test_minimal_creation(self) -> None:
        """Can create with minimal fields."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentContext,
        )

        context = SingleAgentContext()

        assert context.agent_id is None
        assert context.current_iteration == 0

    def test_default_values(self) -> None:
        """Default values are set correctly."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentContext,
        )

        context = SingleAgentContext(agent_id="BANK_A", current_iteration=1)

        assert context.iteration_history == []
        assert context.cost_breakdown == {}
        assert context.cost_rates == {}
        assert context.current_policy == {}
        assert context.current_metrics == {}
        assert context.best_seed_output is None
        assert context.worst_seed_output is None
        assert context.best_seed == 0
        assert context.worst_seed == 0
        assert context.best_seed_cost == 0
        assert context.worst_seed_cost == 0
        assert context.ticks_per_day == 100

    def test_stores_agent_id(self) -> None:
        """Agent ID is stored correctly."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentContext,
        )

        context = SingleAgentContext(agent_id="BANK_A", current_iteration=1)

        assert context.agent_id == "BANK_A"

    def test_full_initialization(self) -> None:
        """All fields can be set on creation."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentContext,
            SingleAgentIterationRecord,
        )

        history = [
            SingleAgentIterationRecord(
                iteration=1, metrics={"cost": 1000}, policy={"parameters": {}},
            ),
        ]

        context = SingleAgentContext(
            agent_id="BANK_B",
            current_iteration=2,
            current_policy={"parameters": {"threshold": 5.0}},
            current_metrics={"total_cost_mean": 800},
            iteration_history=history,
            best_seed_output="[Tick 0] Start...",
            worst_seed_output="[Tick 0] Failed...",
            best_seed=42,
            worst_seed=17,
            best_seed_cost=700,
            worst_seed_cost=1200,
            cost_breakdown={"delay": 500, "collateral": 300},
            cost_rates={"delay_per_tick": 100},
            ticks_per_day=50,
        )

        assert context.agent_id == "BANK_B"
        assert context.current_iteration == 2
        assert context.current_policy == {"parameters": {"threshold": 5.0}}
        assert len(context.iteration_history) == 1
        assert context.best_seed == 42
        assert context.cost_breakdown == {"delay": 500, "collateral": 300}
        assert context.ticks_per_day == 50

    def test_iteration_history_list_independent(self) -> None:
        """Each instance has independent iteration_history list."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentContext,
            SingleAgentIterationRecord,
        )

        context1 = SingleAgentContext(agent_id="A")
        context2 = SingleAgentContext(agent_id="B")

        context1.iteration_history.append(
            SingleAgentIterationRecord(iteration=1, metrics={}, policy={})
        )

        assert len(context1.iteration_history) == 1
        assert len(context2.iteration_history) == 0

    def test_cost_breakdown_dict_independent(self) -> None:
        """Each instance has independent cost_breakdown dict."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentContext,
        )

        context1 = SingleAgentContext(agent_id="A")
        context2 = SingleAgentContext(agent_id="B")

        context1.cost_breakdown["delay"] = 1000

        assert context1.cost_breakdown == {"delay": 1000}
        assert context2.cost_breakdown == {}
