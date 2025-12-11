"""TDD tests for generic experiment CLI commands: run, list, info, validate.

Phase 17: Tests for generic CLI commands in core.
These tests MUST FAIL before implementation.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
from typer.testing import CliRunner


class TestValidateCommand:
    """Tests for experiment validate command."""

    def test_validate_command_exists(self) -> None:
        """validate command exists in experiment_app."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["validate", "--help"])
        assert result.exit_code == 0
        assert "validate" in result.output.lower()

    def test_validate_requires_config_path(self) -> None:
        """validate command requires config_path argument."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["validate"])
        # Should fail or show help for missing argument
        assert result.exit_code != 0 or "CONFIG_PATH" in result.output

    def test_validate_shows_success_for_valid_config(self, tmp_path: Path) -> None:
        """validate shows success message for valid config."""
        from payment_simulator.experiments.cli import experiment_app

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
            optimized_agents:
              - BANK_A
        """)
        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["validate", str(config_path)])
        assert result.exit_code == 0
        assert "valid" in result.output.lower() or "test_exp" in result.output

    def test_validate_shows_error_for_missing_file(self, tmp_path: Path) -> None:
        """validate shows error for missing file."""
        from payment_simulator.experiments.cli import experiment_app

        nonexistent = tmp_path / "nonexistent.yaml"
        runner = CliRunner()
        result = runner.invoke(experiment_app, ["validate", str(nonexistent)])
        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_validate_shows_error_for_yaml_syntax_error(self, tmp_path: Path) -> None:
        """validate shows error for YAML syntax errors."""
        from payment_simulator.experiments.cli import experiment_app

        yaml_content = "name: test\n  invalid: yaml syntax"
        config_path = tmp_path / "invalid.yaml"
        config_path.write_text(yaml_content)

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["validate", str(config_path)])
        assert result.exit_code != 0

    def test_validate_shows_error_for_missing_required_fields(
        self, tmp_path: Path
    ) -> None:
        """validate shows error for missing required fields."""
        from payment_simulator.experiments.cli import experiment_app

        yaml_content = dedent("""
            name: test_exp
            # Missing required fields
        """)
        config_path = tmp_path / "incomplete.yaml"
        config_path.write_text(yaml_content)

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["validate", str(config_path)])
        assert result.exit_code != 0

    def test_validate_shows_summary_of_config(self, tmp_path: Path) -> None:
        """validate shows summary of valid config."""
        from payment_simulator.experiments.cli import experiment_app

        yaml_content = dedent("""
            name: test_exp
            description: "Test experiment"
            scenario: configs/test.yaml
            evaluation:
              mode: bootstrap
              num_samples: 10
              ticks: 2
            convergence:
              max_iterations: 25
            llm:
              model: "anthropic:claude-sonnet-4-5"
            optimized_agents:
              - BANK_A
              - BANK_B
        """)
        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["validate", str(config_path)])
        assert result.exit_code == 0
        # Should show some summary information
        assert "bootstrap" in result.output.lower() or "BANK_A" in result.output


class TestInfoCommand:
    """Tests for experiment info command."""

    def test_info_command_exists(self) -> None:
        """info command exists in experiment_app."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["info", "--help"])
        assert result.exit_code == 0

    def test_info_requires_config_path(self) -> None:
        """info requires experiment config path argument."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["info"])
        # Should fail or show help for missing argument
        assert result.exit_code != 0 or "CONFIG_PATH" in result.output

    def test_info_shows_experiment_name(self, tmp_path: Path) -> None:
        """info shows experiment name."""
        from payment_simulator.experiments.cli import experiment_app

        yaml_content = dedent("""
            name: my_test_experiment
            description: "Test experiment"
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

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["info", str(config_path)])
        assert result.exit_code == 0
        assert "my_test_experiment" in result.output

    def test_info_shows_description(self, tmp_path: Path) -> None:
        """info shows experiment description."""
        from payment_simulator.experiments.cli import experiment_app

        yaml_content = dedent("""
            name: test_exp
            description: "A detailed test experiment description"
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

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["info", str(config_path)])
        assert result.exit_code == 0
        assert "detailed test experiment" in result.output

    def test_info_shows_evaluation_mode(self, tmp_path: Path) -> None:
        """info shows evaluation mode (bootstrap/deterministic)."""
        from payment_simulator.experiments.cli import experiment_app

        yaml_content = dedent("""
            name: test_exp
            description: "Test"
            scenario: configs/test.yaml
            evaluation:
              mode: bootstrap
              num_samples: 15
              ticks: 5
            convergence:
              max_iterations: 10
            llm:
              model: "anthropic:claude-sonnet-4-5"
            optimized_agents:
              - BANK_A
        """)
        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["info", str(config_path)])
        assert result.exit_code == 0
        assert "bootstrap" in result.output.lower()

    def test_info_shows_convergence_settings(self, tmp_path: Path) -> None:
        """info shows convergence criteria."""
        from payment_simulator.experiments.cli import experiment_app

        yaml_content = dedent("""
            name: test_exp
            description: "Test"
            scenario: configs/test.yaml
            evaluation:
              mode: deterministic
              ticks: 2
            convergence:
              max_iterations: 42
              stability_threshold: 0.05
              stability_window: 7
            llm:
              model: "anthropic:claude-sonnet-4-5"
            optimized_agents:
              - BANK_A
        """)
        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["info", str(config_path)])
        assert result.exit_code == 0
        assert "42" in result.output  # max_iterations

    def test_info_shows_llm_config(self, tmp_path: Path) -> None:
        """info shows LLM model configuration."""
        from payment_simulator.experiments.cli import experiment_app

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
              temperature: 0.7
            optimized_agents:
              - BANK_A
        """)
        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["info", str(config_path)])
        assert result.exit_code == 0
        assert "claude-sonnet" in result.output.lower() or "anthropic" in result.output.lower()

    def test_info_shows_optimized_agents(self, tmp_path: Path) -> None:
        """info shows list of optimized agents."""
        from payment_simulator.experiments.cli import experiment_app

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
              - BANK_B
              - BANK_C
        """)
        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["info", str(config_path)])
        assert result.exit_code == 0
        assert "BANK_A" in result.output
        assert "BANK_B" in result.output
        assert "BANK_C" in result.output

    def test_info_handles_missing_file(self, tmp_path: Path) -> None:
        """info shows error for missing file."""
        from payment_simulator.experiments.cli import experiment_app

        nonexistent = tmp_path / "nonexistent.yaml"
        runner = CliRunner()
        result = runner.invoke(experiment_app, ["info", str(nonexistent)])
        assert result.exit_code != 0


class TestListCommand:
    """Tests for experiment list command."""

    def test_list_command_exists(self) -> None:
        """list command exists in experiment_app."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["list", "--help"])
        assert result.exit_code == 0

    def test_list_scans_directory(self, tmp_path: Path) -> None:
        """list scans directory for YAML files."""
        from payment_simulator.experiments.cli import experiment_app

        # Create a YAML file in directory
        yaml_content = dedent("""
            name: exp1
            description: "Test experiment"
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
        (tmp_path / "exp1.yaml").write_text(yaml_content)

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["list", str(tmp_path)])
        assert result.exit_code == 0
        assert "exp1" in result.output

    def test_list_shows_multiple_experiments(self, tmp_path: Path) -> None:
        """list shows all experiments in directory."""
        from payment_simulator.experiments.cli import experiment_app

        # Create multiple YAML files
        for name in ["exp1", "exp2", "exp3"]:
            yaml_content = dedent(f"""
                name: {name}
                description: "Test {name}"
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
            (tmp_path / f"{name}.yaml").write_text(yaml_content)

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["list", str(tmp_path)])
        assert result.exit_code == 0
        assert "exp1" in result.output
        assert "exp2" in result.output
        assert "exp3" in result.output

    def test_list_shows_descriptions(self, tmp_path: Path) -> None:
        """list shows experiment descriptions."""
        from payment_simulator.experiments.cli import experiment_app

        yaml_content = dedent("""
            name: exp1
            description: "A unique test description here"
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
        (tmp_path / "exp1.yaml").write_text(yaml_content)

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["list", str(tmp_path)])
        assert result.exit_code == 0
        # Description should appear (possibly truncated)
        assert "unique test" in result.output.lower() or "description" in result.output.lower()

    def test_list_handles_empty_directory(self, tmp_path: Path) -> None:
        """list handles empty directory gracefully."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["list", str(tmp_path)])
        assert result.exit_code == 0
        # Should show some message about no experiments
        assert "no" in result.output.lower() or "empty" in result.output.lower() or "0" in result.output

    def test_list_handles_invalid_yaml(self, tmp_path: Path) -> None:
        """list skips invalid YAML files with warning."""
        from payment_simulator.experiments.cli import experiment_app

        # Create valid and invalid YAML files
        valid_yaml = dedent("""
            name: valid_exp
            description: "Valid"
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
        (tmp_path / "valid.yaml").write_text(valid_yaml)
        (tmp_path / "invalid.yaml").write_text("name: test\n  broken: yaml")

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["list", str(tmp_path)])
        # Should succeed but potentially show warning
        assert result.exit_code == 0
        assert "valid_exp" in result.output

    def test_list_uses_current_directory_if_not_specified(self) -> None:
        """list uses current directory if not specified."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        # Just check it doesn't crash when no dir is specified
        result = runner.invoke(experiment_app, ["list"])
        # May have experiments or show "no experiments"
        assert result.exit_code == 0

    def test_list_handles_nonexistent_directory(self, tmp_path: Path) -> None:
        """list shows error for nonexistent directory."""
        from payment_simulator.experiments.cli import experiment_app

        nonexistent = tmp_path / "nonexistent_dir"
        runner = CliRunner()
        result = runner.invoke(experiment_app, ["list", str(nonexistent)])
        assert result.exit_code != 0


class TestRunCommand:
    """Tests for experiment run command."""

    def test_run_command_exists(self) -> None:
        """run command exists in experiment_app."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["run", "--help"])
        assert result.exit_code == 0

    def test_run_requires_config_path(self) -> None:
        """run requires experiment config path argument."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["run"])
        # Should fail or show help for missing argument
        assert result.exit_code != 0 or "CONFIG_PATH" in result.output

    def test_run_accepts_dry_run_flag(self) -> None:
        """run --dry-run flag exists."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["run", "--help"])
        assert "--dry-run" in result.output

    def test_run_dry_run_validates_without_executing(self, tmp_path: Path) -> None:
        """run --dry-run validates config without executing experiment."""
        from payment_simulator.experiments.cli import experiment_app

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
            optimized_agents:
              - BANK_A
        """)
        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["run", str(config_path), "--dry-run"])
        assert result.exit_code == 0
        assert "valid" in result.output.lower() or "dry" in result.output.lower()

    def test_run_accepts_seed_override(self) -> None:
        """run --seed flag exists."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["run", "--help"])
        assert "--seed" in result.output

    def test_run_accepts_verbose_flags(self) -> None:
        """run accepts --verbose and individual verbose flags."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["run", "--help"])
        assert "--verbose" in result.output

    def test_run_handles_missing_file(self, tmp_path: Path) -> None:
        """run shows error for missing config file."""
        from payment_simulator.experiments.cli import experiment_app

        nonexistent = tmp_path / "nonexistent.yaml"
        runner = CliRunner()
        result = runner.invoke(experiment_app, ["run", str(nonexistent)])
        assert result.exit_code != 0

    def test_run_handles_invalid_config(self, tmp_path: Path) -> None:
        """run shows error for invalid config."""
        from payment_simulator.experiments.cli import experiment_app

        yaml_content = "name: incomplete"
        config_path = tmp_path / "invalid.yaml"
        config_path.write_text(yaml_content)

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["run", str(config_path)])
        assert result.exit_code != 0

    def test_run_accepts_db_path(self) -> None:
        """run accepts --db option for persistence."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["run", "--help"])
        assert "--db" in result.output


class TestRunCommandVerboseFlags:
    """Tests for run command verbose flag handling."""

    def test_run_has_verbose_iterations(self) -> None:
        """run command has --verbose-iterations option."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["run", "--help"])
        assert "--verbose-iterations" in result.output

    def test_run_has_verbose_bootstrap(self) -> None:
        """run command has --verbose-bootstrap option."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["run", "--help"])
        assert "--verbose-bootstrap" in result.output

    def test_run_has_verbose_llm(self) -> None:
        """run command has --verbose-llm option."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["run", "--help"])
        assert "--verbose-llm" in result.output

    def test_run_has_verbose_policy(self) -> None:
        """run command has --verbose-policy option."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["run", "--help"])
        assert "--verbose-policy" in result.output


class TestTemplateCommand:
    """Tests for experiment template command (Phase 4 CLI Cleanup)."""

    def test_template_command_exists(self) -> None:
        """template command exists in experiment_app."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["template", "--help"])
        assert result.exit_code == 0
        assert "template" in result.output.lower() or "generate" in result.output.lower()

    def test_template_generates_valid_yaml(self) -> None:
        """template command generates valid experiment YAML."""
        import yaml

        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["template"])
        assert result.exit_code == 0

        # Parse the output as YAML
        config = yaml.safe_load(result.output)

        # Verify required fields
        assert "name" in config
        assert "evaluation" in config
        assert "convergence" in config
        assert "optimized_agents" in config

    def test_template_has_required_fields(self) -> None:
        """template output has all required fields for experiment config."""
        import yaml

        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["template"])
        assert result.exit_code == 0

        config = yaml.safe_load(result.output)

        # Check all required fields for ExperimentConfig
        assert "name" in config
        assert "scenario" in config
        assert "evaluation" in config
        assert "mode" in config["evaluation"]
        assert "ticks" in config["evaluation"]
        assert "convergence" in config
        assert "max_iterations" in config["convergence"]
        assert "llm" in config
        assert "model" in config["llm"]
        assert "optimized_agents" in config
        assert isinstance(config["optimized_agents"], list)

    def test_template_can_write_to_file(self, tmp_path: Path) -> None:
        """template command can write to output file."""
        import yaml

        from payment_simulator.experiments.cli import experiment_app

        output_file = tmp_path / "template.yaml"
        runner = CliRunner()
        result = runner.invoke(experiment_app, ["template", "-o", str(output_file)])

        assert result.exit_code == 0
        assert output_file.exists()

        # Verify file contents
        with open(output_file) as f:
            config = yaml.safe_load(f)
        assert "name" in config

    def test_template_output_option_long_form(self, tmp_path: Path) -> None:
        """template command accepts --output option."""
        import yaml

        from payment_simulator.experiments.cli import experiment_app

        output_file = tmp_path / "template.yaml"
        runner = CliRunner()
        result = runner.invoke(
            experiment_app, ["template", "--output", str(output_file)]
        )

        assert result.exit_code == 0
        assert output_file.exists()

        with open(output_file) as f:
            config = yaml.safe_load(f)
        assert "name" in config

    def test_template_shows_success_message_when_writing_file(
        self, tmp_path: Path
    ) -> None:
        """template shows success message when writing to file."""
        from payment_simulator.experiments.cli import experiment_app

        output_file = tmp_path / "template.yaml"
        runner = CliRunner()
        result = runner.invoke(experiment_app, ["template", "-o", str(output_file)])

        assert result.exit_code == 0
        # Should show some confirmation message
        assert "template" in result.output.lower() or str(output_file) in result.output


class TestMainCLIIntegration:
    """Tests for main CLI integration with experiment commands."""

    def test_main_cli_has_experiment_subcommand(self) -> None:
        """Main CLI has 'experiment' subcommand."""
        from payment_simulator.cli.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["experiment", "--help"])
        assert result.exit_code == 0
        assert "experiment" in result.output.lower()

    def test_main_cli_experiment_run_accessible(self) -> None:
        """Run command accessible via main CLI."""
        from payment_simulator.cli.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["experiment", "run", "--help"])
        assert result.exit_code == 0
        assert "run" in result.output.lower()

    def test_main_cli_experiment_replay_accessible(self) -> None:
        """Replay command accessible via main CLI."""
        from payment_simulator.cli.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["experiment", "replay", "--help"])
        assert result.exit_code == 0
        assert "replay" in result.output.lower()

    def test_main_cli_experiment_results_accessible(self) -> None:
        """Results command accessible via main CLI."""
        from payment_simulator.cli.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["experiment", "results", "--help"])
        assert result.exit_code == 0

    def test_main_cli_experiment_template_accessible(self) -> None:
        """Template command accessible via main CLI."""
        from payment_simulator.cli.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["experiment", "template", "--help"])
        assert result.exit_code == 0

    def test_main_cli_experiment_validate_accessible(self) -> None:
        """Validate command accessible via main CLI."""
        from payment_simulator.cli.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["experiment", "validate", "--help"])
        assert result.exit_code == 0

    def test_main_cli_experiment_list_accessible(self) -> None:
        """List command accessible via main CLI."""
        from payment_simulator.cli.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["experiment", "list", "--help"])
        assert result.exit_code == 0

    def test_main_cli_experiment_info_accessible(self) -> None:
        """Info command accessible via main CLI."""
        from payment_simulator.cli.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["experiment", "info", "--help"])
        assert result.exit_code == 0
