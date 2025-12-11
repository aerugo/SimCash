"""TDD tests for runner.py protocol compatibility.

These tests verify runner.py works with both CastroExperiment
and YamlExperimentConfig via the protocol.
"""

from __future__ import annotations

import inspect
import os
from pathlib import Path

import pytest

# Skip tests that require API key if not available
# Default model is Anthropic, so specifically require ANTHROPIC_API_KEY
SKIP_RUNNER_TESTS = not os.environ.get("ANTHROPIC_API_KEY")
skip_without_api_key = pytest.mark.skipif(
    SKIP_RUNNER_TESTS,
    reason="Requires ANTHROPIC_API_KEY (default model is Anthropic)",
)


class TestRunnerAcceptsProtocol:
    """Tests that ExperimentRunner accepts protocol implementations."""

    @skip_without_api_key
    def test_runner_accepts_castro_experiment(self) -> None:
        """Runner should accept CastroExperiment (backward compat)."""
        from castro.experiment_config import CastroExperiment
        from castro.runner import ExperimentRunner

        exp = CastroExperiment(
            name="test",
            description="Test",
            scenario_path=Path("configs/exp1_2period.yaml"),
            deterministic=True,
        )
        # Should not raise
        runner = ExperimentRunner(exp)
        assert runner is not None

    @skip_without_api_key
    def test_runner_accepts_yaml_experiment_config(self) -> None:
        """Runner should accept YamlExperimentConfig."""
        from castro.experiment_config import YamlExperimentConfig
        from castro.experiment_loader import load_experiment
        from castro.runner import ExperimentRunner

        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        # Should not raise
        runner = ExperimentRunner(yaml_config)
        assert runner is not None

    def test_runner_type_hint_accepts_protocol(self) -> None:
        """Runner __init__ should accept ExperimentConfigProtocol."""
        from castro.runner import ExperimentRunner

        sig = inspect.signature(ExperimentRunner.__init__)
        experiment_param = sig.parameters.get("experiment")
        # Type hint should exist
        assert experiment_param is not None
        # Can't easily test annotation without parsing, but param should exist


@skip_without_api_key
class TestRunnerBehaviorWithYamlConfig:
    """Tests that runner behaves correctly with YamlExperimentConfig."""

    def test_runner_gets_correct_name(self) -> None:
        """Runner should get correct experiment name from YAML config."""
        from castro.experiment_config import YamlExperimentConfig
        from castro.experiment_loader import load_experiment
        from castro.runner import ExperimentRunner

        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        runner = ExperimentRunner(yaml_config)

        # Internal state should have correct name
        assert runner._experiment.name == "exp1"

    def test_runner_gets_correct_seed(self) -> None:
        """Runner should get correct master_seed from YAML config."""
        from castro.experiment_config import YamlExperimentConfig
        from castro.experiment_loader import load_experiment
        from castro.runner import ExperimentRunner

        config_dict = load_experiment("exp1", seed_override=12345)
        yaml_config = YamlExperimentConfig(config_dict)
        runner = ExperimentRunner(yaml_config)

        assert runner._seed_manager._master_seed == 12345

    def test_runner_gets_correct_optimized_agents(self) -> None:
        """Runner should get correct optimized_agents from YAML config."""
        from castro.experiment_config import YamlExperimentConfig
        from castro.experiment_loader import load_experiment
        from castro.runner import ExperimentRunner

        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        runner = ExperimentRunner(yaml_config)

        expected_agents = config_dict["optimized_agents"]
        assert list(runner._experiment.optimized_agents) == expected_agents

    def test_runner_gets_correct_bootstrap_config(self) -> None:
        """Runner should get correct bootstrap config from YAML config."""
        from castro.experiment_config import YamlExperimentConfig
        from castro.experiment_loader import load_experiment
        from castro.runner import ExperimentRunner

        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        runner = ExperimentRunner(yaml_config)

        # exp1 is deterministic
        assert runner._bootstrap_config.deterministic is True

    def test_runner_gets_correct_convergence_criteria(self) -> None:
        """Runner should get correct convergence criteria from YAML config."""
        from castro.experiment_config import YamlExperimentConfig
        from castro.experiment_loader import load_experiment
        from castro.runner import ExperimentRunner

        config_dict = load_experiment("exp1", max_iter_override=100)
        yaml_config = YamlExperimentConfig(config_dict)
        runner = ExperimentRunner(yaml_config)

        assert runner._convergence_criteria.max_iterations == 100


@skip_without_api_key
class TestRunnerWithBothConfigTypes:
    """Tests that runner works identically with both config types."""

    def test_identical_initial_state_with_both_configs(self) -> None:
        """Runner should have identical initial state with both config types."""
        from castro.experiment_config import YamlExperimentConfig
        from castro.experiment_loader import load_experiment
        from castro.experiment_config import CastroExperiment
        from castro.runner import ExperimentRunner

        # Create runner with CastroExperiment
        castro_exp = CastroExperiment(
            name="exp1",
            description="2-Period Deterministic Nash Equilibrium",
            scenario_path=Path("configs/exp1_2period.yaml"),
            deterministic=True,
            max_iterations=25,
            master_seed=42,
        )
        runner1 = ExperimentRunner(castro_exp)

        # Create runner with YamlExperimentConfig
        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        runner2 = ExperimentRunner(yaml_config)

        # Should have same experiment name
        assert runner1._experiment.name == runner2._experiment.name

        # Should have same seed
        assert runner1._seed_manager._master_seed == runner2._seed_manager._master_seed

        # Should have same deterministic setting
        assert (
            runner1._bootstrap_config.deterministic
            == runner2._bootstrap_config.deterministic
        )
