"""Tests for PolicyConfigBuilder protocol and StandardPolicyConfigBuilder.

These tests follow strict TDD principles:
1. Tests are written BEFORE implementation
2. Tests should FAIL initially
3. Implementation makes tests pass
4. Tests define the expected behavior, not the implementation

INVARIANT (Policy Evaluation Identity):
For any (policy, agent_config) pair, the extracted configuration MUST be
identical regardless of which code path calls the builder.
"""

from __future__ import annotations

from typing import Any

import pytest

from payment_simulator.config.policy_config_builder import (
    PolicyConfigBuilder,
    StandardPolicyConfigBuilder,
)


class TestLiquidityConfigExtraction:
    """Tests for extract_liquidity_config method."""

    @pytest.fixture
    def builder(self) -> StandardPolicyConfigBuilder:
        """Create builder instance for tests."""
        return StandardPolicyConfigBuilder()

    def test_extracts_fraction_from_nested_parameters(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """Nested policy["parameters"]["initial_liquidity_fraction"] is extracted."""
        policy: dict[str, Any] = {"parameters": {"initial_liquidity_fraction": 0.3}}
        agent_config: dict[str, Any] = {"liquidity_pool": 10_000_000, "opening_balance": 0}

        result = builder.extract_liquidity_config(policy, agent_config)

        assert result["liquidity_allocation_fraction"] == 0.3

    def test_extracts_fraction_from_flat_policy(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """Flat policy["initial_liquidity_fraction"] is extracted."""
        policy: dict[str, Any] = {"initial_liquidity_fraction": 0.25}
        agent_config: dict[str, Any] = {"liquidity_pool": 5_000_000, "opening_balance": 100_000}

        result = builder.extract_liquidity_config(policy, agent_config)

        assert result["liquidity_allocation_fraction"] == 0.25

    def test_nested_takes_precedence_over_flat(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """If both nested and flat exist, nested wins."""
        policy: dict[str, Any] = {
            "parameters": {"initial_liquidity_fraction": 0.8},
            "initial_liquidity_fraction": 0.2,  # Should be ignored
        }
        agent_config: dict[str, Any] = {"liquidity_pool": 1_000_000}

        result = builder.extract_liquidity_config(policy, agent_config)

        assert result["liquidity_allocation_fraction"] == 0.8

    def test_default_fraction_when_not_specified(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """Missing fraction defaults to 0.5 when liquidity_pool exists."""
        policy: dict[str, Any] = {}  # No fraction specified
        agent_config: dict[str, Any] = {"liquidity_pool": 1_000_000}

        result = builder.extract_liquidity_config(policy, agent_config)

        assert result["liquidity_allocation_fraction"] == 0.5

    def test_extracts_liquidity_pool_from_agent_config(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """liquidity_pool comes from agent_config, not policy."""
        policy: dict[str, Any] = {"parameters": {"initial_liquidity_fraction": 0.4}}
        agent_config: dict[str, Any] = {"liquidity_pool": 20_000_000}

        result = builder.extract_liquidity_config(policy, agent_config)

        assert result["liquidity_pool"] == 20_000_000

    def test_no_fraction_when_no_liquidity_pool(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """No liquidity_allocation_fraction if no liquidity_pool in agent_config."""
        policy: dict[str, Any] = {"parameters": {"initial_liquidity_fraction": 0.5}}
        agent_config: dict[str, Any] = {"opening_balance": 100_000}  # No liquidity_pool

        result = builder.extract_liquidity_config(policy, agent_config)

        # Should not have liquidity_allocation_fraction
        assert "liquidity_allocation_fraction" not in result

    def test_opening_balance_passthrough(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """opening_balance is extracted from agent_config."""
        policy: dict[str, Any] = {}
        agent_config: dict[str, Any] = {"opening_balance": 500_000}

        result = builder.extract_liquidity_config(policy, agent_config)

        assert result["opening_balance"] == 500_000

    def test_opening_balance_defaults_to_zero(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """opening_balance defaults to 0 if not in agent_config."""
        policy: dict[str, Any] = {}
        agent_config: dict[str, Any] = {}

        result = builder.extract_liquidity_config(policy, agent_config)

        assert result["opening_balance"] == 0


class TestCollateralConfigExtraction:
    """Tests for extract_collateral_config method."""

    @pytest.fixture
    def builder(self) -> StandardPolicyConfigBuilder:
        """Create builder instance for tests."""
        return StandardPolicyConfigBuilder()

    def test_extracts_max_collateral_capacity(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """max_collateral_capacity extracted from agent_config."""
        policy: dict[str, Any] = {}
        agent_config: dict[str, Any] = {"max_collateral_capacity": 5_000_000}

        result = builder.extract_collateral_config(policy, agent_config)

        assert result["max_collateral_capacity"] == 5_000_000

    def test_extracts_initial_collateral_fraction_nested(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """initial_collateral_fraction from nested policy structure."""
        policy: dict[str, Any] = {"parameters": {"initial_collateral_fraction": 0.6}}
        agent_config: dict[str, Any] = {"max_collateral_capacity": 3_000_000}

        result = builder.extract_collateral_config(policy, agent_config)

        assert result["initial_collateral_fraction"] == 0.6

    def test_extracts_initial_collateral_fraction_flat(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """initial_collateral_fraction from flat policy structure."""
        policy: dict[str, Any] = {"initial_collateral_fraction": 0.4}
        agent_config: dict[str, Any] = {"max_collateral_capacity": 2_000_000}

        result = builder.extract_collateral_config(policy, agent_config)

        assert result["initial_collateral_fraction"] == 0.4

    def test_no_collateral_fraction_if_not_specified(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """No initial_collateral_fraction if not in policy."""
        policy: dict[str, Any] = {}
        agent_config: dict[str, Any] = {"max_collateral_capacity": 1_000_000}

        result = builder.extract_collateral_config(policy, agent_config)

        # Should not have initial_collateral_fraction
        assert "initial_collateral_fraction" not in result


class TestEdgeCases:
    """Edge case handling tests."""

    @pytest.fixture
    def builder(self) -> StandardPolicyConfigBuilder:
        """Create builder instance for tests."""
        return StandardPolicyConfigBuilder()

    def test_empty_policy_dict(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """Empty policy should return defaults."""
        policy: dict[str, Any] = {}
        agent_config: dict[str, Any] = {"opening_balance": 100_000}

        result = builder.extract_liquidity_config(policy, agent_config)

        assert result["opening_balance"] == 100_000

    def test_empty_agent_config(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """Empty agent_config should handle gracefully."""
        policy: dict[str, Any] = {"parameters": {"initial_liquidity_fraction": 0.5}}
        agent_config: dict[str, Any] = {}

        result = builder.extract_liquidity_config(policy, agent_config)

        # No liquidity_pool, so no fraction
        assert "liquidity_allocation_fraction" not in result
        assert result["opening_balance"] == 0

    def test_none_liquidity_pool_handled(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """None value for liquidity_pool treated as absent."""
        policy: dict[str, Any] = {"parameters": {"initial_liquidity_fraction": 0.5}}
        agent_config: dict[str, Any] = {"liquidity_pool": None, "opening_balance": 50_000}

        result = builder.extract_liquidity_config(policy, agent_config)

        # None liquidity_pool should not trigger fraction extraction
        assert "liquidity_allocation_fraction" not in result

    def test_type_coercion_liquidity_pool_string(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """String liquidity_pool coerced to int."""
        policy: dict[str, Any] = {"parameters": {"initial_liquidity_fraction": 0.5}}
        agent_config: dict[str, Any] = {"liquidity_pool": "1000000"}  # String, not int

        result = builder.extract_liquidity_config(policy, agent_config)

        assert result["liquidity_pool"] == 1_000_000
        assert isinstance(result["liquidity_pool"], int)

    def test_type_coercion_fraction_string(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """String fraction coerced to float."""
        policy: dict[str, Any] = {"parameters": {"initial_liquidity_fraction": "0.75"}}
        agent_config: dict[str, Any] = {"liquidity_pool": 1_000_000}

        result = builder.extract_liquidity_config(policy, agent_config)

        assert result["liquidity_allocation_fraction"] == 0.75
        assert isinstance(result["liquidity_allocation_fraction"], float)

    def test_type_coercion_fraction_int(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """Int fraction coerced to float."""
        policy: dict[str, Any] = {"parameters": {"initial_liquidity_fraction": 1}}
        agent_config: dict[str, Any] = {"liquidity_pool": 1_000_000}

        result = builder.extract_liquidity_config(policy, agent_config)

        assert result["liquidity_allocation_fraction"] == 1.0
        assert isinstance(result["liquidity_allocation_fraction"], float)

    def test_type_coercion_opening_balance_float(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """Float opening_balance coerced to int."""
        policy: dict[str, Any] = {}
        agent_config: dict[str, Any] = {"opening_balance": 100000.99}  # float, not int

        result = builder.extract_liquidity_config(policy, agent_config)

        assert result["opening_balance"] == 100000
        assert isinstance(result["opening_balance"], int)


class TestProtocolCompliance:
    """Tests verifying protocol compliance."""

    def test_standard_builder_implements_protocol(self) -> None:
        """StandardPolicyConfigBuilder implements PolicyConfigBuilder protocol."""
        builder = StandardPolicyConfigBuilder()

        assert isinstance(builder, PolicyConfigBuilder)

    def test_protocol_is_runtime_checkable(self) -> None:
        """Protocol can be used with isinstance at runtime."""
        builder = StandardPolicyConfigBuilder()

        # This should not raise
        result = isinstance(builder, PolicyConfigBuilder)

        assert result is True


class TestTypeAnnotations:
    """Tests verifying TypedDict return types."""

    @pytest.fixture
    def builder(self) -> StandardPolicyConfigBuilder:
        """Create builder instance for tests."""
        return StandardPolicyConfigBuilder()

    def test_liquidity_config_is_dict(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """LiquidityConfig return is a dict."""
        policy: dict[str, Any] = {"parameters": {"initial_liquidity_fraction": 0.5}}
        agent_config: dict[str, Any] = {"liquidity_pool": 1_000_000}

        result = builder.extract_liquidity_config(policy, agent_config)

        assert isinstance(result, dict)

    def test_collateral_config_is_dict(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """CollateralConfig return is a dict."""
        policy: dict[str, Any] = {}
        agent_config: dict[str, Any] = {"max_collateral_capacity": 1_000_000}

        result = builder.extract_collateral_config(policy, agent_config)

        assert isinstance(result, dict)
