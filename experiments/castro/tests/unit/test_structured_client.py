"""Unit tests for structured output client.

These tests verify the StructuredPolicyGenerator interface
without making actual API calls (those are in integration tests).

Run with: pytest experiments/castro/tests/unit/test_structured_client.py -v
"""

from __future__ import annotations

import pytest


class TestStructuredPolicyGenerator:
    """Tests for StructuredPolicyGenerator class."""

    def test_generator_initialization(self) -> None:
        """Generator initializes with model and depth settings."""
        from experiments.castro.generator.client import StructuredPolicyGenerator

        gen = StructuredPolicyGenerator(
            model="gpt-4o-2024-08-06",
            max_depth=3,
        )
        assert gen.model == "gpt-4o-2024-08-06"
        assert gen.max_depth == 3

    def test_generator_default_model(self) -> None:
        """Generator has sensible default model."""
        from experiments.castro.generator.client import StructuredPolicyGenerator

        gen = StructuredPolicyGenerator()
        assert gen.model is not None
        assert "gpt" in gen.model.lower() or gen.model.startswith("o")

    def test_generator_default_depth(self) -> None:
        """Generator has sensible default depth."""
        from experiments.castro.generator.client import StructuredPolicyGenerator

        gen = StructuredPolicyGenerator()
        assert gen.max_depth >= 3
        assert gen.max_depth <= 5


class TestPolicyContext:
    """Tests for PolicyContext dataclass."""

    def test_policy_context_creation(self) -> None:
        """PolicyContext can be created with metrics."""
        from experiments.castro.generator.client import PolicyContext

        ctx = PolicyContext(
            current_costs={"BANK_A": 1000, "BANK_B": 1500},
            settlement_rate=0.95,
            total_settled=50,
            total_pending=2,
        )
        assert ctx.settlement_rate == 0.95
        assert ctx.current_costs["BANK_A"] == 1000

    def test_policy_context_total_cost(self) -> None:
        """PolicyContext computes total cost from per-bank costs."""
        from experiments.castro.generator.client import PolicyContext

        ctx = PolicyContext(
            current_costs={"A": 500, "B": 700, "C": 300},
            settlement_rate=1.0,
        )
        assert ctx.total_cost == 1500

    def test_policy_context_from_simulation(self) -> None:
        """PolicyContext can be created from simulation results."""
        from experiments.castro.generator.client import PolicyContext

        # Mock simulation result dict
        result = {
            "per_bank_costs": {"BANK_A": 1000, "BANK_B": 2000},
            "settlement_rate": 0.98,
            "total_settled": 100,
            "total_pending": 2,
        }

        ctx = PolicyContext.from_simulation_result(result)
        assert ctx.settlement_rate == 0.98
        assert ctx.total_cost == 3000


class TestValidationWrapper:
    """Tests for policy validation wrapper."""

    def test_validate_valid_policy(self) -> None:
        """Valid policy passes validation."""
        from experiments.castro.generator.validation import validate_policy_structure

        policy = {
            "type": "action",
            "action": "Release",
            "parameters": {},
        }
        result = validate_policy_structure(policy, tree_type="payment_tree")
        assert result.is_valid
        assert len(result.errors) == 0

    def test_validate_invalid_action(self) -> None:
        """Invalid action type fails validation."""
        from experiments.castro.generator.validation import validate_policy_structure

        policy = {
            "type": "action",
            "action": "InvalidAction",
            "parameters": {},
        }
        result = validate_policy_structure(policy, tree_type="payment_tree")
        assert not result.is_valid
        assert len(result.errors) > 0

    def test_validate_missing_type(self) -> None:
        """Missing type field fails validation."""
        from experiments.castro.generator.validation import validate_policy_structure

        policy = {
            "action": "Release",
        }
        result = validate_policy_structure(policy, tree_type="payment_tree")
        assert not result.is_valid

    def test_validate_valid_condition(self) -> None:
        """Valid condition tree passes validation."""
        from experiments.castro.generator.validation import validate_policy_structure

        policy = {
            "type": "condition",
            "condition": {
                "op": ">=",
                "left": {"field": "balance"},
                "right": {"value": 0},
            },
            "on_true": {"type": "action", "action": "Release", "parameters": {}},
            "on_false": {"type": "action", "action": "Hold", "parameters": {}},
        }
        result = validate_policy_structure(policy, tree_type="payment_tree")
        assert result.is_valid


class TestRetryLogic:
    """Tests for generation retry logic."""

    def test_retry_config_defaults(self) -> None:
        """Retry configuration has sensible defaults."""
        from experiments.castro.generator.client import StructuredPolicyGenerator

        gen = StructuredPolicyGenerator()
        assert gen.max_retries >= 1
        assert gen.max_retries <= 5

    def test_retry_config_custom(self) -> None:
        """Retry configuration can be customized."""
        from experiments.castro.generator.client import StructuredPolicyGenerator

        gen = StructuredPolicyGenerator(max_retries=2)
        assert gen.max_retries == 2
