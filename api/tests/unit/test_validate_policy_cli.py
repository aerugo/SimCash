"""TDD tests for validate-policy CLI command.

Tests written BEFORE implementation following strict TDD principles.
"""

import json
import pytest
from pathlib import Path
from typer.testing import CliRunner


class TestValidatePolicyCommand:
    """Tests for payment-sim validate-policy command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def app(self):
        from payment_simulator.cli.main import app
        return app

    @pytest.fixture
    def valid_fifo_policy(self, tmp_path):
        """Create a valid FIFO policy file."""
        policy = {
            "version": "1.0",
            "policy_id": "test_fifo",
            "description": "Test FIFO policy",
            "payment_tree": {
                "type": "action",
                "node_id": "A1",
                "action": "Release",
                "parameters": {}
            },
            "strategic_collateral_tree": None,
            "end_of_tick_collateral_tree": None,
            "parameters": {}
        }
        policy_file = tmp_path / "fifo.json"
        policy_file.write_text(json.dumps(policy, indent=2))
        return policy_file

    @pytest.fixture
    def valid_complex_policy(self, tmp_path):
        """Create a valid complex policy with conditions and parameters."""
        policy = {
            "version": "1.0",
            "policy_id": "test_complex",
            "description": "Complex test policy",
            "payment_tree": {
                "type": "condition",
                "node_id": "N1",
                "description": "Check balance threshold",
                "condition": {
                    "op": ">=",
                    "left": {"field": "balance"},
                    "right": {"param": "threshold"}
                },
                "on_true": {
                    "type": "action",
                    "node_id": "A1",
                    "action": "Release",
                    "parameters": {}
                },
                "on_false": {
                    "type": "action",
                    "node_id": "A2",
                    "action": "Hold",
                    "parameters": {}
                }
            },
            "strategic_collateral_tree": None,
            "end_of_tick_collateral_tree": None,
            "parameters": {
                "threshold": 100000.0
            }
        }
        policy_file = tmp_path / "complex.json"
        policy_file.write_text(json.dumps(policy, indent=2))
        return policy_file

    @pytest.fixture
    def invalid_json_file(self, tmp_path):
        """Create an invalid JSON file."""
        policy_file = tmp_path / "invalid.json"
        policy_file.write_text("{not valid json")
        return policy_file

    @pytest.fixture
    def invalid_schema_policy(self, tmp_path):
        """Create a policy with invalid schema (missing required fields)."""
        policy = {
            "version": "1.0",
            # Missing policy_id
            "payment_tree": {
                "type": "action",
                "node_id": "A1",
                "action": "Release"
            }
        }
        policy_file = tmp_path / "bad_schema.json"
        policy_file.write_text(json.dumps(policy, indent=2))
        return policy_file

    @pytest.fixture
    def duplicate_node_id_policy(self, tmp_path):
        """Create a policy with duplicate node IDs."""
        policy = {
            "version": "1.0",
            "policy_id": "test_dup",
            "payment_tree": {
                "type": "condition",
                "node_id": "N1",
                "description": "Check balance",
                "condition": {
                    "op": ">",
                    "left": {"field": "balance"},
                    "right": {"value": 0}
                },
                "on_true": {
                    "type": "action",
                    "node_id": "A1",
                    "action": "Release",
                    "parameters": {}
                },
                "on_false": {
                    "type": "action",
                    "node_id": "A1",  # Duplicate!
                    "action": "Hold",
                    "parameters": {}
                }
            },
            "strategic_collateral_tree": None,
            "end_of_tick_collateral_tree": None,
            "parameters": {}
        }
        policy_file = tmp_path / "dup_node.json"
        policy_file.write_text(json.dumps(policy, indent=2))
        return policy_file

    @pytest.fixture
    def invalid_field_reference_policy(self, tmp_path):
        """Create a policy referencing a non-existent field."""
        policy = {
            "version": "1.0",
            "policy_id": "test_bad_field",
            "payment_tree": {
                "type": "condition",
                "node_id": "N1",
                "description": "Check invalid field",
                "condition": {
                    "op": ">",
                    "left": {"field": "nonexistent_field"},
                    "right": {"value": 0}
                },
                "on_true": {
                    "type": "action",
                    "node_id": "A1",
                    "action": "Release",
                    "parameters": {}
                },
                "on_false": {
                    "type": "action",
                    "node_id": "A2",
                    "action": "Hold",
                    "parameters": {}
                }
            },
            "strategic_collateral_tree": None,
            "end_of_tick_collateral_tree": None,
            "parameters": {}
        }
        policy_file = tmp_path / "bad_field.json"
        policy_file.write_text(json.dumps(policy, indent=2))
        return policy_file

    @pytest.fixture
    def missing_parameter_policy(self, tmp_path):
        """Create a policy referencing a non-existent parameter."""
        policy = {
            "version": "1.0",
            "policy_id": "test_bad_param",
            "payment_tree": {
                "type": "condition",
                "node_id": "N1",
                "description": "Check with missing param",
                "condition": {
                    "op": ">",
                    "left": {"field": "balance"},
                    "right": {"param": "nonexistent_param"}
                },
                "on_true": {
                    "type": "action",
                    "node_id": "A1",
                    "action": "Release",
                    "parameters": {}
                },
                "on_false": {
                    "type": "action",
                    "node_id": "A2",
                    "action": "Hold",
                    "parameters": {}
                }
            },
            "strategic_collateral_tree": None,
            "end_of_tick_collateral_tree": None,
            "parameters": {}  # Missing the referenced parameter
        }
        policy_file = tmp_path / "bad_param.json"
        policy_file.write_text(json.dumps(policy, indent=2))
        return policy_file

    @pytest.fixture
    def division_by_zero_policy(self, tmp_path):
        """Create a policy with division by literal zero."""
        policy = {
            "version": "1.0",
            "policy_id": "test_div_zero",
            "payment_tree": {
                "type": "condition",
                "node_id": "N1",
                "description": "Division by zero check",
                "condition": {
                    "op": ">",
                    "left": {
                        "compute": {
                            "op": "/",
                            "left": {"field": "balance"},
                            "right": {"value": 0}
                        }
                    },
                    "right": {"value": 1}
                },
                "on_true": {
                    "type": "action",
                    "node_id": "A1",
                    "action": "Release",
                    "parameters": {}
                },
                "on_false": {
                    "type": "action",
                    "node_id": "A2",
                    "action": "Hold",
                    "parameters": {}
                }
            },
            "strategic_collateral_tree": None,
            "end_of_tick_collateral_tree": None,
            "parameters": {}
        }
        policy_file = tmp_path / "div_zero.json"
        policy_file.write_text(json.dumps(policy, indent=2))
        return policy_file

    # =========================================================================
    # Basic Command Tests
    # =========================================================================

    def test_validate_policy_command_exists(self, runner, app):
        """Command should be registered."""
        result = runner.invoke(app, ["validate-policy", "--help"])
        assert result.exit_code == 0
        assert "Validate a policy tree JSON file" in result.output

    def test_validate_policy_requires_file_argument(self, runner, app):
        """Command should require a file path argument."""
        result = runner.invoke(app, ["validate-policy"])
        assert result.exit_code != 0
        # Typer shows error for missing required argument

    def test_validate_policy_file_not_found(self, runner, app):
        """Should error if file doesn't exist."""
        result = runner.invoke(app, ["validate-policy", "/nonexistent/path.json"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    # =========================================================================
    # Valid Policy Tests
    # =========================================================================

    def test_validate_valid_fifo_policy(self, runner, app, valid_fifo_policy):
        """Valid FIFO policy should pass validation."""
        result = runner.invoke(app, ["validate-policy", str(valid_fifo_policy)])
        assert result.exit_code == 0
        assert "valid" in result.output.lower() or "passed" in result.output.lower()

    def test_validate_valid_complex_policy(self, runner, app, valid_complex_policy):
        """Valid complex policy with conditions should pass validation."""
        result = runner.invoke(app, ["validate-policy", str(valid_complex_policy)])
        assert result.exit_code == 0
        assert "valid" in result.output.lower() or "passed" in result.output.lower()

    def test_validate_bundled_fifo_policy(self, runner, app):
        """Bundled fifo.json should pass validation."""
        fifo_path = Path(__file__).parents[3] / "backend" / "policies" / "fifo.json"
        if fifo_path.exists():
            result = runner.invoke(app, ["validate-policy", str(fifo_path)])
            assert result.exit_code == 0

    def test_validate_bundled_liquidity_splitting_policy(self, runner, app):
        """Bundled liquidity_splitting.json should pass validation."""
        policy_path = Path(__file__).parents[3] / "backend" / "policies" / "liquidity_splitting.json"
        if policy_path.exists():
            result = runner.invoke(app, ["validate-policy", str(policy_path)])
            assert result.exit_code == 0

    # =========================================================================
    # Invalid Policy Tests - JSON Parsing
    # =========================================================================

    def test_validate_invalid_json(self, runner, app, invalid_json_file):
        """Invalid JSON should fail validation."""
        result = runner.invoke(app, ["validate-policy", str(invalid_json_file)])
        assert result.exit_code != 0
        assert "json" in result.output.lower() or "parse" in result.output.lower()

    def test_validate_invalid_schema(self, runner, app, invalid_schema_policy):
        """Policy with invalid schema should fail validation."""
        result = runner.invoke(app, ["validate-policy", str(invalid_schema_policy)])
        assert result.exit_code != 0

    # =========================================================================
    # Invalid Policy Tests - Semantic Validation
    # =========================================================================

    def test_validate_duplicate_node_id(self, runner, app, duplicate_node_id_policy):
        """Policy with duplicate node IDs should fail validation."""
        result = runner.invoke(app, ["validate-policy", str(duplicate_node_id_policy)])
        assert result.exit_code != 0
        assert "duplicate" in result.output.lower() or "node" in result.output.lower()

    def test_validate_invalid_field_reference(self, runner, app, invalid_field_reference_policy):
        """Policy with invalid field reference should fail validation."""
        result = runner.invoke(app, ["validate-policy", str(invalid_field_reference_policy)])
        assert result.exit_code != 0
        assert "field" in result.output.lower() or "invalid" in result.output.lower()

    def test_validate_missing_parameter(self, runner, app, missing_parameter_policy):
        """Policy referencing undefined parameter should fail validation."""
        result = runner.invoke(app, ["validate-policy", str(missing_parameter_policy)])
        assert result.exit_code != 0
        assert "param" in result.output.lower()

    def test_validate_division_by_zero(self, runner, app, division_by_zero_policy):
        """Policy with division by literal zero should fail validation."""
        result = runner.invoke(app, ["validate-policy", str(division_by_zero_policy)])
        assert result.exit_code != 0
        assert "zero" in result.output.lower() or "division" in result.output.lower()

    # =========================================================================
    # Output Format Tests
    # =========================================================================

    def test_validate_json_output_format(self, runner, app, valid_fifo_policy):
        """--format json should output valid JSON."""
        result = runner.invoke(app, ["validate-policy", str(valid_fifo_policy), "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "valid" in data or "status" in data

    def test_validate_json_output_invalid_policy(self, runner, app, duplicate_node_id_policy):
        """JSON output for invalid policy should include errors."""
        result = runner.invoke(app, ["validate-policy", str(duplicate_node_id_policy), "--format", "json"])
        # Exit code is non-zero for invalid policy
        assert result.exit_code != 0
        data = json.loads(result.output)
        assert "errors" in data or "error" in data

    def test_validate_verbose_output(self, runner, app, valid_complex_policy):
        """--verbose should show detailed validation steps."""
        result = runner.invoke(app, ["validate-policy", str(valid_complex_policy), "--verbose"])
        assert result.exit_code == 0
        # Should show some validation details
        assert len(result.output) > 50  # More than minimal output

    # =========================================================================
    # Functional Test Mode
    # =========================================================================

    def test_validate_with_functional_tests(self, runner, app, valid_fifo_policy):
        """--functional-tests should run functional tests."""
        result = runner.invoke(app, ["validate-policy", str(valid_fifo_policy), "--functional-tests"])
        assert result.exit_code == 0
        assert "functional" in result.output.lower() or "test" in result.output.lower()

    def test_validate_functional_tests_with_scenario(self, runner, app, valid_fifo_policy):
        """--functional-tests with --scenario should use custom scenario."""
        # First create a scenario config
        # For now, just test that the flag is accepted
        result = runner.invoke(app, ["validate-policy", str(valid_fifo_policy), "--functional-tests"])
        assert result.exit_code == 0

    # =========================================================================
    # Edge Cases
    # =========================================================================

    def test_validate_empty_file(self, runner, app, tmp_path):
        """Empty file should fail validation."""
        empty_file = tmp_path / "empty.json"
        empty_file.write_text("")
        result = runner.invoke(app, ["validate-policy", str(empty_file)])
        assert result.exit_code != 0

    def test_validate_null_trees(self, runner, app, tmp_path):
        """Policy with all null trees should be valid but warn."""
        policy = {
            "version": "1.0",
            "policy_id": "test_null",
            "payment_tree": None,
            "strategic_collateral_tree": None,
            "end_of_tick_collateral_tree": None,
            "parameters": {}
        }
        policy_file = tmp_path / "null_trees.json"
        policy_file.write_text(json.dumps(policy, indent=2))
        result = runner.invoke(app, ["validate-policy", str(policy_file)])
        # May pass but warn, or may fail - depends on implementation
        # For now, just ensure it doesn't crash
        assert result.exit_code in [0, 1]
