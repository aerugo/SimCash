"""
Unit tests for InlineJsonPolicy schema.

TDD Tests: These tests should FAIL until InlineJsonPolicy is implemented.

The InlineJsonPolicy type allows passing raw JSON strings directly,
complementing InlinePolicy (dict) and FromJsonPolicy (file path).
This enables policy injection from databases, LLM responses, and
programmatic sources without file I/O.
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
    PolicyConfig,
)


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def minimal_policy_json() -> str:
    """Minimal valid policy JSON string."""
    policy_dict = {
        "version": "2.0",
        "policy_id": "test_policy",
        "parameters": {},
        "payment_tree": {
            "type": "action",
            "node_id": "release",
            "action": "Release",
        },
    }
    return json.dumps(policy_dict)


@pytest.fixture
def complex_policy_json() -> str:
    """Complex policy JSON string with conditions."""
    policy_dict = {
        "version": "2.0",
        "policy_id": "complex_test_policy",
        "parameters": {
            "urgency_threshold": 3.0,
        },
        "strategic_collateral_tree": {
            "type": "action",
            "node_id": "hold",
            "action": "HoldCollateral",
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
    return json.dumps(policy_dict)


# ============================================================================
# Schema Validation Tests
# ============================================================================


class TestInlineJsonPolicySchemaValidation:
    """Test InlineJsonPolicy schema validation."""

    def test_inline_json_policy_import_exists(self) -> None:
        """InlineJsonPolicy should be importable from schemas."""
        from payment_simulator.config.schemas import InlineJsonPolicy

        assert InlineJsonPolicy is not None

    def test_inline_json_policy_in_policy_config_union(self) -> None:
        """InlineJsonPolicy should be part of PolicyConfig union type."""
        from payment_simulator.config.schemas import InlineJsonPolicy
        from typing import get_args

        policy_types = get_args(PolicyConfig)

        assert InlineJsonPolicy in policy_types, (
            f"InlineJsonPolicy should be in PolicyConfig union. "
            f"Current types: {[t.__name__ for t in policy_types]}"
        )

    def test_inline_json_policy_accepts_valid_json_string(
        self, minimal_policy_json: str
    ) -> None:
        """InlineJsonPolicy should accept valid JSON string."""
        from payment_simulator.config.schemas import InlineJsonPolicy

        policy = InlineJsonPolicy(
            type="InlineJson",
            json_string=minimal_policy_json,
        )

        assert policy.type == "InlineJson"
        assert policy.json_string == minimal_policy_json

    def test_inline_json_policy_default_type_literal(
        self, minimal_policy_json: str
    ) -> None:
        """InlineJsonPolicy type field should default to 'InlineJson'."""
        from payment_simulator.config.schemas import InlineJsonPolicy

        # Create without explicitly setting type
        policy = InlineJsonPolicy(json_string=minimal_policy_json)

        assert policy.type == "InlineJson"

    def test_inline_json_policy_requires_json_string(self) -> None:
        """InlineJsonPolicy should require json_string field."""
        from payment_simulator.config.schemas import InlineJsonPolicy

        with pytest.raises(ValidationError) as exc_info:
            InlineJsonPolicy(type="InlineJson")  # Missing json_string

        errors = exc_info.value.errors()
        assert any("json_string" in str(e) for e in errors)

    def test_inline_json_policy_validates_json_format(self) -> None:
        """InlineJsonPolicy should reject invalid JSON strings."""
        from payment_simulator.config.schemas import InlineJsonPolicy

        invalid_json = "{ not valid json }"

        with pytest.raises(ValidationError) as exc_info:
            InlineJsonPolicy(json_string=invalid_json)

        errors = exc_info.value.errors()
        # Should mention "Invalid JSON" from the validator
        assert any("invalid" in str(e).lower() or "json" in str(e).lower() for e in errors)

    def test_inline_json_policy_with_complex_json(
        self, complex_policy_json: str
    ) -> None:
        """InlineJsonPolicy should accept complex nested JSON."""
        from payment_simulator.config.schemas import InlineJsonPolicy

        policy = InlineJsonPolicy(json_string=complex_policy_json)

        # Verify we can parse it back
        parsed = json.loads(policy.json_string)
        assert parsed["version"] == "2.0"
        assert "strategic_collateral_tree" in parsed
        assert "payment_tree" in parsed


class TestInlineJsonPolicyInAgentConfig:
    """Test InlineJsonPolicy usage within AgentConfig."""

    def test_agent_config_accepts_inline_json_policy(
        self, minimal_policy_json: str
    ) -> None:
        """AgentConfig should accept InlineJsonPolicy."""
        agent_dict = {
            "id": "BANK_A",
            "opening_balance": 100000,
            "unsecured_cap": 0,
            "policy": {
                "type": "InlineJson",
                "json_string": minimal_policy_json,
            },
        }

        agent = AgentConfig.model_validate(agent_dict)

        assert agent.id == "BANK_A"
        assert agent.policy.type == "InlineJson"  # type: ignore[union-attr]

    def test_agent_config_inline_json_policy_from_dict(
        self, minimal_policy_json: str
    ) -> None:
        """AgentConfig should parse InlineJsonPolicy from raw dict."""
        config_dict = {
            "id": "TEST_BANK",
            "opening_balance": 50000,
            "unsecured_cap": 10000,
            "policy": {
                "type": "InlineJson",
                "json_string": minimal_policy_json,
            },
        }

        agent = AgentConfig.model_validate(config_dict)

        from payment_simulator.config.schemas import InlineJsonPolicy

        assert isinstance(agent.policy, InlineJsonPolicy)
        assert agent.policy.json_string == minimal_policy_json


class TestInlineJsonPolicyInSimulationConfig:
    """Test InlineJsonPolicy in full SimulationConfig."""

    def test_simulation_config_with_inline_json_policy(
        self, minimal_policy_json: str
    ) -> None:
        """SimulationConfig should accept agents with InlineJsonPolicy."""
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
                        "type": "InlineJson",
                        "json_string": minimal_policy_json,
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

        from payment_simulator.config.schemas import InlineJsonPolicy

        assert isinstance(sim_config.agents[0].policy, InlineJsonPolicy)
        assert isinstance(sim_config.agents[1].policy, FifoPolicy)

    def test_mixed_inline_and_inline_json_policies(
        self, minimal_policy_json: str
    ) -> None:
        """Config should support both InlinePolicy and InlineJsonPolicy."""
        decision_trees = {
            "version": "2.0",
            "policy_id": "inline_trees",
            "parameters": {},
            "payment_tree": {
                "type": "action",
                "node_id": "release",
                "action": "Release",
            },
        }

        config_dict = {
            "simulation": {
                "rng_seed": 123,
                "ticks_per_day": 100,
                "num_days": 1,
            },
            "agents": [
                {
                    "id": "INLINE_JSON_AGENT",
                    "opening_balance": 100000,
                    "unsecured_cap": 0,
                    "policy": {
                        "type": "InlineJson",
                        "json_string": minimal_policy_json,
                    },
                },
                {
                    "id": "INLINE_AGENT",
                    "opening_balance": 100000,
                    "unsecured_cap": 0,
                    "policy": {
                        "type": "Inline",
                        "decision_trees": decision_trees,
                    },
                },
            ],
        }

        sim_config = SimulationConfig.from_dict(config_dict)

        from payment_simulator.config.schemas import InlineJsonPolicy, InlinePolicy

        assert isinstance(sim_config.agents[0].policy, InlineJsonPolicy)
        assert isinstance(sim_config.agents[1].policy, InlinePolicy)


class TestInlineJsonPolicyFFIConversion:
    """Test InlineJsonPolicy FFI conversion."""

    def test_inline_json_policy_ffi_conversion(
        self, minimal_policy_json: str
    ) -> None:
        """InlineJsonPolicy should convert to FFI format: {'type': 'FromJson', 'json': ...}."""
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
                        "type": "InlineJson",
                        "json_string": minimal_policy_json,
                    },
                },
            ],
        }

        sim_config = SimulationConfig.from_dict(config_dict)
        ffi_dict = sim_config.to_ffi_dict()

        # Check agent policy in FFI format
        agent_ffi = ffi_dict["agent_configs"][0]
        policy_ffi = agent_ffi["policy"]

        assert policy_ffi["type"] == "FromJson"
        assert policy_ffi["json"] == minimal_policy_json

    def test_inline_json_policy_ffi_preserves_original_json(
        self, complex_policy_json: str
    ) -> None:
        """FFI conversion should preserve the original JSON string exactly."""
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
                        "type": "InlineJson",
                        "json_string": complex_policy_json,
                    },
                },
            ],
        }

        sim_config = SimulationConfig.from_dict(config_dict)
        ffi_dict = sim_config.to_ffi_dict()

        agent_ffi = ffi_dict["agent_configs"][0]
        policy_ffi = agent_ffi["policy"]

        # The JSON string should be preserved exactly
        assert policy_ffi["json"] == complex_policy_json


class TestInlineJsonPolicyCastroUseCase:
    """Test InlineJsonPolicy for Castro experiment use case.

    Castro needs to inject policies as JSON strings from LLM responses
    without writing to files.
    """

    def test_castro_policy_injection_pattern(self) -> None:
        """Simulate Castro's policy injection workflow."""
        # This is how Castro would inject an LLM-generated policy
        llm_generated_policy = json.dumps({
            "version": "2.0",
            "policy_id": "llm_optimized_policy",
            "parameters": {
                "urgency_threshold": 5.0,
            },
            "payment_tree": {
                "type": "action",
                "node_id": "release",
                "action": "Release",
            },
        })

        config_dict = {
            "simulation": {
                "rng_seed": 42,
                "ticks_per_day": 100,
                "num_days": 1,
            },
            "agents": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1000000,
                    "unsecured_cap": 0,
                    "policy": {
                        "type": "InlineJson",
                        "json_string": llm_generated_policy,
                    },
                    "arrival_config": {
                        "rate_per_tick": 0.5,
                        "amount_distribution": {"type": "Normal", "mean": 10000, "std_dev": 1000},
                        "counterparty_weights": {"BANK_B": 1.0},
                        "deadline_range": [5, 20],
                    },
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1000000,
                    "unsecured_cap": 0,
                    "policy": {
                        "type": "InlineJson",
                        "json_string": llm_generated_policy,
                    },
                    "arrival_config": {
                        "rate_per_tick": 0.5,
                        "amount_distribution": {"type": "Normal", "mean": 10000, "std_dev": 1000},
                        "counterparty_weights": {"BANK_A": 1.0},
                        "deadline_range": [5, 20],
                    },
                },
            ],
        }

        # This should work without errors
        sim_config = SimulationConfig.from_dict(config_dict)
        ffi_dict = sim_config.to_ffi_dict()

        # Both agents should have the LLM policy
        for agent in ffi_dict["agent_configs"]:
            assert agent["policy"]["type"] == "FromJson"
            assert agent["policy"]["json"] == llm_generated_policy
