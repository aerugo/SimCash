"""TDD tests for cost-schema CLI command."""

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner


class TestCostSchemaCommand:
    """Tests for payment-sim cost-schema command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    @pytest.fixture
    def app(self) -> Any:
        from payment_simulator.cli.main import app

        return app

    def test_cost_schema_command_exists(self, runner: CliRunner, app: Any) -> None:
        """Command should be registered."""
        result = runner.invoke(app, ["cost-schema", "--help"])
        assert result.exit_code == 0
        assert "Generate cost types schema documentation" in result.output

    def test_cost_schema_json_format(self, runner: CliRunner, app: Any) -> None:
        """--format json should output valid JSON."""
        result = runner.invoke(app, ["cost-schema", "--format", "json"])
        assert result.exit_code == 0

        schema = json.loads(result.output)
        assert "version" in schema
        assert "cost_types" in schema

    def test_cost_schema_markdown_format(self, runner: CliRunner, app: Any) -> None:
        """--format markdown should output markdown."""
        result = runner.invoke(app, ["cost-schema", "--format", "markdown"])
        assert result.exit_code == 0
        assert "# Cost Types Reference" in result.output

    def test_cost_schema_default_format_is_markdown(self, runner: CliRunner, app: Any) -> None:
        """Default format should be markdown."""
        result = runner.invoke(app, ["cost-schema"])
        assert result.exit_code == 0
        assert "# Cost Types Reference" in result.output

    def test_cost_schema_category_filter(self, runner: CliRunner, app: Any) -> None:
        """--category should filter by category."""
        result = runner.invoke(app, ["cost-schema", "--format", "json", "--category", "PerTick"])
        assert result.exit_code == 0

        schema = json.loads(result.output)
        # Only per-tick costs should be present
        for cost in schema.get("cost_types", []):
            assert cost["category"] == "PerTick"

    def test_cost_schema_multiple_categories(self, runner: CliRunner, app: Any) -> None:
        """Multiple --category options should include all specified categories."""
        result = runner.invoke(
            app, ["cost-schema", "--format", "json", "--category", "PerTick", "--category", "OneTime"]
        )
        assert result.exit_code == 0

        schema = json.loads(result.output)
        categories = {c["category"] for c in schema.get("cost_types", [])}
        assert categories <= {"PerTick", "OneTime"}
        assert len(schema["cost_types"]) == 6  # 4 PerTick + 2 OneTime

    def test_cost_schema_output_file(
        self, runner: CliRunner, app: Any, tmp_path: Path
    ) -> None:
        """--output should write to file."""
        output_file = tmp_path / "costs.json"
        result = runner.invoke(
            app, ["cost-schema", "--format", "json", "--output", str(output_file)]
        )
        assert result.exit_code == 0

        assert output_file.exists()
        schema = json.loads(output_file.read_text())
        assert "version" in schema
        assert "cost_types" in schema

    def test_cost_schema_compact_mode(self, runner: CliRunner, app: Any) -> None:
        """--compact should produce table format."""
        result = runner.invoke(app, ["cost-schema", "--compact"])
        assert result.exit_code == 0

        # Should have table format with header
        assert "| Cost Type | Category | Default | Unit | Description |" in result.output
        assert "---" in result.output  # Table separator

    def test_cost_schema_compact_shorter_than_full(self, runner: CliRunner, app: Any) -> None:
        """--compact should produce shorter output."""
        full_result = runner.invoke(app, ["cost-schema", "--format", "markdown"])
        compact_result = runner.invoke(app, ["cost-schema", "--compact"])

        assert compact_result.exit_code == 0
        assert full_result.exit_code == 0
        # Compact should be significantly shorter
        assert len(compact_result.output) < len(full_result.output)

    def test_cost_schema_no_examples(self, runner: CliRunner, app: Any) -> None:
        """--no-examples should exclude examples."""
        with_examples = runner.invoke(app, ["cost-schema", "--format", "markdown"])
        without_examples = runner.invoke(
            app, ["cost-schema", "--format", "markdown", "--no-examples"]
        )

        assert without_examples.exit_code == 0
        # Without examples should be shorter
        assert len(without_examples.output) < len(with_examples.output)
        # Examples header should not appear
        assert "**Example:**" not in without_examples.output

    def test_cost_schema_contains_expected_costs(self, runner: CliRunner, app: Any) -> None:
        """Output should contain all expected cost type names."""
        result = runner.invoke(app, ["cost-schema", "--format", "json"])
        assert result.exit_code == 0

        schema = json.loads(result.output)
        names = {c["name"] for c in schema["cost_types"]}

        expected = {
            "overdraft_bps_per_tick",
            "delay_cost_per_tick_per_cent",
            "deadline_penalty",
            "eod_penalty_per_transaction",
        }
        assert expected <= names

    def test_cost_schema_markdown_has_formulas(self, runner: CliRunner, app: Any) -> None:
        """Markdown output should include formulas."""
        result = runner.invoke(app, ["cost-schema", "--format", "markdown"])
        assert result.exit_code == 0

        # Should have formula sections
        assert "**Formula:**" in result.output
        assert "```" in result.output  # Formula code blocks

    def test_cost_schema_markdown_has_defaults(self, runner: CliRunner, app: Any) -> None:
        """Markdown output should include default values."""
        result = runner.invoke(app, ["cost-schema", "--format", "markdown"])
        assert result.exit_code == 0

        # Should have default value sections
        assert "**Default:**" in result.output

    def test_cost_schema_markdown_categorized(self, runner: CliRunner, app: Any) -> None:
        """Markdown output should be organized by category."""
        result = runner.invoke(app, ["cost-schema", "--format", "markdown"])
        assert result.exit_code == 0

        # Should have category headers
        assert "## Per-Tick Costs" in result.output
        assert "## One-Time Penalties" in result.output
        assert "## Daily Penalties" in result.output
        assert "## Cost Modifiers" in result.output
