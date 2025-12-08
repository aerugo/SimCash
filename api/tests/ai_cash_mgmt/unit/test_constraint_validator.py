"""Unit tests for ConstraintValidator - policy validation against constraints.

TDD: These tests are written BEFORE the implementation.
"""

from __future__ import annotations

import pytest


class TestParameterSpec:
    """Test parameter specification model."""

    def test_parameter_spec_int_type(self) -> None:
        """ParameterSpec should define integer parameters."""
        from payment_simulator.ai_cash_mgmt.constraints.parameter_spec import (
            ParameterSpec,
        )

        spec = ParameterSpec(
            name="amount_threshold",
            param_type="int",
            min_value=0,
            max_value=1000000,
        )

        assert spec.name == "amount_threshold"
        assert spec.param_type == "int"
        assert spec.min_value == 0
        assert spec.max_value == 1000000

    def test_parameter_spec_float_type(self) -> None:
        """ParameterSpec should define float parameters."""
        from payment_simulator.ai_cash_mgmt.constraints.parameter_spec import (
            ParameterSpec,
        )

        spec = ParameterSpec(
            name="priority_weight",
            param_type="float",
            min_value=0.0,
            max_value=1.0,
        )

        assert spec.param_type == "float"
        assert spec.min_value == 0.0
        assert spec.max_value == 1.0

    def test_parameter_spec_enum_type(self) -> None:
        """ParameterSpec should define enum parameters."""
        from payment_simulator.ai_cash_mgmt.constraints.parameter_spec import (
            ParameterSpec,
        )

        spec = ParameterSpec(
            name="comparison_op",
            param_type="enum",
            allowed_values=["<", "<=", ">", ">=", "=="],
        )

        assert spec.param_type == "enum"
        assert "<" in spec.allowed_values
        assert "==" in spec.allowed_values


class TestScenarioConstraints:
    """Test scenario constraints model."""

    def test_scenario_constraints_from_dict(self) -> None:
        """ScenarioConstraints should parse from dict."""
        from payment_simulator.ai_cash_mgmt.constraints.scenario_constraints import (
            ScenarioConstraints,
        )

        data = {
            "allowed_parameters": [
                {"name": "threshold", "param_type": "int", "min_value": 0},
            ],
            "allowed_fields": ["amount", "priority", "sender_id"],
            "allowed_actions": {
                "payment_tree": ["submit", "queue", "hold"],
                "bank_tree": ["borrow", "repay"],
                "collateral_tree": ["pledge", "release"],
            },
        }

        constraints = ScenarioConstraints.model_validate(data)

        assert len(constraints.allowed_parameters) == 1
        assert "amount" in constraints.allowed_fields
        assert "submit" in constraints.allowed_actions["payment_tree"]

    def test_scenario_constraints_defaults(self) -> None:
        """ScenarioConstraints should have empty defaults."""
        from payment_simulator.ai_cash_mgmt.constraints.scenario_constraints import (
            ScenarioConstraints,
        )

        constraints = ScenarioConstraints()

        assert constraints.allowed_parameters == []
        assert constraints.allowed_fields == []
        assert constraints.allowed_actions == {}


class TestConstraintValidator:
    """Test constraint validator."""

    def test_validator_accepts_valid_policy(self) -> None:
        """Validator should accept a policy that meets all constraints."""
        from payment_simulator.ai_cash_mgmt.constraints.scenario_constraints import (
            ScenarioConstraints,
        )
        from payment_simulator.ai_cash_mgmt.optimization.constraint_validator import (
            ConstraintValidator,
        )

        constraints = ScenarioConstraints(
            allowed_parameters=[
                {"name": "threshold", "param_type": "int", "min_value": 0, "max_value": 1000000},
            ],
            allowed_fields=["amount", "priority"],
            allowed_actions={
                "payment_tree": ["submit", "queue", "hold"],
            },
        )

        policy = {
            "payment_tree": {
                "parameters": {"threshold": 50000},
                "root": {
                    "field": "amount",
                    "op": ">",
                    "value": {"param": "threshold"},
                    "if_true": {"action": "submit"},
                    "if_false": {"action": "queue"},
                },
            },
        }

        validator = ConstraintValidator(constraints)
        result = validator.validate(policy)

        assert result.is_valid
        assert len(result.errors) == 0

    def test_validator_rejects_unknown_parameters(self) -> None:
        """Validator should reject policies with unknown parameters."""
        from payment_simulator.ai_cash_mgmt.constraints.scenario_constraints import (
            ScenarioConstraints,
        )
        from payment_simulator.ai_cash_mgmt.optimization.constraint_validator import (
            ConstraintValidator,
        )

        constraints = ScenarioConstraints(
            allowed_parameters=[
                {"name": "threshold", "param_type": "int", "min_value": 0},
            ],
            allowed_fields=["amount"],
            allowed_actions={"payment_tree": ["submit"]},
        )

        policy = {
            "payment_tree": {
                "parameters": {"unknown_param": 100},  # Not allowed!
                "root": {"action": "submit"},
            },
        }

        validator = ConstraintValidator(constraints)
        result = validator.validate(policy)

        assert not result.is_valid
        assert any("unknown_param" in err for err in result.errors)

    def test_validator_rejects_out_of_bounds_parameters(self) -> None:
        """Validator should reject parameters outside allowed range."""
        from payment_simulator.ai_cash_mgmt.constraints.scenario_constraints import (
            ScenarioConstraints,
        )
        from payment_simulator.ai_cash_mgmt.optimization.constraint_validator import (
            ConstraintValidator,
        )

        constraints = ScenarioConstraints(
            allowed_parameters=[
                {"name": "threshold", "param_type": "int", "min_value": 0, "max_value": 100},
            ],
            allowed_fields=["amount"],
            allowed_actions={"payment_tree": ["submit"]},
        )

        policy = {
            "payment_tree": {
                "parameters": {"threshold": 200},  # Out of bounds!
                "root": {"action": "submit"},
            },
        }

        validator = ConstraintValidator(constraints)
        result = validator.validate(policy)

        assert not result.is_valid
        assert any("threshold" in err and ("range" in err.lower() or "bounds" in err.lower() or "200" in err) for err in result.errors)

    def test_validator_rejects_unknown_fields(self) -> None:
        """Validator should reject policies with unknown context fields."""
        from payment_simulator.ai_cash_mgmt.constraints.scenario_constraints import (
            ScenarioConstraints,
        )
        from payment_simulator.ai_cash_mgmt.optimization.constraint_validator import (
            ConstraintValidator,
        )

        constraints = ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["amount", "priority"],
            allowed_actions={"payment_tree": ["submit", "queue"]},
        )

        policy = {
            "payment_tree": {
                "parameters": {},
                "root": {
                    "field": "unknown_field",  # Not allowed!
                    "op": ">",
                    "value": 100,
                    "if_true": {"action": "submit"},
                    "if_false": {"action": "queue"},
                },
            },
        }

        validator = ConstraintValidator(constraints)
        result = validator.validate(policy)

        assert not result.is_valid
        assert any("unknown_field" in err for err in result.errors)

    def test_validator_rejects_invalid_actions_for_tree_type(self) -> None:
        """Validator should reject actions not allowed for specific tree type."""
        from payment_simulator.ai_cash_mgmt.constraints.scenario_constraints import (
            ScenarioConstraints,
        )
        from payment_simulator.ai_cash_mgmt.optimization.constraint_validator import (
            ConstraintValidator,
        )

        constraints = ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["amount"],
            allowed_actions={
                "payment_tree": ["submit", "queue"],  # "hold" not allowed
            },
        )

        policy = {
            "payment_tree": {
                "parameters": {},
                "root": {"action": "hold"},  # Not in allowed list!
            },
        }

        validator = ConstraintValidator(constraints)
        result = validator.validate(policy)

        assert not result.is_valid
        assert any("hold" in err for err in result.errors)

    def test_validator_checks_nested_conditions(self) -> None:
        """Validator should validate nested decision tree nodes."""
        from payment_simulator.ai_cash_mgmt.constraints.scenario_constraints import (
            ScenarioConstraints,
        )
        from payment_simulator.ai_cash_mgmt.optimization.constraint_validator import (
            ConstraintValidator,
        )

        constraints = ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["amount", "priority"],
            allowed_actions={"payment_tree": ["submit", "queue"]},
        )

        policy = {
            "payment_tree": {
                "parameters": {},
                "root": {
                    "field": "amount",
                    "op": ">",
                    "value": 100,
                    "if_true": {
                        "field": "invalid_nested_field",  # Invalid in nested node!
                        "op": ">",
                        "value": 5,
                        "if_true": {"action": "submit"},
                        "if_false": {"action": "queue"},
                    },
                    "if_false": {"action": "queue"},
                },
            },
        }

        validator = ConstraintValidator(constraints)
        result = validator.validate(policy)

        assert not result.is_valid
        assert any("invalid_nested_field" in err for err in result.errors)

    def test_validator_collects_multiple_errors(self) -> None:
        """Validator should collect all errors, not stop at first."""
        from payment_simulator.ai_cash_mgmt.constraints.scenario_constraints import (
            ScenarioConstraints,
        )
        from payment_simulator.ai_cash_mgmt.optimization.constraint_validator import (
            ConstraintValidator,
        )

        constraints = ScenarioConstraints(
            allowed_parameters=[
                {"name": "threshold", "param_type": "int", "min_value": 0, "max_value": 100},
            ],
            allowed_fields=["amount"],
            allowed_actions={"payment_tree": ["submit"]},
        )

        policy = {
            "payment_tree": {
                "parameters": {
                    "threshold": 200,  # Error 1: out of bounds
                    "unknown": 50,  # Error 2: unknown param
                },
                "root": {
                    "field": "bad_field",  # Error 3: unknown field
                    "op": ">",
                    "value": 100,
                    "if_true": {"action": "hold"},  # Error 4: invalid action
                    "if_false": {"action": "submit"},
                },
            },
        }

        validator = ConstraintValidator(constraints)
        result = validator.validate(policy)

        assert not result.is_valid
        # Should have collected multiple errors
        assert len(result.errors) >= 3


class TestValidationResult:
    """Test validation result dataclass."""

    def test_validation_result_valid(self) -> None:
        """ValidationResult should represent valid policy."""
        from payment_simulator.ai_cash_mgmt.optimization.constraint_validator import (
            ValidationResult,
        )

        result = ValidationResult(is_valid=True, errors=[])

        assert result.is_valid
        assert len(result.errors) == 0

    def test_validation_result_invalid(self) -> None:
        """ValidationResult should represent invalid policy with errors."""
        from payment_simulator.ai_cash_mgmt.optimization.constraint_validator import (
            ValidationResult,
        )

        errors = [
            "Unknown parameter: foo",
            "Invalid action: bar",
        ]
        result = ValidationResult(is_valid=False, errors=errors)

        assert not result.is_valid
        assert len(result.errors) == 2
        assert "foo" in result.errors[0]


class TestConstraintValidatorWithMultipleTrees:
    """Test validator with multiple tree types."""

    def test_validator_validates_all_tree_types(self) -> None:
        """Validator should validate payment, bank, and collateral trees."""
        from payment_simulator.ai_cash_mgmt.constraints.scenario_constraints import (
            ScenarioConstraints,
        )
        from payment_simulator.ai_cash_mgmt.optimization.constraint_validator import (
            ConstraintValidator,
        )

        constraints = ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["amount", "balance"],
            allowed_actions={
                "payment_tree": ["submit", "queue"],
                "bank_tree": ["borrow", "repay", "none"],
                "collateral_tree": ["pledge", "release", "none"],
            },
        )

        policy = {
            "payment_tree": {
                "parameters": {},
                "root": {"action": "submit"},
            },
            "bank_tree": {
                "parameters": {},
                "root": {"action": "borrow"},
            },
            "collateral_tree": {
                "parameters": {},
                "root": {"action": "pledge"},
            },
        }

        validator = ConstraintValidator(constraints)
        result = validator.validate(policy)

        assert result.is_valid

    def test_validator_rejects_invalid_bank_tree_action(self) -> None:
        """Validator should reject invalid bank tree actions."""
        from payment_simulator.ai_cash_mgmt.constraints.scenario_constraints import (
            ScenarioConstraints,
        )
        from payment_simulator.ai_cash_mgmt.optimization.constraint_validator import (
            ConstraintValidator,
        )

        constraints = ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=[],
            allowed_actions={
                "payment_tree": ["submit"],
                "bank_tree": ["borrow", "repay"],  # "steal" not allowed!
            },
        )

        policy = {
            "payment_tree": {
                "parameters": {},
                "root": {"action": "submit"},
            },
            "bank_tree": {
                "parameters": {},
                "root": {"action": "steal"},  # Invalid!
            },
        }

        validator = ConstraintValidator(constraints)
        result = validator.validate(policy)

        assert not result.is_valid
        assert any("steal" in err for err in result.errors)
