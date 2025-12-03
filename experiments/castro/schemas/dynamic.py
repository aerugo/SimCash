"""Dynamic Pydantic model generation from scenario constraints.

This module generates Pydantic models at runtime based on ScenarioConstraints,
enabling the LLM to use any parameters, fields, and actions that SimCash
supports for a given scenario.

Key functions:
- create_parameter_model: Generate model for policy parameters
- create_context_field_model: Generate model for field references
- create_param_ref_model: Generate model for parameter references
- create_action_model: Generate model for action types
- create_constrained_policy_model: Generate complete policy model
"""

from __future__ import annotations

from typing import Any, Literal, Union, get_args

from pydantic import BaseModel, ConfigDict, Field, create_model

from experiments.castro.schemas.parameter_config import ScenarioConstraints


def create_parameter_model(constraints: ScenarioConstraints) -> type[BaseModel]:
    """Generate a Pydantic model for policy parameters.

    Creates a model where each allowed parameter becomes a field with
    the specified bounds and default value.

    Args:
        constraints: Scenario constraints defining allowed parameters

    Returns:
        A Pydantic model class that validates parameter values

    Example:
        >>> constraints = ScenarioConstraints(
        ...     allowed_parameters=[ParameterSpec("threshold", 0, 20, 5, "Threshold")],
        ...     allowed_fields=["balance"],
        ...     allowed_actions=["Release"],
        ... )
        >>> ParamModel = create_parameter_model(constraints)
        >>> params = ParamModel(threshold=10.0)
    """
    if not constraints.allowed_parameters:
        # Return empty model for no parameters
        return create_model(
            "DynamicParameters",
            __config__=ConfigDict(extra="forbid"),
        )

    fields: dict[str, Any] = {}
    for spec in constraints.allowed_parameters:
        fields[spec.name] = (
            float,
            Field(
                default=spec.default,
                ge=spec.min_value,
                le=spec.max_value,
                description=spec.description,
            ),
        )

    return create_model(
        "DynamicParameters",
        __config__=ConfigDict(extra="forbid"),
        **fields,
    )


def create_context_field_model(constraints: ScenarioConstraints) -> type[BaseModel]:
    """Generate a model that only accepts allowed field names.

    Args:
        constraints: Scenario constraints defining allowed fields

    Returns:
        A Pydantic model class for field references
    """
    # Create Literal type from allowed fields
    field_literal = Literal[tuple(constraints.allowed_fields)]  # type: ignore[valid-type]

    return create_model(
        "DynamicContextField",
        field=(field_literal, ...),
    )


def create_param_ref_model(constraints: ScenarioConstraints) -> type[BaseModel] | None:
    """Generate a model that only accepts defined parameter names.

    Args:
        constraints: Scenario constraints defining allowed parameters

    Returns:
        A Pydantic model class for parameter references, or None if no parameters
    """
    param_names = constraints.get_parameter_names()
    if not param_names:
        return None

    param_literal = Literal[tuple(param_names)]  # type: ignore[valid-type]

    return create_model(
        "DynamicParamRef",
        param=(param_literal, ...),
    )


def create_action_model(constraints: ScenarioConstraints) -> type[BaseModel]:
    """Generate a model that only accepts allowed action types.

    Args:
        constraints: Scenario constraints defining allowed actions

    Returns:
        A Pydantic model class for action types
    """
    action_literal = Literal[tuple(constraints.allowed_actions)]  # type: ignore[valid-type]

    return create_model(
        "DynamicAction",
        action=(action_literal, ...),
    )


def create_constrained_policy_model(constraints: ScenarioConstraints) -> type[BaseModel]:
    """Generate a complete policy model from constraints.

    Creates a Pydantic model that enforces all constraints at validation time:
    - Parameters must be from allowed set with valid bounds
    - Field references must be from allowed set
    - Parameter references must be from defined parameters
    - Actions must be from allowed set

    Args:
        constraints: Scenario constraints defining all allowed elements

    Returns:
        A Pydantic model class for complete policies
    """
    # Create component models
    FieldLiteral = Literal[tuple(constraints.allowed_fields)]  # type: ignore[valid-type]
    ActionLiteral = Literal[tuple(constraints.allowed_actions)]  # type: ignore[valid-type]

    param_names = constraints.get_parameter_names()
    has_params = bool(param_names)

    # Build value types
    class DynamicContextField(BaseModel):
        field: FieldLiteral  # type: ignore[valid-type]

    class DynamicLiteralValue(BaseModel):
        value: int | float | str

    if has_params:
        ParamLiteral = Literal[tuple(param_names)]  # type: ignore[valid-type]

        class DynamicParamRef(BaseModel):
            param: ParamLiteral  # type: ignore[valid-type]

        # Value can be field, literal, param, or compute
        DynamicValue = DynamicContextField | DynamicLiteralValue | DynamicParamRef | dict[str, Any]
    else:
        DynamicValue = DynamicContextField | DynamicLiteralValue | dict[str, Any]  # type: ignore[misc]

    # Expression types (comparison and logical)
    class DynamicExpression(BaseModel):
        model_config = ConfigDict(extra="allow")

        op: str
        left: DynamicValue | None = None
        right: DynamicValue | None = None
        conditions: list["DynamicExpression"] | None = None
        condition: "DynamicExpression | None" = None

    # Action node
    class DynamicActionNode(BaseModel):
        type: Literal["action"]
        action: ActionLiteral  # type: ignore[valid-type]
        node_id: str | None = None
        description: str | None = None
        parameters: dict[str, Any] | None = None

    # Condition node (recursive via dict for simplicity)
    class DynamicConditionNode(BaseModel):
        type: Literal["condition"]
        condition: DynamicExpression | dict[str, Any]
        on_true: "DynamicTreeNode"
        on_false: "DynamicTreeNode"
        node_id: str | None = None
        description: str | None = None

    # Tree node union
    DynamicTreeNode = DynamicActionNode | DynamicConditionNode

    # Rebuild for forward refs
    DynamicConditionNode.model_rebuild()

    # Parameter model
    param_fields: dict[str, Any] = {}
    for spec in constraints.allowed_parameters:
        param_fields[spec.name] = (
            float,
            Field(
                default=spec.default,
                ge=spec.min_value,
                le=spec.max_value,
                description=spec.description,
            ),
        )

    DynamicParameters = create_model(
        "DynamicParameters",
        __config__=ConfigDict(extra="forbid"),
        **param_fields,
    )

    # Full policy model
    class DynamicPolicy(BaseModel):
        model_config = ConfigDict(extra="forbid")

        policy_id: str | None = None
        version: str = "2.0"
        description: str | None = None
        parameters: dict[str, float] = Field(default_factory=dict)
        payment_tree: DynamicTreeNode | dict[str, Any]
        bank_tree: DynamicTreeNode | dict[str, Any] | None = None
        strategic_collateral_tree: DynamicTreeNode | dict[str, Any] | None = None
        end_of_tick_collateral_tree: DynamicTreeNode | dict[str, Any] | None = None

    return DynamicPolicy
