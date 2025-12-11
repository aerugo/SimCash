"""Unit tests for PolicyOptimizer - LLM-based policy generation.

TDD: These tests are written BEFORE the implementation.
All tests use mocked LLM responses for determinism and speed.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

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
            llm_model="gpt-5.2",
        )

        assert result.agent_id == "BANK_A"
        assert result.iteration == 5
        assert result.was_accepted is True
        assert result.llm_model == "gpt-5.2"

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
            llm_model="gpt-5.2",
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
            current_iteration=1,
            current_metrics={"total_cost_mean": 1000},
            llm_client=mock_llm_client,
            llm_model="gpt-5.2",
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
            current_iteration=1,
            current_metrics={},
            llm_client=mock_llm_client,
            llm_model="gpt-5.2",
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
            current_iteration=1,
            current_metrics={},
            llm_client=mock_llm_client,
            llm_model="gpt-5.2",
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
            current_iteration=1,
            current_metrics={},
            llm_client=mock_llm_client,
            llm_model="gpt-5.2",
        )

        # Check second call includes error context in prompt
        second_call = mock_llm_client.generate_policy.call_args_list[1]
        prompt = second_call[1].get(
            "prompt", second_call[0][0] if second_call[0] else ""
        )

        # Retry prompt should contain validation error info
        assert "VALIDATION ERROR" in prompt
        assert mock_llm_client.generate_policy.call_count == 2

    @pytest.mark.asyncio
    async def test_optimizer_uses_extended_context(
        self,
        mock_llm_client: MagicMock,
        valid_policy_response: dict[str, Any],
    ) -> None:
        """Optimizer should build extended context with all sections."""
        from payment_simulator.ai_cash_mgmt.constraints.scenario_constraints import (
            ScenarioConstraints,
        )
        from payment_simulator.ai_cash_mgmt.optimization.policy_optimizer import (
            PolicyOptimizer,
        )
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentIterationRecord,
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

        iteration_history = [
            SingleAgentIterationRecord(
                iteration=1,
                metrics={"total_cost_mean": 15000},
                policy={"parameters": {"threshold": 5.0}},
            ),
        ]

        await optimizer.optimize(
            agent_id="BANK_A",
            current_policy={"parameters": {"threshold": 4.0}},
            current_iteration=2,
            current_metrics={"total_cost_mean": 12000},
            llm_client=mock_llm_client,
            llm_model="gpt-5.2",
            iteration_history=iteration_history,
            cost_breakdown={"delay": 6000, "collateral": 4000},
            best_seed=42,
            best_seed_cost=11000,
        )

        # Verify prompt contains extended context sections
        call_args = mock_llm_client.generate_policy.call_args
        prompt = call_args[1].get("prompt", call_args[0][0] if call_args[0] else "")

        assert "BANK_A" in prompt
        assert "ITERATION 2" in prompt
        assert "COST ANALYSIS" in prompt
        assert "delay" in prompt
        assert "$6,000" in prompt


class TestLLMClientProtocol:
    """Test the LLM client protocol."""

    def test_protocol_defines_generate_policy(self) -> None:
        """LLMClientProtocol should define generate_policy method."""
        from payment_simulator.ai_cash_mgmt.optimization.policy_optimizer import (
            LLMClientProtocol,
        )

        assert hasattr(LLMClientProtocol, "generate_policy")
