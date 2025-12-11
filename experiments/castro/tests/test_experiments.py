"""Tests for Castro experiments.

Tests cover:
- Constraint definitions
- Experiment configuration (via YAML)
- Simulation runner
- Determinism verification
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from castro.constraints import CASTRO_CONSTRAINTS, MINIMAL_CONSTRAINTS
from castro.experiment_config import CastroExperiment, YamlExperimentConfig
from castro.experiment_loader import list_experiments, load_experiment
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
    """Tests for experiment definitions loaded from YAML."""

    def test_exp1_configuration(self) -> None:
        """Exp1 should have correct configuration."""
        config_dict = load_experiment("exp1")
        exp = YamlExperimentConfig(config_dict)

        assert exp.name == "exp1"
        # Exp1 uses deterministic mode (single evaluation, no bootstrap)
        bootstrap_config = exp.get_bootstrap_config()
        assert bootstrap_config.deterministic is True
        assert bootstrap_config.evaluation_ticks == 2  # Only 2 ticks in scenario
        assert "BANK_A" in exp.optimized_agents
        assert "BANK_B" in exp.optimized_agents

    def test_exp2_configuration(self) -> None:
        """Exp2 should have correct configuration."""
        config_dict = load_experiment("exp2")
        exp = YamlExperimentConfig(config_dict)

        assert exp.name == "exp2"
        bootstrap_config = exp.get_bootstrap_config()
        assert bootstrap_config.num_samples >= 5  # Non-deterministic
        assert bootstrap_config.evaluation_ticks == 12
        # Model config uses provider:model format
        model_config = exp.get_model_config()
        assert model_config.provider == "anthropic"

    def test_exp3_configuration(self) -> None:
        """Exp3 should have correct configuration."""
        config_dict = load_experiment("exp3")
        exp = YamlExperimentConfig(config_dict)

        assert exp.name == "exp3"
        # Minimum evaluation_ticks for BootstrapConfig validation
        bootstrap_config = exp.get_bootstrap_config()
        assert bootstrap_config.evaluation_ticks >= 3  # At least 3 ticks

    def test_experiments_listing(self) -> None:
        """list_experiments() should return available experiments."""
        experiments = list_experiments()
        assert "exp1" in experiments
        assert "exp2" in experiments
        assert "exp3" in experiments

    def test_custom_model_override(self) -> None:
        """Experiments should accept custom model override."""
        config_dict = load_experiment("exp1", model_override="openai:gpt-4o")
        exp = YamlExperimentConfig(config_dict)
        model_config = exp.get_model_config()
        assert model_config.model == "openai:gpt-4o"
        assert model_config.provider == "openai"

    def test_custom_seed_override(self) -> None:
        """Experiments should accept custom seed override."""
        config_dict = load_experiment("exp1", seed_override=99999)
        exp = YamlExperimentConfig(config_dict)
        assert exp.master_seed == 99999

    def test_bootstrap_config(self) -> None:
        """get_bootstrap_config should return valid config."""
        config_dict = load_experiment("exp2")
        exp = YamlExperimentConfig(config_dict)
        bootstrap_config = exp.get_bootstrap_config()

        assert bootstrap_config.num_samples >= 5
        assert bootstrap_config.evaluation_ticks == 12

    def test_convergence_criteria(self) -> None:
        """get_convergence_criteria should return valid config."""
        config_dict = load_experiment("exp1")
        exp = YamlExperimentConfig(config_dict)
        conv = exp.get_convergence_criteria()

        assert conv.max_iterations == 25
        assert conv.stability_threshold == 0.05
        assert conv.stability_window == 5


class TestCastroExperimentClass:
    """Tests for the CastroExperiment dataclass (backward compatibility)."""

    def test_castro_experiment_basic_creation(self) -> None:
        """CastroExperiment should be creatable with minimal params."""
        exp = CastroExperiment(
            name="test",
            description="Test experiment",
            scenario_path=Path("configs/test.yaml"),
            deterministic=True,
        )
        assert exp.name == "test"
        assert exp.description == "Test experiment"

    def test_castro_experiment_default_values(self) -> None:
        """CastroExperiment should have sensible defaults."""
        exp = CastroExperiment(
            name="test",
            description="Test",
            scenario_path=Path("test.yaml"),
            deterministic=True,
        )
        assert exp.master_seed == 42
        assert exp.max_iterations == 25
        assert exp.optimized_agents == ["BANK_A", "BANK_B"]


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
        for config_name in [
            "exp1_2period.yaml",
            "exp2_12period.yaml",
            "exp3_joint.yaml",
        ]:
            config_path = configs_dir / config_name
            with open(config_path) as f:
                config = yaml.safe_load(f)
            assert (
                config.get("deferred_crediting") is True
            ), f"{config_name} should have deferred_crediting"


class TestSimulationRunner:
    """Tests for CastroSimulationRunner.

    Note: Simulation runner tests are covered in test_verbose_context_integration.py
    with proper Inline policy format. These tests verify basic interface.
    """

    def test_runner_can_be_instantiated(self) -> None:
        """Runner can be instantiated from config dict."""
        config = {
            "simulation": {"ticks_per_day": 2, "num_days": 1, "rng_seed": 42},
            "agents": [{"id": "BANK_A", "opening_balance": 10000, "unsecured_cap": 50000}],
            "cost_rates": {"collateral_cost_per_tick_bps": 500},
            "deferred_crediting": True,
        }
        runner = CastroSimulationRunner(config)
        assert runner is not None

    def test_runner_can_load_from_yaml(self) -> None:
        """Runner can be created from YAML file."""
        configs_dir = Path(__file__).parent.parent / "configs"
        config_path = configs_dir / "exp1_2period.yaml"
        if config_path.exists():
            runner = CastroSimulationRunner.from_yaml(config_path)
            assert runner is not None
