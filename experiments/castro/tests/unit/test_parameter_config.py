"""Unit tests for parameter configuration schema.

TDD: These tests define the expected behavior for ParameterSpec and ScenarioConstraints.
Run with: pytest experiments/castro/tests/unit/test_parameter_config.py -v
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestParameterSpec:
    """Tests for ParameterSpec - defines a single policy parameter."""

    def test_parameter_spec_valid(self) -> None:
        """ParameterSpec accepts valid configuration."""
        from experiments.castro.schemas.parameter_config import ParameterSpec

        spec = ParameterSpec(
            name="urgency_threshold",
            min_value=0.0,
            max_value=20.0,
            default=3.0,
            description="Ticks before deadline when payment is urgent",
        )
        assert spec.name == "urgency_threshold"
        assert spec.min_value == 0.0
        assert spec.max_value == 20.0
        assert spec.default == 3.0
        assert spec.description == "Ticks before deadline when payment is urgent"

    def test_parameter_spec_default_at_min(self) -> None:
        """ParameterSpec accepts default equal to min_value."""
        from experiments.castro.schemas.parameter_config import ParameterSpec

        spec = ParameterSpec(
            name="threshold",
            min_value=0.0,
            max_value=10.0,
            default=0.0,
            description="At minimum",
        )
        assert spec.default == 0.0

    def test_parameter_spec_default_at_max(self) -> None:
        """ParameterSpec accepts default equal to max_value."""
        from experiments.castro.schemas.parameter_config import ParameterSpec

        spec = ParameterSpec(
            name="threshold",
            min_value=0.0,
            max_value=10.0,
            default=10.0,
            description="At maximum",
        )
        assert spec.default == 10.0

    def test_parameter_spec_negative_range(self) -> None:
        """ParameterSpec accepts negative value ranges."""
        from experiments.castro.schemas.parameter_config import ParameterSpec

        spec = ParameterSpec(
            name="adjustment",
            min_value=-10.0,
            max_value=10.0,
            default=0.0,
            description="Can be negative or positive",
        )
        assert spec.min_value == -10.0

    def test_parameter_spec_default_below_min_rejected(self) -> None:
        """ParameterSpec rejects default below min_value."""
        from experiments.castro.schemas.parameter_config import ParameterSpec

        with pytest.raises(ValidationError, match="default must be within"):
            ParameterSpec(
                name="bad_param",
                min_value=5.0,
                max_value=10.0,
                default=3.0,  # Below min!
                description="Invalid",
            )

    def test_parameter_spec_default_above_max_rejected(self) -> None:
        """ParameterSpec rejects default above max_value."""
        from experiments.castro.schemas.parameter_config import ParameterSpec

        with pytest.raises(ValidationError, match="default must be within"):
            ParameterSpec(
                name="bad_param",
                min_value=0.0,
                max_value=10.0,
                default=15.0,  # Above max!
                description="Invalid",
            )

    def test_parameter_spec_min_equals_max_rejected(self) -> None:
        """ParameterSpec rejects min_value equal to max_value."""
        from experiments.castro.schemas.parameter_config import ParameterSpec

        with pytest.raises(ValidationError, match="min_value must be < max_value"):
            ParameterSpec(
                name="bad_param",
                min_value=5.0,
                max_value=5.0,  # Equal to min!
                default=5.0,
                description="Invalid",
            )

    def test_parameter_spec_min_greater_than_max_rejected(self) -> None:
        """ParameterSpec rejects min_value greater than max_value."""
        from experiments.castro.schemas.parameter_config import ParameterSpec

        with pytest.raises(ValidationError, match="min_value must be < max_value"):
            ParameterSpec(
                name="bad_param",
                min_value=10.0,
                max_value=5.0,  # Less than min!
                default=7.0,
                description="Invalid",
            )

    def test_parameter_spec_empty_name_rejected(self) -> None:
        """ParameterSpec rejects empty parameter name."""
        from experiments.castro.schemas.parameter_config import ParameterSpec

        with pytest.raises(ValidationError):
            ParameterSpec(
                name="",  # Empty!
                min_value=0.0,
                max_value=10.0,
                default=5.0,
                description="Invalid",
            )

    def test_parameter_spec_json_serialization(self) -> None:
        """ParameterSpec serializes to JSON correctly."""
        from experiments.castro.schemas.parameter_config import ParameterSpec

        spec = ParameterSpec(
            name="buffer",
            min_value=0.5,
            max_value=3.0,
            default=1.0,
            description="Buffer multiplier",
        )
        data = spec.model_dump()
        assert data["name"] == "buffer"
        assert data["min_value"] == 0.5
        assert data["max_value"] == 3.0
        assert data["default"] == 1.0


class TestScenarioConstraints:
    """Tests for ScenarioConstraints - defines allowed elements for a scenario."""

    def test_scenario_constraints_valid(self) -> None:
        """ScenarioConstraints accepts valid configuration."""
        from experiments.castro.schemas.parameter_config import (
            ParameterSpec,
            ScenarioConstraints,
        )

        constraints = ScenarioConstraints(
            allowed_parameters=[
                ParameterSpec(
                    name="threshold",
                    min_value=0,
                    max_value=20,
                    default=5,
                    description="A threshold",
                ),
            ],
            allowed_fields=["balance", "effective_liquidity"],
            allowed_actions=["Release", "Hold"],
        )
        assert len(constraints.allowed_parameters) == 1
        assert "balance" in constraints.allowed_fields
        assert "Release" in constraints.allowed_actions

    def test_scenario_constraints_empty_parameters_allowed(self) -> None:
        """ScenarioConstraints allows empty parameter list."""
        from experiments.castro.schemas.parameter_config import ScenarioConstraints

        constraints = ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["balance"],
            allowed_actions=["Release"],
        )
        assert len(constraints.allowed_parameters) == 0

    def test_scenario_constraints_multiple_parameters(self) -> None:
        """ScenarioConstraints accepts multiple parameters."""
        from experiments.castro.schemas.parameter_config import (
            ParameterSpec,
            ScenarioConstraints,
        )

        constraints = ScenarioConstraints(
            allowed_parameters=[
                ParameterSpec(
                    name="urgency", min_value=0, max_value=20, default=3, description="Urgency"
                ),
                ParameterSpec(
                    name="buffer", min_value=0.5, max_value=3.0, default=1.0, description="Buffer"
                ),
                ParameterSpec(
                    name="split_size", min_value=0.1, max_value=0.9, default=0.5, description="Split"
                ),
            ],
            allowed_fields=["balance"],
            allowed_actions=["Release"],
        )
        assert len(constraints.allowed_parameters) == 3
        param_names = [p.name for p in constraints.allowed_parameters]
        assert "urgency" in param_names
        assert "buffer" in param_names
        assert "split_size" in param_names

    def test_scenario_constraints_rejects_unknown_field(self) -> None:
        """ScenarioConstraints rejects fields not in SimCash registry."""
        from experiments.castro.schemas.parameter_config import ScenarioConstraints

        with pytest.raises(ValidationError, match="unknown field"):
            ScenarioConstraints(
                allowed_parameters=[],
                allowed_fields=["invented_field_xyz"],  # Not in registry!
                allowed_actions=["Release"],
            )

    def test_scenario_constraints_rejects_unknown_action(self) -> None:
        """ScenarioConstraints rejects actions not in SimCash registry."""
        from experiments.castro.schemas.parameter_config import ScenarioConstraints

        with pytest.raises(ValidationError, match="unknown payment action"):
            ScenarioConstraints(
                allowed_parameters=[],
                allowed_fields=["balance"],
                allowed_actions=["InventedAction"],  # Not in registry!
            )

    def test_scenario_constraints_all_payment_fields_valid(self) -> None:
        """ScenarioConstraints accepts all payment tree fields."""
        from experiments.castro.schemas.parameter_config import ScenarioConstraints
        from experiments.castro.schemas.registry import PAYMENT_TREE_FIELDS

        constraints = ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=PAYMENT_TREE_FIELDS,
            allowed_actions=["Release"],
        )
        assert len(constraints.allowed_fields) == len(PAYMENT_TREE_FIELDS)

    def test_scenario_constraints_all_payment_actions_valid(self) -> None:
        """ScenarioConstraints accepts all payment actions."""
        from experiments.castro.schemas.parameter_config import ScenarioConstraints
        from experiments.castro.schemas.registry import PAYMENT_ACTIONS

        constraints = ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["balance"],
            allowed_actions=PAYMENT_ACTIONS,
        )
        assert len(constraints.allowed_actions) == len(PAYMENT_ACTIONS)

    def test_scenario_constraints_empty_fields_rejected(self) -> None:
        """ScenarioConstraints rejects empty field list."""
        from experiments.castro.schemas.parameter_config import ScenarioConstraints

        with pytest.raises(ValidationError, match="at least 1 item"):
            ScenarioConstraints(
                allowed_parameters=[],
                allowed_fields=[],  # Empty!
                allowed_actions=["Release"],
            )

    def test_scenario_constraints_empty_actions_rejected(self) -> None:
        """ScenarioConstraints rejects empty action list."""
        from experiments.castro.schemas.parameter_config import ScenarioConstraints

        with pytest.raises(ValidationError, match="at least 1 item"):
            ScenarioConstraints(
                allowed_parameters=[],
                allowed_fields=["balance"],
                allowed_actions=[],  # Empty!
            )

    def test_scenario_constraints_duplicate_params_rejected(self) -> None:
        """ScenarioConstraints rejects duplicate parameter names."""
        from experiments.castro.schemas.parameter_config import (
            ParameterSpec,
            ScenarioConstraints,
        )

        with pytest.raises(ValidationError, match="duplicate parameter"):
            ScenarioConstraints(
                allowed_parameters=[
                    ParameterSpec(
                        name="threshold", min_value=0, max_value=10, default=5, description="First"
                    ),
                    ParameterSpec(
                        name="threshold", min_value=0, max_value=20, default=10, description="Duplicate!"
                    ),
                ],
                allowed_fields=["balance"],
                allowed_actions=["Release"],
            )

    def test_scenario_constraints_get_parameter_names(self) -> None:
        """ScenarioConstraints provides parameter names list."""
        from experiments.castro.schemas.parameter_config import (
            ParameterSpec,
            ScenarioConstraints,
        )

        constraints = ScenarioConstraints(
            allowed_parameters=[
                ParameterSpec(
                    name="urgency", min_value=0, max_value=20, default=3, description="Urgency"
                ),
                ParameterSpec(
                    name="buffer", min_value=0.5, max_value=3.0, default=1.0, description="Buffer"
                ),
            ],
            allowed_fields=["balance"],
            allowed_actions=["Release"],
        )
        names = constraints.get_parameter_names()
        assert names == ["urgency", "buffer"]

    def test_scenario_constraints_json_round_trip(self) -> None:
        """ScenarioConstraints survives JSON serialization round-trip."""
        from experiments.castro.schemas.parameter_config import (
            ParameterSpec,
            ScenarioConstraints,
        )

        original = ScenarioConstraints(
            allowed_parameters=[
                ParameterSpec(
                    name="threshold", min_value=0, max_value=20, default=5, description="Threshold"
                ),
            ],
            allowed_fields=["balance", "effective_liquidity"],
            allowed_actions=["Release", "Hold"],
        )

        # Serialize and deserialize
        json_str = original.model_dump_json()
        restored = ScenarioConstraints.model_validate_json(json_str)

        assert len(restored.allowed_parameters) == 1
        assert restored.allowed_parameters[0].name == "threshold"
        assert restored.allowed_fields == ["balance", "effective_liquidity"]
        assert restored.allowed_actions == ["Release", "Hold"]
