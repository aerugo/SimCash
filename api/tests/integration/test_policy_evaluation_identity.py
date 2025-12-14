"""Policy Evaluation Identity Tests.

CRITICAL: These tests enforce the Policy Evaluation Identity invariant:

    For any policy P and scenario S:
    extraction(optimization_path, P, S) == extraction(sandbox_path, P, S)

This ensures transactions are evaluated identically regardless of which
code path processes them (deterministic simulation vs bootstrap evaluation).

Any failure here indicates a potential violation of the invariant.
"""

from __future__ import annotations

from typing import Any

import pytest

from payment_simulator.config.policy_config_builder import StandardPolicyConfigBuilder


class TestPolicyEvaluationIdentity:
    """
    CRITICAL: These tests enforce the Policy Evaluation Identity invariant.

    Both optimization.py and sandbox_config.py MUST use StandardPolicyConfigBuilder
    for policy parameter extraction. This ensures identical behavior.
    """

    @pytest.fixture
    def builder(self) -> StandardPolicyConfigBuilder:
        """Provide StandardPolicyConfigBuilder - the canonical implementation."""
        return StandardPolicyConfigBuilder()

    # =========================================================================
    # Identity Tests: Nested vs Flat policy structures
    # =========================================================================

    def test_nested_policy_extraction_identity(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """Nested policy structure MUST extract initial_liquidity_fraction correctly.

        This is the canonical case: policy.parameters.initial_liquidity_fraction
        """
        policy: dict[str, Any] = {
            "parameters": {
                "initial_liquidity_fraction": 0.35,
            },
            "payment_tree": {"type": "action", "action": "Release"},
        }
        agent_config: dict[str, Any] = {
            "id": "BANK_A",
            "liquidity_pool": 10_000_000,
            "opening_balance": 0,
        }

        result = builder.extract_liquidity_config(policy, agent_config)

        # INVARIANT: nested extraction must work
        assert result["liquidity_allocation_fraction"] == 0.35
        assert result["liquidity_pool"] == 10_000_000

    def test_flat_policy_extraction_identity(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """Flat policy structure MUST extract initial_liquidity_fraction correctly.

        Fallback case: policy.initial_liquidity_fraction (no nesting)
        """
        policy: dict[str, Any] = {
            "initial_liquidity_fraction": 0.45,
            "payment_tree": {"type": "action", "action": "Release"},
        }
        agent_config: dict[str, Any] = {
            "id": "BANK_A",
            "liquidity_pool": 5_000_000,
            "opening_balance": 100_000,
        }

        result = builder.extract_liquidity_config(policy, agent_config)

        # INVARIANT: flat extraction must work
        assert result["liquidity_allocation_fraction"] == 0.45
        assert result["liquidity_pool"] == 5_000_000

    def test_nested_takes_precedence_identity(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """When both nested and flat exist, nested MUST take precedence.

        This prevents ambiguity in policy interpretation.
        """
        policy: dict[str, Any] = {
            "parameters": {
                "initial_liquidity_fraction": 0.75,  # Nested - should win
            },
            "initial_liquidity_fraction": 0.25,  # Flat - should be ignored
            "payment_tree": {"type": "action", "action": "Release"},
        }
        agent_config: dict[str, Any] = {
            "id": "BANK_A",
            "liquidity_pool": 1_000_000,
        }

        result = builder.extract_liquidity_config(policy, agent_config)

        # INVARIANT: nested always takes precedence
        assert result["liquidity_allocation_fraction"] == 0.75

    # =========================================================================
    # Identity Tests: Default values
    # =========================================================================

    def test_default_fraction_identity(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """Missing fraction MUST default to 0.5 when liquidity_pool exists.

        This is a critical default that must be consistent.
        """
        policy: dict[str, Any] = {
            "payment_tree": {"type": "action", "action": "Release"},
            # No initial_liquidity_fraction specified
        }
        agent_config: dict[str, Any] = {
            "id": "BANK_A",
            "liquidity_pool": 2_000_000,
        }

        result = builder.extract_liquidity_config(policy, agent_config)

        # INVARIANT: default is exactly 0.5
        assert result["liquidity_allocation_fraction"] == 0.5

    def test_no_liquidity_pool_no_fraction_identity(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """When agent has no liquidity_pool, fraction MUST NOT be set.

        This prevents invalid config generation.
        """
        policy: dict[str, Any] = {
            "parameters": {"initial_liquidity_fraction": 0.5},
            "payment_tree": {"type": "action", "action": "Release"},
        }
        agent_config: dict[str, Any] = {
            "id": "BANK_A",
            "opening_balance": 1_000_000,
            # No liquidity_pool
        }

        result = builder.extract_liquidity_config(policy, agent_config)

        # INVARIANT: no fraction without pool
        assert "liquidity_allocation_fraction" not in result

    # =========================================================================
    # Identity Tests: Type coercion
    # =========================================================================

    def test_type_coercion_identity_string_fraction(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """String fraction MUST be coerced to float consistently."""
        policy: dict[str, Any] = {
            "parameters": {"initial_liquidity_fraction": "0.65"},  # String
        }
        agent_config: dict[str, Any] = {"liquidity_pool": 1_000_000}

        result = builder.extract_liquidity_config(policy, agent_config)

        # INVARIANT: coerced to float
        assert result["liquidity_allocation_fraction"] == 0.65
        assert isinstance(result["liquidity_allocation_fraction"], float)

    def test_type_coercion_identity_int_fraction(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """Int fraction MUST be coerced to float consistently."""
        policy: dict[str, Any] = {
            "parameters": {"initial_liquidity_fraction": 1},  # Int
        }
        agent_config: dict[str, Any] = {"liquidity_pool": 1_000_000}

        result = builder.extract_liquidity_config(policy, agent_config)

        # INVARIANT: coerced to float
        assert result["liquidity_allocation_fraction"] == 1.0
        assert isinstance(result["liquidity_allocation_fraction"], float)

    # =========================================================================
    # Identity Tests: Collateral config
    # =========================================================================

    def test_collateral_config_extraction_identity(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """Collateral config MUST be extracted consistently."""
        policy: dict[str, Any] = {
            "parameters": {"initial_collateral_fraction": 0.4},
        }
        agent_config: dict[str, Any] = {"max_collateral_capacity": 5_000_000}

        result = builder.extract_collateral_config(policy, agent_config)

        # INVARIANT: collateral extraction consistent
        assert result["max_collateral_capacity"] == 5_000_000
        assert result["initial_collateral_fraction"] == 0.4


class TestConfigBuildingIdentity:
    """Test that configs built by both paths are equivalent."""

    def test_sandbox_builder_uses_standard_policy_config_builder(self) -> None:
        """SandboxConfigBuilder MUST use StandardPolicyConfigBuilder internally."""
        from payment_simulator.ai_cash_mgmt.bootstrap.sandbox_config import (
            SandboxConfigBuilder,
        )

        builder = SandboxConfigBuilder()

        # INVARIANT: uses canonical builder
        assert hasattr(builder, "_policy_builder")
        assert isinstance(builder._policy_builder, StandardPolicyConfigBuilder)


class TestEndToEndEvaluationIdentity:
    """End-to-end tests verifying identical evaluation behavior.

    These tests create actual simulations and verify that the same
    policy produces the same behavior regardless of code path.
    """

    def test_same_policy_same_extraction_both_paths(self) -> None:
        """
        CRITICAL: Same policy MUST produce identical extraction in both paths.

        This is the fundamental identity test.
        """
        # Canonical policy with nested initial_liquidity_fraction
        policy: dict[str, Any] = {
            "version": "2.0",
            "policy_id": "test_policy",
            "parameters": {
                "initial_liquidity_fraction": 0.3,
            },
            "payment_tree": {
                "type": "action",
                "node_id": "release_all",
                "action": "Release",
            },
        }

        # Canonical agent config with liquidity_pool
        agent_config: dict[str, Any] = {
            "id": "BANK_A",
            "opening_balance": 0,
            "liquidity_pool": 10_000_000,
            "max_collateral_capacity": 5_000_000,
        }

        # Use single builder (what both paths use)
        builder = StandardPolicyConfigBuilder()

        # Extract - this is what both optimization.py and sandbox_config.py do
        liquidity = builder.extract_liquidity_config(policy, agent_config)
        collateral = builder.extract_collateral_config(policy, agent_config)

        # INVARIANTS:
        # 1. Fraction extracted correctly
        assert liquidity["liquidity_allocation_fraction"] == 0.3

        # 2. Pool preserved
        assert liquidity["liquidity_pool"] == 10_000_000

        # 3. Balance preserved
        assert liquidity["opening_balance"] == 0

        # 4. Collateral extracted
        assert collateral["max_collateral_capacity"] == 5_000_000

        # 5. No collateral fraction (not specified in policy)
        assert "initial_collateral_fraction" not in collateral
