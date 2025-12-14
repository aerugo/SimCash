"""Unit tests for PolicyConfigBuilder Protocol and StandardPolicyConfigBuilder.

Tests ensure identical policy interpretation between main simulation
and bootstrap evaluation (replay identity guarantee).
"""

from __future__ import annotations

import pytest

from payment_simulator.config.policy_config_builder import (
    AgentLiquidityConfig,
    PolicyConfigBuilder,
    StandardPolicyConfigBuilder,
)


class TestStandardPolicyConfigBuilder:
    """Tests for StandardPolicyConfigBuilder implementation."""

    @pytest.fixture
    def builder(self) -> StandardPolicyConfigBuilder:
        """Fixture for StandardPolicyConfigBuilder."""
        return StandardPolicyConfigBuilder()

    def test_protocol_conformance(self, builder: StandardPolicyConfigBuilder) -> None:
        """Verify builder conforms to PolicyConfigBuilder protocol."""
        assert isinstance(builder, PolicyConfigBuilder)

    def test_nested_policy_structure(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """Test extraction from nested policy structure."""
        policy = {"parameters": {"initial_liquidity_fraction": 0.25}}
        agent_config = {"liquidity_pool": 10_000_000, "opening_balance": 0}

        result = builder.extract_liquidity_config(policy, agent_config)

        assert result["liquidity_pool"] == 10_000_000
        assert result["liquidity_allocation_fraction"] == 0.25
        assert result["opening_balance"] == 0

    def test_flat_policy_structure(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """Test extraction from flat policy structure."""
        policy = {"initial_liquidity_fraction": 0.15}
        agent_config = {"liquidity_pool": 5_000_000, "opening_balance": 100_000}

        result = builder.extract_liquidity_config(policy, agent_config)

        assert result["liquidity_pool"] == 5_000_000
        assert result["liquidity_allocation_fraction"] == 0.15
        assert result["opening_balance"] == 100_000

    def test_nested_vs_flat_policy_identical_results(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """Both nested and flat policy structures produce same result."""
        agent_config = {"liquidity_pool": 1_000_000, "opening_balance": 0}

        nested_policy = {"parameters": {"initial_liquidity_fraction": 0.15}}
        flat_policy = {"initial_liquidity_fraction": 0.15}

        nested_result = builder.extract_liquidity_config(nested_policy, agent_config)
        flat_result = builder.extract_liquidity_config(flat_policy, agent_config)

        assert nested_result == flat_result

    def test_default_fraction_when_missing(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """Missing fraction defaults to 0.5 (50%)."""
        policy: dict[str, object] = {}
        agent_config = {"liquidity_pool": 1_000_000, "opening_balance": 0}

        result = builder.extract_liquidity_config(policy, agent_config)

        assert result["liquidity_allocation_fraction"] == 0.5

    def test_no_liquidity_pool_skips_fraction(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """Without liquidity_pool, fraction is not extracted."""
        policy = {"initial_liquidity_fraction": 0.25}
        agent_config = {"opening_balance": 100_000}

        result = builder.extract_liquidity_config(policy, agent_config)

        assert "liquidity_allocation_fraction" not in result
        assert "liquidity_pool" not in result
        assert result["opening_balance"] == 100_000

    def test_max_collateral_capacity_passthrough(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """max_collateral_capacity is passed through."""
        policy: dict[str, object] = {}
        agent_config = {
            "max_collateral_capacity": 500_000,
            "opening_balance": 100_000,
        }

        result = builder.extract_liquidity_config(policy, agent_config)

        assert result["max_collateral_capacity"] == 500_000
        assert result["opening_balance"] == 100_000

    def test_both_modes_together(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """Both liquidity_pool and max_collateral_capacity can coexist."""
        policy = {"initial_liquidity_fraction": 0.3}
        agent_config = {
            "liquidity_pool": 2_000_000,
            "max_collateral_capacity": 500_000,
            "opening_balance": 50_000,
        }

        result = builder.extract_liquidity_config(policy, agent_config)

        assert result["liquidity_pool"] == 2_000_000
        assert result["liquidity_allocation_fraction"] == 0.3
        assert result["max_collateral_capacity"] == 500_000
        assert result["opening_balance"] == 50_000

    def test_type_conversion_string_fraction(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """String fraction is converted to float."""
        policy = {"initial_liquidity_fraction": "0.42"}
        agent_config = {"liquidity_pool": 1_000_000, "opening_balance": 0}

        result = builder.extract_liquidity_config(policy, agent_config)

        assert result["liquidity_allocation_fraction"] == 0.42
        assert isinstance(result["liquidity_allocation_fraction"], float)

    def test_type_conversion_string_amounts(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """String amounts are converted to int."""
        policy: dict[str, object] = {}
        agent_config = {
            "liquidity_pool": "1000000",
            "max_collateral_capacity": "500000",
            "opening_balance": "100000",
        }

        result = builder.extract_liquidity_config(policy, agent_config)

        assert result["liquidity_pool"] == 1_000_000
        assert result["max_collateral_capacity"] == 500_000
        assert result["opening_balance"] == 100_000

    def test_default_opening_balance(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """Missing opening_balance defaults to 0."""
        policy: dict[str, object] = {}
        agent_config: dict[str, object] = {}

        result = builder.extract_liquidity_config(policy, agent_config)

        assert result["opening_balance"] == 0

    def test_nested_takes_precedence(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """Nested parameters.initial_liquidity_fraction takes precedence over flat."""
        policy = {
            "initial_liquidity_fraction": 0.1,  # Flat (lower priority)
            "parameters": {"initial_liquidity_fraction": 0.9},  # Nested (higher priority)
        }
        agent_config = {"liquidity_pool": 1_000_000, "opening_balance": 0}

        result = builder.extract_liquidity_config(policy, agent_config)

        # Nested value should take precedence
        assert result["liquidity_allocation_fraction"] == 0.9


class TestAgentLiquidityConfigTypedDict:
    """Tests for AgentLiquidityConfig TypedDict structure."""

    def test_typed_dict_structure(self) -> None:
        """Verify TypedDict has expected optional fields."""
        # AgentLiquidityConfig should accept these fields
        config: AgentLiquidityConfig = {
            "liquidity_pool": 1_000_000,
            "liquidity_allocation_fraction": 0.5,
            "max_collateral_capacity": 500_000,
            "opening_balance": 100_000,
        }

        assert config["liquidity_pool"] == 1_000_000
        assert config["liquidity_allocation_fraction"] == 0.5
        assert config["max_collateral_capacity"] == 500_000
        assert config["opening_balance"] == 100_000

    def test_partial_config_allowed(self) -> None:
        """Partial config (not all fields) is allowed."""
        config: AgentLiquidityConfig = {"opening_balance": 50_000}
        assert config["opening_balance"] == 50_000
