"""Tests for PolicyAgent - the simple PydanticAI integration."""

from __future__ import annotations

import pytest


class TestPolicyAgent:
    """Tests for PolicyAgent class."""

    def test_agent_initialization(self) -> None:
        """Agent initializes with model string."""
        from experiments.castro.generator import PolicyAgent

        agent = PolicyAgent(model="openai:gpt-4o")
        assert agent.model == "openai:gpt-4o"
        assert agent.max_depth == 3
        assert agent.retries == 3

    def test_agent_custom_settings(self) -> None:
        """Agent accepts custom settings."""
        from experiments.castro.generator import PolicyAgent

        agent = PolicyAgent(model="anthropic:claude-3-5-sonnet-20241022", max_depth=5, retries=5)
        assert agent.model == "anthropic:claude-3-5-sonnet-20241022"
        assert agent.max_depth == 5
        assert agent.retries == 5

    def test_agent_caches_per_tree_type(self) -> None:
        """Agent caches agents per tree type."""
        from experiments.castro.generator import PolicyAgent

        agent = PolicyAgent()
        # Access internal agent cache
        agent._get_agent("payment_tree")
        agent._get_agent("bank_tree")

        assert "payment_tree" in agent._agents
        assert "bank_tree" in agent._agents
        assert len(agent._agents) == 2


class TestPolicyDeps:
    """Tests for PolicyDeps dataclass."""

    def test_deps_creation(self) -> None:
        """PolicyDeps can be created with tree type."""
        from experiments.castro.generator import PolicyDeps

        deps = PolicyDeps(tree_type="payment_tree")
        assert deps.tree_type == "payment_tree"
        assert deps.max_depth == 3
        assert deps.current_policy is None

    def test_deps_with_context(self) -> None:
        """PolicyDeps accepts performance context."""
        from experiments.castro.generator import PolicyDeps

        deps = PolicyDeps(
            tree_type="payment_tree",
            total_cost=50000.0,
            settlement_rate=0.95,
            per_bank_costs={"BANK_A": 25000.0},
        )
        assert deps.total_cost == 50000.0
        assert deps.settlement_rate == 0.95


class TestGeneratePolicyFunction:
    """Tests for generate_policy convenience function."""

    def test_function_exists(self) -> None:
        """generate_policy function is importable."""
        from experiments.castro.generator import generate_policy

        assert callable(generate_policy)


class TestValidation:
    """Tests for validation utilities."""

    def test_validate_valid_action(self) -> None:
        """Valid action passes validation."""
        from experiments.castro.generator import validate_policy_structure

        policy = {"type": "action", "action": "Release", "parameters": {}}
        result = validate_policy_structure(policy, "payment_tree")
        assert result.is_valid

    def test_validate_invalid_action(self) -> None:
        """Invalid action fails validation."""
        from experiments.castro.generator import validate_policy_structure

        policy = {"type": "action", "action": "NotAnAction", "parameters": {}}
        result = validate_policy_structure(policy, "payment_tree")
        assert not result.is_valid

    def test_validate_condition(self) -> None:
        """Valid condition passes validation."""
        from experiments.castro.generator import validate_policy_structure

        policy = {
            "type": "condition",
            "condition": {"op": ">=", "left": {"field": "balance"}, "right": {"value": 0}},
            "on_true": {"type": "action", "action": "Release", "parameters": {}},
            "on_false": {"type": "action", "action": "Hold", "parameters": {}},
        }
        result = validate_policy_structure(policy, "payment_tree")
        assert result.is_valid


class TestModelStrings:
    """Tests verifying model string format."""

    def test_openai_format(self) -> None:
        """OpenAI model string format."""
        from experiments.castro.generator import PolicyAgent

        agent = PolicyAgent(model="openai:gpt-4o")
        assert "openai" in agent.model

    def test_anthropic_format(self) -> None:
        """Anthropic model string format."""
        from experiments.castro.generator import PolicyAgent

        agent = PolicyAgent(model="anthropic:claude-3-5-sonnet-20241022")
        assert "anthropic" in agent.model

    def test_ollama_format(self) -> None:
        """Ollama model string format."""
        from experiments.castro.generator import PolicyAgent

        agent = PolicyAgent(model="ollama:llama3.1:8b")
        assert "ollama" in agent.model
