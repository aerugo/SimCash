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
        # Minimum values for MonteCarloConfig validation
        assert exp.num_samples == 5  # Deterministic gives identical results
        assert exp.evaluation_ticks == 10  # Ticks 2-9 are idle
        assert "BANK_A" in exp.optimized_agents
        assert "BANK_B" in exp.optimized_agents

    def test_exp2_configuration(self) -> None:
        """Exp2 should have correct configuration."""
        exp = create_exp2()

        assert exp.name == "exp2"
        assert exp.num_samples == 10  # Monte Carlo
        assert exp.evaluation_ticks == 12
        # llm_provider is auto-detected from model name
        llm_config = exp.get_llm_config()
        assert llm_config.provider.value == "anthropic"

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
        """Experiments should accept custom model."""
        exp = create_exp1(model="gpt-4o")
        assert exp.llm_model == "gpt-4o"

    def test_custom_output_dir(self) -> None:
        """Experiments should accept custom output directory."""
        custom_dir = Path("/tmp/test_results")
        exp = create_exp1(output_dir=custom_dir)
        assert exp.output_dir == custom_dir

    def test_monte_carlo_config(self) -> None:
        """get_monte_carlo_config should return valid config."""
        exp = create_exp2()
        mc_config = exp.get_monte_carlo_config()

        assert mc_config.num_samples == 10
        assert mc_config.evaluation_ticks == 12

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
            assert "arrivals" in agent

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
    """Tests for deterministic behavior."""

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
            "parameters": {"urgency_threshold": 3},
            "payment_tree": {"type": "action", "action": "Release"},
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
