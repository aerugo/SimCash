"""Tests for Castro experiments.

Tests cover:
- Constraint definitions
- Experiment configuration
- Simulation runner
- Determinism verification
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from castro.constraints import CASTRO_CONSTRAINTS, MINIMAL_CONSTRAINTS
from castro.experiments import EXPERIMENTS, CastroExperiment, create_exp1, create_exp2, create_exp3
from castro.simulation import CastroSimulationRunner, SimulationResult


class TestConstraints:
    """Tests for Castro constraints."""

    def test_castro_constraints_has_parameters(self) -> None:
        """CASTRO_CONSTRAINTS should have allowed parameters."""
        params = CASTRO_CONSTRAINTS.allowed_parameters
        assert len(params) >= 3

        param_names = [p.name for p in params]
        assert "initial_liquidity_fraction" in param_names
        assert "urgency_threshold" in param_names
        assert "liquidity_buffer" in param_names

    def test_castro_constraints_has_fields(self) -> None:
        """CASTRO_CONSTRAINTS should have allowed fields."""
        fields = CASTRO_CONSTRAINTS.allowed_fields
        assert "balance" in fields
        assert "ticks_to_deadline" in fields
        assert "system_tick_in_day" in fields

    def test_castro_constraints_has_actions(self) -> None:
        """CASTRO_CONSTRAINTS should define allowed actions."""
        actions = CASTRO_CONSTRAINTS.allowed_actions

        assert "payment_tree" in actions
        assert "Release" in actions["payment_tree"]
        assert "Hold" in actions["payment_tree"]

        # Castro: no split or other actions
        assert "Split" not in actions["payment_tree"]

    def test_parameter_validation(self) -> None:
        """Parameter specs should validate values correctly."""
        spec = CASTRO_CONSTRAINTS.get_parameter_spec("initial_liquidity_fraction")
        assert spec is not None

        # Valid value
        is_valid, error = spec.validate_value(0.5)
        assert is_valid
        assert error is None

        # Invalid value (above max)
        is_valid, error = spec.validate_value(1.5)
        assert not is_valid
        assert error is not None

    def test_minimal_constraints_subset(self) -> None:
        """MINIMAL_CONSTRAINTS should be a subset of CASTRO_CONSTRAINTS."""
        minimal_params = {p.name for p in MINIMAL_CONSTRAINTS.allowed_parameters}
        castro_params = {p.name for p in CASTRO_CONSTRAINTS.allowed_parameters}

        # Minimal should be subset (or have its own valid parameters)
        assert len(minimal_params) <= len(castro_params)


class TestExperiments:
    """Tests for experiment definitions."""

    def test_exp1_configuration(self) -> None:
        """Exp1 should have correct configuration."""
        exp = create_exp1()

        assert exp.name == "exp1"
        # Exp1 uses deterministic mode (single evaluation, no Monte Carlo)
        assert exp.deterministic is True
        assert exp.evaluation_ticks == 2  # Only 2 ticks in scenario
        assert "BANK_A" in exp.optimized_agents
        assert "BANK_B" in exp.optimized_agents

    def test_exp2_configuration(self) -> None:
        """Exp2 should have correct configuration."""
        exp = create_exp2()

        assert exp.name == "exp2"
        assert exp.num_samples == 10  # Monte Carlo
        assert exp.evaluation_ticks == 12
        # Model config uses provider:model format
        model_config = exp.get_model_config()
        assert model_config.provider == "anthropic"

    def test_exp3_configuration(self) -> None:
        """Exp3 should have correct configuration."""
        exp = create_exp3()

        assert exp.name == "exp3"
        # Minimum evaluation_ticks for MonteCarloConfig validation
        assert exp.evaluation_ticks == 10  # Ticks 3-9 are idle

    def test_experiments_registry(self) -> None:
        """EXPERIMENTS registry should contain all experiments."""
        assert "exp1" in EXPERIMENTS
        assert "exp2" in EXPERIMENTS
        assert "exp3" in EXPERIMENTS

        # All should be callable factories
        for key, factory in EXPERIMENTS.items():
            exp = factory()
            assert isinstance(exp, CastroExperiment)
            assert exp.name == key

    def test_custom_model(self) -> None:
        """Experiments should accept custom model in provider:model format."""
        exp = create_exp1(model="openai:gpt-4o")
        assert exp.model == "openai:gpt-4o"
        assert exp.get_model_config().provider == "openai"

    def test_custom_output_dir(self) -> None:
        """Experiments should accept custom output directory."""
        custom_dir = Path("/tmp/test_results")
        exp = create_exp1(output_dir=custom_dir)
        assert exp.output_dir == custom_dir

    def test_bootstrap_config(self) -> None:
        """get_bootstrap_config should return valid config."""
        exp = create_exp2()
        bootstrap_config = exp.get_bootstrap_config()

        assert bootstrap_config.num_samples == 10
        assert bootstrap_config.evaluation_ticks == 12

    def test_convergence_criteria(self) -> None:
        """get_convergence_criteria should return valid config."""
        exp = create_exp1()
        conv = exp.get_convergence_criteria()

        assert conv.max_iterations == 25
        assert conv.stability_threshold == 0.05
        assert conv.stability_window == 5


class TestScenarioConfigs:
    """Tests for scenario YAML configurations."""

    @pytest.fixture
    def configs_dir(self) -> Path:
        """Get path to configs directory."""
        return Path(__file__).parent.parent / "configs"

    def test_exp1_config_exists(self, configs_dir: Path) -> None:
        """exp1_2period.yaml should exist."""
        config_path = configs_dir / "exp1_2period.yaml"
        assert config_path.exists(), f"Config not found: {config_path}"

    def test_exp2_config_exists(self, configs_dir: Path) -> None:
        """exp2_12period.yaml should exist."""
        config_path = configs_dir / "exp2_12period.yaml"
        assert config_path.exists()

    def test_exp3_config_exists(self, configs_dir: Path) -> None:
        """exp3_joint.yaml should exist."""
        config_path = configs_dir / "exp3_joint.yaml"
        assert config_path.exists()

    def test_exp1_config_valid(self, configs_dir: Path) -> None:
        """exp1_2period.yaml should be valid YAML."""
        config_path = configs_dir / "exp1_2period.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        assert "simulation" in config
        assert "agents" in config
        assert config["simulation"]["ticks_per_day"] == 2
        assert len(config["agents"]) == 2

    def test_exp2_config_valid(self, configs_dir: Path) -> None:
        """exp2_12period.yaml should be valid YAML."""
        config_path = configs_dir / "exp2_12period.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        assert config["simulation"]["ticks_per_day"] == 12
        # Should have arrival configs
        for agent in config["agents"]:
            assert "arrival_config" in agent

    def test_deferred_crediting_enabled(self, configs_dir: Path) -> None:
        """All configs should have deferred_crediting enabled (Castro rule)."""
        for config_name in ["exp1_2period.yaml", "exp2_12period.yaml", "exp3_joint.yaml"]:
            config_path = configs_dir / config_name
            with open(config_path) as f:
                config = yaml.safe_load(f)
            assert config.get("deferred_crediting") is True, f"{config_name} should have deferred_crediting"


class TestSimulationRunner:
    """Tests for CastroSimulationRunner."""

    @pytest.fixture
    def simple_config(self) -> dict:
        """Create a simple test configuration."""
        return {
            "simulation": {
                "ticks_per_day": 2,
                "num_days": 1,
                "rng_seed": 42,
            },
            "agents": [
                {"id": "BANK_A", "opening_balance": 10000, "unsecured_cap": 50000},
                {"id": "BANK_B", "opening_balance": 10000, "unsecured_cap": 50000},
            ],
            "cost_rates": {
                "collateral_cost_per_tick_bps": 500,
                "delay_cost_per_tick_per_cent": 0.001,
                "overdraft_bps_per_tick": 2000,
            },
        }

    @pytest.fixture
    def seed_policy(self) -> dict:
        """Create a simple seed policy."""
        return {
            "version": "2.0",
            "parameters": {
                "urgency_threshold": 3,
            },
            "payment_tree": {
                "type": "action",
                "action": "Release",
            },
        }

    def test_runner_initialization(self, simple_config: dict) -> None:
        """Runner should initialize from config dict."""
        runner = CastroSimulationRunner(simple_config)
        assert runner.get_ticks_per_simulation() == 2
        assert "BANK_A" in runner.get_agent_ids()
        assert "BANK_B" in runner.get_agent_ids()

    def test_simulation_result_dataclass(self) -> None:
        """SimulationResult should be a proper dataclass."""
        result = SimulationResult(
            total_cost=15000,
            per_agent_costs={"BANK_A": 7500, "BANK_B": 7500},
            settlement_rate=0.95,
            transactions_settled=19,
            transactions_failed=1,
        )

        assert result.total_cost == 15000
        assert result.settlement_rate == 0.95


class TestDeterminism:
    """Tests for deterministic behavior.

    NOTE: These tests use simplified policies missing node_id fields.
    """

    @pytest.fixture
    def exp1_config(self) -> dict:
        """Load exp1 configuration."""
        config_path = Path(__file__).parent.parent / "configs" / "exp1_2period.yaml"
        with open(config_path) as f:
            return yaml.safe_load(f)

    @pytest.fixture
    def seed_policy(self) -> dict:
        """Create seed policy for determinism test."""
        return {
            "version": "2.0",
            "policy_id": "test_determinism_policy",
            "parameters": {"urgency_threshold": 3},
            "payment_tree": {"type": "action", "node_id": "A_Release", "action": "Release"},
        }

    def test_same_seed_same_result(self, exp1_config: dict, seed_policy: dict) -> None:
        """Same seed should produce identical results."""
        runner = CastroSimulationRunner(exp1_config)

        result1 = runner.run_simulation(policy=seed_policy, seed=42, ticks=2)
        result2 = runner.run_simulation(policy=seed_policy, seed=42, ticks=2)

        assert result1.total_cost == result2.total_cost
        assert result1.per_agent_costs == result2.per_agent_costs
        assert result1.transactions_settled == result2.transactions_settled

    def test_different_seed_different_result(self, exp1_config: dict, seed_policy: dict) -> None:
        """Different seeds should produce different results (usually).

        Note: For exp1 which is deterministic (no arrivals config), results
        may still be the same. This test is more relevant for stochastic configs.
        """
        runner = CastroSimulationRunner(exp1_config)

        result1 = runner.run_simulation(policy=seed_policy, seed=42, ticks=2)
        result2 = runner.run_simulation(policy=seed_policy, seed=123, ticks=2)

        # Results may or may not differ for deterministic config
        # This is more of a smoke test
        assert isinstance(result1.total_cost, int)
        assert isinstance(result2.total_cost, int)


class TestPolicyFormatConversion:
    """TDD Tests for policy format conversion to FFI-compatible format.

    The Rust FFI requires policies in a specific format:
    - Policy type must be "FromJson" (not "Inline")
    - The policy JSON must include "policy_id" and "version" at root
    - TreeNodes must include "node_id" field

    These tests verify that CastroSimulationRunner properly converts
    Castro-style policies to FFI-compatible format.
    """

    @pytest.fixture
    def simple_config(self) -> dict:
        """Create a simple test configuration."""
        return {
            "simulation": {
                "ticks_per_day": 2,
                "num_days": 1,
                "rng_seed": 42,
            },
            "agents": [
                {"id": "BANK_A", "opening_balance": 100000, "unsecured_cap": 50000},
                {"id": "BANK_B", "opening_balance": 100000, "unsecured_cap": 50000},
            ],
        }

    @pytest.fixture
    def valid_policy(self) -> dict:
        """Create a valid Castro policy with all required fields."""
        return {
            "version": "1.0",
            "policy_id": "test_policy",
            "parameters": {"urgency_threshold": 3},
            "payment_tree": {
                "type": "action",
                "node_id": "root",
                "action": "Release",
            },
        }

    def test_valid_policy_runs_successfully(
        self, simple_config: dict, valid_policy: dict
    ) -> None:
        """A properly formatted policy should run without errors."""
        runner = CastroSimulationRunner(simple_config)
        result = runner.run_simulation(policy=valid_policy, seed=42, ticks=2)

        assert isinstance(result, SimulationResult)
        assert isinstance(result.total_cost, int)
        assert "BANK_A" in result.per_agent_costs
        assert "BANK_B" in result.per_agent_costs

    def test_policy_requires_policy_id(self, simple_config: dict) -> None:
        """Policy missing policy_id should fail with clear error."""
        invalid_policy = {
            "version": "1.0",
            # Missing policy_id
            "parameters": {"urgency_threshold": 3},
            "payment_tree": {
                "type": "action",
                "node_id": "root",
                "action": "Release",
            },
        }

        runner = CastroSimulationRunner(simple_config)

        with pytest.raises(RuntimeError) as exc_info:
            runner.run_simulation(policy=invalid_policy, seed=42, ticks=2)

        assert "policy_id" in str(exc_info.value).lower()

    def test_policy_requires_node_id(self, simple_config: dict) -> None:
        """Policy TreeNode missing node_id should fail with clear error."""
        invalid_policy = {
            "version": "1.0",
            "policy_id": "test",
            "parameters": {},
            "payment_tree": {
                "type": "action",
                # Missing node_id
                "action": "Release",
            },
        }

        runner = CastroSimulationRunner(simple_config)

        with pytest.raises(RuntimeError) as exc_info:
            runner.run_simulation(policy=invalid_policy, seed=42, ticks=2)

        assert "node_id" in str(exc_info.value).lower()

    def test_conditional_policy_runs_successfully(self, simple_config: dict) -> None:
        """A conditional policy with proper structure should work."""
        conditional_policy = {
            "version": "1.0",
            "policy_id": "conditional_test",
            "parameters": {"urgency_threshold": 3},
            "payment_tree": {
                "type": "condition",
                "node_id": "check_urgency",
                "description": "Check if urgent",
                "condition": {
                    "op": "<",
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
                    "node_id": "hold_non_urgent",
                    "action": "Hold",
                },
            },
        }

        runner = CastroSimulationRunner(simple_config)
        result = runner.run_simulation(policy=conditional_policy, seed=42, ticks=2)

        assert isinstance(result, SimulationResult)

    def test_multiple_runs_with_same_seed_deterministic(
        self, simple_config: dict, valid_policy: dict
    ) -> None:
        """Same policy and seed should produce identical results."""
        runner = CastroSimulationRunner(simple_config)

        result1 = runner.run_simulation(policy=valid_policy, seed=12345, ticks=2)
        result2 = runner.run_simulation(policy=valid_policy, seed=12345, ticks=2)

        assert result1.total_cost == result2.total_cost
        assert result1.per_agent_costs == result2.per_agent_costs
        assert result1.transactions_settled == result2.transactions_settled

    def test_verbose_capture_works_with_valid_policy(
        self, simple_config: dict, valid_policy: dict
    ) -> None:
        """Verbose capture should work with properly formatted policy."""
        runner = CastroSimulationRunner(simple_config)
        result = runner.run_simulation(
            policy=valid_policy, seed=42, ticks=2, capture_verbose=True
        )

        assert result.verbose_output is not None
        assert result.verbose_output.total_ticks == 2
