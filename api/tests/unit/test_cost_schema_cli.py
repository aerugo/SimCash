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

    # -------------------------------------------------------------------------
    # TDD Tests for new features: exclude-category, include, exclude, scenario
    # -------------------------------------------------------------------------

    def test_cost_schema_exclude_category(self, runner: CliRunner, app: Any) -> None:
        """--exclude-category should exclude specified categories."""
        result = runner.invoke(
            app, ["cost-schema", "--format", "json", "--exclude-category", "Modifier"]
        )
        assert result.exit_code == 0

        schema = json.loads(result.output)
        # Modifier costs should not be present
        for cost in schema.get("cost_types", []):
            assert cost["category"] != "Modifier"

        # Should have 7 costs (9 total - 2 Modifier)
        assert len(schema["cost_types"]) == 7

    def test_cost_schema_multiple_exclude_categories(
        self, runner: CliRunner, app: Any
    ) -> None:
        """Multiple --exclude-category options should exclude all specified."""
        result = runner.invoke(
            app,
            [
                "cost-schema",
                "--format",
                "json",
                "--exclude-category",
                "Modifier",
                "--exclude-category",
                "Daily",
            ],
        )
        assert result.exit_code == 0

        schema = json.loads(result.output)
        categories = {c["category"] for c in schema.get("cost_types", [])}

        # Should not contain Modifier or Daily
        assert "Modifier" not in categories
        assert "Daily" not in categories

        # Should have 6 costs (9 - 2 Modifier - 1 Daily)
        assert len(schema["cost_types"]) == 6

    def test_cost_schema_include_cost_names(self, runner: CliRunner, app: Any) -> None:
        """--include should filter to only specific cost names."""
        result = runner.invoke(
            app,
            [
                "cost-schema",
                "--format",
                "json",
                "--include",
                "overdraft_bps_per_tick",
                "--include",
                "deadline_penalty",
            ],
        )
        assert result.exit_code == 0

        schema = json.loads(result.output)
        names = {c["name"] for c in schema.get("cost_types", [])}

        # Should only have the included costs
        assert names == {"overdraft_bps_per_tick", "deadline_penalty"}
        assert len(schema["cost_types"]) == 2

    def test_cost_schema_exclude_cost_names(self, runner: CliRunner, app: Any) -> None:
        """--exclude should filter out specific cost names."""
        result = runner.invoke(
            app,
            [
                "cost-schema",
                "--format",
                "json",
                "--exclude",
                "priority_delay_multipliers",
                "--exclude",
                "liquidity_cost_per_tick_bps",
            ],
        )
        assert result.exit_code == 0

        schema = json.loads(result.output)
        names = {c["name"] for c in schema.get("cost_types", [])}

        # Should not contain excluded costs
        assert "priority_delay_multipliers" not in names
        assert "liquidity_cost_per_tick_bps" not in names

        # Should have 7 costs (9 - 2)
        assert len(schema["cost_types"]) == 7

    def test_cost_schema_category_and_exclude_category(
        self, runner: CliRunner, app: Any
    ) -> None:
        """--category and --exclude-category can be combined."""
        # Include PerTick and OneTime, but exclude PerTick (should leave only OneTime)
        result = runner.invoke(
            app,
            [
                "cost-schema",
                "--format",
                "json",
                "--category",
                "PerTick",
                "--category",
                "OneTime",
                "--exclude-category",
                "PerTick",
            ],
        )
        assert result.exit_code == 0

        schema = json.loads(result.output)
        categories = {c["category"] for c in schema.get("cost_types", [])}

        # Should only have OneTime (PerTick excluded)
        assert categories == {"OneTime"}
        assert len(schema["cost_types"]) == 2

    def test_cost_schema_include_and_category_combined(
        self, runner: CliRunner, app: Any
    ) -> None:
        """--include and --category can be combined (intersection)."""
        # Include specific costs, but also filter by category
        result = runner.invoke(
            app,
            [
                "cost-schema",
                "--format",
                "json",
                "--include",
                "overdraft_bps_per_tick",
                "--include",
                "deadline_penalty",  # This is OneTime, not PerTick
                "--category",
                "PerTick",
            ],
        )
        assert result.exit_code == 0

        schema = json.loads(result.output)
        names = {c["name"] for c in schema.get("cost_types", [])}

        # Only overdraft_bps_per_tick should remain (PerTick + in include list)
        assert names == {"overdraft_bps_per_tick"}

    def test_cost_schema_scenario_filter(
        self, runner: CliRunner, app: Any, tmp_path: Path
    ) -> None:
        """--scenario should filter based on scenario's cost_feature_toggles."""
        # Create a scenario file with cost_feature_toggles
        scenario_content = """
simulation:
  ticks_per_day: 100
  num_days: 1
  rng_seed: 42

agents:
  - id: BANK_A
    opening_balance: 1000000

cost_feature_toggles:
  include:
    - PerTick
"""
        scenario_file = tmp_path / "scenario.yaml"
        scenario_file.write_text(scenario_content)

        result = runner.invoke(
            app,
            ["cost-schema", "--format", "json", "--scenario", str(scenario_file)],
        )
        assert result.exit_code == 0

        schema = json.loads(result.output)
        categories = {c["category"] for c in schema.get("cost_types", [])}

        # Should only have PerTick costs
        assert categories == {"PerTick"}
        assert len(schema["cost_types"]) == 4

    def test_cost_schema_scenario_exclude(
        self, runner: CliRunner, app: Any, tmp_path: Path
    ) -> None:
        """--scenario with exclude should filter out categories."""
        scenario_content = """
simulation:
  ticks_per_day: 100
  num_days: 1
  rng_seed: 42

agents:
  - id: BANK_A
    opening_balance: 1000000

cost_feature_toggles:
  exclude:
    - Modifier
    - Daily
"""
        scenario_file = tmp_path / "scenario.yaml"
        scenario_file.write_text(scenario_content)

        result = runner.invoke(
            app,
            ["cost-schema", "--format", "json", "--scenario", str(scenario_file)],
        )
        assert result.exit_code == 0

        schema = json.loads(result.output)
        categories = {c["category"] for c in schema.get("cost_types", [])}

        # Should not have Modifier or Daily
        assert "Modifier" not in categories
        assert "Daily" not in categories

    def test_cost_schema_scenario_and_cli_combined(
        self, runner: CliRunner, app: Any, tmp_path: Path
    ) -> None:
        """CLI options and scenario toggles should combine."""
        # Scenario includes PerTick and OneTime
        scenario_content = """
simulation:
  ticks_per_day: 100
  num_days: 1
  rng_seed: 42

agents:
  - id: BANK_A
    opening_balance: 1000000

cost_feature_toggles:
  include:
    - PerTick
    - OneTime
"""
        scenario_file = tmp_path / "scenario.yaml"
        scenario_file.write_text(scenario_content)

        # CLI further restricts to only PerTick
        result = runner.invoke(
            app,
            [
                "cost-schema",
                "--format",
                "json",
                "--scenario",
                str(scenario_file),
                "--category",
                "PerTick",
            ],
        )
        assert result.exit_code == 0

        schema = json.loads(result.output)
        categories = {c["category"] for c in schema.get("cost_types", [])}

        # Should only have PerTick (intersection of scenario and CLI)
        assert categories == {"PerTick"}

    def test_cost_schema_invalid_scenario_file(
        self, runner: CliRunner, app: Any, tmp_path: Path
    ) -> None:
        """--scenario with invalid file should error gracefully."""
        result = runner.invoke(
            app,
            ["cost-schema", "--scenario", "/nonexistent/path.yaml"],
        )
        assert result.exit_code == 1
        assert "Error loading scenario" in result.output
