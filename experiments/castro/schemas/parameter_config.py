"""Parameter configuration schema for dynamic policy generation.

This module provides configuration models that define what parameters, fields,
and actions are allowed in a policy generation scenario. These constraints
are used to dynamically generate Pydantic models that enforce schema
validation at LLM generation time.

Key classes:
- ParameterSpec: Defines a single policy parameter with bounds and default
- ScenarioConstraints: Defines all allowed elements for a scenario
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator


class ParameterSpec(BaseModel):
    """Specification for a single policy parameter.

    Defines the name, valid range, default value, and description for a
    parameter that policies can use. The LLM can set values within the
    [min_value, max_value] range.

    Example:
        >>> spec = ParameterSpec(
        ...     name="urgency_threshold",
        ...     min_value=0.0,
        ...     max_value=20.0,
        ...     default=3.0,
        ...     description="Ticks before deadline when payment is urgent",
        ... )
    """

    name: str = Field(
        ...,
        min_length=1,
        description="Parameter name (must be valid Python identifier)",
    )
    min_value: float = Field(
        ...,
        description="Minimum allowed value (inclusive)",
    )
    max_value: float = Field(
        ...,
        description="Maximum allowed value (inclusive)",
    )
    default: float = Field(
        ...,
        description="Default value if not specified by LLM",
    )
    description: str = Field(
        ...,
        description="Human-readable description for LLM prompt",
    )

    @model_validator(mode="after")
    def validate_bounds(self) -> "ParameterSpec":
        """Validate that min < max and default is within bounds."""
        if self.min_value >= self.max_value:
            raise ValueError("min_value must be < max_value")
        if not (self.min_value <= self.default <= self.max_value):
            raise ValueError(
                f"default must be within [{self.min_value}, {self.max_value}], "
                f"got {self.default}"
            )
        return self


class ScenarioConstraints(BaseModel):
    """Constraints defining allowed policy elements for a scenario.

    This model validates that all specified fields and actions exist in the
    SimCash registry, ensuring generated policies will pass SimCash validation.

    Example:
        >>> constraints = ScenarioConstraints(
        ...     allowed_parameters=[
        ...         ParameterSpec("urgency", 0, 20, 3, "Urgency threshold"),
        ...     ],
        ...     allowed_fields=["balance", "ticks_to_deadline"],
        ...     allowed_actions=["Release", "Hold"],
        ... )
    """

    allowed_parameters: list[ParameterSpec] = Field(
        default_factory=list,
        description="Parameters the LLM can define and use",
    )
    allowed_fields: list[str] = Field(
        ...,
        min_length=1,
        description="Context fields the LLM can reference",
    )
    allowed_actions: list[str] = Field(
        ...,
        min_length=1,
        description="Actions the LLM can use in trees",
    )

    @field_validator("allowed_fields")
    @classmethod
    def validate_fields_exist(cls, v: list[str]) -> list[str]:
        """Validate all fields exist in SimCash registry."""
        if not v:
            raise ValueError("Must specify at least one field")

        from experiments.castro.schemas.registry import PAYMENT_TREE_FIELDS

        # Use payment tree fields as the superset (most comprehensive)
        valid_fields = set(PAYMENT_TREE_FIELDS)
        unknown = set(v) - valid_fields
        if unknown:
            raise ValueError(f"unknown field(s): {unknown}")
        return v

    @field_validator("allowed_actions")
    @classmethod
    def validate_actions_exist(cls, v: list[str]) -> list[str]:
        """Validate all actions exist in SimCash registry."""
        if not v:
            raise ValueError("Must specify at least one action")

        from experiments.castro.schemas.registry import (
            PAYMENT_ACTIONS,
            BANK_ACTIONS,
            COLLATERAL_ACTIONS,
        )

        # All valid actions across all tree types
        valid_actions = set(PAYMENT_ACTIONS + BANK_ACTIONS + COLLATERAL_ACTIONS)
        unknown = set(v) - valid_actions
        if unknown:
            raise ValueError(f"unknown action(s): {unknown}")
        return v

    @model_validator(mode="after")
    def validate_no_duplicate_params(self) -> "ScenarioConstraints":
        """Validate no duplicate parameter names."""
        names = [p.name for p in self.allowed_parameters]
        if len(names) != len(set(names)):
            duplicates = [n for n in names if names.count(n) > 1]
            raise ValueError(f"duplicate parameter name(s): {set(duplicates)}")
        return self

    def get_parameter_names(self) -> list[str]:
        """Get list of allowed parameter names."""
        return [p.name for p in self.allowed_parameters]

    def get_parameter_by_name(self, name: str) -> ParameterSpec | None:
        """Get a parameter spec by name."""
        for p in self.allowed_parameters:
            if p.name == name:
                return p
        return None
