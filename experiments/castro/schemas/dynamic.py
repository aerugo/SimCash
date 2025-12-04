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

from pydantic import BaseModel, ConfigDict, Field, create_model, model_validator

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
    - Actions must be from allowed set (per tree type)

    Args:
        constraints: Scenario constraints defining all allowed elements

    Returns:
        A Pydantic model class for complete policies
    """
    # Create component models
    FieldLiteral = Literal[tuple(constraints.allowed_fields)]  # type: ignore[valid-type]
    PaymentActionLiteral = Literal[tuple(constraints.allowed_actions)]  # type: ignore[valid-type]

    # Create action literals for bank and collateral trees if enabled
    has_bank_actions = bool(constraints.allowed_bank_actions)
    has_collateral_actions = bool(constraints.allowed_collateral_actions)

    if has_bank_actions:
        BankActionLiteral = Literal[tuple(constraints.allowed_bank_actions)]  # type: ignore[valid-type]

    if has_collateral_actions:
        CollateralActionLiteral = Literal[tuple(constraints.allowed_collateral_actions)]  # type: ignore[valid-type]

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

    # Payment action node (for payment_tree)
    class DynamicPaymentActionNode(BaseModel):
        type: Literal["action"]
        action: PaymentActionLiteral  # type: ignore[valid-type]
        node_id: str | None = None
        description: str | None = None
        parameters: dict[str, Any] | None = None

    # Bank action node (for bank_tree) - only if bank actions are defined
    if has_bank_actions:
        class DynamicBankActionNode(BaseModel):
            type: Literal["action"]
            action: BankActionLiteral  # type: ignore[valid-type]
            node_id: str | None = None
            description: str | None = None
            parameters: dict[str, Any] | None = None
    else:
        DynamicBankActionNode = None  # type: ignore[assignment, misc]

    # Collateral action node (for collateral trees) - only if collateral actions defined
    if has_collateral_actions:
        class DynamicCollateralActionNode(BaseModel):
            type: Literal["action"]
            action: CollateralActionLiteral  # type: ignore[valid-type]
            node_id: str | None = None
            description: str | None = None
            parameters: dict[str, Any] | None = None
    else:
        DynamicCollateralActionNode = None  # type: ignore[assignment, misc]

    # Payment tree condition node (recursive)
    # Note: on_true/on_false are nullable to support Gemini's recursive schema requirement
    # but validated to ensure they're actually provided
    class DynamicPaymentConditionNode(BaseModel):
        type: Literal["condition"]
        condition: DynamicExpression | dict[str, Any]
        on_true: "DynamicPaymentTreeNode | None" = None
        on_false: "DynamicPaymentTreeNode | None" = None
        node_id: str | None = None
        description: str | None = None

        @model_validator(mode="after")
        def validate_branches_present(self) -> "DynamicPaymentConditionNode":
            """Ensure both branches are provided for condition nodes."""
            if self.on_true is None:
                raise ValueError("on_true branch is required for condition nodes")
            if self.on_false is None:
                raise ValueError("on_false branch is required for condition nodes")
            return self

    # Payment tree node union
    DynamicPaymentTreeNode = DynamicPaymentActionNode | DynamicPaymentConditionNode
    DynamicPaymentConditionNode.model_rebuild()

    # Bank tree nodes (only if bank actions defined)
    if has_bank_actions:
        # Note: on_true/on_false are nullable to support Gemini's recursive schema requirement
        # but validated to ensure they're actually provided
        class DynamicBankConditionNode(BaseModel):
            type: Literal["condition"]
            condition: DynamicExpression | dict[str, Any]
            on_true: "DynamicBankTreeNode | None" = None
            on_false: "DynamicBankTreeNode | None" = None
            node_id: str | None = None
            description: str | None = None

            @model_validator(mode="after")
            def validate_branches_present(self) -> "DynamicBankConditionNode":
                """Ensure both branches are provided for condition nodes."""
                if self.on_true is None:
                    raise ValueError("on_true branch is required for condition nodes")
                if self.on_false is None:
                    raise ValueError("on_false branch is required for condition nodes")
                return self

        DynamicBankTreeNode = DynamicBankActionNode | DynamicBankConditionNode
        DynamicBankConditionNode.model_rebuild()
    else:
        DynamicBankTreeNode = None  # type: ignore[assignment, misc]

    # Collateral tree nodes (only if collateral actions defined)
    if has_collateral_actions:
        # Note: on_true/on_false are nullable to support Gemini's recursive schema requirement
        # but validated to ensure they're actually provided
        class DynamicCollateralConditionNode(BaseModel):
            type: Literal["condition"]
            condition: DynamicExpression | dict[str, Any]
            on_true: "DynamicCollateralTreeNode | None" = None
            on_false: "DynamicCollateralTreeNode | None" = None
            node_id: str | None = None
            description: str | None = None

            @model_validator(mode="after")
            def validate_branches_present(self) -> "DynamicCollateralConditionNode":
                """Ensure both branches are provided for condition nodes."""
                if self.on_true is None:
                    raise ValueError("on_true branch is required for condition nodes")
                if self.on_false is None:
                    raise ValueError("on_false branch is required for condition nodes")
                return self

        DynamicCollateralTreeNode = DynamicCollateralActionNode | DynamicCollateralConditionNode
        DynamicCollateralConditionNode.model_rebuild()
    else:
        DynamicCollateralTreeNode = None  # type: ignore[assignment, misc]

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

    # Build the policy model fields dynamically based on what's enabled
    policy_fields: dict[str, Any] = {
        "policy_id": (str | None, None),
        "version": (str, "2.0"),
        "description": (str | None, None),
        "parameters": (dict[str, float], Field(default_factory=dict)),
        "payment_tree": (DynamicPaymentTreeNode | dict[str, Any], ...),
    }

    # Add bank_tree if bank actions are defined
    if has_bank_actions and DynamicBankTreeNode is not None:
        policy_fields["bank_tree"] = (
            DynamicBankTreeNode | dict[str, Any] | None,
            None,
        )
    else:
        policy_fields["bank_tree"] = (dict[str, Any] | None, None)

    # Add collateral trees if collateral actions are defined
    if has_collateral_actions and DynamicCollateralTreeNode is not None:
        policy_fields["strategic_collateral_tree"] = (
            DynamicCollateralTreeNode | dict[str, Any] | None,
            None,
        )
        policy_fields["end_of_tick_collateral_tree"] = (
            DynamicCollateralTreeNode | dict[str, Any] | None,
            None,
        )
    else:
        policy_fields["strategic_collateral_tree"] = (dict[str, Any] | None, None)
        policy_fields["end_of_tick_collateral_tree"] = (dict[str, Any] | None, None)

    DynamicPolicy = create_model(
        "DynamicPolicy",
        __config__=ConfigDict(extra="forbid"),
        **policy_fields,
    )

    return DynamicPolicy
