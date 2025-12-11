"""TDD tests for GenericExperimentRunner.

Phase 16.3: Tests for GenericExperimentRunner in core.
These tests MUST FAIL before implementation.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestGenericExperimentRunnerImport:
    """Tests for GenericExperimentRunner import."""

    def test_import_from_experiments_runner(self) -> None:
        """GenericExperimentRunner can be imported from experiments.runner."""
        from payment_simulator.experiments.runner import GenericExperimentRunner

        assert GenericExperimentRunner is not None


class TestGenericExperimentRunnerCreation:
    """Tests for runner creation."""

    def test_creates_from_experiment_config(self, tmp_path: Path) -> None:
        """Runner created from ExperimentConfig."""
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.experiments.runner import GenericExperimentRunner

        yaml_content = dedent("""
            name: test_exp
            description: "Test experiment"
            scenario: configs/test.yaml
            evaluation:
              mode: deterministic
              ticks: 2
            convergence:
              max_iterations: 10
            llm:
              model: "anthropic:claude-sonnet-4-5"
              system_prompt: "You are a test optimizer."
            optimized_agents:
              - BANK_A
            policy_constraints:
              allowed_parameters: []
              allowed_fields: []
              allowed_actions: {}
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)
        runner = GenericExperimentRunner(config)

        assert runner is not None
        assert runner.experiment_name == "test_exp"

    def test_accepts_verbose_config(self, tmp_path: Path) -> None:
        """Runner accepts optional VerboseConfig."""
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.experiments.runner import (
            GenericExperimentRunner,
            VerboseConfig,
        )

        yaml_content = dedent("""
            name: test_exp
            description: "Test"
            scenario: configs/test.yaml
            evaluation:
              mode: deterministic
              ticks: 2
            convergence:
              max_iterations: 10
            llm:
              model: "anthropic:claude-sonnet-4-5"
            optimized_agents:
              - BANK_A
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)
        verbose_config = VerboseConfig.all_enabled()

        runner = GenericExperimentRunner(config, verbose_config=verbose_config)

        assert runner is not None

    def test_accepts_run_id(self, tmp_path: Path) -> None:
        """Runner accepts optional run_id."""
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.experiments.runner import GenericExperimentRunner

        yaml_content = dedent("""
            name: test_exp
            description: "Test"
            scenario: configs/test.yaml
            evaluation:
              mode: deterministic
              ticks: 2
            convergence:
              max_iterations: 10
            llm:
              model: "anthropic:claude-sonnet-4-5"
            optimized_agents:
              - BANK_A
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)
        runner = GenericExperimentRunner(config, run_id="custom-run-id-123")

        assert runner.run_id == "custom-run-id-123"


class TestGenericExperimentRunnerProtocol:
    """Tests for protocol implementation."""

    def test_implements_runner_protocol(self, tmp_path: Path) -> None:
        """GenericExperimentRunner implements ExperimentRunnerProtocol."""
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.experiments.runner import (
            ExperimentRunnerProtocol,
            GenericExperimentRunner,
        )

        yaml_content = dedent("""
            name: test_exp
            description: "Test"
            scenario: configs/test.yaml
            evaluation:
              mode: deterministic
              ticks: 2
            convergence:
              max_iterations: 10
            llm:
              model: "anthropic:claude-sonnet-4-5"
            optimized_agents:
              - BANK_A
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)
        runner = GenericExperimentRunner(config)

        # Should implement the protocol
        assert isinstance(runner, ExperimentRunnerProtocol)

    def test_has_async_run_method(self, tmp_path: Path) -> None:
        """Runner has async run() method."""
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.experiments.runner import GenericExperimentRunner

        yaml_content = dedent("""
            name: test_exp
            description: "Test"
            scenario: configs/test.yaml
            evaluation:
              mode: deterministic
              ticks: 2
            convergence:
              max_iterations: 10
            llm:
              model: "anthropic:claude-sonnet-4-5"
            optimized_agents:
              - BANK_A
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)
        runner = GenericExperimentRunner(config)

        assert hasattr(runner, "run")
        import inspect
        assert inspect.iscoroutinefunction(runner.run)

    def test_has_get_current_state_method(self, tmp_path: Path) -> None:
        """Runner has get_current_state() method."""
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.experiments.runner import GenericExperimentRunner

        yaml_content = dedent("""
            name: test_exp
            description: "Test"
            scenario: configs/test.yaml
            evaluation:
              mode: deterministic
              ticks: 2
            convergence:
              max_iterations: 10
            llm:
              model: "anthropic:claude-sonnet-4-5"
            optimized_agents:
              - BANK_A
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)
        runner = GenericExperimentRunner(config)

        assert hasattr(runner, "get_current_state")


class TestGenericExperimentRunnerConfigUsage:
    """Tests for config field usage."""

    def test_uses_constraints_from_config(self, tmp_path: Path) -> None:
        """Runner uses config.get_constraints() for validation."""
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.experiments.runner import GenericExperimentRunner

        yaml_content = dedent("""
            name: test_exp
            description: "Test"
            scenario: configs/test.yaml
            evaluation:
              mode: deterministic
              ticks: 2
            convergence:
              max_iterations: 10
            llm:
              model: "anthropic:claude-sonnet-4-5"
            optimized_agents:
              - BANK_A
            policy_constraints:
              allowed_parameters:
                - name: threshold
                  param_type: int
                  min_value: 0
                  max_value: 100
              allowed_fields:
                - balance
              allowed_actions:
                payment_tree:
                  - Release
                  - Hold
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)
        runner = GenericExperimentRunner(config)

        # Runner should have constraints from config
        assert runner.constraints is not None
        assert runner.constraints.is_field_allowed("balance")

    def test_uses_system_prompt_from_config(self, tmp_path: Path) -> None:
        """Runner uses config.llm.system_prompt for LLM."""
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.experiments.runner import GenericExperimentRunner

        custom_prompt = "You are a custom payment optimizer for testing."
        yaml_content = dedent(f"""
            name: test_exp
            description: "Test"
            scenario: configs/test.yaml
            evaluation:
              mode: deterministic
              ticks: 2
            convergence:
              max_iterations: 10
            llm:
              model: "anthropic:claude-sonnet-4-5"
              system_prompt: "{custom_prompt}"
            optimized_agents:
              - BANK_A
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)
        runner = GenericExperimentRunner(config)

        assert runner.system_prompt == custom_prompt

    def test_loads_scenario_from_config_path(self, tmp_path: Path) -> None:
        """Runner exposes scenario_path from config."""
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.experiments.runner import GenericExperimentRunner

        yaml_content = dedent("""
            name: test_exp
            description: "Test"
            scenario: configs/my_scenario.yaml
            evaluation:
              mode: deterministic
              ticks: 2
            convergence:
              max_iterations: 10
            llm:
              model: "anthropic:claude-sonnet-4-5"
            optimized_agents:
              - BANK_A
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)
        runner = GenericExperimentRunner(config)

        assert runner.scenario_path == Path("configs/my_scenario.yaml")


class TestGenericExperimentRunnerRunId:
    """Tests for run ID generation."""

    def test_generates_run_id(self, tmp_path: Path) -> None:
        """Runner generates unique run_id if not provided."""
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.experiments.runner import GenericExperimentRunner

        yaml_content = dedent("""
            name: test_exp
            description: "Test"
            scenario: configs/test.yaml
            evaluation:
              mode: deterministic
              ticks: 2
            convergence:
              max_iterations: 10
            llm:
              model: "anthropic:claude-sonnet-4-5"
            optimized_agents:
              - BANK_A
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)
        runner = GenericExperimentRunner(config)

        assert runner.run_id is not None
        assert len(runner.run_id) > 0
        # Should contain experiment name
        assert "test_exp" in runner.run_id

    def test_different_runners_have_different_run_ids(self, tmp_path: Path) -> None:
        """Each runner instance gets unique run_id."""
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.experiments.runner import GenericExperimentRunner

        yaml_content = dedent("""
            name: test_exp
            description: "Test"
            scenario: configs/test.yaml
            evaluation:
              mode: deterministic
              ticks: 2
            convergence:
              max_iterations: 10
            llm:
              model: "anthropic:claude-sonnet-4-5"
            optimized_agents:
              - BANK_A
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)
        runner1 = GenericExperimentRunner(config)
        runner2 = GenericExperimentRunner(config)

        assert runner1.run_id != runner2.run_id


class TestGenericExperimentRunnerState:
    """Tests for state management."""

    def test_get_current_state_returns_experiment_state(self, tmp_path: Path) -> None:
        """get_current_state() returns ExperimentState."""
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.experiments.runner import (
            ExperimentState,
            GenericExperimentRunner,
        )

        yaml_content = dedent("""
            name: test_exp
            description: "Test"
            scenario: configs/test.yaml
            evaluation:
              mode: deterministic
              ticks: 2
            convergence:
              max_iterations: 10
            llm:
              model: "anthropic:claude-sonnet-4-5"
            optimized_agents:
              - BANK_A
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)
        runner = GenericExperimentRunner(config)

        state = runner.get_current_state()

        assert isinstance(state, ExperimentState)
        assert state.experiment_name == "test_exp"


class TestBackwardCompatibility:
    """Tests for Castro backward compatibility (skipped in API env)."""

    @pytest.mark.skip(reason="Castro not available in API test environment")
    def test_castro_can_use_generic_runner(self) -> None:
        """Castro can import and use GenericExperimentRunner from core."""
        pass
