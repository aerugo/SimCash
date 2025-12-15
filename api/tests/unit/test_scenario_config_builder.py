"""ScenarioConfigBuilder unit tests.

CRITICAL: These tests enforce the Scenario Config Interpretation Identity (INV-10):

    For any scenario S and agent A:
    extraction(path_1, S, A) == extraction(path_2, S, A)

This ensures agents are configured identically regardless of which code path
(deterministic simulation vs bootstrap evaluation) processes the scenario.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from payment_simulator.config.scenario_config_builder import (
    AgentScenarioConfig,
    ScenarioConfigBuilder,
    StandardScenarioConfigBuilder,
)


class TestAgentScenarioConfig:
    """Tests for AgentScenarioConfig dataclass."""

    def test_create_config_with_all_fields(self) -> None:
        """AgentScenarioConfig can be created with all fields."""
        config = AgentScenarioConfig(
            agent_id="BANK_A",
            opening_balance=1_000_000,
            credit_limit=500_000,
            max_collateral_capacity=2_000_000,
            liquidity_pool=3_000_000,
        )
        assert config.agent_id == "BANK_A"
        assert config.opening_balance == 1_000_000
        assert config.credit_limit == 500_000
        assert config.max_collateral_capacity == 2_000_000
        assert config.liquidity_pool == 3_000_000

    def test_create_config_with_optional_none(self) -> None:
        """AgentScenarioConfig can have None for optional fields."""
        config = AgentScenarioConfig(
            agent_id="BANK_A",
            opening_balance=100,
            credit_limit=50,
            max_collateral_capacity=None,
            liquidity_pool=None,
        )
        assert config.max_collateral_capacity is None
        assert config.liquidity_pool is None

    def test_config_is_frozen(self) -> None:
        """AgentScenarioConfig MUST be immutable (frozen dataclass)."""
        config = AgentScenarioConfig(
            agent_id="A",
            opening_balance=100,
            credit_limit=50,
            max_collateral_capacity=None,
            liquidity_pool=None,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.opening_balance = 200  # type: ignore[misc]

    def test_config_is_hashable(self) -> None:
        """AgentScenarioConfig MUST be hashable (for use in sets/dicts)."""
        config = AgentScenarioConfig(
            agent_id="A",
            opening_balance=100,
            credit_limit=50,
            max_collateral_capacity=None,
            liquidity_pool=None,
        )
        # Should not raise
        hash(config)
        # Should work in set
        config_set = {config}
        assert config in config_set


class TestStandardScenarioConfigBuilder:
    """Tests for StandardScenarioConfigBuilder."""

    # =========================================================================
    # Basic Extraction Tests
    # =========================================================================

    def test_extract_opening_balance(self) -> None:
        """Opening balance MUST be extracted as integer cents."""
        scenario: dict[str, Any] = {
            "agents": [{"id": "BANK_A", "opening_balance": 1_000_000}]
        }
        builder = StandardScenarioConfigBuilder(scenario)
        config = builder.extract_agent_config("BANK_A")
        assert config.opening_balance == 1_000_000

    def test_extract_credit_limit_from_unsecured_cap(self) -> None:
        """Credit limit MUST be extracted from unsecured_cap field."""
        scenario: dict[str, Any] = {
            "agents": [{"id": "BANK_A", "unsecured_cap": 500_000, "opening_balance": 0}]
        }
        builder = StandardScenarioConfigBuilder(scenario)
        config = builder.extract_agent_config("BANK_A")
        assert config.credit_limit == 500_000

    def test_extract_agent_id(self) -> None:
        """Agent ID MUST be preserved in config."""
        scenario: dict[str, Any] = {
            "agents": [{"id": "BANK_A", "opening_balance": 0}]
        }
        builder = StandardScenarioConfigBuilder(scenario)
        config = builder.extract_agent_config("BANK_A")
        assert config.agent_id == "BANK_A"

    # =========================================================================
    # Optional Field Tests
    # =========================================================================

    def test_extract_max_collateral_capacity_present(self) -> None:
        """max_collateral_capacity extracted when present."""
        scenario: dict[str, Any] = {
            "agents": [
                {"id": "A", "opening_balance": 0, "max_collateral_capacity": 2_000_000}
            ]
        }
        config = StandardScenarioConfigBuilder(scenario).extract_agent_config("A")
        assert config.max_collateral_capacity == 2_000_000

    def test_extract_max_collateral_capacity_absent(self) -> None:
        """max_collateral_capacity is None when not present."""
        scenario: dict[str, Any] = {"agents": [{"id": "A", "opening_balance": 0}]}
        config = StandardScenarioConfigBuilder(scenario).extract_agent_config("A")
        assert config.max_collateral_capacity is None

    def test_extract_liquidity_pool_present(self) -> None:
        """liquidity_pool extracted when present."""
        scenario: dict[str, Any] = {
            "agents": [{"id": "A", "opening_balance": 0, "liquidity_pool": 5_000_000}]
        }
        config = StandardScenarioConfigBuilder(scenario).extract_agent_config("A")
        assert config.liquidity_pool == 5_000_000

    def test_extract_liquidity_pool_absent(self) -> None:
        """liquidity_pool is None when not present."""
        scenario: dict[str, Any] = {"agents": [{"id": "A", "opening_balance": 0}]}
        config = StandardScenarioConfigBuilder(scenario).extract_agent_config("A")
        assert config.liquidity_pool is None

    # =========================================================================
    # Type Coercion Tests (INV-1: Money as Integer Cents)
    # =========================================================================

    def test_type_coercion_string_to_int_opening_balance(self) -> None:
        """String opening_balance MUST be coerced to int (INV-1)."""
        scenario: dict[str, Any] = {
            "agents": [{"id": "A", "opening_balance": "1000000"}]
        }
        config = StandardScenarioConfigBuilder(scenario).extract_agent_config("A")
        assert config.opening_balance == 1000000
        assert isinstance(config.opening_balance, int)

    def test_type_coercion_float_to_int_opening_balance(self) -> None:
        """Float opening_balance MUST be coerced to int (INV-1)."""
        scenario: dict[str, Any] = {
            "agents": [{"id": "A", "opening_balance": 1000000.0}]
        }
        config = StandardScenarioConfigBuilder(scenario).extract_agent_config("A")
        assert config.opening_balance == 1000000
        assert isinstance(config.opening_balance, int)

    def test_type_coercion_string_to_int_credit_limit(self) -> None:
        """String unsecured_cap MUST be coerced to int (INV-1)."""
        scenario: dict[str, Any] = {
            "agents": [{"id": "A", "opening_balance": 0, "unsecured_cap": "500000"}]
        }
        config = StandardScenarioConfigBuilder(scenario).extract_agent_config("A")
        assert config.credit_limit == 500000
        assert isinstance(config.credit_limit, int)

    def test_type_coercion_optional_fields(self) -> None:
        """Optional fields MUST be coerced to int when present (INV-1)."""
        scenario: dict[str, Any] = {
            "agents": [
                {
                    "id": "A",
                    "opening_balance": 0,
                    "max_collateral_capacity": "2000000",
                    "liquidity_pool": 3000000.5,  # Will truncate to 3000000
                }
            ]
        }
        config = StandardScenarioConfigBuilder(scenario).extract_agent_config("A")
        assert config.max_collateral_capacity == 2000000
        assert isinstance(config.max_collateral_capacity, int)
        assert config.liquidity_pool == 3000000
        assert isinstance(config.liquidity_pool, int)

    # =========================================================================
    # Default Value Tests
    # =========================================================================

    def test_default_opening_balance_zero(self) -> None:
        """Missing opening_balance defaults to 0."""
        scenario: dict[str, Any] = {"agents": [{"id": "A"}]}
        config = StandardScenarioConfigBuilder(scenario).extract_agent_config("A")
        assert config.opening_balance == 0

    def test_default_credit_limit_zero(self) -> None:
        """Missing unsecured_cap defaults to 0."""
        scenario: dict[str, Any] = {"agents": [{"id": "A", "opening_balance": 100}]}
        config = StandardScenarioConfigBuilder(scenario).extract_agent_config("A")
        assert config.credit_limit == 0

    # =========================================================================
    # Error Handling Tests
    # =========================================================================

    def test_agent_not_found_raises_keyerror(self) -> None:
        """Requesting unknown agent MUST raise KeyError."""
        scenario: dict[str, Any] = {
            "agents": [{"id": "BANK_A", "opening_balance": 0}]
        }
        builder = StandardScenarioConfigBuilder(scenario)
        with pytest.raises(KeyError, match="Agent 'BANK_B' not found"):
            builder.extract_agent_config("BANK_B")

    def test_empty_agents_list(self) -> None:
        """Empty agents list should work (list_agent_ids returns empty)."""
        scenario: dict[str, Any] = {"agents": []}
        builder = StandardScenarioConfigBuilder(scenario)
        assert builder.list_agent_ids() == []

    def test_missing_agents_key(self) -> None:
        """Missing agents key should behave like empty list."""
        scenario: dict[str, Any] = {}
        builder = StandardScenarioConfigBuilder(scenario)
        assert builder.list_agent_ids() == []

    # =========================================================================
    # list_agent_ids Tests
    # =========================================================================

    def test_list_agent_ids_single(self) -> None:
        """list_agent_ids returns single agent ID."""
        scenario: dict[str, Any] = {
            "agents": [{"id": "BANK_A", "opening_balance": 0}]
        }
        builder = StandardScenarioConfigBuilder(scenario)
        assert builder.list_agent_ids() == ["BANK_A"]

    def test_list_agent_ids_multiple(self) -> None:
        """list_agent_ids returns all agent IDs."""
        scenario: dict[str, Any] = {
            "agents": [
                {"id": "BANK_A", "opening_balance": 0},
                {"id": "BANK_B", "opening_balance": 0},
                {"id": "BANK_C", "opening_balance": 0},
            ]
        }
        builder = StandardScenarioConfigBuilder(scenario)
        ids = builder.list_agent_ids()
        assert set(ids) == {"BANK_A", "BANK_B", "BANK_C"}

    # =========================================================================
    # Protocol Compliance Tests
    # =========================================================================

    def test_standard_builder_is_protocol_compliant(self) -> None:
        """StandardScenarioConfigBuilder MUST satisfy Protocol."""
        scenario: dict[str, Any] = {"agents": []}
        builder = StandardScenarioConfigBuilder(scenario)
        assert isinstance(builder, ScenarioConfigBuilder)

    # =========================================================================
    # Full Scenario Tests
    # =========================================================================

    def test_extract_full_agent_config(self) -> None:
        """Test extraction with all fields populated."""
        scenario: dict[str, Any] = {
            "agents": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 5_000_000,
                    "max_collateral_capacity": 2_000_000,
                    "liquidity_pool": 3_000_000,
                }
            ]
        }
        builder = StandardScenarioConfigBuilder(scenario)
        config = builder.extract_agent_config("BANK_A")

        assert config.agent_id == "BANK_A"
        assert config.opening_balance == 10_000_000
        assert config.credit_limit == 5_000_000
        assert config.max_collateral_capacity == 2_000_000
        assert config.liquidity_pool == 3_000_000

    def test_extract_multiple_agents(self) -> None:
        """Test extraction of multiple agents from same scenario."""
        scenario: dict[str, Any] = {
            "agents": [
                {"id": "A", "opening_balance": 100, "unsecured_cap": 50},
                {"id": "B", "opening_balance": 200, "unsecured_cap": 100},
            ]
        }
        builder = StandardScenarioConfigBuilder(scenario)

        config_a = builder.extract_agent_config("A")
        config_b = builder.extract_agent_config("B")

        assert config_a.opening_balance == 100
        assert config_a.credit_limit == 50
        assert config_b.opening_balance == 200
        assert config_b.credit_limit == 100


class TestScenarioConfigIdentity:
    """Tests verifying identical extraction regardless of how builder is used.

    These tests enforce INV-10: Scenario Config Interpretation Identity.
    """

    def test_same_scenario_same_config_multiple_extractions(self) -> None:
        """Multiple extractions from same builder MUST return equal configs."""
        scenario: dict[str, Any] = {
            "agents": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 500_000,
                    "max_collateral_capacity": 200_000,
                    "liquidity_pool": 300_000,
                }
            ]
        }
        builder = StandardScenarioConfigBuilder(scenario)

        config1 = builder.extract_agent_config("BANK_A")
        config2 = builder.extract_agent_config("BANK_A")

        assert config1 == config2

    def test_same_scenario_different_builders_same_config(self) -> None:
        """Different builder instances with same scenario MUST return equal configs."""
        scenario: dict[str, Any] = {
            "agents": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 500_000,
                }
            ]
        }

        builder1 = StandardScenarioConfigBuilder(scenario)
        builder2 = StandardScenarioConfigBuilder(scenario)

        config1 = builder1.extract_agent_config("BANK_A")
        config2 = builder2.extract_agent_config("BANK_A")

        assert config1 == config2
