"""Tests for experiment CLI commands (Phase 5 TDD).

Test Coverage:
1. validate command - validates experiment config YAML
2. info command - shows module info
3. template command - generates config template
4. list command - lists experiments from directory
5. run command - runs experiment (with mock runner)
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
import yaml

if TYPE_CHECKING:
    from pytest import TempPathFactory


# ==============================================================================
# Test Fixtures
# ==============================================================================


@pytest.fixture
def valid_experiment_yaml(tmp_path: Path) -> Path:
    """Create a valid experiment config YAML file."""
    config_data = {
        "name": "test_exp",
        "description": "Test experiment",
        "scenario": str(tmp_path / "scenario.yaml"),
        "evaluation": {
            "mode": "bootstrap",
            "num_samples": 10,
            "ticks": 12,
        },
        "convergence": {
            "max_iterations": 25,
            "stability_threshold": 0.05,
        },
        "llm": {
            "model": "anthropic:claude-sonnet-4-5",
            "temperature": 0.0,
        },
        "optimized_agents": ["BANK_A"],
        "constraints": "castro.constraints.CASTRO_CONSTRAINTS",
        "output": {
            "directory": "results",
            "verbose": True,
        },
        "master_seed": 42,
    }

    # Create dummy scenario file
    scenario_file = tmp_path / "scenario.yaml"
    scenario_file.write_text(yaml.dump({"simulation": {"ticks_per_day": 10}}))

    config_file = tmp_path / "test_exp.yaml"
    config_file.write_text(yaml.dump(config_data))
    return config_file


@pytest.fixture
def invalid_experiment_yaml(tmp_path: Path) -> Path:
    """Create an invalid experiment config YAML (missing required fields)."""
    config_data = {
        "name": "broken_exp",
        # Missing: scenario, evaluation, convergence, llm, optimized_agents
    }
    config_file = tmp_path / "broken_exp.yaml"
    config_file.write_text(yaml.dump(config_data))
    return config_file


@pytest.fixture
def experiments_directory(tmp_path: Path) -> Path:
    """Create a directory with multiple experiment configs."""
    exp_dir = tmp_path / "experiments"
    exp_dir.mkdir()

    # Create exp1.yaml
    exp1_data = {
        "name": "exp1",
        "description": "First experiment",
        "scenario": "configs/scenario1.yaml",
        "evaluation": {"mode": "bootstrap", "num_samples": 10, "ticks": 12},
        "convergence": {"max_iterations": 25},
        "llm": {"model": "anthropic:claude-sonnet-4-5"},
        "optimized_agents": ["BANK_A"],
    }
    (exp_dir / "exp1.yaml").write_text(yaml.dump(exp1_data))

    # Create exp2.yaml
    exp2_data = {
        "name": "exp2",
        "description": "Second experiment",
        "scenario": "configs/scenario2.yaml",
        "evaluation": {"mode": "deterministic", "ticks": 24},
        "convergence": {"max_iterations": 50},
        "llm": {"model": "openai:gpt-4"},
        "optimized_agents": ["BANK_A", "BANK_B"],
    }
    (exp_dir / "exp2.yaml").write_text(yaml.dump(exp2_data))

    # Create non-yaml file (should be ignored)
    (exp_dir / "readme.txt").write_text("Not an experiment")

    return exp_dir


# ==============================================================================
# Test validate command
# ==============================================================================


class TestValidateCommand:
    """Tests for 'experiment validate' command."""

    def test_validate_valid_config_succeeds(self, valid_experiment_yaml: Path) -> None:
        """Valid config should print success message."""
        from payment_simulator.cli.commands.experiment import validate_experiment

        # Capture output
        output_lines: list[str] = []

        def mock_echo(msg: str) -> None:
            output_lines.append(msg)

        with patch(
            "payment_simulator.cli.commands.experiment._echo", side_effect=mock_echo
        ):
            validate_experiment(valid_experiment_yaml)

        # Should report success
        assert any("valid" in line.lower() for line in output_lines)
        assert any("test_exp" in line for line in output_lines)

    def test_validate_nonexistent_file_fails(self, tmp_path: Path) -> None:
        """Non-existent file should raise Exit with code 1."""
        from payment_simulator.cli.commands.experiment import validate_experiment

        import typer

        nonexistent = tmp_path / "does_not_exist.yaml"

        with pytest.raises(typer.Exit) as exc_info:
            validate_experiment(nonexistent)

        assert exc_info.value.exit_code == 1

    def test_validate_invalid_yaml_fails(self, tmp_path: Path) -> None:
        """Invalid YAML should raise Exit with code 1."""
        from payment_simulator.cli.commands.experiment import validate_experiment

        import typer

        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text(":::invalid yaml:::")

        with pytest.raises(typer.Exit) as exc_info:
            validate_experiment(bad_yaml)

        assert exc_info.value.exit_code == 1

    def test_validate_missing_required_fields_fails(
        self, invalid_experiment_yaml: Path
    ) -> None:
        """Config missing required fields should raise Exit with code 1."""
        from payment_simulator.cli.commands.experiment import validate_experiment

        import typer

        with pytest.raises(typer.Exit) as exc_info:
            validate_experiment(invalid_experiment_yaml)

        assert exc_info.value.exit_code == 1


# ==============================================================================
# Test info command
# ==============================================================================


class TestInfoCommand:
    """Tests for 'experiment info' command."""

    def test_info_shows_module_name(self) -> None:
        """Info should show 'Experiment Framework' header."""
        from payment_simulator.cli.commands.experiment import show_experiment_info

        output_lines: list[str] = []

        def mock_echo(msg: str) -> None:
            output_lines.append(msg)

        with patch(
            "payment_simulator.cli.commands.experiment._echo", side_effect=mock_echo
        ):
            show_experiment_info()

        # Should mention experiment framework
        full_output = "\n".join(output_lines)
        assert "experiment" in full_output.lower()

    def test_info_shows_evaluation_modes(self) -> None:
        """Info should list available evaluation modes."""
        from payment_simulator.cli.commands.experiment import show_experiment_info

        output_lines: list[str] = []

        def mock_echo(msg: str) -> None:
            output_lines.append(msg)

        with patch(
            "payment_simulator.cli.commands.experiment._echo", side_effect=mock_echo
        ):
            show_experiment_info()

        full_output = "\n".join(output_lines)
        assert "bootstrap" in full_output.lower()
        assert "deterministic" in full_output.lower()

    def test_info_shows_available_commands(self) -> None:
        """Info should list available subcommands."""
        from payment_simulator.cli.commands.experiment import show_experiment_info

        output_lines: list[str] = []

        def mock_echo(msg: str) -> None:
            output_lines.append(msg)

        with patch(
            "payment_simulator.cli.commands.experiment._echo", side_effect=mock_echo
        ):
            show_experiment_info()

        full_output = "\n".join(output_lines)
        # Should mention main commands
        assert "validate" in full_output.lower()
        assert "template" in full_output.lower()


# ==============================================================================
# Test template command
# ==============================================================================


class TestTemplateCommand:
    """Tests for 'experiment template' command."""

    def test_template_outputs_valid_yaml(self) -> None:
        """Template should output valid YAML."""
        from payment_simulator.cli.commands.experiment import generate_experiment_template

        output_lines: list[str] = []

        def mock_echo(msg: str) -> None:
            output_lines.append(msg)

        with patch(
            "payment_simulator.cli.commands.experiment._echo", side_effect=mock_echo
        ):
            generate_experiment_template(output=None)

        # Parse as YAML
        yaml_content = "\n".join(output_lines)
        data = yaml.safe_load(yaml_content)

        assert data is not None
        assert isinstance(data, dict)

    def test_template_has_required_fields(self) -> None:
        """Template should include all required fields."""
        from payment_simulator.cli.commands.experiment import generate_experiment_template

        output_lines: list[str] = []

        def mock_echo(msg: str) -> None:
            output_lines.append(msg)

        with patch(
            "payment_simulator.cli.commands.experiment._echo", side_effect=mock_echo
        ):
            generate_experiment_template(output=None)

        yaml_content = "\n".join(output_lines)
        data = yaml.safe_load(yaml_content)

        # Check required fields
        assert "name" in data
        assert "scenario" in data
        assert "evaluation" in data
        assert "convergence" in data
        assert "llm" in data
        assert "optimized_agents" in data

    def test_template_writes_to_file(self, tmp_path: Path) -> None:
        """Template should write to file when path specified."""
        from payment_simulator.cli.commands.experiment import generate_experiment_template

        output_file = tmp_path / "new_experiment.yaml"

        with patch("payment_simulator.cli.commands.experiment._echo"):
            generate_experiment_template(output=output_file)

        assert output_file.exists()
        data = yaml.safe_load(output_file.read_text())
        assert data["name"] is not None


# ==============================================================================
# Test list command
# ==============================================================================


class TestListCommand:
    """Tests for 'experiment list' command."""

    def test_list_finds_yaml_files(self, experiments_directory: Path) -> None:
        """List should find all .yaml experiment files."""
        from payment_simulator.cli.commands.experiment import list_experiments

        output_lines: list[str] = []

        def mock_echo(msg: str) -> None:
            output_lines.append(msg)

        with patch(
            "payment_simulator.cli.commands.experiment._echo", side_effect=mock_echo
        ):
            list_experiments(experiments_directory)

        full_output = "\n".join(output_lines)
        assert "exp1" in full_output
        assert "exp2" in full_output

    def test_list_shows_experiment_names(self, experiments_directory: Path) -> None:
        """List should show experiment names from YAML."""
        from payment_simulator.cli.commands.experiment import list_experiments

        output_lines: list[str] = []

        def mock_echo(msg: str) -> None:
            output_lines.append(msg)

        with patch(
            "payment_simulator.cli.commands.experiment._echo", side_effect=mock_echo
        ):
            list_experiments(experiments_directory)

        full_output = "\n".join(output_lines)
        assert "First experiment" in full_output or "exp1" in full_output
        assert "Second experiment" in full_output or "exp2" in full_output

    def test_list_empty_directory(self, tmp_path: Path) -> None:
        """List on empty directory should show 'no experiments'."""
        from payment_simulator.cli.commands.experiment import list_experiments

        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        output_lines: list[str] = []

        def mock_echo(msg: str) -> None:
            output_lines.append(msg)

        with patch(
            "payment_simulator.cli.commands.experiment._echo", side_effect=mock_echo
        ):
            list_experiments(empty_dir)

        full_output = "\n".join(output_lines)
        assert "no experiment" in full_output.lower() or "0" in full_output

    def test_list_nonexistent_directory_fails(self, tmp_path: Path) -> None:
        """Non-existent directory should raise Exit with code 1."""
        from payment_simulator.cli.commands.experiment import list_experiments

        import typer

        nonexistent = tmp_path / "does_not_exist"

        with pytest.raises(typer.Exit) as exc_info:
            list_experiments(nonexistent)

        assert exc_info.value.exit_code == 1


# ==============================================================================
# Test run command (mocked)
# ==============================================================================


class TestRunCommand:
    """Tests for 'experiment run' command."""

    def test_run_loads_config(self, valid_experiment_yaml: Path) -> None:
        """Run should load and validate the config."""
        from payment_simulator.cli.commands.experiment import run_experiment

        # Mock the experiment runner to avoid actual execution
        with (
            patch(
                "payment_simulator.cli.commands.experiment.ExperimentConfig.from_yaml"
            ) as mock_from_yaml,
            patch(
                "payment_simulator.cli.commands.experiment._run_experiment_async"
            ) as mock_run,
            patch("payment_simulator.cli.commands.experiment._echo"),
        ):
            mock_config = MagicMock()
            mock_config.name = "test_exp"
            mock_from_yaml.return_value = mock_config
            mock_run.return_value = None  # Simulate successful run

            # This should not raise
            run_experiment(valid_experiment_yaml, dry_run=True)

            mock_from_yaml.assert_called_once_with(valid_experiment_yaml)

    def test_run_dry_run_does_not_execute(self, valid_experiment_yaml: Path) -> None:
        """Dry run should not execute the experiment."""
        from payment_simulator.cli.commands.experiment import run_experiment

        with (
            patch(
                "payment_simulator.cli.commands.experiment.ExperimentConfig.from_yaml"
            ) as mock_from_yaml,
            patch(
                "payment_simulator.cli.commands.experiment._run_experiment_async"
            ) as mock_run,
            patch("payment_simulator.cli.commands.experiment._echo"),
        ):
            mock_config = MagicMock()
            mock_config.name = "test_exp"
            mock_from_yaml.return_value = mock_config

            run_experiment(valid_experiment_yaml, dry_run=True)

            # Should NOT call actual runner in dry_run mode
            mock_run.assert_not_called()

    def test_run_invalid_config_fails(self, invalid_experiment_yaml: Path) -> None:
        """Invalid config should raise Exit with code 1."""
        from payment_simulator.cli.commands.experiment import run_experiment

        import typer

        with (
            patch("payment_simulator.cli.commands.experiment._echo"),
            patch("payment_simulator.cli.commands.experiment._echo_error"),
        ):
            with pytest.raises(typer.Exit) as exc_info:
                run_experiment(invalid_experiment_yaml, dry_run=True)

            assert exc_info.value.exit_code == 1

    def test_run_with_seed_override(self, valid_experiment_yaml: Path) -> None:
        """Run should allow seed override."""
        from payment_simulator.cli.commands.experiment import run_experiment

        with (
            patch(
                "payment_simulator.cli.commands.experiment.ExperimentConfig.from_yaml"
            ) as mock_from_yaml,
            patch("payment_simulator.cli.commands.experiment._echo"),
        ):
            # Create a mock config that we can track
            mock_config = MagicMock()
            mock_config.name = "test_exp"
            mock_config.master_seed = 42
            mock_from_yaml.return_value = mock_config

            run_experiment(valid_experiment_yaml, seed=12345, dry_run=True)

            # Config was loaded
            mock_from_yaml.assert_called_once()


# ==============================================================================
# Test CLI app structure
# ==============================================================================


class TestExperimentApp:
    """Tests for experiment CLI app structure."""

    def test_experiment_app_is_typer(self) -> None:
        """experiment_app should be a Typer instance."""
        from payment_simulator.cli.commands.experiment import experiment_app

        import typer

        assert isinstance(experiment_app, typer.Typer)

    def test_experiment_app_has_commands(self) -> None:
        """experiment_app should have registered commands."""
        from payment_simulator.cli.commands.experiment import experiment_app

        # Check that commands are registered
        # Typer registers commands in its internal structure
        assert experiment_app.registered_commands is not None
