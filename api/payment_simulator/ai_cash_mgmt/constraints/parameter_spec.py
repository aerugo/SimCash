"""Parameter specification for policy constraints.

Defines what parameters are allowed in policy trees and their valid ranges.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ParameterSpec(BaseModel):
    """Specification for a policy parameter.

    Defines the name, type, and valid range/values for a parameter
    that can be used in policy decision trees.

    Example:
        >>> # Integer parameter with range
        >>> spec = ParameterSpec(
        ...     name="amount_threshold",
        ...     param_type="int",
        ...     min_value=0,
        ...     max_value=1000000,
        ... )

        >>> # Enum parameter with allowed values
        >>> spec = ParameterSpec(
        ...     name="comparison_op",
        ...     param_type="enum",
        ...     allowed_values=["<", "<=", ">", ">=", "=="],
        ... )
    """

    name: str = Field(
        ...,
        min_length=1,
        description="Parameter name",
    )
    param_type: str = Field(
        ...,
        description="Parameter type (int, float, enum)",
    )
    min_value: int | float | None = Field(
        default=None,
        description="Minimum allowed value (for int/float)",
    )
    max_value: int | float | None = Field(
        default=None,
        description="Maximum allowed value (for int/float)",
    )
    allowed_values: list[Any] | None = Field(
        default=None,
        description="Allowed values (for enum type)",
    )
    description: str | None = Field(
        default=None,
        description="Human-readable description",
    )

    def validate_value(self, value: Any) -> tuple[bool, str | None]:
        """Validate a value against this parameter spec.

        Args:
            value: The value to validate.

        Returns:
            Tuple of (is_valid, error_message).
        """
        if self.param_type == "int":
            if not isinstance(value, int):
                return False, f"Parameter '{self.name}' must be int, got {type(value).__name__}"
            if self.min_value is not None and value < self.min_value:
                return False, f"Parameter '{self.name}' value {value} below min {self.min_value}"
            if self.max_value is not None and value > self.max_value:
                return False, f"Parameter '{self.name}' value {value} above max {self.max_value}"

        elif self.param_type == "float":
            if not isinstance(value, (int, float)):
                return False, f"Parameter '{self.name}' must be numeric, got {type(value).__name__}"
            if self.min_value is not None and value < self.min_value:
                return False, f"Parameter '{self.name}' value {value} below min {self.min_value}"
            if self.max_value is not None and value > self.max_value:
                return False, f"Parameter '{self.name}' value {value} above max {self.max_value}"

        elif self.param_type == "enum":
            if self.allowed_values and value not in self.allowed_values:
                return (
                    False,
                    f"Parameter '{self.name}' value {value} not in "
                    f"allowed values {self.allowed_values}",
                )

        return True, None
