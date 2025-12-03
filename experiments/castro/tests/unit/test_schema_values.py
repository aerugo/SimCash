"""Unit tests for policy schema value types.

TDD: These tests are written BEFORE implementation.
Run with: pytest experiments/castro/tests/unit/test_schema_values.py -v
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestContextField:
    """Tests for ContextField - references to evaluation context fields."""

    def test_context_field_with_valid_field_name(self) -> None:
        """Context fields accept valid field names."""
        from experiments.castro.schemas.values import ContextField

        field = ContextField(field="tx.amount")
        assert field.field == "tx.amount"

    def test_context_field_simple_name(self) -> None:
        """Context fields accept simple field names without dots."""
        from experiments.castro.schemas.values import ContextField

        field = ContextField(field="balance")
        assert field.field == "balance"

    def test_context_field_underscore_name(self) -> None:
        """Context fields accept names with underscores."""
        from experiments.castro.schemas.values import ContextField

        field = ContextField(field="effective_liquidity")
        assert field.field == "effective_liquidity"

    def test_context_field_empty_string_rejected(self) -> None:
        """Empty field names are rejected."""
        from experiments.castro.schemas.values import ContextField

        with pytest.raises(ValidationError):
            ContextField(field="")

    def test_context_field_json_serialization(self) -> None:
        """Context fields serialize to expected JSON structure."""
        from experiments.castro.schemas.values import ContextField

        field = ContextField(field="remaining_amount")
        json_dict = field.model_dump()
        assert json_dict == {"field": "remaining_amount"}

    def test_context_field_from_json(self) -> None:
        """Context fields can be parsed from JSON."""
        from experiments.castro.schemas.values import ContextField

        field = ContextField.model_validate({"field": "ticks_to_deadline"})
        assert field.field == "ticks_to_deadline"


class TestLiteralValue:
    """Tests for LiteralValue - constant numeric or string values."""

    def test_literal_integer_value(self) -> None:
        """Literal values accept integers."""
        from experiments.castro.schemas.values import LiteralValue

        literal = LiteralValue(value=100)
        assert literal.value == 100

    def test_literal_float_value(self) -> None:
        """Literal values accept floats."""
        from experiments.castro.schemas.values import LiteralValue

        literal = LiteralValue(value=3.14159)
        assert literal.value == 3.14159

    def test_literal_negative_value(self) -> None:
        """Literal values accept negative numbers."""
        from experiments.castro.schemas.values import LiteralValue

        literal = LiteralValue(value=-500)
        assert literal.value == -500

    def test_literal_zero_value(self) -> None:
        """Literal values accept zero."""
        from experiments.castro.schemas.values import LiteralValue

        literal = LiteralValue(value=0)
        assert literal.value == 0

    def test_literal_string_value(self) -> None:
        """Literal values accept strings (for action parameters)."""
        from experiments.castro.schemas.values import LiteralValue

        literal = LiteralValue(value="HIGH")
        assert literal.value == "HIGH"

    def test_literal_json_serialization(self) -> None:
        """Literal values serialize to expected JSON structure."""
        from experiments.castro.schemas.values import LiteralValue

        literal = LiteralValue(value=10000)
        json_dict = literal.model_dump()
        assert json_dict == {"value": 10000}

    def test_literal_from_json_int(self) -> None:
        """Literal values can be parsed from JSON with int."""
        from experiments.castro.schemas.values import LiteralValue

        literal = LiteralValue.model_validate({"value": 50000})
        assert literal.value == 50000

    def test_literal_from_json_string(self) -> None:
        """Literal values can be parsed from JSON with string."""
        from experiments.castro.schemas.values import LiteralValue

        literal = LiteralValue.model_validate({"value": "InsufficientLiquidity"})
        assert literal.value == "InsufficientLiquidity"


class TestParameterRef:
    """Tests for ParameterRef - references to policy parameters."""

    def test_parameter_ref_valid_name(self) -> None:
        """Parameter refs accept valid parameter names."""
        from experiments.castro.schemas.values import ParameterRef

        param = ParameterRef(param="urgency_threshold")
        assert param.param == "urgency_threshold"

    def test_parameter_ref_with_underscores(self) -> None:
        """Parameter refs accept names with underscores."""
        from experiments.castro.schemas.values import ParameterRef

        param = ParameterRef(param="initial_liquidity_fraction")
        assert param.param == "initial_liquidity_fraction"

    def test_parameter_ref_empty_rejected(self) -> None:
        """Empty parameter names are rejected."""
        from experiments.castro.schemas.values import ParameterRef

        with pytest.raises(ValidationError):
            ParameterRef(param="")

    def test_parameter_ref_json_serialization(self) -> None:
        """Parameter refs serialize to expected JSON structure."""
        from experiments.castro.schemas.values import ParameterRef

        param = ParameterRef(param="liquidity_buffer_factor")
        json_dict = param.model_dump()
        assert json_dict == {"param": "liquidity_buffer_factor"}

    def test_parameter_ref_from_json(self) -> None:
        """Parameter refs can be parsed from JSON."""
        from experiments.castro.schemas.values import ParameterRef

        param = ParameterRef.model_validate({"param": "target_buffer"})
        assert param.param == "target_buffer"


class TestPolicyValueUnion:
    """Tests for PolicyValue union type - combines all value types."""

    def test_policy_value_field_variant(self) -> None:
        """PolicyValue accepts ContextField variant."""
        from experiments.castro.schemas.values import PolicyValue, ContextField

        value: PolicyValue = ContextField(field="balance")
        assert isinstance(value, ContextField)

    def test_policy_value_literal_variant(self) -> None:
        """PolicyValue accepts LiteralValue variant."""
        from experiments.castro.schemas.values import PolicyValue, LiteralValue

        value: PolicyValue = LiteralValue(value=100)
        assert isinstance(value, LiteralValue)

    def test_policy_value_param_variant(self) -> None:
        """PolicyValue accepts ParameterRef variant."""
        from experiments.castro.schemas.values import PolicyValue, ParameterRef

        value: PolicyValue = ParameterRef(param="threshold")
        assert isinstance(value, ParameterRef)


class TestComputeValue:
    """Tests for ComputeValue - computed values with operations."""

    def test_compute_binary_multiply(self) -> None:
        """Compute supports binary multiply operation."""
        from experiments.castro.schemas.values import ComputeValue, ContextField, ParameterRef

        compute = ComputeValue(
            compute={
                "op": "*",
                "left": ContextField(field="max_collateral_capacity"),
                "right": ParameterRef(param="initial_liquidity_fraction"),
            }
        )
        assert compute.compute["op"] == "*"

    def test_compute_binary_divide(self) -> None:
        """Compute supports binary divide operation."""
        from experiments.castro.schemas.values import ComputeValue, ContextField, LiteralValue

        compute = ComputeValue(
            compute={
                "op": "/",
                "left": ContextField(field="remaining_amount"),
                "right": LiteralValue(value=100),
            }
        )
        assert compute.compute["op"] == "/"

    def test_compute_binary_add(self) -> None:
        """Compute supports binary add operation."""
        from experiments.castro.schemas.values import ComputeValue, ContextField

        compute = ComputeValue(
            compute={
                "op": "+",
                "left": ContextField(field="balance"),
                "right": ContextField(field="credit_headroom"),
            }
        )
        assert compute.compute["op"] == "+"

    def test_compute_binary_subtract(self) -> None:
        """Compute supports binary subtract operation."""
        from experiments.castro.schemas.values import ComputeValue, ContextField, ParameterRef

        compute = ComputeValue(
            compute={
                "op": "-",
                "left": ContextField(field="effective_liquidity"),
                "right": ParameterRef(param="target_buffer"),
            }
        )
        assert compute.compute["op"] == "-"

    def test_compute_nary_max(self) -> None:
        """Compute supports n-ary max operation."""
        from experiments.castro.schemas.values import ComputeValue, ContextField, LiteralValue

        compute = ComputeValue(
            compute={
                "op": "max",
                "values": [
                    ContextField(field="amount"),
                    LiteralValue(value=0),
                ],
            }
        )
        assert compute.compute["op"] == "max"

    def test_compute_nary_min(self) -> None:
        """Compute supports n-ary min operation."""
        from experiments.castro.schemas.values import ComputeValue, ContextField, LiteralValue

        compute = ComputeValue(
            compute={
                "op": "min",
                "values": [
                    ContextField(field="queue1_total_value"),
                    ContextField(field="effective_liquidity"),
                    LiteralValue(value=100000),
                ],
            }
        )
        assert compute.compute["op"] == "min"

    def test_compute_unary_ceil(self) -> None:
        """Compute supports unary ceil operation."""
        from experiments.castro.schemas.values import ComputeValue, ContextField

        compute = ComputeValue(
            compute={
                "op": "ceil",
                "value": ContextField(field="day_progress_fraction"),
            }
        )
        assert compute.compute["op"] == "ceil"

    def test_compute_unary_floor(self) -> None:
        """Compute supports unary floor operation."""
        from experiments.castro.schemas.values import ComputeValue, ContextField

        compute = ComputeValue(
            compute={
                "op": "floor",
                "value": ContextField(field="collateral_utilization"),
            }
        )
        assert compute.compute["op"] == "floor"

    def test_compute_unary_abs(self) -> None:
        """Compute supports unary abs operation."""
        from experiments.castro.schemas.values import ComputeValue, ContextField

        compute = ComputeValue(
            compute={
                "op": "abs",
                "value": ContextField(field="my_bilateral_net_q2"),
            }
        )
        assert compute.compute["op"] == "abs"

    def test_compute_json_serialization(self) -> None:
        """Compute values serialize to expected JSON structure."""
        from experiments.castro.schemas.values import ComputeValue, ContextField, ParameterRef

        compute = ComputeValue(
            compute={
                "op": "*",
                "left": ContextField(field="max_collateral_capacity"),
                "right": ParameterRef(param="initial_liquidity_fraction"),
            }
        )
        json_dict = compute.model_dump()
        assert "compute" in json_dict
        assert json_dict["compute"]["op"] == "*"


class TestValueTypeDiscrimination:
    """Tests for proper discrimination between value types in schemas."""

    def test_distinguish_field_from_value(self) -> None:
        """Can distinguish field from value by key presence."""
        from experiments.castro.schemas.values import ContextField, LiteralValue

        field_data = {"field": "balance"}
        value_data = {"value": 100}

        field = ContextField.model_validate(field_data)
        literal = LiteralValue.model_validate(value_data)

        assert hasattr(field, "field")
        assert hasattr(literal, "value")

    def test_distinguish_param_from_field(self) -> None:
        """Can distinguish param from field by key presence."""
        from experiments.castro.schemas.values import ContextField, ParameterRef

        field_data = {"field": "balance"}
        param_data = {"param": "threshold"}

        field = ContextField.model_validate(field_data)
        param = ParameterRef.model_validate(param_data)

        assert hasattr(field, "field")
        assert hasattr(param, "param")
