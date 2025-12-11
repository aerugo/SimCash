"""TDD tests for YAML-based experiment loading.

These tests define the interface for experiment_loader.py
which replaces experiments.py.
"""

from __future__ import annotations

import pytest
from pathlib import Path


class TestListExperiments:
    """Tests for listing available experiments."""

    def test_list_experiments_returns_list(self) -> None:
        """list_experiments() should return a list of strings."""
        from castro.experiment_loader import list_experiments

        result = list_experiments()
        assert isinstance(result, list)

    def test_list_experiments_contains_exp1(self) -> None:
        """list_experiments() should include 'exp1'."""
        from castro.experiment_loader import list_experiments

        result = list_experiments()
        assert "exp1" in result

    def test_list_experiments_contains_exp2(self) -> None:
        """list_experiments() should include 'exp2'."""
        from castro.experiment_loader import list_experiments

        result = list_experiments()
        assert "exp2" in result

    def test_list_experiments_contains_exp3(self) -> None:
        """list_experiments() should include 'exp3'."""
        from castro.experiment_loader import list_experiments

        result = list_experiments()
        assert "exp3" in result


class TestLoadExperiment:
    """Tests for loading individual experiments."""

    def test_load_experiment_returns_dict(self) -> None:
        """load_experiment() should return a dictionary."""
        from castro.experiment_loader import load_experiment

        result = load_experiment("exp1")
        assert isinstance(result, dict)

    def test_load_experiment_has_name(self) -> None:
        """Loaded experiment should have 'name' field."""
        from castro.experiment_loader import load_experiment

        result = load_experiment("exp1")
        assert "name" in result
        assert result["name"] == "exp1"

    def test_load_experiment_has_description(self) -> None:
        """Loaded experiment should have 'description' field."""
        from castro.experiment_loader import load_experiment

        result = load_experiment("exp1")
        assert "description" in result
        assert isinstance(result["description"], str)

    def test_load_experiment_has_evaluation_config(self) -> None:
        """Loaded experiment should have 'evaluation' config."""
        from castro.experiment_loader import load_experiment

        result = load_experiment("exp1")
        assert "evaluation" in result
        assert "mode" in result["evaluation"]
        assert "ticks" in result["evaluation"]

    def test_load_experiment_has_llm_config(self) -> None:
        """Loaded experiment should have 'llm' config."""
        from castro.experiment_loader import load_experiment

        result = load_experiment("exp1")
        assert "llm" in result
        assert "model" in result["llm"]

    def test_load_experiment_has_optimized_agents(self) -> None:
        """Loaded experiment should have 'optimized_agents' list."""
        from castro.experiment_loader import load_experiment

        result = load_experiment("exp1")
        assert "optimized_agents" in result
        assert isinstance(result["optimized_agents"], list)


class TestLoadExperimentOverrides:
    """Tests for CLI override parameters."""

    def test_model_override_changes_llm_model(self) -> None:
        """model_override should change the LLM model."""
        from castro.experiment_loader import load_experiment

        result = load_experiment("exp1", model_override="openai:gpt-4o")
        assert result["llm"]["model"] == "openai:gpt-4o"

    def test_thinking_budget_override(self) -> None:
        """thinking_budget should be added to LLM config."""
        from castro.experiment_loader import load_experiment

        result = load_experiment("exp1", thinking_budget=16000)
        assert result["llm"]["thinking_budget"] == 16000

    def test_reasoning_effort_override(self) -> None:
        """reasoning_effort should be added to LLM config."""
        from castro.experiment_loader import load_experiment

        result = load_experiment("exp1", reasoning_effort="high")
        assert result["llm"]["reasoning_effort"] == "high"

    def test_max_iter_override(self) -> None:
        """max_iter_override should change max_iterations."""
        from castro.experiment_loader import load_experiment

        result = load_experiment("exp1", max_iter_override=100)
        assert result["convergence"]["max_iterations"] == 100

    def test_seed_override(self) -> None:
        """seed_override should change master_seed."""
        from castro.experiment_loader import load_experiment

        result = load_experiment("exp1", seed_override=99999)
        assert result["master_seed"] == 99999


class TestLoadExperimentErrors:
    """Tests for error handling."""

    def test_load_nonexistent_raises_file_not_found(self) -> None:
        """Loading nonexistent experiment should raise FileNotFoundError."""
        from castro.experiment_loader import load_experiment

        with pytest.raises(FileNotFoundError):
            load_experiment("nonexistent_experiment")

    def test_error_message_includes_name(self) -> None:
        """Error message should include the experiment name."""
        from castro.experiment_loader import load_experiment

        with pytest.raises(FileNotFoundError) as exc_info:
            load_experiment("fake_experiment")
        assert "fake_experiment" in str(exc_info.value)


class TestGetLLMConfig:
    """Tests for extracting LLMConfig from experiment config."""

    def test_get_llm_config_returns_llm_config(self) -> None:
        """get_llm_config() should return LLMConfig instance."""
        from castro.experiment_loader import get_llm_config, load_experiment
        from payment_simulator.llm import LLMConfig

        exp_config = load_experiment("exp1")
        llm_config = get_llm_config(exp_config)

        assert isinstance(llm_config, LLMConfig)

    def test_get_llm_config_preserves_model(self) -> None:
        """LLMConfig should have correct model."""
        from castro.experiment_loader import get_llm_config, load_experiment

        exp_config = load_experiment("exp1")
        llm_config = get_llm_config(exp_config)

        assert llm_config.model == exp_config["llm"]["model"]

    def test_get_llm_config_preserves_temperature(self) -> None:
        """LLMConfig should have correct temperature."""
        from castro.experiment_loader import get_llm_config, load_experiment

        exp_config = load_experiment("exp1")
        llm_config = get_llm_config(exp_config)

        expected_temp = exp_config["llm"].get("temperature", 0.0)
        assert llm_config.temperature == expected_temp


class TestGetExperimentsDir:
    """Tests for the experiments directory path helper."""

    def test_get_experiments_dir_returns_path(self) -> None:
        """get_experiments_dir() should return a Path."""
        from castro.experiment_loader import get_experiments_dir

        result = get_experiments_dir()
        assert isinstance(result, Path)

    def test_get_experiments_dir_exists(self) -> None:
        """get_experiments_dir() should return an existing directory."""
        from castro.experiment_loader import get_experiments_dir

        result = get_experiments_dir()
        assert result.exists()
        assert result.is_dir()

    def test_get_experiments_dir_contains_yaml_files(self) -> None:
        """Experiments directory should contain YAML files."""
        from castro.experiment_loader import get_experiments_dir

        result = get_experiments_dir()
        yaml_files = list(result.glob("*.yaml"))
        assert len(yaml_files) > 0
