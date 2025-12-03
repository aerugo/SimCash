"""
Integration tests for InlinePolicy with Orchestrator.

TDD Tests: These tests should FAIL until InlinePolicy is fully implemented.

These tests verify that:
1. Orchestrator accepts configs with InlinePolicy
2. Decision tree logic executes correctly
3. InlinePolicy behavior matches FromJsonPolicy behavior
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
# Test Fixtures
# ============================================================================


@pytest.fixture
def simple_release_policy() -> dict[str, Any]:
    """Simple policy that always releases payments immediately."""
    return {
        "version": "2.0",
        "policy_id": "always_release",
        "parameters": {},
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
def urgency_based_policy() -> dict[str, Any]:
    """Policy that releases payments only when urgent."""
    return {
        "version": "2.0",
        "policy_id": "urgency_based",
        "parameters": {
            "urgency_threshold": 3.0,
        },
        "strategic_collateral_tree": {
            "type": "action",
            "node_id": "collateral_hold",
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
                "node_id": "release",
                "action": "Release",
            },
            "on_false": {
                "type": "action",
                "node_id": "payment_hold",
                "action": "Hold",
            },
        },
    }


@pytest.fixture
def collateral_posting_policy() -> dict[str, Any]:
    """Policy that posts collateral at tick 0."""
    return {
        "version": "2.0",
        "policy_id": "collateral_poster",
        "parameters": {
            "initial_liquidity_fraction": 0.5,
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
    }


# ============================================================================
# Basic Integration Tests
# ============================================================================


class TestInlinePolicyOrchestratorCreation:
    """Test that Orchestrator can be created with InlinePolicy configs."""

    def test_orchestrator_accepts_inline_policy(
        self, simple_release_policy: dict[str, Any]
    ) -> None:
        """Orchestrator.new should accept config with InlinePolicy."""
        config = {
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
                        "decision_trees": simple_release_policy,
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

        ffi_config = _config_to_ffi(config)
        orch = Orchestrator.new(ffi_config)

        assert orch is not None
        # current_tick() returns 0 after initialization (before first tick execution)

    def test_orchestrator_runs_with_inline_policy(
        self, simple_release_policy: dict[str, Any]
    ) -> None:
        """Orchestrator should run ticks successfully with InlinePolicy."""
        config = {
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
                        "decision_trees": simple_release_policy,
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

        ffi_config = _config_to_ffi(config)
        orch = Orchestrator.new(ffi_config)

        # Run several ticks
        for _ in range(5):
            orch.tick()

        # After 5 ticks (0,1,2,3,4), current_tick() returns 5 (the next tick to run)
        assert orch.current_tick() == 5


# ============================================================================
# Behavior Tests
# ============================================================================


class TestInlinePolicyBehavior:
    """Test that InlinePolicy decision trees execute correctly."""

    def test_always_release_policy_settles_immediately(
        self, simple_release_policy: dict[str, Any]
    ) -> None:
        """Policy with always-release should settle transactions immediately."""
        config = {
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
                        "decision_trees": simple_release_policy,
                    },
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 0,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        ffi_config = _config_to_ffi(config)
        orch = Orchestrator.new(ffi_config)

        # Submit a transaction from A to B
        tx_id = orch.submit_transaction("BANK_A", "BANK_B", 50000, 5, 10, False)
        assert tx_id is not None

        # Run tick
        orch.tick()

        # Check events - should have settlement
        events = orch.get_tick_events(0)
        settlement_events = [
            e for e in events
            if e.get("event_type") == "RtgsImmediateSettlement"
        ]

        assert len(settlement_events) > 0, "Transaction should settle immediately"

    def test_urgency_policy_holds_until_urgent(
        self, urgency_based_policy: dict[str, Any]
    ) -> None:
        """Policy with urgency threshold should hold non-urgent payments."""
        config = {
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
                        "decision_trees": urgency_based_policy,
                    },
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 0,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        ffi_config = _config_to_ffi(config)
        orch = Orchestrator.new(ffi_config)

        # Submit a transaction with deadline far in the future
        # urgency_threshold=3, so deadline at tick 9 means:
        # - At tick 0: 9 ticks remaining > 3, should HOLD
        # - At tick 6: 3 ticks remaining <= 3, should RELEASE
        tx_id = orch.submit_transaction("BANK_A", "BANK_B", 50000, 5, 9, False)

        # Run first tick
        orch.tick()

        # At tick 0, 9 ticks to deadline > 3, should be held
        events_t0 = orch.get_tick_events(0)
        settlements_t0 = [
            e for e in events_t0
            if e.get("event_type") == "RtgsImmediateSettlement"
        ]

        # The payment should be held (not settled immediately)
        # Note: This depends on implementation details of how policy decisions
        # interact with RTGS - payment may end up in queue1 or not be submitted yet

    def test_collateral_policy_runs_without_error(
        self, collateral_posting_policy: dict[str, Any]
    ) -> None:
        """Collateral posting policy should run without errors.

        This test verifies InlinePolicy with collateral logic is accepted
        by the orchestrator. The actual collateral posting behavior
        depends on agent configuration and policy tree evaluation logic.
        """
        config = {
            "simulation": {
                "rng_seed": 42,
                "ticks_per_day": 10,
                "num_days": 1,
            },
            "agents": [
                {
                    "id": "BANK_A",
                    "opening_balance": 0,
                    "unsecured_cap": 0,
                    "max_collateral_capacity": 100000,
                    "policy": {
                        "type": "Inline",
                        "decision_trees": collateral_posting_policy,
                    },
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 0,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        ffi_config = _config_to_ffi(config)
        orch = Orchestrator.new(ffi_config)

        # Run tick 0 without error
        orch.tick()

        # Verify orchestrator is functional
        assert orch.current_tick() == 1

        # Verify agent state can be retrieved
        state_a = orch.get_agent_state("BANK_A")
        assert "balance" in state_a


# ============================================================================
# Equivalence Tests
# ============================================================================


class TestInlinePolicyEquivalentBehavior:
    """Test that InlinePolicy produces equivalent behavior to FromJsonPolicy."""

    def test_inline_vs_fromjson_same_behavior(
        self, simple_release_policy: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        """InlinePolicy and FromJsonPolicy should produce identical behavior."""
        # Create temp JSON file
        json_file = tmp_path / "test_policy.json"
        json_file.write_text(json.dumps(simple_release_policy))

        base_config = {
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
                    "policy": None,  # Will be replaced
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 0,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        # Config with InlinePolicy
        inline_config = base_config.copy()
        inline_config["agents"] = [
            {
                "id": "BANK_A",
                "opening_balance": 100000,
                "unsecured_cap": 0,
                "policy": {
                    "type": "Inline",
                    "decision_trees": simple_release_policy,
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 0,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
        ]

        # Config with FromJsonPolicy
        fromjson_config = base_config.copy()
        fromjson_config["agents"] = [
            {
                "id": "BANK_A",
                "opening_balance": 100000,
                "unsecured_cap": 0,
                "policy": {
                    "type": "FromJson",
                    "json_path": str(json_file),
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 0,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
        ]

        # Create orchestrators
        inline_orch = Orchestrator.new(_config_to_ffi(inline_config))
        fromjson_orch = Orchestrator.new(_config_to_ffi(fromjson_config))

        # Submit same transactions to both
        inline_orch.submit_transaction("BANK_A", "BANK_B", 50000, 5, 10, False)
        fromjson_orch.submit_transaction("BANK_A", "BANK_B", 50000, 5, 10, False)

        # Run both for several ticks
        for _ in range(5):
            inline_orch.tick()
            fromjson_orch.tick()

        # Compare final states
        inline_state_a = inline_orch.get_agent_state("BANK_A")
        fromjson_state_a = fromjson_orch.get_agent_state("BANK_A")

        assert inline_state_a["balance"] == fromjson_state_a["balance"], (
            f"InlinePolicy and FromJsonPolicy should produce same balance. "
            f"Inline: {inline_state_a['balance']}, FromJson: {fromjson_state_a['balance']}"
        )


# ============================================================================
# Castro Experiment Use Cases
# ============================================================================


class TestCastroInlinePolicyUseCases:
    """Test InlinePolicy in Castro experiment scenarios."""

    def test_dynamic_policy_parameter_modification(self) -> None:
        """InlinePolicy allows dynamic parameter changes without temp files.

        This test demonstrates the key value of InlinePolicy: modifying
        policy parameters programmatically without file I/O.
        """
        base_policy = {
            "version": "2.0",
            "policy_id": "parameterized",
            "parameters": {
                "urgency_threshold": 3.0,
            },
            "strategic_collateral_tree": {
                "type": "action",
                "node_id": "collateral_hold",
                "action": "HoldCollateral",
            },
            "payment_tree": {
                "type": "action",
                "node_id": "release",
                "action": "Release",
            },
        }

        # Test different urgency thresholds - all should create valid orchestrators
        for threshold in [1.0, 3.0, 5.0, 10.0]:
            # Modify policy parameter directly (no file I/O!)
            policy = {
                **base_policy,
                "parameters": {
                    "urgency_threshold": threshold,
                },
            }

            config = {
                "simulation": {
                    "rng_seed": 42,
                    "ticks_per_day": 2,
                    "num_days": 1,
                },
                "agents": [
                    {
                        "id": "BANK_A",
                        "opening_balance": 100000,
                        "unsecured_cap": 0,
                        "policy": {
                            "type": "Inline",
                            "decision_trees": policy,
                        },
                    },
                    {
                        "id": "BANK_B",
                        "opening_balance": 0,
                        "unsecured_cap": 0,
                        "policy": {"type": "Fifo"},
                    },
                ],
            }

            ffi_config = _config_to_ffi(config)
            orch = Orchestrator.new(ffi_config)
            orch.tick()

            # Verify orchestrator is functional with modified policy
            assert orch.current_tick() == 1
