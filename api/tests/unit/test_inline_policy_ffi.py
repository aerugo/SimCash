"""
Unit tests for InlinePolicy FFI conversion.

TDD Tests: These tests should FAIL until InlinePolicy FFI conversion is implemented.

Both FromJsonPolicy and InlinePolicy should produce the same FFI format:
{"type": "FromJson", "json": "...json string..."}

This allows the Rust backend to receive decision trees from either:
- External JSON files (FromJsonPolicy)
- Embedded dictionaries (InlinePolicy)
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from payment_simulator.config import SimulationConfig


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
def minimal_config_with_inline_policy(
    minimal_decision_trees: dict[str, Any],
) -> dict[str, Any]:
    """Minimal config with InlinePolicy for FFI testing."""
    return {
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


# ============================================================================
# FFI Conversion Tests
# ============================================================================


class TestInlinePolicyFfiConversion:
    """Test InlinePolicy to FFI dict conversion."""

    def test_to_ffi_dict_includes_inline_policy(
        self, minimal_config_with_inline_policy: dict[str, Any],
    ) -> None:
        """SimulationConfig.to_ffi_dict should convert InlinePolicy correctly."""
        sim_config = SimulationConfig.from_dict(minimal_config_with_inline_policy)
        ffi_dict = sim_config.to_ffi_dict()

        # Check agent_configs are present
        assert "agent_configs" in ffi_dict
        assert len(ffi_dict["agent_configs"]) == 2

    def test_inline_policy_ffi_format(
        self,
        minimal_config_with_inline_policy: dict[str, Any],
        minimal_decision_trees: dict[str, Any],
    ) -> None:
        """InlinePolicy should convert to FromJson FFI format."""
        sim_config = SimulationConfig.from_dict(minimal_config_with_inline_policy)
        ffi_dict = sim_config.to_ffi_dict()

        # Get first agent (with InlinePolicy)
        agent_ffi = ffi_dict["agent_configs"][0]
        policy_ffi = agent_ffi["policy"]

        # Should be converted to FromJson format for Rust
        assert policy_ffi["type"] == "FromJson", (
            f"InlinePolicy should convert to FromJson type for FFI, got {policy_ffi['type']}"
        )

        # Should have 'json' field with serialized decision_trees
        assert "json" in policy_ffi, "FFI policy should have 'json' field"

        # Verify the JSON content matches original decision_trees
        json_content = json.loads(policy_ffi["json"])
        assert json_content == minimal_decision_trees

    def test_inline_policy_json_is_valid(
        self, minimal_config_with_inline_policy: dict[str, Any],
    ) -> None:
        """InlinePolicy 'json' field should be valid JSON string."""
        sim_config = SimulationConfig.from_dict(minimal_config_with_inline_policy)
        ffi_dict = sim_config.to_ffi_dict()

        agent_ffi = ffi_dict["agent_configs"][0]
        policy_ffi = agent_ffi["policy"]

        # Should be a string
        assert isinstance(policy_ffi["json"], str), "json field should be a string"

        # Should be valid JSON
        try:
            parsed = json.loads(policy_ffi["json"])
        except json.JSONDecodeError as e:
            pytest.fail(f"policy json field is not valid JSON: {e}")

        # Should be a dict
        assert isinstance(parsed, dict), "Parsed JSON should be a dict"

    def test_fifo_policy_unchanged_in_mixed_config(
        self, minimal_config_with_inline_policy: dict[str, Any],
    ) -> None:
        """FifoPolicy should still work correctly alongside InlinePolicy."""
        sim_config = SimulationConfig.from_dict(minimal_config_with_inline_policy)
        ffi_dict = sim_config.to_ffi_dict()

        # Second agent has FifoPolicy
        fifo_agent_ffi = ffi_dict["agent_configs"][1]
        assert fifo_agent_ffi["policy"]["type"] == "Fifo"

    def test_complex_decision_trees_serialize_correctly(self) -> None:
        """Complex nested decision trees should serialize to valid JSON."""
        complex_trees = {
            "version": "2.0",
            "policy_id": "complex_policy",
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
                        "decision_trees": complex_trees,
                    },
                },
            ],
        }

        sim_config = SimulationConfig.from_dict(config_dict)
        ffi_dict = sim_config.to_ffi_dict()

        policy_ffi = ffi_dict["agent_configs"][0]["policy"]

        # Verify complex nested structure survives serialization
        parsed = json.loads(policy_ffi["json"])
        assert parsed["strategic_collateral_tree"]["type"] == "condition"
        assert parsed["strategic_collateral_tree"]["on_true"]["type"] == "action"
        assert parsed["strategic_collateral_tree"]["on_true"]["parameters"]["amount"]["compute"]["op"] == "*"


class TestInlinePolicyEquivalentToFromJson:
    """Test that InlinePolicy produces equivalent FFI output to FromJsonPolicy."""

    def test_inline_and_fromjson_produce_equivalent_ffi(
        self, minimal_decision_trees: dict[str, Any],
        tmp_path: Any,
    ) -> None:
        """InlinePolicy and FromJsonPolicy should produce equivalent FFI output.

        This test creates a temp JSON file, loads it via FromJsonPolicy,
        and verifies the FFI output matches InlinePolicy with same content.
        """
        # Create temp JSON file with decision trees
        json_file = tmp_path / "test_policy.json"
        json_file.write_text(json.dumps(minimal_decision_trees))

        # Config with InlinePolicy
        inline_config = {
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
            ],
        }

        # Config with FromJsonPolicy
        fromjson_config = {
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
                        "type": "FromJson",
                        "json_path": str(json_file),
                    },
                },
            ],
        }

        inline_ffi = SimulationConfig.from_dict(inline_config).to_ffi_dict()
        fromjson_ffi = SimulationConfig.from_dict(fromjson_config).to_ffi_dict()

        # Extract policy FFI from each
        inline_policy_ffi = inline_ffi["agent_configs"][0]["policy"]
        fromjson_policy_ffi = fromjson_ffi["agent_configs"][0]["policy"]

        # Both should have same type
        assert inline_policy_ffi["type"] == fromjson_policy_ffi["type"] == "FromJson"

        # Both should have json field
        assert "json" in inline_policy_ffi
        assert "json" in fromjson_policy_ffi

        # JSON content should be equivalent (compare parsed dicts)
        inline_json = json.loads(inline_policy_ffi["json"])
        fromjson_json = json.loads(fromjson_policy_ffi["json"])

        assert inline_json == fromjson_json, (
            f"InlinePolicy and FromJsonPolicy should produce equivalent JSON. "
            f"InlinePolicy: {inline_json}, FromJsonPolicy: {fromjson_json}"
        )
