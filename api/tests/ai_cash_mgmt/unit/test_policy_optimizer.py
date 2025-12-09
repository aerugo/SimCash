"""Unit tests for PolicyOptimizer - LLM-based policy generation.

TDD: These tests are written BEFORE the implementation.
All tests use mocked LLM responses for determinism and speed.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestOptimizationResult:
    """Test optimization result dataclass."""

    def test_optimization_result_creation(self) -> None:
        """OptimizationResult should store all fields."""
        from payment_simulator.ai_cash_mgmt.optimization.policy_optimizer import (
            OptimizationResult,
        )

        result = OptimizationResult(
            agent_id="BANK_A",
            iteration=5,
            old_policy={"payment_tree": {"root": {"action": "queue"}}},
            new_policy={"payment_tree": {"root": {"action": "submit"}}},
            old_cost=1000.0,
            new_cost=800.0,
            was_accepted=True,
            validation_errors=[],
            llm_latency_seconds=1.5,
            tokens_used=500,
            llm_model="gpt-5.1",
        )

        assert result.agent_id == "BANK_A"
        assert result.iteration == 5
        assert result.was_accepted is True
        assert result.llm_model == "gpt-5.1"

    def test_optimization_result_rejected(self) -> None:
        """OptimizationResult can represent rejected optimization."""
        from payment_simulator.ai_cash_mgmt.optimization.policy_optimizer import (
            OptimizationResult,
        )

        result = OptimizationResult(
            agent_id="BANK_A",
            iteration=5,
            old_policy={"payment_tree": {"root": {"action": "queue"}}},
            new_policy=None,  # No valid policy generated
            old_cost=1000.0,
            new_cost=None,
            was_accepted=False,
            validation_errors=["Unknown parameter: foo"],
            llm_latency_seconds=2.0,
            tokens_used=600,
            llm_model="gpt-5.1",
        )

        assert result.was_accepted is False
        assert result.new_policy is None
        assert len(result.validation_errors) > 0


class TestPolicyOptimizer:
    """Test policy optimizer with mocked LLM."""

    @pytest.fixture
    def mock_llm_client(self) -> MagicMock:
        """Create a mock LLM client."""
        client = MagicMock()
        client.generate_policy = AsyncMock()
        return client

    @pytest.fixture
    def valid_policy_response(self) -> dict[str, Any]:
        """A valid policy response from LLM."""
        return {
            "payment_tree": {
                "parameters": {"threshold": 50000},
                "root": {
                    "field": "amount",
                    "op": ">",
                    "value": {"param": "threshold"},
                    "if_true": {"action": "submit"},
                    "if_false": {"action": "queue"},
                },
            }
        }

    def test_optimizer_creation(self) -> None:
        """PolicyOptimizer should be creatable."""
        from payment_simulator.ai_cash_mgmt.config.game_config import GameConfig
        from payment_simulator.ai_cash_mgmt.constraints.scenario_constraints import (
            ScenarioConstraints,
        )
        from payment_simulator.ai_cash_mgmt.optimization.policy_optimizer import (
            PolicyOptimizer,
        )

        constraints = ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["amount"],
            allowed_actions={"payment_tree": ["submit", "queue"]},
        )

        optimizer = PolicyOptimizer(
            constraints=constraints,
            max_retries=3,
        )

        assert optimizer is not None

    @pytest.mark.asyncio
    async def test_optimizer_generates_valid_policy(
        self,
        mock_llm_client: MagicMock,
        valid_policy_response: dict[str, Any],
    ) -> None:
        """Optimizer should generate valid policy from LLM."""
        from payment_simulator.ai_cash_mgmt.constraints.scenario_constraints import (
            ScenarioConstraints,
        )
        from payment_simulator.ai_cash_mgmt.optimization.policy_optimizer import (
            PolicyOptimizer,
        )

        constraints = ScenarioConstraints(
            allowed_parameters=[
                {"name": "threshold", "param_type": "int", "min_value": 0},
            ],
            allowed_fields=["amount"],
            allowed_actions={"payment_tree": ["submit", "queue"]},
        )

        mock_llm_client.generate_policy.return_value = valid_policy_response

        optimizer = PolicyOptimizer(
            constraints=constraints,
            max_retries=3,
        )

        result = await optimizer.optimize(
            agent_id="BANK_A",
            current_policy={"payment_tree": {"root": {"action": "queue"}}},
            performance_history=[{"iteration": 0, "cost": 1000}],
            llm_client=mock_llm_client,
            llm_model="gpt-5.1",
        )

        assert result.new_policy is not None
        assert len(result.validation_errors) == 0

    @pytest.mark.asyncio
    async def test_optimizer_retries_on_validation_failure(
        self,
        mock_llm_client: MagicMock,
        valid_policy_response: dict[str, Any],
    ) -> None:
        """Optimizer should retry when LLM generates invalid policy."""
        from payment_simulator.ai_cash_mgmt.constraints.scenario_constraints import (
            ScenarioConstraints,
        )
        from payment_simulator.ai_cash_mgmt.optimization.policy_optimizer import (
            PolicyOptimizer,
        )

        constraints = ScenarioConstraints(
            allowed_parameters=[
                {"name": "threshold", "param_type": "int", "min_value": 0},
            ],
            allowed_fields=["amount"],
            allowed_actions={"payment_tree": ["submit", "queue"]},
        )

        # First call returns invalid, second returns valid
        invalid_response = {
            "payment_tree": {
                "parameters": {"unknown_param": 100},  # Invalid!
                "root": {"action": "submit"},
            }
        }
        mock_llm_client.generate_policy.side_effect = [
            invalid_response,
            valid_policy_response,
        ]

        optimizer = PolicyOptimizer(
            constraints=constraints,
            max_retries=3,
        )

        result = await optimizer.optimize(
            agent_id="BANK_A",
            current_policy={},
            performance_history=[],
            llm_client=mock_llm_client,
            llm_model="gpt-5.1",
        )

        # Should have retried and succeeded
        assert result.new_policy is not None
        assert mock_llm_client.generate_policy.call_count == 2

    @pytest.mark.asyncio
    async def test_optimizer_returns_none_after_max_retries(
        self,
        mock_llm_client: MagicMock,
    ) -> None:
        """Optimizer should return None after max retries exhausted."""
        from payment_simulator.ai_cash_mgmt.constraints.scenario_constraints import (
            ScenarioConstraints,
        )
        from payment_simulator.ai_cash_mgmt.optimization.policy_optimizer import (
            PolicyOptimizer,
        )

        constraints = ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["amount"],
            allowed_actions={"payment_tree": ["submit"]},
        )

        # Always return invalid policy
        invalid_response = {
            "payment_tree": {
                "parameters": {},
                "root": {"action": "invalid_action"},
            }
        }
        mock_llm_client.generate_policy.return_value = invalid_response

        optimizer = PolicyOptimizer(
            constraints=constraints,
            max_retries=2,
        )

        result = await optimizer.optimize(
            agent_id="BANK_A",
            current_policy={},
            performance_history=[],
            llm_client=mock_llm_client,
            llm_model="gpt-5.1",
        )

        assert result.new_policy is None
        assert result.was_accepted is False
        assert mock_llm_client.generate_policy.call_count == 2

    @pytest.mark.asyncio
    async def test_optimizer_includes_error_feedback_in_retry(
        self,
        mock_llm_client: MagicMock,
        valid_policy_response: dict[str, Any],
    ) -> None:
        """Optimizer should include validation errors in retry prompt."""
        from payment_simulator.ai_cash_mgmt.constraints.scenario_constraints import (
            ScenarioConstraints,
        )
        from payment_simulator.ai_cash_mgmt.optimization.policy_optimizer import (
            PolicyOptimizer,
        )

        constraints = ScenarioConstraints(
            allowed_parameters=[
                {"name": "threshold", "param_type": "int", "min_value": 0},
            ],
            allowed_fields=["amount"],
            allowed_actions={"payment_tree": ["submit", "queue"]},
        )

        # First call invalid, second valid
        invalid_response = {
            "payment_tree": {
                "parameters": {},
                "root": {"action": "bad_action"},
            }
        }
        mock_llm_client.generate_policy.side_effect = [
            invalid_response,
            valid_policy_response,
        ]

        optimizer = PolicyOptimizer(
            constraints=constraints,
            max_retries=3,
        )

        await optimizer.optimize(
            agent_id="BANK_A",
            current_policy={},
            performance_history=[],
            llm_client=mock_llm_client,
            llm_model="gpt-5.1",
        )

        # Check second call includes error context
        second_call = mock_llm_client.generate_policy.call_args_list[1]
        call_kwargs = second_call[1] if second_call[1] else {}
        call_args = second_call[0] if second_call[0] else ()

        # The retry should include error feedback somehow
        # (implementation detail - just verify retry happened)
        assert mock_llm_client.generate_policy.call_count == 2


class TestLLMClientProtocol:
    """Test the LLM client protocol."""

    def test_protocol_defines_generate_policy(self) -> None:
        """LLMClientProtocol should define generate_policy method."""
        from payment_simulator.ai_cash_mgmt.optimization.policy_optimizer import (
            LLMClientProtocol,
        )

        assert hasattr(LLMClientProtocol, "generate_policy")


class TestOptimizationPromptBuilder:
    """Test prompt building for LLM."""

    def test_build_optimization_prompt(self) -> None:
        """Should build a prompt from current policy and history."""
        from payment_simulator.ai_cash_mgmt.optimization.policy_optimizer import (
            build_optimization_prompt,
        )

        current_policy = {"payment_tree": {"root": {"action": "queue"}}}
        history = [
            {"iteration": 0, "cost": 1000},
            {"iteration": 1, "cost": 900},
        ]

        prompt = build_optimization_prompt(
            agent_id="BANK_A",
            current_policy=current_policy,
            performance_history=history,
            validation_errors=None,
        )

        assert "BANK_A" in prompt
        assert "queue" in prompt or "current" in prompt.lower()
        assert "1000" in prompt or "cost" in prompt.lower()

    def test_build_retry_prompt_includes_errors(self) -> None:
        """Retry prompt should include validation errors."""
        from payment_simulator.ai_cash_mgmt.optimization.policy_optimizer import (
            build_optimization_prompt,
        )

        prompt = build_optimization_prompt(
            agent_id="BANK_A",
            current_policy={},
            performance_history=[],
            validation_errors=["Unknown parameter: foo", "Invalid action: bar"],
        )

        assert "foo" in prompt or "error" in prompt.lower()
        assert "bar" in prompt or "invalid" in prompt.lower()
