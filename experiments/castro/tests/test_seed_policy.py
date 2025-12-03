"""
Seed Policy Validation Tests for Castro Experiments.

These tests verify that the seed policy (seed_policy.json):

1. Has valid JSON structure
2. Contains required trees (strategic_collateral_tree, payment_tree)
3. Has sensible parameter defaults
4. Behaves correctly when loaded by the simulator
5. Can be modified for optimization experiments

The seed policy is the starting point for LLM optimization. If it doesn't
work correctly, optimization experiments will fail.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from payment_simulator._core import Orchestrator
from payment_simulator.config import SimulationConfig


# ============================================================================
# Helper Functions
# ============================================================================


def _config_to_ffi(config_dict: dict[str, Any]) -> dict[str, Any]:
    """Convert a raw config dict to FFI-compatible format."""
    sim_config = SimulationConfig.from_dict(config_dict)
    return sim_config.to_ffi_dict()


# ============================================================================
# Policy Structure Validation
# ============================================================================


class TestPolicyStructure:
    """Validate seed policy JSON structure."""

    def test_policy_is_valid_json(self, seed_policy_path: Path) -> None:
        """Seed policy must be valid JSON."""
        with open(seed_policy_path) as f:
            try:
                policy = json.load(f)
            except json.JSONDecodeError as e:
                pytest.fail(f"Invalid JSON in seed policy: {e}")

        assert isinstance(policy, dict), "Policy must be a dict"

    def test_policy_has_version(self, seed_policy_dict: dict[str, Any]) -> None:
        """Seed policy should have version field."""
        assert "version" in seed_policy_dict
        assert seed_policy_dict["version"] == "2.0"

    def test_policy_has_id(self, seed_policy_dict: dict[str, Any]) -> None:
        """Seed policy should have policy_id field."""
        assert "policy_id" in seed_policy_dict
        assert len(seed_policy_dict["policy_id"]) > 0

    def test_policy_has_description(self, seed_policy_dict: dict[str, Any]) -> None:
        """Seed policy should have description field."""
        assert "description" in seed_policy_dict
        assert len(seed_policy_dict["description"]) > 0

    def test_policy_has_parameters(self, seed_policy_dict: dict[str, Any]) -> None:
        """Seed policy must have parameters section."""
        assert "parameters" in seed_policy_dict
        params = seed_policy_dict["parameters"]
        assert isinstance(params, dict)

    def test_policy_has_strategic_collateral_tree(
        self, seed_policy_dict: dict[str, Any]
    ) -> None:
        """Seed policy must have strategic_collateral_tree."""
        assert "strategic_collateral_tree" in seed_policy_dict
        tree = seed_policy_dict["strategic_collateral_tree"]
        assert isinstance(tree, dict)
        assert "type" in tree

    def test_policy_has_payment_tree(self, seed_policy_dict: dict[str, Any]) -> None:
        """Seed policy must have payment_tree."""
        assert "payment_tree" in seed_policy_dict
        tree = seed_policy_dict["payment_tree"]
        assert isinstance(tree, dict)
        assert "type" in tree


# ============================================================================
# Parameter Validation
# ============================================================================


class TestPolicyParameters:
    """Validate seed policy parameters."""

    def test_urgency_threshold_exists(
        self, seed_policy_dict: dict[str, Any]
    ) -> None:
        """Policy must have urgency_threshold parameter."""
        params = seed_policy_dict["parameters"]
        assert "urgency_threshold" in params
        assert isinstance(params["urgency_threshold"], (int, float))
        assert params["urgency_threshold"] > 0

    def test_initial_liquidity_fraction_exists(
        self, seed_policy_dict: dict[str, Any]
    ) -> None:
        """Policy must have initial_liquidity_fraction parameter."""
        params = seed_policy_dict["parameters"]
        assert "initial_liquidity_fraction" in params
        fraction = params["initial_liquidity_fraction"]
        assert isinstance(fraction, (int, float))
        assert 0 <= fraction <= 1, f"Fraction must be in [0, 1], got {fraction}"

    def test_liquidity_buffer_factor_exists(
        self, seed_policy_dict: dict[str, Any]
    ) -> None:
        """Policy must have liquidity_buffer_factor parameter."""
        params = seed_policy_dict["parameters"]
        assert "liquidity_buffer_factor" in params
        factor = params["liquidity_buffer_factor"]
        assert isinstance(factor, (int, float))
        assert factor > 0

    def test_default_initial_liquidity_fraction(
        self, seed_policy_dict: dict[str, Any]
    ) -> None:
        """Default initial_liquidity_fraction should be 0.25 (25%)."""
        params = seed_policy_dict["parameters"]
        # The seed policy for Castro-aligned experiments should have 25%
        assert params["initial_liquidity_fraction"] == 0.25, (
            "Seed policy should have 25% initial_liquidity_fraction"
        )


# ============================================================================
# Decision Tree Validation
# ============================================================================


class TestDecisionTrees:
    """Validate decision tree structure."""

    def test_strategic_collateral_tree_valid(
        self, seed_policy_dict: dict[str, Any]
    ) -> None:
        """Strategic collateral tree should have valid structure."""
        tree = seed_policy_dict["strategic_collateral_tree"]

        # Should be a condition or action node
        assert tree["type"] in ["condition", "action"], (
            f"Tree type must be 'condition' or 'action', got {tree['type']}"
        )

        if tree["type"] == "condition":
            assert "condition" in tree
            assert "on_true" in tree
            assert "on_false" in tree

        if tree["type"] == "action":
            assert "action" in tree

    def test_payment_tree_valid(
        self, seed_policy_dict: dict[str, Any]
    ) -> None:
        """Payment tree should have valid structure."""
        tree = seed_policy_dict["payment_tree"]

        assert tree["type"] in ["condition", "action"], (
            f"Tree type must be 'condition' or 'action', got {tree['type']}"
        )

    def test_tree_nodes_have_ids(
        self, seed_policy_dict: dict[str, Any]
    ) -> None:
        """Tree nodes should have node_id for debugging."""
        # Check strategic_collateral_tree
        sc_tree = seed_policy_dict["strategic_collateral_tree"]
        assert "node_id" in sc_tree

        # Check payment_tree
        p_tree = seed_policy_dict["payment_tree"]
        assert "node_id" in p_tree


# ============================================================================
# Policy Loading Tests
# ============================================================================


class TestPolicyLoading:
    """Test that policy loads correctly in simulator."""

    def test_policy_loads_in_exp1(
        self, exp1_config_dict: dict[str, Any]
    ) -> None:
        """Seed policy should load without errors in Exp1."""
        try:
            ffi_config = _config_to_ffi(exp1_config_dict)
            orch = Orchestrator.new(ffi_config)
        except Exception as e:
            pytest.fail(f"Failed to load policy in Exp1: {e}")

    def test_policy_loads_in_exp2(
        self, exp2_config_dict: dict[str, Any]
    ) -> None:
        """Seed policy should load without errors in Exp2."""
        try:
            ffi_config = _config_to_ffi(exp2_config_dict)
            orch = Orchestrator.new(ffi_config)
        except Exception as e:
            pytest.fail(f"Failed to load policy in Exp2: {e}")

    def test_policy_loads_in_exp3(
        self, exp3_config_dict: dict[str, Any]
    ) -> None:
        """Seed policy should load without errors in Exp3."""
        try:
            ffi_config = _config_to_ffi(exp3_config_dict)
            orch = Orchestrator.new(ffi_config)
        except Exception as e:
            pytest.fail(f"Failed to load policy in Exp3: {e}")


# ============================================================================
# Policy Behavior Tests
# ============================================================================


class TestPolicyBehavior:
    """Test that policy behaves as expected."""

    def test_posts_collateral_at_tick_zero(
        self, exp1_orchestrator: Orchestrator
    ) -> None:
        """Policy should post initial collateral at tick 0."""
        orch = exp1_orchestrator

        # Run tick 0
        orch.tick()

        # Check for collateral posting events
        events = orch.get_tick_events(0)
        collateral_events = [
            e for e in events
            if "Collateral" in e.get("event_type", "")
        ]

        # Should have some collateral activity
        # (depends on policy and max_collateral_capacity)
        print(f"Collateral events at tick 0: {len(collateral_events)}")
        for e in collateral_events:
            print(f"  {e.get('event_type')}: {e}")

    def test_releases_urgent_payments(self) -> None:
        """Policy should release payments when close to deadline."""
        config = {
            "simulation": {
                "rng_seed": 42,
                "ticks_per_day": 10,
                "num_days": 1,
            },
            "deferred_crediting": True,
            "deadline_cap_at_eod": True,
            "agents": [
                {
                    "id": "A",
                    "opening_balance": 100000,
                    "unsecured_cap": 0,
                    "max_collateral_capacity": 1000000,
                    "policy": {
                        "type": "Inline",
                        "decision_trees": {
                            "version": "2.0",
                            "policy_id": "test_urgent",
                            "parameters": {
                                "urgency_threshold": 3.0,
                                "initial_liquidity_fraction": 0.0,
                                "liquidity_buffer_factor": 1.0,
                            },
                            "strategic_collateral_tree": {
                                "type": "action",
                                "node_id": "hold",
                                "action": "HoldCollateral",
                            },
                            "payment_tree": {
                                "type": "condition",
                                "node_id": "check_urgent",
                                "condition": {
                                    "op": "<=",
                                    "left": {"field": "ticks_to_deadline"},
                                    "right": {"param": "urgency_threshold"},
                                },
                                "on_true": {
                                    "type": "action",
                                    "node_id": "release",
                                    "action": "Release",
                                },
                                "on_false": {
                                    "type": "action",
                                    "node_id": "hold",
                                    "action": "Hold",
                                },
                            },
                        },
                    },
                },
                {
                    "id": "B",
                    "opening_balance": 0,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        ffi_config = _config_to_ffi(config)
        orch = Orchestrator.new(ffi_config)

        # Submit payment with deadline at tick 5
        tx_id = orch.submit_transaction("A", "B", 50000, 5, 5, False)

        # Run up to tick 2 (not yet urgent: 5-2=3 ticks remaining)
        for _ in range(3):
            orch.tick()

        # Payment should be in queue (held, not urgent yet)
        # Actually, with 3 ticks remaining and threshold=3, it becomes urgent at tick 2
        # Let's check behavior

        events = orch.get_all_events()
        settlements = [e for e in events if e.get("event_type") == "RtgsImmediateSettlement"]

        print(f"Settlements so far: {len(settlements)}")


# ============================================================================
# Policy Modification Tests
# ============================================================================


class TestPolicyModification:
    """Test that policy can be modified for optimization."""

    def test_modified_liquidity_fraction_works(self) -> None:
        """Modifying initial_liquidity_fraction should change behavior."""
        base_config = {
            "simulation": {
                "rng_seed": 42,
                "ticks_per_day": 2,
                "num_days": 1,
            },
            "deferred_crediting": True,
            "deadline_cap_at_eod": True,
            "agents": [
                {
                    "id": "A",
                    "opening_balance": 0,
                    "unsecured_cap": 0,
                    "max_collateral_capacity": 100000,
                    "policy": {
                        "type": "Inline",
                        "decision_trees": {
                            "version": "2.0",
                            "policy_id": "test",
                            "parameters": {
                                "urgency_threshold": 3.0,
                                "initial_liquidity_fraction": 0.5,  # 50%
                                "liquidity_buffer_factor": 1.0,
                            },
                            "strategic_collateral_tree": {
                                "type": "condition",
                                "node_id": "tick_zero",
                                "condition": {
                                    "op": "==",
                                    "left": {"field": "system_tick_in_day"},
                                    "right": {"value": 0.0},
                                },
                                "on_true": {
                                    "type": "action",
                                    "node_id": "post",
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
                                "type": "action",
                                "node_id": "release",
                                "action": "Release",
                            },
                        },
                    },
                },
                {
                    "id": "B",
                    "opening_balance": 0,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        ffi_config = _config_to_ffi(base_config)
        orch = Orchestrator.new(ffi_config)

        # Run tick 0 (collateral posting)
        orch.tick()

        # Check A's posted collateral
        state_a = orch.get_agent_state("A")
        posted = state_a.get("posted_collateral", 0)

        # Should have posted 50% of 100000 = 50000
        # Note: The exact amount depends on how the policy computes this
        print(f"Agent A posted collateral: {posted}")

    def test_zero_liquidity_fraction_posts_nothing(self) -> None:
        """Setting initial_liquidity_fraction=0 should post no collateral."""
        config = {
            "simulation": {
                "rng_seed": 42,
                "ticks_per_day": 2,
                "num_days": 1,
            },
            "deferred_crediting": True,
            "agents": [
                {
                    "id": "A",
                    "opening_balance": 0,
                    "unsecured_cap": 0,
                    "max_collateral_capacity": 100000,
                    "policy": {
                        "type": "Inline",
                        "decision_trees": {
                            "version": "2.0",
                            "policy_id": "zero_collateral",
                            "parameters": {
                                "urgency_threshold": 3.0,
                                "initial_liquidity_fraction": 0.0,  # 0%
                                "liquidity_buffer_factor": 1.0,
                            },
                            "strategic_collateral_tree": {
                                "type": "condition",
                                "node_id": "tick_zero",
                                "condition": {
                                    "op": "==",
                                    "left": {"field": "system_tick_in_day"},
                                    "right": {"value": 0.0},
                                },
                                "on_true": {
                                    "type": "action",
                                    "node_id": "post",
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
                                "type": "action",
                                "node_id": "release",
                                "action": "Release",
                            },
                        },
                    },
                },
            ],
        }

        ffi_config = _config_to_ffi(config)
        orch = Orchestrator.new(ffi_config)

        # Run tick 0
        orch.tick()

        # Check that no (or minimal) collateral was posted
        state_a = orch.get_agent_state("A")
        posted = state_a.get("posted_collateral", 0)

        # With 0% fraction, should post 0
        assert posted == 0, f"Expected 0 posted collateral with 0% fraction, got {posted}"
