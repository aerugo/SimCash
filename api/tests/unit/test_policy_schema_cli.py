"""TDD tests for policy-schema CLI command."""

import json
import pytest
from typer.testing import CliRunner


class TestPolicySchemaCommand:
    """Tests for payment-sim policy-schema command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def app(self):
        from payment_simulator.cli.main import app
        return app

    def test_policy_schema_command_exists(self, runner, app):
        """Command should be registered."""
        result = runner.invoke(app, ["policy-schema", "--help"])
        assert result.exit_code == 0
        assert "Generate policy schema documentation" in result.output

    def test_policy_schema_json_format(self, runner, app):
        """--format json should output valid JSON."""
        result = runner.invoke(app, ["policy-schema", "--format", "json"])
        assert result.exit_code == 0

        schema = json.loads(result.output)
        assert "version" in schema
        assert "expressions" in schema

    def test_policy_schema_markdown_format(self, runner, app):
        """--format markdown should output markdown."""
        result = runner.invoke(app, ["policy-schema", "--format", "markdown"])
        assert result.exit_code == 0
        assert "# Policy Schema Reference" in result.output

    def test_policy_schema_default_format_is_markdown(self, runner, app):
        """Default format should be markdown."""
        result = runner.invoke(app, ["policy-schema"])
        assert result.exit_code == 0
        assert "# Policy Schema Reference" in result.output

    def test_policy_schema_section_filter(self, runner, app):
        """--section should filter to specific sections."""
        result = runner.invoke(app, ["policy-schema", "--format", "json", "--section", "actions"])
        assert result.exit_code == 0

        schema = json.loads(result.output)
        assert "actions" in schema
        # Other sections should be absent or None
        assert schema.get("expressions") in [None, []]
        assert schema.get("fields") in [None, []]

    def test_policy_schema_category_filter(self, runner, app):
        """--category should filter by category."""
        result = runner.invoke(app, ["policy-schema", "--format", "json", "--category", "PaymentAction"])
        assert result.exit_code == 0

        schema = json.loads(result.output)
        # Only payment actions should be present
        if "actions" in schema and schema["actions"]:
            for action in schema["actions"]:
                assert action["category"] == "PaymentAction"

    def test_policy_schema_exclude_category(self, runner, app):
        """--exclude-category should exclude categories."""
        result = runner.invoke(app, ["policy-schema", "--format", "json", "--exclude-category", "CollateralAction"])
        assert result.exit_code == 0

        schema = json.loads(result.output)
        if "actions" in schema and schema["actions"]:
            for action in schema["actions"]:
                assert action["category"] != "CollateralAction"

    def test_policy_schema_tree_filter(self, runner, app):
        """--tree should filter to elements valid in specific trees."""
        result = runner.invoke(app, ["policy-schema", "--format", "json", "--tree", "bank_tree"])
        assert result.exit_code == 0

        schema = json.loads(result.output)
        # Actions valid in bank_tree should be present
        if "actions" in schema and schema["actions"]:
            for action in schema["actions"]:
                assert "bank_tree" in action.get("valid_in_trees", [])

    def test_policy_schema_output_file(self, runner, app, tmp_path):
        """--output should write to file."""
        output_file = tmp_path / "schema.json"
        result = runner.invoke(app, ["policy-schema", "--format", "json", "--output", str(output_file)])
        assert result.exit_code == 0

        assert output_file.exists()
        schema = json.loads(output_file.read_text())
        assert "version" in schema

    def test_policy_schema_compact_mode(self, runner, app):
        """--compact should produce shorter output."""
        full_result = runner.invoke(app, ["policy-schema", "--format", "markdown"])
        compact_result = runner.invoke(app, ["policy-schema", "--format", "markdown", "--compact"])

        assert compact_result.exit_code == 0
        # Compact should be shorter
        assert len(compact_result.output) < len(full_result.output)

    def test_policy_schema_no_examples(self, runner, app):
        """--no-examples should exclude JSON examples."""
        with_examples = runner.invoke(app, ["policy-schema", "--format", "markdown"])
        without_examples = runner.invoke(app, ["policy-schema", "--format", "markdown", "--no-examples"])

        assert without_examples.exit_code == 0
        # Without examples should be shorter
        assert len(without_examples.output) < len(with_examples.output)
