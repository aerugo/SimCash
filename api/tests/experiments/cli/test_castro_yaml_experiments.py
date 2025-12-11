"""Tests verifying Castro experiments work via core CLI.

These tests verify that after Phase 18:
1. Castro YAML experiments load with inline system_prompt and policy_constraints
2. No Python code remains in the Castro directory
3. Core CLI commands work with Castro YAML files
"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from payment_simulator.cli.main import app
from payment_simulator.experiments.config import ExperimentConfig


# Path relative to api/ directory where tests run
CASTRO_EXPERIMENTS_DIR = Path("../experiments/castro/experiments")


class TestCastroYamlExperimentsValidate:
    """Test Castro YAML experiments validate successfully."""

    @pytest.mark.skipif(
        not CASTRO_EXPERIMENTS_DIR.exists(),
        reason="Castro experiments directory not found",
    )
    def test_exp1_yaml_validates(self) -> None:
        """exp1.yaml should validate successfully."""
        config_path = CASTRO_EXPERIMENTS_DIR / "exp1.yaml"
        config = ExperimentConfig.from_yaml(config_path)
        assert config.name == "exp1"
        assert config.llm.system_prompt is not None
        assert len(config.llm.system_prompt) > 500  # Has full system prompt

    @pytest.mark.skipif(
        not CASTRO_EXPERIMENTS_DIR.exists(),
        reason="Castro experiments directory not found",
    )
    def test_exp2_yaml_validates(self) -> None:
        """exp2.yaml should validate successfully."""
        config_path = CASTRO_EXPERIMENTS_DIR / "exp2.yaml"
        config = ExperimentConfig.from_yaml(config_path)
        assert config.name == "exp2"
        assert config.evaluation.mode == "bootstrap"
        assert config.llm.system_prompt is not None

    @pytest.mark.skipif(
        not CASTRO_EXPERIMENTS_DIR.exists(),
        reason="Castro experiments directory not found",
    )
    def test_exp3_yaml_validates(self) -> None:
        """exp3.yaml should validate successfully."""
        config_path = CASTRO_EXPERIMENTS_DIR / "exp3.yaml"
        config = ExperimentConfig.from_yaml(config_path)
        assert config.name == "exp3"
        assert config.llm.system_prompt is not None

    @pytest.mark.skipif(
        not CASTRO_EXPERIMENTS_DIR.exists(),
        reason="Castro experiments directory not found",
    )
    def test_exp1_has_policy_constraints(self) -> None:
        """exp1.yaml should have inline policy_constraints."""
        config_path = CASTRO_EXPERIMENTS_DIR / "exp1.yaml"
        config = ExperimentConfig.from_yaml(config_path)
        assert config.policy_constraints is not None
        # Verify structure
        assert config.policy_constraints.allowed_parameters is not None
        assert config.policy_constraints.allowed_fields is not None
        assert config.policy_constraints.allowed_actions is not None

    @pytest.mark.skipif(
        not CASTRO_EXPERIMENTS_DIR.exists(),
        reason="Castro experiments directory not found",
    )
    def test_all_experiments_have_same_system_prompt(self) -> None:
        """All experiments should have the same system prompt (Castro-specific)."""
        exp1 = ExperimentConfig.from_yaml(CASTRO_EXPERIMENTS_DIR / "exp1.yaml")
        exp2 = ExperimentConfig.from_yaml(CASTRO_EXPERIMENTS_DIR / "exp2.yaml")
        exp3 = ExperimentConfig.from_yaml(CASTRO_EXPERIMENTS_DIR / "exp3.yaml")

        # All should have the same system prompt
        assert exp1.llm.system_prompt == exp2.llm.system_prompt
        assert exp2.llm.system_prompt == exp3.llm.system_prompt


class TestCastroYamlNoPythonCode:
    """Verify Castro has no Python code after Phase 18."""

    def test_no_castro_python_module(self) -> None:
        """experiments/castro/castro/ should not exist."""
        castro_module = Path("../experiments/castro/castro")
        assert not castro_module.exists(), "Castro Python module should be deleted"

    def test_no_castro_cli(self) -> None:
        """experiments/castro/cli.py should not exist."""
        cli_file = Path("../experiments/castro/cli.py")
        assert not cli_file.exists(), "Castro CLI should be deleted"

    def test_no_castro_tests(self) -> None:
        """experiments/castro/tests/ should not exist."""
        tests_dir = Path("../experiments/castro/tests")
        assert not tests_dir.exists(), "Castro tests should be deleted"

    def test_castro_yaml_files_exist(self) -> None:
        """Castro YAML experiment files should still exist."""
        assert (Path("../experiments/castro/experiments/exp1.yaml")).exists()
        assert (Path("../experiments/castro/experiments/exp2.yaml")).exists()
        assert (Path("../experiments/castro/experiments/exp3.yaml")).exists()

    def test_castro_config_files_exist(self) -> None:
        """Castro YAML config files should still exist."""
        assert (Path("../experiments/castro/configs/exp1_2period.yaml")).exists()
        assert (Path("../experiments/castro/configs/exp2_12period.yaml")).exists()
        assert (Path("../experiments/castro/configs/exp3_joint.yaml")).exists()


class TestCoreCLIWithCastroYaml:
    """Test core CLI commands work with Castro YAML files."""

    @pytest.mark.skipif(
        not CASTRO_EXPERIMENTS_DIR.exists(),
        reason="Castro experiments directory not found",
    )
    def test_validate_command_works(self) -> None:
        """Validate command should work with Castro YAMLs."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["experiment", "validate", str(CASTRO_EXPERIMENTS_DIR / "exp1.yaml")],
        )
        assert result.exit_code == 0
        assert "valid" in result.stdout.lower()

    @pytest.mark.skipif(
        not CASTRO_EXPERIMENTS_DIR.exists(),
        reason="Castro experiments directory not found",
    )
    def test_list_command_works(self) -> None:
        """List command should show Castro experiments."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["experiment", "list", str(CASTRO_EXPERIMENTS_DIR)],
        )
        assert result.exit_code == 0
        assert "exp1" in result.stdout

    @pytest.mark.skipif(
        not CASTRO_EXPERIMENTS_DIR.exists(),
        reason="Castro experiments directory not found",
    )
    def test_dry_run_command_works(self) -> None:
        """Dry-run should validate without executing."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["experiment", "run", str(CASTRO_EXPERIMENTS_DIR / "exp1.yaml"), "--dry-run"],
        )
        assert result.exit_code == 0
        assert "dry run" in result.stdout.lower() or "valid" in result.stdout.lower()

    @pytest.mark.skipif(
        not CASTRO_EXPERIMENTS_DIR.exists(),
        reason="Castro experiments directory not found",
    )
    def test_validate_all_experiments(self) -> None:
        """All three experiments should validate successfully."""
        runner = CliRunner()

        for exp in ["exp1.yaml", "exp2.yaml", "exp3.yaml"]:
            result = runner.invoke(
                app,
                ["experiment", "validate", str(CASTRO_EXPERIMENTS_DIR / exp)],
            )
            assert result.exit_code == 0, f"{exp} failed to validate: {result.stdout}"
