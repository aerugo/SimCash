"""Unit tests for prompt building.

TDD: These tests are written BEFORE implementation.
Run with: pytest experiments/castro/tests/unit/test_prompt_builder.py -v
"""

from __future__ import annotations

import pytest


class TestPolicyPromptBuilder:
    """Tests for PolicyPromptBuilder class."""

    def test_prompt_builder_initialization(self) -> None:
        """Builder initializes with tree type and constraints."""
        from experiments.castro.prompts.builder import PolicyPromptBuilder

        builder = PolicyPromptBuilder(
            tree_type="payment_tree",
            allowed_actions=["Release", "Hold", "Split"],
            allowed_fields=["balance", "amount", "ticks_to_deadline"],
        )
        assert builder.tree_type == "payment_tree"
        assert "Release" in builder.allowed_actions

    def test_prompt_includes_allowed_actions(self) -> None:
        """Built prompt lists all allowed actions."""
        from experiments.castro.prompts.builder import PolicyPromptBuilder

        builder = PolicyPromptBuilder(
            tree_type="payment_tree",
            allowed_actions=["Release", "Hold"],
            allowed_fields=["balance"],
        )
        prompt = builder.build()
        assert "Release" in prompt
        assert "Hold" in prompt

    def test_prompt_includes_allowed_fields(self) -> None:
        """Built prompt lists allowed context fields."""
        from experiments.castro.prompts.builder import PolicyPromptBuilder

        builder = PolicyPromptBuilder(
            tree_type="payment_tree",
            allowed_actions=["Release"],
            allowed_fields=["balance", "effective_liquidity", "ticks_to_deadline"],
        )
        prompt = builder.build()
        assert "balance" in prompt
        assert "effective_liquidity" in prompt
        assert "ticks_to_deadline" in prompt

    def test_prompt_includes_current_policy(self) -> None:
        """Built prompt includes current policy if provided."""
        from experiments.castro.prompts.builder import PolicyPromptBuilder
        import json

        current_policy = {
            "type": "action",
            "action": "Release",
        }

        builder = PolicyPromptBuilder(
            tree_type="payment_tree",
            allowed_actions=["Release", "Hold"],
            allowed_fields=["balance"],
        )
        builder.set_current_policy(current_policy)
        prompt = builder.build()
        # Should contain the policy JSON
        assert "Release" in prompt

    def test_prompt_includes_performance_context(self) -> None:
        """Built prompt includes performance metrics when set."""
        from experiments.castro.prompts.builder import PolicyPromptBuilder

        builder = PolicyPromptBuilder(
            tree_type="payment_tree",
            allowed_actions=["Release"],
            allowed_fields=["balance"],
        )
        builder.set_performance(
            total_cost=15000,
            settlement_rate=0.95,
            per_bank_costs={"BANK_A": 8000, "BANK_B": 7000},
        )
        prompt = builder.build()
        assert "15000" in prompt or "150" in prompt  # Cost value
        assert "95" in prompt or "0.95" in prompt  # Settlement rate

    def test_prompt_without_current_policy(self) -> None:
        """Built prompt works without current policy (initial generation)."""
        from experiments.castro.prompts.builder import PolicyPromptBuilder

        builder = PolicyPromptBuilder(
            tree_type="strategic_collateral_tree",
            allowed_actions=["PostCollateral", "HoldCollateral"],
            allowed_fields=["posted_collateral", "max_collateral_capacity"],
        )
        # Don't set current policy
        prompt = builder.build()
        assert "strategic_collateral_tree" in prompt or "collateral" in prompt.lower()

    def test_prompt_tree_type_specific_language(self) -> None:
        """Prompt uses tree-type appropriate language."""
        from experiments.castro.prompts.builder import PolicyPromptBuilder

        builder = PolicyPromptBuilder(
            tree_type="payment_tree",
            allowed_actions=["Release", "Hold"],
            allowed_fields=["amount"],
        )
        prompt = builder.build()
        # Should mention payments for payment tree
        assert "payment" in prompt.lower() or "transaction" in prompt.lower()


class TestSystemPrompt:
    """Tests for system prompt generation."""

    def test_system_prompt_exists(self) -> None:
        """System prompt template exists."""
        from experiments.castro.prompts.templates import SYSTEM_PROMPT

        assert isinstance(SYSTEM_PROMPT, str)
        assert len(SYSTEM_PROMPT) > 100  # Should be substantive

    def test_system_prompt_mentions_json(self) -> None:
        """System prompt mentions JSON format."""
        from experiments.castro.prompts.templates import SYSTEM_PROMPT

        assert "JSON" in SYSTEM_PROMPT or "json" in SYSTEM_PROMPT

    def test_system_prompt_mentions_policy(self) -> None:
        """System prompt mentions policy trees."""
        from experiments.castro.prompts.templates import SYSTEM_PROMPT

        assert "policy" in SYSTEM_PROMPT.lower()


class TestPromptFromGenerator:
    """Tests for creating prompts from PolicySchemaGenerator."""

    def test_create_prompt_from_generator(self) -> None:
        """Can create prompt builder from schema generator."""
        from experiments.castro.schemas.generator import PolicySchemaGenerator
        from experiments.castro.schemas.toggles import PolicyFeatureToggles
        from experiments.castro.prompts.builder import PolicyPromptBuilder

        gen = PolicySchemaGenerator(
            tree_type="payment_tree",
            feature_toggles=PolicyFeatureToggles(),
            max_depth=3,
        )

        builder = PolicyPromptBuilder.from_generator(gen)
        assert builder.tree_type == "payment_tree"
        assert "Release" in builder.allowed_actions

    def test_prompt_from_generator_respects_toggles(self) -> None:
        """Prompt from generator respects feature toggles."""
        from experiments.castro.schemas.generator import PolicySchemaGenerator
        from experiments.castro.schemas.toggles import PolicyFeatureToggles
        from experiments.castro.prompts.builder import PolicyPromptBuilder

        # Exclude transaction fields
        toggles = PolicyFeatureToggles(exclude=["TransactionField"])
        gen = PolicySchemaGenerator(
            tree_type="payment_tree",
            feature_toggles=toggles,
            max_depth=3,
        )

        builder = PolicyPromptBuilder.from_generator(gen)
        # Transaction fields should be excluded
        assert "amount" not in builder.allowed_fields
        assert "ticks_to_deadline" not in builder.allowed_fields
