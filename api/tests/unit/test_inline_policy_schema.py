"""
Unit tests for InlinePolicy schema.

TDD Tests: These tests should FAIL until InlinePolicy is implemented.

The InlinePolicy type allows embedding decision tree DSL structures directly
in configuration dictionaries, complementing the existing FromJson policy
that loads from external files.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from payment_simulator.config import SimulationConfig
from payment_simulator.config.schemas import (
    AgentConfig,
    FifoPolicy,
    FromJsonPolicy,
    PolicyConfig,
)


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def minimal_decision_trees() -> dict[str, Any]:
    """Minimal valid decision trees structure."""
    return {
        "version": "2.0",
        "policy_id": "test_policy",
        "parameters": {
            "urgency_threshold": 3.0,
            "initial_liquidity_fraction": 0.5,
            "liquidity_buffer_factor": 1.0,
        },
        "strategic_collateral_tree": {
            "type": "action",
            "node_id": "hold",
            "action": "HoldCollateral",
        },
        "payment_tree": {
            "type": "action",
            "node_id": "release",
            "action": "Release",
        },
    }


@pytest.fixture
def complex_decision_trees() -> dict[str, Any]:
    """Complex decision trees with conditions."""
    return {
        "version": "2.0",
        "policy_id": "complex_test_policy",
        "parameters": {
            "urgency_threshold": 3.0,
            "initial_liquidity_fraction": 0.25,
            "liquidity_buffer_factor": 1.5,
        },
        "strategic_collateral_tree": {
            "type": "condition",
            "node_id": "tick_zero_check",
            "condition": {
                "op": "==",
                "left": {"field": "system_tick_in_day"},
                "right": {"value": 0.0},
            },
            "on_true": {
                "type": "action",
                "node_id": "post_initial",
                "action": "PostCollateral",
                "parameters": {
                    "amount": {
                        "compute": {
                            "op": "*",
                            "left": {"field": "max_collateral_capacity"},
                            "right": {"param": "initial_liquidity_fraction"},
                        }
                    },
                    "reason": {"value": "InitialAllocation"},
                },
            },
            "on_false": {
                "type": "action",
                "node_id": "hold",
                "action": "HoldCollateral",
            },
        },
        "payment_tree": {
            "type": "condition",
            "node_id": "urgency_check",
            "condition": {
                "op": "<=",
                "left": {"field": "ticks_to_deadline"},
                "right": {"param": "urgency_threshold"},
            },
            "on_true": {
                "type": "action",
                "node_id": "release_urgent",
                "action": "Release",
            },
            "on_false": {
                "type": "action",
                "node_id": "hold_payment",
                "action": "Hold",
            },
        },
    }


# ============================================================================
# Schema Validation Tests
# ============================================================================


class TestInlinePolicySchemaValidation:
    """Test InlinePolicy schema validation."""

    def test_inline_policy_import_exists(self) -> None:
        """InlinePolicy should be importable from schemas."""
        # This test will fail until InlinePolicy is added to schemas.py
        from payment_simulator.config.schemas import InlinePolicy

        assert InlinePolicy is not None

    def test_inline_policy_in_policy_config_union(self) -> None:
        """InlinePolicy should be part of PolicyConfig union type."""
        from payment_simulator.config.schemas import InlinePolicy

        # Get the types in the PolicyConfig union
        # PolicyConfig is a Union, so we need to check __args__
        from typing import get_args

        policy_types = get_args(PolicyConfig)

        # InlinePolicy should be one of the types
        assert InlinePolicy in policy_types, (
            f"InlinePolicy should be in PolicyConfig union. "
            f"Current types: {[t.__name__ for t in policy_types]}"
        )

    def test_inline_policy_accepts_valid_decision_trees(
        self, minimal_decision_trees: dict[str, Any]
    ) -> None:
        """InlinePolicy should accept valid decision_trees dict."""
        from payment_simulator.config.schemas import InlinePolicy

        policy = InlinePolicy(
            type="Inline",
            decision_trees=minimal_decision_trees,
        )

        assert policy.type == "Inline"
        assert policy.decision_trees == minimal_decision_trees

    def test_inline_policy_default_type_literal(
        self, minimal_decision_trees: dict[str, Any]
    ) -> None:
        """InlinePolicy type field should default to 'Inline'."""
        from payment_simulator.config.schemas import InlinePolicy

        # Create without explicitly setting type
        policy = InlinePolicy(decision_trees=minimal_decision_trees)

        assert policy.type == "Inline"

    def test_inline_policy_requires_decision_trees(self) -> None:
        """InlinePolicy should require decision_trees field."""
        from payment_simulator.config.schemas import InlinePolicy

        with pytest.raises(ValidationError) as exc_info:
            InlinePolicy(type="Inline")  # Missing decision_trees

        # Check that the error mentions decision_trees
        errors = exc_info.value.errors()
        assert any("decision_trees" in str(e) for e in errors)

    def test_inline_policy_with_complex_trees(
        self, complex_decision_trees: dict[str, Any]
    ) -> None:
        """InlinePolicy should accept complex nested decision trees."""
        from payment_simulator.config.schemas import InlinePolicy

        policy = InlinePolicy(decision_trees=complex_decision_trees)

        assert policy.decision_trees["version"] == "2.0"
        assert "strategic_collateral_tree" in policy.decision_trees
        assert "payment_tree" in policy.decision_trees
        assert policy.decision_trees["strategic_collateral_tree"]["type"] == "condition"


class TestInlinePolicyInAgentConfig:
    """Test InlinePolicy usage within AgentConfig."""

    def test_agent_config_accepts_inline_policy(
        self, minimal_decision_trees: dict[str, Any]
    ) -> None:
        """AgentConfig should accept InlinePolicy."""
        agent_dict = {
            "id": "BANK_A",
            "opening_balance": 100000,
            "unsecured_cap": 0,
            "policy": {
                "type": "Inline",
                "decision_trees": minimal_decision_trees,
            },
        }

        agent = AgentConfig.model_validate(agent_dict)

        assert agent.id == "BANK_A"
        assert agent.policy.type == "Inline"  # type: ignore[union-attr]

    def test_agent_config_inline_policy_from_dict(
        self, minimal_decision_trees: dict[str, Any]
    ) -> None:
        """AgentConfig should parse InlinePolicy from raw dict."""
        config_dict = {
            "id": "TEST_BANK",
            "opening_balance": 50000,
            "unsecured_cap": 10000,
            "policy": {
                "type": "Inline",
                "decision_trees": minimal_decision_trees,
            },
        }

        agent = AgentConfig.model_validate(config_dict)

        # Verify the policy was parsed as InlinePolicy
        from payment_simulator.config.schemas import InlinePolicy

        assert isinstance(agent.policy, InlinePolicy)
        assert agent.policy.decision_trees == minimal_decision_trees


class TestInlinePolicyInSimulationConfig:
    """Test InlinePolicy in full SimulationConfig."""

    def test_simulation_config_with_inline_policy(
        self, minimal_decision_trees: dict[str, Any]
    ) -> None:
        """SimulationConfig should accept agents with InlinePolicy."""
        config_dict = {
            "simulation": {
                "rng_seed": 42,
                "ticks_per_day": 10,
                "num_days": 1,
            },
            "agents": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100000,
                    "unsecured_cap": 0,
                    "policy": {
                        "type": "Inline",
                        "decision_trees": minimal_decision_trees,
                    },
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 100000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        sim_config = SimulationConfig.from_dict(config_dict)

        # First agent should have InlinePolicy
        from payment_simulator.config.schemas import InlinePolicy

        assert isinstance(sim_config.agents[0].policy, InlinePolicy)

        # Second agent should have FifoPolicy
        assert isinstance(sim_config.agents[1].policy, FifoPolicy)

    def test_mixed_policy_types_in_config(
        self, minimal_decision_trees: dict[str, Any]
    ) -> None:
        """Config should support mixed FromJson, Inline, and builtin policies."""
        config_dict = {
            "simulation": {
                "rng_seed": 123,
                "ticks_per_day": 100,
                "num_days": 1,
            },
            "agents": [
                {
                    "id": "INLINE_AGENT",
                    "opening_balance": 100000,
                    "unsecured_cap": 0,
                    "policy": {
                        "type": "Inline",
                        "decision_trees": minimal_decision_trees,
                    },
                },
                {
                    "id": "FIFO_AGENT",
                    "opening_balance": 100000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        sim_config = SimulationConfig.from_dict(config_dict)

        from payment_simulator.config.schemas import InlinePolicy

        assert isinstance(sim_config.agents[0].policy, InlinePolicy)
        assert isinstance(sim_config.agents[1].policy, FifoPolicy)
