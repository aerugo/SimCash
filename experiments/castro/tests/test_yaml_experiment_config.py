"""TDD tests for YamlExperimentConfig.

YamlExperimentConfig wraps a dict from load_experiment() and
implements ExperimentConfigProtocol.
"""

from __future__ import annotations

from pathlib import Path

import pytest


class TestYamlExperimentConfigCreation:
    """Tests for creating YamlExperimentConfig."""

    def test_yaml_config_importable(self) -> None:
        """YamlExperimentConfig should be importable."""
        from castro.experiment_config import YamlExperimentConfig

        assert YamlExperimentConfig is not None

    def test_yaml_config_from_load_experiment(self) -> None:
        """YamlExperimentConfig can be created from load_experiment() dict."""
        from castro.experiment_config import YamlExperimentConfig
        from castro.experiment_loader import load_experiment

        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        assert yaml_config is not None

    def test_yaml_config_implements_protocol(self) -> None:
        """YamlExperimentConfig should implement ExperimentConfigProtocol."""
        from castro.experiment_config import (
            ExperimentConfigProtocol,
            YamlExperimentConfig,
        )
        from castro.experiment_loader import load_experiment

        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        assert isinstance(yaml_config, ExperimentConfigProtocol)


class TestYamlExperimentConfigProperties:
    """Tests for YamlExperimentConfig properties."""

    def test_name_property(self) -> None:
        """name property returns experiment name."""
        from castro.experiment_config import YamlExperimentConfig
        from castro.experiment_loader import load_experiment

        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        assert yaml_config.name == "exp1"

    def test_description_property(self) -> None:
        """description property returns experiment description."""
        from castro.experiment_config import YamlExperimentConfig
        from castro.experiment_loader import load_experiment

        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        assert isinstance(yaml_config.description, str)
        assert len(yaml_config.description) > 0

    def test_master_seed_property(self) -> None:
        """master_seed property returns integer seed."""
        from castro.experiment_config import YamlExperimentConfig
        from castro.experiment_loader import load_experiment

        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        assert isinstance(yaml_config.master_seed, int)

    def test_scenario_path_property(self) -> None:
        """scenario_path property returns Path."""
        from castro.experiment_config import YamlExperimentConfig
        from castro.experiment_loader import load_experiment

        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        assert isinstance(yaml_config.scenario_path, Path)

    def test_optimized_agents_property(self) -> None:
        """optimized_agents property returns list of agent IDs."""
        from castro.experiment_config import YamlExperimentConfig
        from castro.experiment_loader import load_experiment

        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        assert isinstance(yaml_config.optimized_agents, list)
        assert all(isinstance(a, str) for a in yaml_config.optimized_agents)


class TestYamlExperimentConfigMethods:
    """Tests for YamlExperimentConfig methods."""

    def test_get_convergence_criteria_returns_correct_type(self) -> None:
        """get_convergence_criteria() returns ConvergenceCriteria."""
        from castro.experiment_config import YamlExperimentConfig
        from castro.experiment_loader import load_experiment
        from payment_simulator.ai_cash_mgmt import ConvergenceCriteria

        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        criteria = yaml_config.get_convergence_criteria()
        assert isinstance(criteria, ConvergenceCriteria)

    def test_get_convergence_criteria_values(self) -> None:
        """get_convergence_criteria() returns correct values from YAML."""
        from castro.experiment_config import YamlExperimentConfig
        from castro.experiment_loader import load_experiment

        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        criteria = yaml_config.get_convergence_criteria()

        # Values should match YAML config
        assert criteria.max_iterations == config_dict["convergence"]["max_iterations"]
        assert (
            criteria.stability_threshold
            == config_dict["convergence"]["stability_threshold"]
        )

    def test_get_bootstrap_config_returns_correct_type(self) -> None:
        """get_bootstrap_config() returns BootstrapConfig."""
        from castro.experiment_config import YamlExperimentConfig
        from castro.experiment_loader import load_experiment
        from payment_simulator.ai_cash_mgmt import BootstrapConfig

        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        bootstrap = yaml_config.get_bootstrap_config()
        assert isinstance(bootstrap, BootstrapConfig)

    def test_get_bootstrap_config_deterministic_mode(self) -> None:
        """get_bootstrap_config() handles deterministic mode."""
        from castro.experiment_config import YamlExperimentConfig
        from castro.experiment_loader import load_experiment

        # exp1 is deterministic
        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        bootstrap = yaml_config.get_bootstrap_config()
        assert bootstrap.deterministic is True

    def test_get_bootstrap_config_bootstrap_mode(self) -> None:
        """get_bootstrap_config() handles bootstrap mode."""
        from castro.experiment_config import YamlExperimentConfig
        from castro.experiment_loader import load_experiment

        # exp2 uses bootstrap sampling
        config_dict = load_experiment("exp2")
        yaml_config = YamlExperimentConfig(config_dict)
        bootstrap = yaml_config.get_bootstrap_config()
        assert bootstrap.deterministic is False
        assert bootstrap.num_samples >= 5

    def test_get_model_config_returns_correct_type(self) -> None:
        """get_model_config() returns LLMConfig."""
        from castro.experiment_config import YamlExperimentConfig
        from castro.experiment_loader import load_experiment
        from payment_simulator.llm import LLMConfig

        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        model = yaml_config.get_model_config()
        assert isinstance(model, LLMConfig)

    def test_get_model_config_values(self) -> None:
        """get_model_config() returns correct values from YAML."""
        from castro.experiment_config import YamlExperimentConfig
        from castro.experiment_loader import load_experiment

        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        model = yaml_config.get_model_config()
        assert model.model == config_dict["llm"]["model"]

    def test_get_output_config_returns_correct_type(self) -> None:
        """get_output_config() returns OutputConfig."""
        from castro.experiment_config import YamlExperimentConfig
        from castro.experiment_loader import load_experiment
        from payment_simulator.ai_cash_mgmt import OutputConfig

        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        output = yaml_config.get_output_config()
        assert isinstance(output, OutputConfig)


class TestYamlExperimentConfigOverrides:
    """Tests for CLI override support."""

    def test_model_override_affects_get_model_config(self) -> None:
        """Model override should affect get_model_config()."""
        from castro.experiment_config import YamlExperimentConfig
        from castro.experiment_loader import load_experiment

        config_dict = load_experiment("exp1", model_override="openai:gpt-4o")
        yaml_config = YamlExperimentConfig(config_dict)
        model = yaml_config.get_model_config()
        assert model.model == "openai:gpt-4o"

    def test_seed_override_affects_master_seed(self) -> None:
        """Seed override should affect master_seed property."""
        from castro.experiment_config import YamlExperimentConfig
        from castro.experiment_loader import load_experiment

        config_dict = load_experiment("exp1", seed_override=99999)
        yaml_config = YamlExperimentConfig(config_dict)
        assert yaml_config.master_seed == 99999

    def test_max_iter_override_affects_convergence(self) -> None:
        """Max iter override should affect get_convergence_criteria()."""
        from castro.experiment_config import YamlExperimentConfig
        from castro.experiment_loader import load_experiment

        config_dict = load_experiment("exp1", max_iter_override=100)
        yaml_config = YamlExperimentConfig(config_dict)
        criteria = yaml_config.get_convergence_criteria()
        assert criteria.max_iterations == 100

    def test_output_dir_override(self) -> None:
        """Output dir parameter should affect get_output_config()."""
        from castro.experiment_config import YamlExperimentConfig
        from castro.experiment_loader import load_experiment

        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict, output_dir=Path("/tmp/custom"))
        output = yaml_config.get_output_config()
        assert "/tmp/custom" in output.database_path
