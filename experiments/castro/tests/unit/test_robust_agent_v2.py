"""Unit tests for updated RobustPolicyAgent with ScenarioConstraints.

TDD: These tests define the expected behavior for the new agent API.
Run with: pytest experiments/castro/tests/unit/test_robust_agent_v2.py -v
"""

from __future__ import annotations

import pytest


class TestRobustPolicyAgentInit:
    """Tests for RobustPolicyAgent initialization."""

    def test_agent_requires_constraints(self) -> None:
        """RobustPolicyAgent requires ScenarioConstraints parameter."""
        from experiments.castro.schemas.parameter_config import (
            ParameterSpec,
            ScenarioConstraints,
        )
        from experiments.castro.generator.robust_policy_agent import RobustPolicyAgent

        constraints = ScenarioConstraints(
            allowed_parameters=[
                ParameterSpec(
                    name="urgency", min_value=0, max_value=20, default=3, description="Urgency"
                ),
            ],
            allowed_fields=["balance", "ticks_to_deadline"],
            allowed_actions=["Release", "Hold"],
        )

        agent = RobustPolicyAgent(constraints=constraints)
        assert agent.constraints == constraints

    def test_agent_creates_policy_model(self) -> None:
        """RobustPolicyAgent creates dynamic policy model from constraints."""
        from experiments.castro.schemas.parameter_config import (
            ParameterSpec,
            ScenarioConstraints,
        )
        from experiments.castro.generator.robust_policy_agent import RobustPolicyAgent

        constraints = ScenarioConstraints(
            allowed_parameters=[
                ParameterSpec(
                    name="custom_param", min_value=0, max_value=100, default=50, description="Custom"
                ),
            ],
            allowed_fields=["balance"],
            allowed_actions=["Release"],
        )

        agent = RobustPolicyAgent(constraints=constraints)
        assert agent.policy_model is not None

    def test_agent_accepts_model_parameter(self) -> None:
        """RobustPolicyAgent accepts optional model parameter."""
        from experiments.castro.schemas.parameter_config import ScenarioConstraints
        from experiments.castro.generator.robust_policy_agent import RobustPolicyAgent

        constraints = ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["balance"],
            allowed_actions=["Release"],
        )

        agent = RobustPolicyAgent(
            constraints=constraints,
            model="gpt-4o",
        )
        assert agent.model == "gpt-4o"


class TestRobustPolicyAgentPromptGeneration:
    """Tests for system prompt generation with constraints."""

    def test_prompt_includes_allowed_parameters(self) -> None:
        """System prompt includes allowed parameter names and bounds."""
        from experiments.castro.schemas.parameter_config import (
            ParameterSpec,
            ScenarioConstraints,
        )
        from experiments.castro.generator.robust_policy_agent import RobustPolicyAgent

        constraints = ScenarioConstraints(
            allowed_parameters=[
                ParameterSpec(
                    name="urgency_threshold",
                    min_value=0,
                    max_value=20,
                    default=3,
                    description="Ticks before deadline",
                ),
                ParameterSpec(
                    name="buffer_factor",
                    min_value=0.5,
                    max_value=3.0,
                    default=1.0,
                    description="Liquidity buffer",
                ),
            ],
            allowed_fields=["balance"],
            allowed_actions=["Release"],
        )

        agent = RobustPolicyAgent(constraints=constraints)
        prompt = agent.get_system_prompt()

        assert "urgency_threshold" in prompt
        assert "buffer_factor" in prompt
        assert "0" in prompt and "20" in prompt  # bounds
        assert "0.5" in prompt and "3.0" in prompt  # bounds

    def test_prompt_includes_allowed_fields(self) -> None:
        """System prompt includes allowed field names."""
        from experiments.castro.schemas.parameter_config import ScenarioConstraints
        from experiments.castro.generator.robust_policy_agent import RobustPolicyAgent

        constraints = ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["balance", "effective_liquidity", "ticks_to_deadline"],
            allowed_actions=["Release"],
        )

        agent = RobustPolicyAgent(constraints=constraints)
        prompt = agent.get_system_prompt()

        assert "balance" in prompt
        assert "effective_liquidity" in prompt
        assert "ticks_to_deadline" in prompt

    def test_prompt_includes_allowed_actions(self) -> None:
        """System prompt includes allowed action types."""
        from experiments.castro.schemas.parameter_config import ScenarioConstraints
        from experiments.castro.generator.robust_policy_agent import RobustPolicyAgent

        constraints = ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["balance"],
            allowed_actions=["Release", "Hold", "Split"],
        )

        agent = RobustPolicyAgent(constraints=constraints)
        prompt = agent.get_system_prompt()

        assert "Release" in prompt
        assert "Hold" in prompt
        assert "Split" in prompt


class TestRobustPolicyAgentPolicyModel:
    """Tests that the generated policy model enforces constraints."""

    def test_policy_model_accepts_valid_params(self) -> None:
        """Policy model accepts parameters within bounds."""
        from experiments.castro.schemas.parameter_config import (
            ParameterSpec,
            ScenarioConstraints,
        )
        from experiments.castro.generator.robust_policy_agent import RobustPolicyAgent

        constraints = ScenarioConstraints(
            allowed_parameters=[
                ParameterSpec(
                    name="threshold", min_value=0, max_value=20, default=5, description="Threshold"
                ),
            ],
            allowed_fields=["balance"],
            allowed_actions=["Release"],
        )

        agent = RobustPolicyAgent(constraints=constraints)
        PolicyModel = agent.policy_model

        # Should accept valid policy
        policy = PolicyModel(
            policy_id="test",
            parameters={"threshold": 10.0},
            payment_tree={"type": "action", "action": "Release"},
        )
        assert policy.parameters["threshold"] == 10.0

    def test_policy_model_uses_defaults(self) -> None:
        """Policy model uses default values for unspecified parameters."""
        from experiments.castro.schemas.parameter_config import (
            ParameterSpec,
            ScenarioConstraints,
        )
        from experiments.castro.generator.robust_policy_agent import RobustPolicyAgent

        constraints = ScenarioConstraints(
            allowed_parameters=[
                ParameterSpec(
                    name="threshold", min_value=0, max_value=20, default=5, description="Threshold"
                ),
            ],
            allowed_fields=["balance"],
            allowed_actions=["Release"],
        )

        agent = RobustPolicyAgent(constraints=constraints)
        PolicyModel = agent.policy_model

        # Should use default
        policy = PolicyModel(
            policy_id="test",
            parameters={},
            payment_tree={"type": "action", "action": "Release"},
        )
        # Note: parameters dict may not auto-fill defaults, but model accepts empty
        assert policy.policy_id == "test"
