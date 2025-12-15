"""Scenario Config Interpretation Identity Tests.

CRITICAL: These tests enforce the Scenario Config Interpretation Identity (INV-10):

    For any scenario S and agent A:
    extraction(path_1, S, A) == extraction(path_2, S, A)

This ensures agent configuration is extracted identically regardless of which
code path performs the extraction (deterministic simulation vs bootstrap evaluation).

This is analogous to:
- INV-5 (Replay Identity) for display output
- INV-9 (Policy Evaluation Identity) for policy parameters

Any failure here indicates a potential violation of the invariant.
"""

from __future__ import annotations

from typing import Any

import pytest

from payment_simulator.config.scenario_config_builder import (
    AgentScenarioConfig,
    ScenarioConfigBuilder,
    StandardScenarioConfigBuilder,
)


class TestScenarioConfigExtractionIdentity:
    """Tests verifying identical extraction regardless of code path.

    CRITICAL: These tests enforce INV-10 - all code paths must produce
    identical AgentScenarioConfig for the same (scenario, agent_id) pair.
    """

    def test_same_scenario_same_config_identity(self) -> None:
        """Same scenario MUST produce identical config on multiple extractions."""
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

        # Multiple extractions must be identical
        config1 = builder.extract_agent_config("BANK_A")
        config2 = builder.extract_agent_config("BANK_A")
        config3 = builder.extract_agent_config("BANK_A")

        assert config1 == config2
        assert config2 == config3

    def test_different_builder_instances_same_config_identity(self) -> None:
        """Different builder instances with same scenario MUST return equal configs."""
        scenario: dict[str, Any] = {
            "agents": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 5_000_000,
                }
            ]
        }

        builder1 = StandardScenarioConfigBuilder(scenario)
        builder2 = StandardScenarioConfigBuilder(scenario)

        config1 = builder1.extract_agent_config("BANK_A")
        config2 = builder2.extract_agent_config("BANK_A")

        assert config1 == config2

    def test_scenario_copy_produces_identical_config(self) -> None:
        """A copy of the scenario dict MUST produce identical config."""
        scenario: dict[str, Any] = {
            "agents": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 5_000_000,
                }
            ]
        }

        # Create a shallow copy
        scenario_copy = dict(scenario)
        scenario_copy["agents"] = list(scenario["agents"])

        builder1 = StandardScenarioConfigBuilder(scenario)
        builder2 = StandardScenarioConfigBuilder(scenario_copy)

        config1 = builder1.extract_agent_config("BANK_A")
        config2 = builder2.extract_agent_config("BANK_A")

        assert config1 == config2


class TestScenarioConfigTypeCoercionIdentity:
    """Tests verifying INV-1 type coercion is consistent.

    All monetary values MUST be coerced to int identically,
    regardless of input type (string, float, int).
    """

    def test_string_opening_balance_coerced_to_int(self) -> None:
        """String opening_balance MUST be coerced to int consistently."""
        scenario: dict[str, Any] = {
            "agents": [{"id": "A", "opening_balance": "10000000"}]  # String
        }

        config = StandardScenarioConfigBuilder(scenario).extract_agent_config("A")

        assert config.opening_balance == 10000000
        assert isinstance(config.opening_balance, int)

    def test_float_opening_balance_coerced_to_int(self) -> None:
        """Float opening_balance MUST be truncated to int consistently."""
        scenario: dict[str, Any] = {
            "agents": [{"id": "A", "opening_balance": 10000000.0}]  # Float
        }

        config = StandardScenarioConfigBuilder(scenario).extract_agent_config("A")

        assert config.opening_balance == 10000000
        assert isinstance(config.opening_balance, int)

    def test_string_credit_limit_coerced_to_int(self) -> None:
        """String unsecured_cap MUST be coerced to int consistently."""
        scenario: dict[str, Any] = {
            "agents": [{"id": "A", "opening_balance": 0, "unsecured_cap": "5000000"}]
        }

        config = StandardScenarioConfigBuilder(scenario).extract_agent_config("A")

        assert config.credit_limit == 5000000
        assert isinstance(config.credit_limit, int)

    def test_optional_fields_coerced_when_present(self) -> None:
        """Optional fields (max_collateral_capacity, liquidity_pool) MUST be coerced."""
        scenario: dict[str, Any] = {
            "agents": [
                {
                    "id": "A",
                    "opening_balance": 0,
                    "max_collateral_capacity": "2000000",  # String
                    "liquidity_pool": 3000000.5,  # Float
                }
            ]
        }

        config = StandardScenarioConfigBuilder(scenario).extract_agent_config("A")

        assert config.max_collateral_capacity == 2000000
        assert isinstance(config.max_collateral_capacity, int)
        assert config.liquidity_pool == 3000000
        assert isinstance(config.liquidity_pool, int)


class TestScenarioConfigDefaultValueIdentity:
    """Tests verifying default values are applied consistently."""

    def test_missing_opening_balance_defaults_to_zero(self) -> None:
        """Missing opening_balance MUST default to 0."""
        scenario: dict[str, Any] = {"agents": [{"id": "A"}]}

        config = StandardScenarioConfigBuilder(scenario).extract_agent_config("A")

        assert config.opening_balance == 0

    def test_missing_credit_limit_defaults_to_zero(self) -> None:
        """Missing unsecured_cap MUST default to 0."""
        scenario: dict[str, Any] = {"agents": [{"id": "A", "opening_balance": 100}]}

        config = StandardScenarioConfigBuilder(scenario).extract_agent_config("A")

        assert config.credit_limit == 0

    def test_missing_optional_fields_are_none(self) -> None:
        """Missing optional fields MUST be None (not 0)."""
        scenario: dict[str, Any] = {"agents": [{"id": "A", "opening_balance": 100}]}

        config = StandardScenarioConfigBuilder(scenario).extract_agent_config("A")

        assert config.max_collateral_capacity is None
        assert config.liquidity_pool is None


class TestScenarioConfigIntegrationIdentity:
    """Tests verifying identical behavior when used in OptimizationLoop.

    These tests ensure the ScenarioConfigBuilder is correctly integrated
    into the optimization workflow.
    """

    def test_optimization_loop_uses_scenario_builder(self) -> None:
        """OptimizationLoop MUST use StandardScenarioConfigBuilder."""
        from unittest.mock import MagicMock, patch

        from payment_simulator.experiments.runner.optimization import OptimizationLoop

        mock_config = MagicMock()
        mock_config.name = "test"
        mock_config.master_seed = 42
        mock_config.convergence.max_iterations = 1
        mock_config.convergence.stability_threshold = 0.05
        mock_config.convergence.stability_window = 3
        mock_config.convergence.improvement_threshold = 0.01
        mock_config.evaluation.mode = "deterministic"
        mock_config.evaluation.num_samples = 1
        mock_config.evaluation.ticks = 10
        mock_config.optimized_agents = ("BANK_A",)
        mock_config.get_constraints.return_value = None
        mock_config.llm.model = "test"
        mock_config.prompt_customization = None

        loop = OptimizationLoop(config=mock_config)

        # Verify the _scenario_builder attribute exists (starts as None, lazily init)
        assert hasattr(loop, "_scenario_builder")

        # Verify _get_scenario_builder method exists
        assert hasattr(loop, "_get_scenario_builder")
        assert callable(loop._get_scenario_builder)

    def test_scenario_builder_returns_standard_implementation(self) -> None:
        """_get_scenario_builder MUST return StandardScenarioConfigBuilder."""
        from unittest.mock import MagicMock, patch

        from payment_simulator.experiments.runner.optimization import OptimizationLoop

        mock_config = MagicMock()
        mock_config.name = "test"
        mock_config.master_seed = 42
        mock_config.convergence.max_iterations = 1
        mock_config.convergence.stability_threshold = 0.05
        mock_config.convergence.stability_window = 3
        mock_config.convergence.improvement_threshold = 0.01
        mock_config.evaluation.mode = "deterministic"
        mock_config.evaluation.num_samples = 1
        mock_config.evaluation.ticks = 10
        mock_config.optimized_agents = ("BANK_A",)
        mock_config.get_constraints.return_value = None
        mock_config.llm.model = "test"
        mock_config.prompt_customization = None

        loop = OptimizationLoop(config=mock_config)

        # Mock scenario loading
        scenario = {"agents": [{"id": "BANK_A", "opening_balance": 1000000}]}
        with patch.object(loop, "_load_scenario_config", return_value=scenario):
            builder = loop._get_scenario_builder()

            # Verify it's the standard implementation
            assert isinstance(builder, StandardScenarioConfigBuilder)
            # Also verify it satisfies the Protocol
            assert isinstance(builder, ScenarioConfigBuilder)


class TestAgentScenarioConfigImmutability:
    """Tests verifying AgentScenarioConfig is immutable (frozen)."""

    def test_config_is_frozen(self) -> None:
        """AgentScenarioConfig MUST be immutable."""
        import dataclasses

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
        """AgentScenarioConfig MUST be hashable for use in sets/dicts."""
        config = AgentScenarioConfig(
            agent_id="A",
            opening_balance=100,
            credit_limit=50,
            max_collateral_capacity=None,
            liquidity_pool=None,
        )

        # Should be hashable
        hash(config)

        # Should work in sets
        config_set = {config}
        assert config in config_set

        # Should work as dict key
        config_dict = {config: "value"}
        assert config_dict[config] == "value"


class TestScenarioConfigEndToEndIdentity:
    """End-to-end tests verifying identical extraction in real scenarios.

    These tests use realistic scenario configurations and verify
    INV-10 is maintained throughout.
    """

    def test_full_scenario_extraction_identity(self) -> None:
        """Full scenario with all fields MUST extract identically."""
        scenario: dict[str, Any] = {
            "agents": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 5_000_000,
                    "max_collateral_capacity": 2_000_000,
                    "liquidity_pool": 3_000_000,
                    # Extra fields should be ignored
                    "arrival_config": {"rate_per_tick": 0.5},
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 8_000_000,
                    "unsecured_cap": 4_000_000,
                },
            ]
        }

        builder = StandardScenarioConfigBuilder(scenario)

        config_a = builder.extract_agent_config("BANK_A")
        config_b = builder.extract_agent_config("BANK_B")

        # Verify BANK_A extraction
        assert config_a.agent_id == "BANK_A"
        assert config_a.opening_balance == 10_000_000
        assert config_a.credit_limit == 5_000_000
        assert config_a.max_collateral_capacity == 2_000_000
        assert config_a.liquidity_pool == 3_000_000

        # Verify BANK_B extraction
        assert config_b.agent_id == "BANK_B"
        assert config_b.opening_balance == 8_000_000
        assert config_b.credit_limit == 4_000_000
        assert config_b.max_collateral_capacity is None
        assert config_b.liquidity_pool is None

    def test_list_agent_ids_identity(self) -> None:
        """list_agent_ids MUST return all agent IDs consistently."""
        scenario: dict[str, Any] = {
            "agents": [
                {"id": "BANK_A", "opening_balance": 0},
                {"id": "BANK_B", "opening_balance": 0},
                {"id": "BANK_C", "opening_balance": 0},
            ]
        }

        builder1 = StandardScenarioConfigBuilder(scenario)
        builder2 = StandardScenarioConfigBuilder(scenario)

        ids1 = set(builder1.list_agent_ids())
        ids2 = set(builder2.list_agent_ids())

        assert ids1 == ids2
        assert ids1 == {"BANK_A", "BANK_B", "BANK_C"}
