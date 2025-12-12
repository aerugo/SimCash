"""Integration tests for new optimizer prompt system.

Tests the integration of:
- system_prompt_builder.py - System prompt with filtered schemas
- user_prompt_builder.py - User prompt with filtered events
- event_filter.py - Agent isolation filtering
- policy_optimizer.py - Integration point

TDD: These tests define the expected behavior BEFORE implementation.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from payment_simulator.ai_cash_mgmt.constraints.scenario_constraints import (
    ScenarioConstraints,
)
from payment_simulator.ai_cash_mgmt.optimization.policy_optimizer import (
    PolicyOptimizer,
)
from payment_simulator.ai_cash_mgmt.prompts.context_types import (
    SingleAgentIterationRecord,
)


class TestSystemPromptIntegration:
    """Tests for system prompt integration with optimizer."""

    @pytest.fixture
    def constraints(self) -> ScenarioConstraints:
        """Create test constraints."""
        return ScenarioConstraints(
            allowed_parameters=[
                {"name": "threshold", "param_type": "int", "min_value": 0, "max_value": 100},
            ],
            allowed_fields=["balance", "amount", "ticks_to_deadline"],
            allowed_actions={"payment_tree": ["Release", "Hold"]},
        )

    @pytest.fixture
    def mock_llm_client(self) -> MagicMock:
        """Create a mock LLM client."""
        client = MagicMock()
        client.generate_policy = AsyncMock()
        return client

    @pytest.fixture
    def valid_policy(self) -> dict[str, Any]:
        """A valid policy for tests."""
        return {
            "version": "2.0",
            "policy_id": "test_policy",
            "payment_tree": {
                "node_id": "root",
                "type": "action",
                "action": "Release",
            },
        }

    def test_optimizer_has_system_prompt_method(
        self, constraints: ScenarioConstraints
    ) -> None:
        """Optimizer should have get_system_prompt method."""
        optimizer = PolicyOptimizer(constraints)
        assert hasattr(optimizer, "get_system_prompt")

    def test_system_prompt_includes_filtered_actions(
        self, constraints: ScenarioConstraints
    ) -> None:
        """System prompt should include only allowed actions."""
        optimizer = PolicyOptimizer(constraints)
        system_prompt = optimizer.get_system_prompt()

        # Should include allowed actions
        assert "Release" in system_prompt
        assert "Hold" in system_prompt
        # Should NOT include disallowed actions
        assert "- **Split**" not in system_prompt

    def test_system_prompt_includes_filtered_fields(
        self, constraints: ScenarioConstraints
    ) -> None:
        """System prompt should include only allowed fields."""
        optimizer = PolicyOptimizer(constraints)
        system_prompt = optimizer.get_system_prompt()

        # Should include allowed fields
        assert "balance" in system_prompt
        assert "amount" in system_prompt
        assert "ticks_to_deadline" in system_prompt

    def test_system_prompt_is_cached(
        self, constraints: ScenarioConstraints
    ) -> None:
        """System prompt should be built once and cached."""
        optimizer = PolicyOptimizer(constraints)

        prompt1 = optimizer.get_system_prompt()
        prompt2 = optimizer.get_system_prompt()

        # Should be the same cached instance
        assert prompt1 is prompt2

    def test_system_prompt_includes_cost_schema(
        self, constraints: ScenarioConstraints
    ) -> None:
        """System prompt should include cost documentation."""
        optimizer = PolicyOptimizer(constraints)
        system_prompt = optimizer.get_system_prompt()

        # Should include cost-related content
        assert "cost" in system_prompt.lower()
        assert "overdraft" in system_prompt.lower() or "delay" in system_prompt.lower()


class TestUserPromptIntegration:
    """Tests for user prompt integration with optimizer."""

    @pytest.fixture
    def constraints(self) -> ScenarioConstraints:
        """Create test constraints."""
        return ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["balance", "amount"],
            allowed_actions={"payment_tree": ["Release", "Hold"]},
        )

    @pytest.fixture
    def mock_llm_client(self) -> MagicMock:
        """Create a mock LLM client that captures prompts."""
        client = MagicMock()
        client.generate_policy = AsyncMock()
        client.captured_prompts: list[str] = []

        async def capture_prompt(
            prompt: str, current_policy: dict[str, Any], context: dict[str, Any]
        ) -> dict[str, Any]:
            client.captured_prompts.append(prompt)
            return {
                "version": "2.0",
                "policy_id": "test",
                "payment_tree": {"node_id": "root", "type": "action", "action": "Release"},
            }

        client.generate_policy.side_effect = capture_prompt
        return client

    @pytest.mark.asyncio
    async def test_user_prompt_includes_agent_id(
        self,
        constraints: ScenarioConstraints,
        mock_llm_client: MagicMock,
    ) -> None:
        """User prompt should include target agent ID."""
        optimizer = PolicyOptimizer(constraints)

        await optimizer.optimize(
            agent_id="BANK_A",
            current_policy={},
            current_iteration=1,
            current_metrics={},
            llm_client=mock_llm_client,
            llm_model="test",
        )

        prompt = mock_llm_client.captured_prompts[0]
        assert "BANK_A" in prompt

    @pytest.mark.asyncio
    async def test_user_prompt_includes_current_policy(
        self,
        constraints: ScenarioConstraints,
        mock_llm_client: MagicMock,
    ) -> None:
        """User prompt should include current policy JSON."""
        optimizer = PolicyOptimizer(constraints)
        current_policy = {
            "payment_tree": {"type": "action", "action": "Hold", "node_id": "n1"}
        }

        await optimizer.optimize(
            agent_id="BANK_A",
            current_policy=current_policy,
            current_iteration=1,
            current_metrics={},
            llm_client=mock_llm_client,
            llm_model="test",
        )

        prompt = mock_llm_client.captured_prompts[0]
        assert "Hold" in prompt
        assert "payment_tree" in prompt


class TestEventFilteringIntegration:
    """Tests for event filtering in user prompt."""

    @pytest.fixture
    def constraints(self) -> ScenarioConstraints:
        """Create test constraints."""
        return ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["balance"],
            allowed_actions={"payment_tree": ["Release", "Hold"]},
        )

    @pytest.fixture
    def mock_llm_client(self) -> MagicMock:
        """Create a mock LLM client that captures prompts."""
        client = MagicMock()
        client.generate_policy = AsyncMock()
        client.captured_prompts: list[str] = []

        async def capture_prompt(
            prompt: str, current_policy: dict[str, Any], context: dict[str, Any]
        ) -> dict[str, Any]:
            client.captured_prompts.append(prompt)
            return {
                "version": "2.0",
                "policy_id": "test",
                "payment_tree": {"node_id": "root", "type": "action", "action": "Release"},
            }

        client.generate_policy.side_effect = capture_prompt
        return client

    @pytest.mark.asyncio
    async def test_events_filtered_by_agent(
        self,
        constraints: ScenarioConstraints,
        mock_llm_client: MagicMock,
    ) -> None:
        """Events should be filtered to only show target agent's data."""
        optimizer = PolicyOptimizer(constraints)
        events: list[dict[str, Any]] = [
            # BANK_A should see this (outgoing)
            {
                "tick": 1,
                "event_type": "Arrival",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 10000,
            },
            # BANK_A should NOT see this (not involved)
            {
                "tick": 1,
                "event_type": "Arrival",
                "sender_id": "BANK_C",
                "receiver_id": "BANK_D",
                "amount": 99999,
            },
        ]

        await optimizer.optimize(
            agent_id="BANK_A",
            current_policy={},
            current_iteration=1,
            current_metrics={},
            llm_client=mock_llm_client,
            llm_model="test",
            events=events,
        )

        prompt = mock_llm_client.captured_prompts[0]
        # BANK_A -> BANK_B should be visible
        assert "BANK_A" in prompt
        # BANK_C -> BANK_D should be filtered out
        assert "99999" not in prompt or "$999.99" not in prompt

    @pytest.mark.asyncio
    async def test_other_agent_costs_not_visible(
        self,
        constraints: ScenarioConstraints,
        mock_llm_client: MagicMock,
    ) -> None:
        """Other agents' costs should not be visible."""
        optimizer = PolicyOptimizer(constraints)
        events: list[dict[str, Any]] = [
            # BANK_A's cost
            {"tick": 1, "event_type": "CostAccrual", "agent_id": "BANK_A", "costs": {"delay": 500}},
            # BANK_B's cost - should be filtered
            {"tick": 1, "event_type": "CostAccrual", "agent_id": "BANK_B", "costs": {"delay": 88888}},
        ]

        await optimizer.optimize(
            agent_id="BANK_A",
            current_policy={},
            current_iteration=1,
            current_metrics={},
            llm_client=mock_llm_client,
            llm_model="test",
            events=events,
        )

        prompt = mock_llm_client.captured_prompts[0]
        # BANK_A's cost should be visible (500 cents = $5.00)
        assert "$5.00" in prompt
        # BANK_B's cost should NOT be visible (88888 cents = $888.88)
        assert "$888.88" not in prompt

    @pytest.mark.asyncio
    async def test_incoming_liquidity_visible(
        self,
        constraints: ScenarioConstraints,
        mock_llm_client: MagicMock,
    ) -> None:
        """Incoming liquidity events should be visible."""
        optimizer = PolicyOptimizer(constraints)
        events: list[dict[str, Any]] = [
            # Incoming payment TO BANK_A
            {
                "tick": 1,
                "event_type": "RtgsImmediateSettlement",
                "sender": "BANK_B",
                "receiver": "BANK_A",
                "amount": 50000,
            },
        ]

        await optimizer.optimize(
            agent_id="BANK_A",
            current_policy={},
            current_iteration=1,
            current_metrics={},
            llm_client=mock_llm_client,
            llm_model="test",
            events=events,
        )

        prompt = mock_llm_client.captured_prompts[0]
        # Incoming payment should be visible
        # 50000 cents = $500.00
        assert "$500.00" in prompt or "50000" in prompt


class TestBackwardCompatibility:
    """Tests for backward compatibility with existing code."""

    @pytest.fixture
    def constraints(self) -> ScenarioConstraints:
        """Create test constraints."""
        return ScenarioConstraints(
            allowed_parameters=[
                {"name": "threshold", "param_type": "int", "min_value": 0},
            ],
            allowed_fields=["amount"],
            allowed_actions={"payment_tree": ["submit", "queue"]},
        )

    @pytest.fixture
    def mock_llm_client(self) -> MagicMock:
        """Create a mock LLM client."""
        client = MagicMock()
        client.generate_policy = AsyncMock(
            return_value={
                "version": "2.0",
                "policy_id": "test",
                "payment_tree": {"node_id": "root", "type": "action", "action": "submit"},
            }
        )
        return client

    @pytest.mark.asyncio
    async def test_optimize_works_without_events(
        self,
        constraints: ScenarioConstraints,
        mock_llm_client: MagicMock,
    ) -> None:
        """Optimize should work when events parameter not provided."""
        optimizer = PolicyOptimizer(constraints)

        result = await optimizer.optimize(
            agent_id="BANK_A",
            current_policy={},
            current_iteration=1,
            current_metrics={},
            llm_client=mock_llm_client,
            llm_model="test",
            # events NOT provided (backward compat)
        )

        assert result is not None
        assert result.new_policy is not None

    @pytest.mark.asyncio
    async def test_optimize_works_with_all_legacy_params(
        self,
        constraints: ScenarioConstraints,
        mock_llm_client: MagicMock,
    ) -> None:
        """Optimize should work with all existing parameters."""
        optimizer = PolicyOptimizer(constraints)

        iteration_history = [
            SingleAgentIterationRecord(
                iteration=1,
                metrics={"total_cost_mean": 15000},
                policy={"parameters": {"threshold": 5}},
            ),
        ]

        result = await optimizer.optimize(
            agent_id="BANK_A",
            current_policy={"parameters": {"threshold": 4}},
            current_iteration=2,
            current_metrics={"total_cost_mean": 12000},
            llm_client=mock_llm_client,
            llm_model="test",
            current_cost=12000.0,
            iteration_history=iteration_history,
            best_seed_output="Tick 1: Arrival...",
            worst_seed_output="Tick 1: Queue...",
            best_seed=42,
            worst_seed=99,
            best_seed_cost=10000,
            worst_seed_cost=15000,
            cost_breakdown={"delay": 6000, "collateral": 4000},
            cost_rates={"overdraft_bps_per_tick": 0.001},
        )

        assert result is not None
        assert result.agent_id == "BANK_A"
        assert result.iteration == 2


class TestIterationHistoryIntegration:
    """Tests for iteration history in user prompt."""

    @pytest.fixture
    def constraints(self) -> ScenarioConstraints:
        """Create test constraints."""
        return ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["balance"],
            allowed_actions={"payment_tree": ["Release", "Hold"]},
        )

    @pytest.fixture
    def mock_llm_client(self) -> MagicMock:
        """Create a mock LLM client that captures prompts."""
        client = MagicMock()
        client.generate_policy = AsyncMock()
        client.captured_prompts: list[str] = []

        async def capture_prompt(
            prompt: str, current_policy: dict[str, Any], context: dict[str, Any]
        ) -> dict[str, Any]:
            client.captured_prompts.append(prompt)
            return {
                "version": "2.0",
                "policy_id": "test",
                "payment_tree": {"node_id": "root", "type": "action", "action": "Release"},
            }

        client.generate_policy.side_effect = capture_prompt
        return client

    @pytest.mark.asyncio
    async def test_iteration_history_included(
        self,
        constraints: ScenarioConstraints,
        mock_llm_client: MagicMock,
    ) -> None:
        """Iteration history should be included in user prompt."""
        optimizer = PolicyOptimizer(constraints)

        iteration_history = [
            SingleAgentIterationRecord(
                iteration=1,
                metrics={"total_cost_mean": 15000},
                policy={"parameters": {}},
            ),
            SingleAgentIterationRecord(
                iteration=2,
                metrics={"total_cost_mean": 12000},
                policy={"parameters": {}},
            ),
        ]

        await optimizer.optimize(
            agent_id="BANK_A",
            current_policy={},
            current_iteration=3,
            current_metrics={"total_cost_mean": 10000},
            llm_client=mock_llm_client,
            llm_model="test",
            iteration_history=iteration_history,
        )

        prompt = mock_llm_client.captured_prompts[0]
        # Should have iteration/history content
        assert "iteration" in prompt.lower() or "history" in prompt.lower()


class TestCostBreakdownIntegration:
    """Tests for cost breakdown in user prompt."""

    @pytest.fixture
    def constraints(self) -> ScenarioConstraints:
        """Create test constraints."""
        return ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["balance"],
            allowed_actions={"payment_tree": ["Release", "Hold"]},
        )

    @pytest.fixture
    def mock_llm_client(self) -> MagicMock:
        """Create a mock LLM client that captures prompts."""
        client = MagicMock()
        client.generate_policy = AsyncMock()
        client.captured_prompts: list[str] = []

        async def capture_prompt(
            prompt: str, current_policy: dict[str, Any], context: dict[str, Any]
        ) -> dict[str, Any]:
            client.captured_prompts.append(prompt)
            return {
                "version": "2.0",
                "policy_id": "test",
                "payment_tree": {"node_id": "root", "type": "action", "action": "Release"},
            }

        client.generate_policy.side_effect = capture_prompt
        return client

    @pytest.mark.asyncio
    async def test_cost_breakdown_included(
        self,
        constraints: ScenarioConstraints,
        mock_llm_client: MagicMock,
    ) -> None:
        """Cost breakdown should be included in user prompt."""
        optimizer = PolicyOptimizer(constraints)

        best_seed: dict[str, Any] = {
            "total_cost": 5000,
            "overdraft_cost": 1000,
            "delay_cost": 4000,
        }
        worst_seed: dict[str, Any] = {
            "total_cost": 15000,
            "overdraft_cost": 5000,
            "delay_cost": 10000,
        }
        average: dict[str, Any] = {
            "total_cost": 10000,
            "overdraft_cost": 3000,
            "delay_cost": 7000,
        }

        await optimizer.optimize(
            agent_id="BANK_A",
            current_policy={},
            current_iteration=1,
            current_metrics={},
            llm_client=mock_llm_client,
            llm_model="test",
            cost_breakdown={"delay": 7000, "overdraft": 3000},
            best_seed_cost=5000,
            worst_seed_cost=15000,
        )

        prompt = mock_llm_client.captured_prompts[0]
        # Should have cost information
        assert "cost" in prompt.lower()
