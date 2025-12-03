"""Policy value types for structured output schemas.

These types represent the different value forms that can appear in policy DSL:
- ContextField: Reference to evaluation context (e.g., {"field": "balance"})
- LiteralValue: Constant value (e.g., {"value": 100})
- ParameterRef: Reference to policy parameter (e.g., {"param": "threshold"})
- ComputeValue: Computed value with operation (e.g., {"compute": {...}})
"""

from __future__ import annotations

from typing import Any, Literal, Union
from pydantic import BaseModel, Field, field_validator


class ContextField(BaseModel):
    """Reference to an evaluation context field.

    Examples:
        {"field": "balance"}
        {"field": "effective_liquidity"}
        {"field": "ticks_to_deadline"}
    """

    field: str = Field(
        ...,
        min_length=1,
        description="Name of the context field to reference",
    )

    @field_validator("field")
    @classmethod
    def validate_field_name(cls, v: str) -> str:
        """Validate field name is not empty and has valid format."""
        if not v.strip():
            raise ValueError("Field name cannot be empty")
        return v


class LiteralValue(BaseModel):
    """A constant literal value (numeric or string).

    Examples:
        {"value": 100}
        {"value": 3.14}
        {"value": "HIGH"}
        {"value": "InsufficientLiquidity"}
    """

    value: int | float | str = Field(
        ...,
        description="The literal value (int, float, or string)",
    )


class ParameterRef(BaseModel):
    """Reference to a policy parameter from the parameters map.

    Examples:
        {"param": "urgency_threshold"}
        {"param": "initial_liquidity_fraction"}
        {"param": "target_buffer"}
    """

    param: str = Field(
        ...,
        min_length=1,
        description="Name of the parameter to reference",
    )

    @field_validator("param")
    @classmethod
    def validate_param_name(cls, v: str) -> str:
        """Validate parameter name is not empty."""
        if not v.strip():
            raise ValueError("Parameter name cannot be empty")
        return v


# Binary arithmetic operators
BinaryArithmeticOp = Literal["*", "/", "+", "-", "div0", "%", "^"]

# N-ary arithmetic operators
NaryArithmeticOp = Literal["max", "min", "sum", "avg"]

# Unary math operators
UnaryMathOp = Literal["ceil", "floor", "round", "abs", "sqrt", "log", "exp"]

# Ternary math operators
TernaryMathOp = Literal["clamp", "if"]

# All computation operators
ComputeOp = BinaryArithmeticOp | NaryArithmeticOp | UnaryMathOp | TernaryMathOp


class ComputeValue(BaseModel):
    """A computed value with an operation.

    Supports various computation types:
    - Binary: {"op": "*", "left": <value>, "right": <value>}
    - N-ary: {"op": "max", "values": [<value>, ...]}
    - Unary: {"op": "ceil", "value": <value>}
    - Ternary: {"op": "clamp", "value": <v>, "min": <min>, "max": <max>}

    Examples:
        {"compute": {"op": "*", "left": {"field": "balance"}, "right": {"value": 0.5}}}
        {"compute": {"op": "max", "values": [{"field": "amount"}, {"value": 0}]}}
        {"compute": {"op": "ceil", "value": {"field": "fraction"}}}
    """

    compute: dict[str, Any] = Field(
        ...,
        description="Computation specification with op and operands",
    )

    @field_validator("compute")
    @classmethod
    def validate_compute(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate computation has required 'op' field."""
        if "op" not in v:
            raise ValueError("Computation must have 'op' field")
        return v


# Union type for all policy value types
# This is used in expressions and action parameters
PolicyValue = Union[ContextField, LiteralValue, ParameterRef, ComputeValue]

# Alias for backward compatibility
ValueType = PolicyValue
