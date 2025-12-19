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

    def test_with_seed_returns_new_config(self, valid_yaml_path: Path) -> None:
        """with_seed() returns new config with different seed."""
        from payment_simulator.experiments.config.experiment_config import (
            ExperimentConfig,
        )

        config = ExperimentConfig.from_yaml(valid_yaml_path)
        original_seed = config.master_seed

        new_config = config.with_seed(99999)

        # New config has new seed
        assert new_config.master_seed == 99999
        # Original config unchanged (frozen)
        assert config.master_seed == original_seed
        # Other fields preserved
        assert new_config.name == config.name
        assert new_config.evaluation == config.evaluation
        assert new_config.convergence == config.convergence
        assert new_config.llm == config.llm
        assert new_config.optimized_agents == config.optimized_agents

    def test_with_seed_preserves_all_fields(self, valid_yaml_path: Path) -> None:
        """with_seed() preserves all other config fields."""
        from payment_simulator.experiments.config.experiment_config import (
            ExperimentConfig,
        )

        config = ExperimentConfig.from_yaml(valid_yaml_path)
        new_config = config.with_seed(12345)

        # All fields should be identical except master_seed
        assert new_config.name == config.name
        assert new_config.description == config.description
        assert new_config.scenario_path == config.scenario_path
        assert new_config.evaluation == config.evaluation
        assert new_config.convergence == config.convergence
        assert new_config.llm == config.llm
        assert new_config.optimized_agents == config.optimized_agents
        assert new_config.constraints_module == config.constraints_module
        assert new_config.output == config.output
        assert new_config.policy_constraints == config.policy_constraints

    def test_with_seed_returns_frozen_config(self, valid_yaml_path: Path) -> None:
        """with_seed() returns a frozen (immutable) config."""
        from payment_simulator.experiments.config.experiment_config import (
            ExperimentConfig,
        )

        config = ExperimentConfig.from_yaml(valid_yaml_path)
        new_config = config.with_seed(12345)

        with pytest.raises(AttributeError):
            new_config.master_seed = 99999  # type: ignore


# =============================================================================
# from_stored_dict Tests (Continuation Support)
# =============================================================================


class TestFromStoredDict:
    """Tests for ExperimentConfig.from_stored_dict method.

    This method is used to reconstruct ExperimentConfig from the JSON
    stored in the database for experiment continuation.
    """

    def test_from_stored_dict_basic(self) -> None:
        """from_stored_dict should reconstruct config from dict."""
        from payment_simulator.experiments.config.experiment_config import (
            ExperimentConfig,
        )

        stored_dict = {
            "name": "test_experiment",
            "description": "Test description",
            "scenario_path": "/path/to/scenario.yaml",
            "master_seed": 42,
            "evaluation": {
                "mode": "deterministic",
                "ticks": 12,
                "num_samples": 5,
            },
            "convergence": {
                "max_iterations": 25,
                "stability_threshold": 0.05,
                "stability_window": 5,
                "improvement_threshold": 0.01,
            },
            "optimized_agents": ["BANK_A", "BANK_B"],
            "constraints_module": "my_module.CONSTRAINTS",
            "llm": {
                "model": "anthropic:claude-sonnet-4-5",
                "temperature": 0.1,
                "max_retries": 3,
                "timeout_seconds": 120,
            },
        }

        config = ExperimentConfig.from_stored_dict(stored_dict)

        assert config.name == "test_experiment"
        assert config.description == "Test description"
        assert config.master_seed == 42
        assert config.evaluation.mode == "deterministic"
        assert config.evaluation.ticks == 12
        assert config.convergence.max_iterations == 25
        assert config.optimized_agents == ("BANK_A", "BANK_B")
        assert config.llm.model == "anthropic:claude-sonnet-4-5"

    def test_from_stored_dict_with_defaults(self) -> None:
        """from_stored_dict should use defaults for missing fields."""
        from payment_simulator.experiments.config.experiment_config import (
            ExperimentConfig,
        )

        # Minimal stored dict
        stored_dict = {
            "name": "minimal_exp",
            "optimized_agents": ["BANK_A"],
        }

        config = ExperimentConfig.from_stored_dict(stored_dict)

        # Check defaults are applied
        assert config.name == "minimal_exp"
        assert config.master_seed == 42  # default
        assert config.evaluation.mode == "bootstrap"  # default
        assert config.evaluation.ticks == 100  # default
        assert config.convergence.max_iterations == 50  # default
        assert config.llm.model == "anthropic:claude-sonnet-4-5"  # default

    def test_from_stored_dict_preserves_llm_config(self) -> None:
        """from_stored_dict should preserve LLM configuration."""
        from payment_simulator.experiments.config.experiment_config import (
            ExperimentConfig,
        )

        stored_dict = {
            "name": "llm_test",
            "optimized_agents": ["BANK_A"],
            "llm": {
                "model": "openai:gpt-4o",
                "temperature": 0.5,
                "max_retries": 5,
                "timeout_seconds": 300,
                "thinking_budget": 10000,
                "reasoning_effort": "high",
                "system_prompt": "Custom prompt text",
            },
        }

        config = ExperimentConfig.from_stored_dict(stored_dict)

        assert config.llm.model == "openai:gpt-4o"
        assert config.llm.temperature == 0.5
        assert config.llm.max_retries == 5
        assert config.llm.timeout_seconds == 300
        assert config.llm.thinking_budget == 10000
        assert config.llm.reasoning_effort == "high"
        assert config.llm.system_prompt == "Custom prompt text"

    def test_from_stored_dict_returns_frozen_config(self) -> None:
        """from_stored_dict should return a frozen (immutable) config."""
        from payment_simulator.experiments.config.experiment_config import (
            ExperimentConfig,
        )

        stored_dict = {
            "name": "test",
            "optimized_agents": ["BANK_A"],
        }

        config = ExperimentConfig.from_stored_dict(stored_dict)

        with pytest.raises(AttributeError):
            config.master_seed = 99999  # type: ignore

    def test_from_stored_dict_scenario_path_is_path_object(self) -> None:
        """from_stored_dict should convert scenario_path to Path."""
        from payment_simulator.experiments.config.experiment_config import (
            ExperimentConfig,
        )

        stored_dict = {
            "name": "test",
            "scenario_path": "/path/to/scenario.yaml",
            "optimized_agents": ["BANK_A"],
        }

        config = ExperimentConfig.from_stored_dict(stored_dict)

        assert isinstance(config.scenario_path, Path)
        assert config.scenario_path == Path("/path/to/scenario.yaml")
