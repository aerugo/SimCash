"""Unit tests for AI Cash Management CLI commands.

TDD: These tests are written BEFORE the implementation.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner


runner = CliRunner()


class TestAiGameValidate:
    """Test ai-game validate command."""

    def test_validate_valid_config(self, tmp_path: Path) -> None:
        """Should validate a correct game config file."""
        from payment_simulator.cli.main import app

        # Create a valid game config
        config = {
            "game_id": "test_game",
            "scenario_config": "scenarios/test.yaml",
            "master_seed": 42,
            "optimized_agents": {
                "BANK_A": {},
                "BANK_B": {"llm_config": {"model": "gpt-5.1"}},
            },
            "default_llm_config": {
                "provider": "openai",
                "model": "gpt-5.1",
            },
            "optimization_schedule": {
                "type": "every_x_ticks",
                "interval_ticks": 50,
            },
            "monte_carlo": {
                "num_samples": 20,
                "sample_method": "bootstrap",
                "evaluation_ticks": 100,
            },
            "convergence": {
                "stability_threshold": 0.05,
                "stability_window": 3,
                "max_iterations": 50,
                "improvement_threshold": 0.01,
            },
        }

        config_path = tmp_path / "game_config.yaml"
        config_path.write_text(yaml.dump(config))

        result = runner.invoke(app, ["ai-game", "validate", str(config_path)])

        assert result.exit_code == 0
        assert "valid" in result.output.lower()

    def test_validate_invalid_config_missing_field(self, tmp_path: Path) -> None:
        """Should report error for missing required field."""
        from payment_simulator.cli.main import app

        # Config missing required fields
        config = {
            "game_id": "test_game",
            # Missing scenario_config, master_seed, etc.
        }

        config_path = tmp_path / "game_config.yaml"
        config_path.write_text(yaml.dump(config))

        result = runner.invoke(app, ["ai-game", "validate", str(config_path)])

        assert result.exit_code != 0
        assert "error" in result.output.lower() or "missing" in result.output.lower()

    def test_validate_nonexistent_file(self) -> None:
        """Should report error for nonexistent file."""
        from payment_simulator.cli.main import app

        result = runner.invoke(app, ["ai-game", "validate", "/nonexistent/path.yaml"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "error" in result.output.lower()


class TestAiGameInfo:
    """Test ai-game info command."""

    def test_info_shows_module_info(self) -> None:
        """Should show module information."""
        from payment_simulator.cli.main import app

        result = runner.invoke(app, ["ai-game", "info"])

        assert result.exit_code == 0
        assert "ai cash management" in result.output.lower()

    def test_info_shows_available_modes(self) -> None:
        """Should list available game modes."""
        from payment_simulator.cli.main import app

        result = runner.invoke(app, ["ai-game", "info"])

        assert result.exit_code == 0
        assert "rl_optimization" in result.output.lower() or "optimization" in result.output.lower()


class TestAiGameConfigTemplate:
    """Test ai-game config-template command."""

    def test_config_template_generates_yaml(self, tmp_path: Path) -> None:
        """Should generate a valid YAML config template."""
        from payment_simulator.cli.main import app

        output_path = tmp_path / "template.yaml"
        result = runner.invoke(app, ["ai-game", "config-template", "-o", str(output_path)])

        assert result.exit_code == 0
        assert output_path.exists()

        # Should be valid YAML
        with open(output_path) as f:
            template = yaml.safe_load(f)

        # Should have required sections
        assert "game_id" in template
        assert "optimization_schedule" in template
        assert "monte_carlo" in template

    def test_config_template_stdout_if_no_output(self) -> None:
        """Should output to stdout if no -o specified."""
        from payment_simulator.cli.main import app

        result = runner.invoke(app, ["ai-game", "config-template"])

        assert result.exit_code == 0
        assert "game_id" in result.output


class TestAiGameSubcommandGroup:
    """Test ai-game subcommand group."""

    def test_ai_game_shows_help(self) -> None:
        """ai-game without subcommand should show help."""
        from payment_simulator.cli.main import app

        result = runner.invoke(app, ["ai-game"])

        # no_args_is_help=True exits with code 2 but shows help content
        assert "validate" in result.output
        assert "info" in result.output

    def test_ai_game_help_shows_commands(self) -> None:
        """ai-game --help should list all commands."""
        from payment_simulator.cli.main import app

        result = runner.invoke(app, ["ai-game", "--help"])

        assert result.exit_code == 0
        assert "validate" in result.output
        assert "info" in result.output
        assert "config-template" in result.output


class TestAiGameSchemas:
    """Test ai-game schema command."""

    def test_schema_shows_game_config_schema(self) -> None:
        """Should output GameConfig JSON schema."""
        from payment_simulator.cli.main import app

        result = runner.invoke(app, ["ai-game", "schema", "game-config"])

        assert result.exit_code == 0
        # Should be valid JSON
        schema = json.loads(result.output)
        assert "properties" in schema or "$defs" in schema

    def test_schema_shows_llm_config_schema(self) -> None:
        """Should output LLMConfig JSON schema."""
        from payment_simulator.cli.main import app

        result = runner.invoke(app, ["ai-game", "schema", "llm-config"])

        assert result.exit_code == 0
        schema = json.loads(result.output)
        assert "properties" in schema or "$defs" in schema

    def test_schema_invalid_type_error(self) -> None:
        """Should error for unknown schema type."""
        from payment_simulator.cli.main import app

        result = runner.invoke(app, ["ai-game", "schema", "unknown-type"])

        assert result.exit_code != 0
