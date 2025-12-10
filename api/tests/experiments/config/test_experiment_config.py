"""Tests for ExperimentConfig YAML loading.

These tests verify the experiment configuration system for loading
YAML-defined experiments with evaluation, convergence, LLM, and
output settings.
"""

from __future__ import annotations

from pathlib import Path

import pytest


class TestEvaluationConfig:
    """Tests for EvaluationConfig dataclass."""

    def test_bootstrap_mode_requires_num_samples(self) -> None:
        """Bootstrap mode requires num_samples."""
        from payment_simulator.experiments.config.experiment_config import (
            EvaluationConfig,
        )

        config = EvaluationConfig(mode="bootstrap", num_samples=10, ticks=12)
        assert config.num_samples == 10

    def test_defaults_mode_to_bootstrap(self) -> None:
        """Default mode is bootstrap."""
        from payment_simulator.experiments.config.experiment_config import (
            EvaluationConfig,
        )

        config = EvaluationConfig(ticks=12)
        assert config.mode == "bootstrap"

    def test_defaults_num_samples_to_10(self) -> None:
        """Default num_samples is 10."""
        from payment_simulator.experiments.config.experiment_config import (
            EvaluationConfig,
        )

        config = EvaluationConfig(ticks=12)
        assert config.num_samples == 10

    def test_is_frozen(self) -> None:
        """EvaluationConfig is immutable."""
        from payment_simulator.experiments.config.experiment_config import (
            EvaluationConfig,
        )

        config = EvaluationConfig(ticks=12)
        with pytest.raises(AttributeError):
            config.mode = "deterministic"  # type: ignore

    def test_raises_on_invalid_mode(self) -> None:
        """Raises ValueError on invalid mode."""
        from payment_simulator.experiments.config.experiment_config import (
            EvaluationConfig,
        )

        with pytest.raises(ValueError, match="Invalid evaluation mode"):
            EvaluationConfig(mode="invalid", ticks=12)


class TestOutputConfig:
    """Tests for OutputConfig dataclass."""

    def test_default_directory_is_results(self) -> None:
        """Default directory is 'results'."""
        from payment_simulator.experiments.config.experiment_config import OutputConfig

        config = OutputConfig()
        assert config.directory == Path("results")

    def test_default_database_is_experiments_db(self) -> None:
        """Default database is 'experiments.db'."""
        from payment_simulator.experiments.config.experiment_config import OutputConfig

        config = OutputConfig()
        assert config.database == "experiments.db"

    def test_default_verbose_is_true(self) -> None:
        """Default verbose is True."""
        from payment_simulator.experiments.config.experiment_config import OutputConfig

        config = OutputConfig()
        assert config.verbose is True

    def test_is_frozen(self) -> None:
        """OutputConfig is immutable."""
        from payment_simulator.experiments.config.experiment_config import OutputConfig

        config = OutputConfig()
        with pytest.raises(AttributeError):
            config.directory = Path("other")  # type: ignore


class TestConvergenceConfig:
    """Tests for ConvergenceConfig dataclass."""

    def test_default_max_iterations(self) -> None:
        """Default max_iterations is 50."""
        from payment_simulator.experiments.config.experiment_config import (
            ConvergenceConfig,
        )

        config = ConvergenceConfig()
        assert config.max_iterations == 50

    def test_default_stability_threshold(self) -> None:
        """Default stability_threshold is 0.05."""
        from payment_simulator.experiments.config.experiment_config import (
            ConvergenceConfig,
        )

        config = ConvergenceConfig()
        assert config.stability_threshold == 0.05

    def test_default_stability_window(self) -> None:
        """Default stability_window is 5."""
        from payment_simulator.experiments.config.experiment_config import (
            ConvergenceConfig,
        )

        config = ConvergenceConfig()
        assert config.stability_window == 5

    def test_default_improvement_threshold(self) -> None:
        """Default improvement_threshold is 0.01."""
        from payment_simulator.experiments.config.experiment_config import (
            ConvergenceConfig,
        )

        config = ConvergenceConfig()
        assert config.improvement_threshold == 0.01

    def test_is_frozen(self) -> None:
        """ConvergenceConfig is immutable."""
        from payment_simulator.experiments.config.experiment_config import (
            ConvergenceConfig,
        )

        config = ConvergenceConfig()
        with pytest.raises(AttributeError):
            config.max_iterations = 100  # type: ignore


class TestExperimentConfig:
    """Tests for ExperimentConfig YAML loading."""

    @pytest.fixture
    def valid_yaml_path(self, tmp_path: Path) -> Path:
        """Create valid experiment YAML."""
        content = """
name: test_experiment
description: "Test experiment for unit tests"
scenario: configs/test_scenario.yaml
evaluation:
  mode: bootstrap
  num_samples: 10
  ticks: 12
convergence:
  max_iterations: 25
  stability_threshold: 0.05
  stability_window: 5
  improvement_threshold: 0.01
llm:
  model: "anthropic:claude-sonnet-4-5"
  temperature: 0.0
optimized_agents:
  - BANK_A
  - BANK_B
constraints: castro.constraints.CASTRO_CONSTRAINTS
output:
  directory: results
  database: test.db
"""
        yaml_path = tmp_path / "experiment.yaml"
        yaml_path.write_text(content)
        return yaml_path

    def test_loads_from_yaml(self, valid_yaml_path: Path) -> None:
        """ExperimentConfig loads from YAML file."""
        from payment_simulator.experiments.config.experiment_config import (
            ExperimentConfig,
        )

        config = ExperimentConfig.from_yaml(valid_yaml_path)
        assert config.name == "test_experiment"
        assert config.description == "Test experiment for unit tests"

    def test_loads_scenario_path(self, valid_yaml_path: Path) -> None:
        """Loads scenario path as Path object."""
        from payment_simulator.experiments.config.experiment_config import (
            ExperimentConfig,
        )

        config = ExperimentConfig.from_yaml(valid_yaml_path)
        assert config.scenario_path == Path("configs/test_scenario.yaml")

    def test_loads_evaluation_config(self, valid_yaml_path: Path) -> None:
        """Loads nested evaluation config."""
        from payment_simulator.experiments.config.experiment_config import (
            ExperimentConfig,
        )

        config = ExperimentConfig.from_yaml(valid_yaml_path)
        assert config.evaluation.mode == "bootstrap"
        assert config.evaluation.num_samples == 10
        assert config.evaluation.ticks == 12

    def test_loads_convergence_config(self, valid_yaml_path: Path) -> None:
        """Loads convergence criteria."""
        from payment_simulator.experiments.config.experiment_config import (
            ExperimentConfig,
        )

        config = ExperimentConfig.from_yaml(valid_yaml_path)
        assert config.convergence.max_iterations == 25
        assert config.convergence.stability_threshold == 0.05

    def test_loads_llm_config(self, valid_yaml_path: Path) -> None:
        """Loads LLM configuration."""
        from payment_simulator.experiments.config.experiment_config import (
            ExperimentConfig,
        )

        config = ExperimentConfig.from_yaml(valid_yaml_path)
        assert config.llm.model == "anthropic:claude-sonnet-4-5"
        assert config.llm.temperature == 0.0

    def test_loads_optimized_agents(self, valid_yaml_path: Path) -> None:
        """Loads list of optimized agents."""
        from payment_simulator.experiments.config.experiment_config import (
            ExperimentConfig,
        )

        config = ExperimentConfig.from_yaml(valid_yaml_path)
        assert config.optimized_agents == ("BANK_A", "BANK_B")

    def test_loads_constraints_module(self, valid_yaml_path: Path) -> None:
        """Loads constraints module path."""
        from payment_simulator.experiments.config.experiment_config import (
            ExperimentConfig,
        )

        config = ExperimentConfig.from_yaml(valid_yaml_path)
        assert config.constraints_module == "castro.constraints.CASTRO_CONSTRAINTS"

    def test_loads_output_config(self, valid_yaml_path: Path) -> None:
        """Loads output configuration."""
        from payment_simulator.experiments.config.experiment_config import (
            ExperimentConfig,
        )

        config = ExperimentConfig.from_yaml(valid_yaml_path)
        assert config.output.directory == Path("results")
        assert config.output.database == "test.db"

    def test_raises_on_missing_file(self) -> None:
        """Raises FileNotFoundError for missing file."""
        from payment_simulator.experiments.config.experiment_config import (
            ExperimentConfig,
        )

        with pytest.raises(FileNotFoundError):
            ExperimentConfig.from_yaml(Path("nonexistent.yaml"))

    def test_raises_on_missing_required_field(self, tmp_path: Path) -> None:
        """Raises ValueError on missing required field."""
        from payment_simulator.experiments.config.experiment_config import (
            ExperimentConfig,
        )

        incomplete = tmp_path / "incomplete.yaml"
        incomplete.write_text("name: test\n")  # Missing other fields
        with pytest.raises(ValueError, match="Missing required fields"):
            ExperimentConfig.from_yaml(incomplete)

    def test_default_master_seed(self, valid_yaml_path: Path) -> None:
        """Default master_seed is 42."""
        from payment_simulator.experiments.config.experiment_config import (
            ExperimentConfig,
        )

        config = ExperimentConfig.from_yaml(valid_yaml_path)
        assert config.master_seed == 42

    def test_is_frozen(self, valid_yaml_path: Path) -> None:
        """ExperimentConfig is immutable."""
        from payment_simulator.experiments.config.experiment_config import (
            ExperimentConfig,
        )

        config = ExperimentConfig.from_yaml(valid_yaml_path)
        with pytest.raises(AttributeError):
            config.name = "different"  # type: ignore

    def test_can_import_from_module(self) -> None:
        """ExperimentConfig can be imported from experiments.config."""
        from payment_simulator.experiments.config import ExperimentConfig

        assert ExperimentConfig is not None

    def test_loads_with_thinking_budget(self, tmp_path: Path) -> None:
        """Loads LLM config with thinking_budget for Anthropic."""
        content = """
name: test_thinking
description: "Test with thinking budget"
scenario: configs/test.yaml
evaluation:
  mode: bootstrap
  num_samples: 5
  ticks: 10
convergence:
  max_iterations: 10
llm:
  model: "anthropic:claude-sonnet-4-5"
  temperature: 0.0
  thinking_budget: 8000
optimized_agents:
  - BANK_A
output:
  directory: results
"""
        yaml_path = tmp_path / "thinking.yaml"
        yaml_path.write_text(content)

        from payment_simulator.experiments.config.experiment_config import (
            ExperimentConfig,
        )

        config = ExperimentConfig.from_yaml(yaml_path)
        assert config.llm.thinking_budget == 8000
