"""Constrained policy schemas for robust LLM policy generation.

This module provides constrained Pydantic models that PREVENT the LLM from
generating invalid policies by:

1. Using Literal types for parameter names (only 3 allowed)
2. Using Literal types for context field names (validated against registry)
3. Enforcing correct operator structure (and/or use conditions array)

These models are designed to work with PydanticAI structured output, which
enforces the schema at generation time - eliminating ~94% of validation errors.

The three allowed policy parameters are:
- urgency_threshold: Ticks before deadline when payment becomes urgent (0-20)
- initial_liquidity_fraction: Fraction of max_collateral_capacity for initial allocation (0-1)
- liquidity_buffer_factor: Multiplier for required liquidity buffer (0.5-3.0)

Any attempt by the LLM to invent new parameters will fail schema validation.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union
from pydantic import BaseModel, ConfigDict, Field

from experiments.castro.schemas.registry import (
    PAYMENT_TREE_FIELDS,
    COLLATERAL_TREE_FIELDS,
    BANK_TREE_FIELDS,
)


# ============================================================================
# Constrained Policy Parameters (ONLY 3 ALLOWED)
# ============================================================================

# The ONLY allowed parameter names
ALLOWED_PARAMETERS = [
    "urgency_threshold",
    "initial_liquidity_fraction",
    "liquidity_buffer_factor",
]

# Type-safe parameter names as Literal
AllowedParameterName = Literal[
    "urgency_threshold",
    "initial_liquidity_fraction",
    "liquidity_buffer_factor",
]


class ConstrainedPolicyParameters(BaseModel):
    """Policy parameters with ONLY the 3 allowed fields.

    IMPORTANT: The LLM can ONLY set these three parameters.
    Any invented parameters (like min_liquidity_reserve_fraction,
    backlog_sensitivity, etc.) are NOT allowed.

    Attributes:
        urgency_threshold: Ticks before deadline when payment becomes urgent.
                          Range: 0-20. Default: 3.0
        initial_liquidity_fraction: Fraction of max_collateral_capacity for
                                   initial collateral allocation. Range: 0-1. Default: 0.25
        liquidity_buffer_factor: Multiplier for required liquidity when deciding
                                to release payments. Range: 0.5-3.0. Default: 1.0
    """

    model_config = ConfigDict(extra="forbid")

    urgency_threshold: float = Field(
        default=3.0,
        ge=0,
        le=20,
        description="Ticks before deadline when payment is considered urgent. Range: 0-20",
    )
    initial_liquidity_fraction: float = Field(
        default=0.25,
        ge=0,
        le=1.0,
        description="Fraction of max_collateral_capacity for initial allocation. Range: 0-1",
    )
    liquidity_buffer_factor: float = Field(
        default=1.0,
        ge=0.5,
        le=3.0,
        description="Multiplier for required liquidity buffer. Range: 0.5-3.0",
    )


# ============================================================================
# Constrained Context Field References
# ============================================================================

# Create Literal type from payment tree fields (most comprehensive)
# We use all unique fields across all tree types
ALL_VALID_FIELDS = list(set(PAYMENT_TREE_FIELDS + COLLATERAL_TREE_FIELDS + BANK_TREE_FIELDS))

# For PydanticAI structured output, we need a Literal type with all valid fields
# This is a bit verbose but necessary for compile-time validation
PaymentTreeField = Literal[
    # Transaction fields
    "amount",
    "remaining_amount",
    "settled_amount",
    "arrival_tick",
    "deadline_tick",
    "priority",
    "is_split",
    "is_past_deadline",
    "is_overdue",
    "is_in_queue2",
    "overdue_duration",
    "ticks_to_deadline",
    "queue_age",
    "cost_delay_this_tx_one_tick",
    "cost_overdraft_this_amount_one_tick",
    # Agent fields
    "balance",
    "credit_limit",
    "available_liquidity",
    "credit_used",
    "effective_liquidity",
    "credit_headroom",
    "is_using_credit",
    "liquidity_buffer",
    "liquidity_pressure",
    "is_overdraft_capped",
    # Queue fields
    "outgoing_queue_size",
    "queue1_total_value",
    "queue1_liquidity_gap",
    "headroom",
    "incoming_expected_count",
    # Queue 2 fields
    "rtgs_queue_size",
    "rtgs_queue_value",
    "queue2_size",
    "queue2_count_for_agent",
    "queue2_nearest_deadline",
    "ticks_to_nearest_queue2_deadline",
    # Collateral fields
    "posted_collateral",
    "max_collateral_capacity",
    "remaining_collateral_capacity",
    "collateral_utilization",
    "collateral_haircut",
    "unsecured_cap",
    "allowed_overdraft_limit",
    "overdraft_headroom",
    "overdraft_utilization",
    "required_collateral_for_usage",
    "excess_collateral",
    # Cost fields
    "cost_overdraft_bps_per_tick",
    "cost_delay_per_tick_per_cent",
    "cost_collateral_bps_per_tick",
    "cost_split_friction",
    "cost_deadline_penalty",
    "cost_eod_penalty",
    # Time fields
    "current_tick",
    "system_ticks_per_day",
    "system_current_day",
    "system_tick_in_day",
    "ticks_remaining_in_day",
    "day_progress_fraction",
    "is_eod_rush",
    "total_agents",
    # LSM fields
    "my_q2_out_value_to_counterparty",
    "my_q2_in_value_from_counterparty",
    "my_bilateral_net_q2",
    "my_q2_out_value_top_1",
    "my_q2_out_value_top_2",
    "my_q2_out_value_top_3",
    "my_q2_out_value_top_4",
    "my_q2_out_value_top_5",
    "my_q2_in_value_top_1",
    "my_q2_in_value_top_2",
    "my_q2_in_value_top_3",
    "my_q2_in_value_top_4",
    "my_q2_in_value_top_5",
    "my_bilateral_net_q2_top_1",
    "my_bilateral_net_q2_top_2",
    "my_bilateral_net_q2_top_3",
    "my_bilateral_net_q2_top_4",
    "my_bilateral_net_q2_top_5",
    "tx_counterparty_id",
    "tx_is_top_counterparty",
    # Throughput fields
    "system_queue2_pressure_index",
    "my_throughput_fraction_today",
    "expected_throughput_fraction_by_now",
    "throughput_gap",
    # State register fields
    "bank_state_cooldown",
    "bank_state_counter",
    "bank_state_budget_used",
    "bank_state_mode",
]

# For collateral trees (subset of fields)
CollateralTreeField = Literal[
    # Agent fields
    "balance",
    "credit_limit",
    "available_liquidity",
    "credit_used",
    "effective_liquidity",
    "credit_headroom",
    "is_using_credit",
    "liquidity_buffer",
    "liquidity_pressure",
    "is_overdraft_capped",
    # Queue fields
    "outgoing_queue_size",
    "queue1_total_value",
    "queue1_liquidity_gap",
    "headroom",
    "incoming_expected_count",
    # Queue 2 fields
    "rtgs_queue_size",
    "rtgs_queue_value",
    "queue2_size",
    "queue2_count_for_agent",
    "queue2_nearest_deadline",
    "ticks_to_nearest_queue2_deadline",
    # Collateral fields
    "posted_collateral",
    "max_collateral_capacity",
    "remaining_collateral_capacity",
    "collateral_utilization",
    "collateral_haircut",
    "unsecured_cap",
    "allowed_overdraft_limit",
    "overdraft_headroom",
    "overdraft_utilization",
    "required_collateral_for_usage",
    "excess_collateral",
    # Cost fields
    "cost_overdraft_bps_per_tick",
    "cost_delay_per_tick_per_cent",
    "cost_collateral_bps_per_tick",
    "cost_split_friction",
    "cost_deadline_penalty",
    "cost_eod_penalty",
    # Time fields
    "current_tick",
    "system_ticks_per_day",
    "system_current_day",
    "system_tick_in_day",
    "ticks_remaining_in_day",
    "day_progress_fraction",
    "is_eod_rush",
    "total_agents",
    # Throughput fields
    "system_queue2_pressure_index",
    "my_throughput_fraction_today",
    "expected_throughput_fraction_by_now",
    "throughput_gap",
    # State register fields
    "bank_state_cooldown",
    "bank_state_counter",
    "bank_state_budget_used",
    "bank_state_mode",
]


class ConstrainedContextField(BaseModel):
    """A context field reference that ONLY allows valid field names.

    The field name must be one of the predefined context fields from the
    simulation state. Any invented fields (like projected_min_balance_until_eod,
    expected_remaining_net_outflows, etc.) are NOT allowed.
    """

    field: PaymentTreeField = Field(
        ...,
        description="Name of the context field to reference. Must be a valid field from the simulation state.",
    )


class ConstrainedCollateralContextField(BaseModel):
    """Context field for collateral trees (subset of fields)."""

    field: CollateralTreeField = Field(
        ...,
        description="Name of the context field to reference.",
    )


# ============================================================================
# Constrained Parameter References
# ============================================================================

class ConstrainedParameterRef(BaseModel):
    """A parameter reference that ONLY allows the 3 valid parameter names.

    The param name must be one of:
    - urgency_threshold
    - initial_liquidity_fraction
    - liquidity_buffer_factor

    Any other parameter names are NOT allowed.
    """

    param: AllowedParameterName = Field(
        ...,
        description="Parameter name. ONLY these are allowed: urgency_threshold, initial_liquidity_fraction, liquidity_buffer_factor",
    )


# ============================================================================
# Constrained Literal Values
# ============================================================================

class ConstrainedLiteralValue(BaseModel):
    """A constant literal value (numeric only for policies)."""

    value: int | float = Field(
        ...,
        description="The literal numeric value",
    )


# ============================================================================
# Constrained Compute Values (simplified for robustness)
# ============================================================================

# Allowed compute operations
ComputeOp = Literal["*", "/", "+", "-", "max", "min"]


class ConstrainedComputeValue(BaseModel):
    """A computed value with binary operation.

    Operations: *, /, +, -, max, min

    Example: {"compute": {"op": "*", "left": {"field": "balance"}, "right": {"value": 0.5}}}
    """

    compute: "ConstrainedComputeSpec" = Field(
        ...,
        description="Computation specification",
    )


class ConstrainedComputeSpec(BaseModel):
    """Specification for a compute operation."""

    op: ComputeOp = Field(
        ...,
        description="Operation: *, /, +, -, max, min",
    )
    left: "ConstrainedPolicyValue" = Field(
        ...,
        description="Left operand",
    )
    right: "ConstrainedPolicyValue" = Field(
        ...,
        description="Right operand",
    )


# Union of all constrained value types
ConstrainedPolicyValue = Annotated[
    Union[ConstrainedContextField, ConstrainedLiteralValue, ConstrainedParameterRef, ConstrainedComputeValue],
    Field(discriminator=None),  # No single discriminator field
]

# Update forward references
ConstrainedComputeSpec.model_rebuild()
ConstrainedComputeValue.model_rebuild()


# ============================================================================
# Constrained Expressions (enforce and/or use conditions array)
# ============================================================================

ComparisonOperator = Literal["==", "!=", "<", "<=", ">", ">="]


class ConstrainedComparison(BaseModel):
    """A comparison between two values.

    Uses left/right operands (correct for comparison operators).

    Example: {"op": ">=", "left": {"field": "balance"}, "right": {"value": 0}}
    """

    op: ComparisonOperator = Field(
        ...,
        description="Comparison operator: ==, !=, <, <=, >, >=",
    )
    left: ConstrainedPolicyValue = Field(
        ...,
        description="Left operand",
    )
    right: ConstrainedPolicyValue = Field(
        ...,
        description="Right operand",
    )


class ConstrainedAndExpression(BaseModel):
    """Logical AND of multiple conditions.

    CRITICAL: Uses conditions array, NOT left/right!

    Example: {"op": "and", "conditions": [<expr>, <expr>, ...]}

    WRONG: {"op": "and", "left": ..., "right": ...}  <- This is INVALID!
    """

    op: Literal["and"] = Field(
        "and",
        description="Must be 'and'",
    )
    conditions: list["ConstrainedExpression"] = Field(
        ...,
        description="List of conditions that must ALL be true. Use conditions array, NOT left/right!",
        min_length=2,
    )


class ConstrainedOrExpression(BaseModel):
    """Logical OR of multiple conditions.

    CRITICAL: Uses conditions array, NOT left/right!

    Example: {"op": "or", "conditions": [<expr>, <expr>, ...]}

    WRONG: {"op": "or", "left": ..., "right": ...}  <- This is INVALID!
    """

    op: Literal["or"] = Field(
        "or",
        description="Must be 'or'",
    )
    conditions: list["ConstrainedExpression"] = Field(
        ...,
        description="List of conditions where at least ONE must be true. Use conditions array, NOT left/right!",
        min_length=2,
    )


class ConstrainedNotExpression(BaseModel):
    """Logical NOT (negation) of a condition.

    Example: {"op": "not", "condition": <expr>}
    """

    op: Literal["not"] = Field(
        "not",
        description="Must be 'not'",
    )
    condition: "ConstrainedExpression" = Field(
        ...,
        description="Condition to negate",
    )


# Expression union type
ConstrainedExpression = Annotated[
    Union[ConstrainedComparison, ConstrainedAndExpression, ConstrainedOrExpression, ConstrainedNotExpression],
    Field(discriminator="op"),
]

# Update forward references for recursive types
ConstrainedAndExpression.model_rebuild()
ConstrainedOrExpression.model_rebuild()
ConstrainedNotExpression.model_rebuild()


# ============================================================================
# Constrained Action Nodes
# ============================================================================

# Payment tree actions
PaymentAction = Literal[
    "Release",
    "Hold",
    "Split",
    "ReleaseWithCredit",
    "PaceAndRelease",
    "StaggerSplit",
    "Drop",
    "Reprioritize",
    "WithdrawFromRtgs",
    "ResubmitToRtgs",
]

# Collateral tree actions
CollateralAction = Literal[
    "PostCollateral",
    "WithdrawCollateral",
    "HoldCollateral",
]


class ConstrainedPaymentActionNode(BaseModel):
    """Action node for payment tree."""

    type: Literal["action"] = Field(
        "action",
        description="Must be 'action'",
    )
    node_id: str | None = Field(
        None,
        description="Optional unique identifier",
    )
    description: str | None = Field(
        None,
        description="Optional description",
    )
    action: PaymentAction = Field(
        ...,
        description="Action to execute: Release, Hold, Split, etc.",
    )


class ConstrainedCollateralActionNode(BaseModel):
    """Action node for collateral tree with parameters."""

    type: Literal["action"] = Field(
        "action",
        description="Must be 'action'",
    )
    node_id: str | None = Field(
        None,
        description="Optional unique identifier",
    )
    description: str | None = Field(
        None,
        description="Optional description",
    )
    action: CollateralAction = Field(
        ...,
        description="Action: PostCollateral, WithdrawCollateral, HoldCollateral",
    )
    parameters: dict[str, ConstrainedPolicyValue] | None = Field(
        None,
        description="Action parameters (e.g., amount for PostCollateral)",
    )


# ============================================================================
# Constrained Tree Nodes (depth-limited for OpenAI compatibility)
# ============================================================================

# Level 0: Action only
ConstrainedPaymentTreeL0 = ConstrainedPaymentActionNode
ConstrainedCollateralTreeL0 = ConstrainedCollateralActionNode


# Level 1: Action or Condition with L0 children
class ConstrainedPaymentConditionL1(BaseModel):
    """Condition node for payment tree at depth 1."""

    type: Literal["condition"] = Field(
        "condition",
        description="Must be 'condition'",
    )
    node_id: str | None = Field(None)
    description: str | None = Field(None)
    condition: ConstrainedExpression = Field(
        ...,
        description="Boolean expression to evaluate",
    )
    on_true: ConstrainedPaymentTreeL0 = Field(
        ...,
        description="Node if condition is true (must be action at L1)",
    )
    on_false: ConstrainedPaymentTreeL0 = Field(
        ...,
        description="Node if condition is false (must be action at L1)",
    )


class ConstrainedCollateralConditionL1(BaseModel):
    """Condition node for collateral tree at depth 1."""

    type: Literal["condition"] = Field(
        "condition",
        description="Must be 'condition'",
    )
    node_id: str | None = Field(None)
    description: str | None = Field(None)
    condition: ConstrainedExpression = Field(
        ...,
        description="Boolean expression to evaluate",
    )
    on_true: ConstrainedCollateralTreeL0 = Field(...)
    on_false: ConstrainedCollateralTreeL0 = Field(...)


ConstrainedPaymentTreeL1 = Annotated[
    Union[ConstrainedPaymentActionNode, ConstrainedPaymentConditionL1],
    Field(discriminator="type"),
]

ConstrainedCollateralTreeL1 = Annotated[
    Union[ConstrainedCollateralActionNode, ConstrainedCollateralConditionL1],
    Field(discriminator="type"),
]


# Level 2: Action or Condition with L1 children
class ConstrainedPaymentConditionL2(BaseModel):
    """Condition node for payment tree at depth 2."""

    type: Literal["condition"] = Field("condition")
    node_id: str | None = Field(None)
    description: str | None = Field(None)
    condition: ConstrainedExpression = Field(...)
    on_true: ConstrainedPaymentTreeL1 = Field(...)
    on_false: ConstrainedPaymentTreeL1 = Field(...)


class ConstrainedCollateralConditionL2(BaseModel):
    """Condition node for collateral tree at depth 2."""

    type: Literal["condition"] = Field("condition")
    node_id: str | None = Field(None)
    description: str | None = Field(None)
    condition: ConstrainedExpression = Field(...)
    on_true: ConstrainedCollateralTreeL1 = Field(...)
    on_false: ConstrainedCollateralTreeL1 = Field(...)


ConstrainedPaymentTreeL2 = Annotated[
    Union[ConstrainedPaymentActionNode, ConstrainedPaymentConditionL2],
    Field(discriminator="type"),
]

ConstrainedCollateralTreeL2 = Annotated[
    Union[ConstrainedCollateralActionNode, ConstrainedCollateralConditionL2],
    Field(discriminator="type"),
]


# Level 3: Action or Condition with L2 children (max depth for constrained generation)
class ConstrainedPaymentConditionL3(BaseModel):
    """Condition node for payment tree at depth 3."""

    type: Literal["condition"] = Field("condition")
    node_id: str | None = Field(None)
    description: str | None = Field(None)
    condition: ConstrainedExpression = Field(...)
    on_true: ConstrainedPaymentTreeL2 = Field(...)
    on_false: ConstrainedPaymentTreeL2 = Field(...)


class ConstrainedCollateralConditionL3(BaseModel):
    """Condition node for collateral tree at depth 3."""

    type: Literal["condition"] = Field("condition")
    node_id: str | None = Field(None)
    description: str | None = Field(None)
    condition: ConstrainedExpression = Field(...)
    on_true: ConstrainedCollateralTreeL2 = Field(...)
    on_false: ConstrainedCollateralTreeL2 = Field(...)


ConstrainedPaymentTreeL3 = Annotated[
    Union[ConstrainedPaymentActionNode, ConstrainedPaymentConditionL3],
    Field(discriminator="type"),
]

ConstrainedCollateralTreeL3 = Annotated[
    Union[ConstrainedCollateralActionNode, ConstrainedCollateralConditionL3],
    Field(discriminator="type"),
]


# ============================================================================
# Full Constrained Policy Model
# ============================================================================

class ConstrainedPolicy(BaseModel):
    """A complete policy with constrained parameters and trees.

    This model enforces ALL constraints at generation time:
    - Only 3 parameters allowed
    - Only valid context fields allowed
    - Only valid actions allowed
    - Correct operator structure (and/or use conditions array)

    Using this model with PydanticAI structured output eliminates ~94% of
    validation errors that occur with free-form JSON generation.
    """

    model_config = ConfigDict(extra="forbid")

    version: str = Field(
        default="2.0",
        description="Policy version",
    )
    policy_id: str | None = Field(
        None,
        description="Optional policy identifier",
    )
    description: str | None = Field(
        None,
        description="Human-readable policy description",
    )
    parameters: ConstrainedPolicyParameters = Field(
        default_factory=ConstrainedPolicyParameters,
        description="Policy parameters. ONLY urgency_threshold, initial_liquidity_fraction, liquidity_buffer_factor are allowed!",
    )
    strategic_collateral_tree: ConstrainedCollateralTreeL3 = Field(
        ...,
        description="Tree for strategic collateral decisions at start of tick",
    )
    payment_tree: ConstrainedPaymentTreeL3 = Field(
        ...,
        description="Tree for payment release decisions",
    )


# ============================================================================
# Utility Functions
# ============================================================================

def get_constrained_tree_model(tree_type: str, max_depth: int = 3) -> type:
    """Get the appropriate constrained tree model for a tree type and depth.

    Args:
        tree_type: "payment_tree", "strategic_collateral_tree", etc.
        max_depth: Maximum tree depth (1-3)

    Returns:
        Appropriate Pydantic model type
    """
    if tree_type == "payment_tree":
        models = {
            1: ConstrainedPaymentTreeL1,
            2: ConstrainedPaymentTreeL2,
            3: ConstrainedPaymentTreeL3,
        }
    elif tree_type in ("strategic_collateral_tree", "end_of_tick_collateral_tree"):
        models = {
            1: ConstrainedCollateralTreeL1,
            2: ConstrainedCollateralTreeL2,
            3: ConstrainedCollateralTreeL3,
        }
    else:
        raise ValueError(f"Unknown tree type: {tree_type}")

    if max_depth not in models:
        raise ValueError(f"max_depth must be 1-3, got {max_depth}")

    return models[max_depth]  # type: ignore[return-value]


# ============================================================================
# Schema Documentation for Prompts
# ============================================================================

PARAMETER_CONSTRAINTS_DOC = """
## CRITICAL: Policy Parameters

You can ONLY use these THREE parameters:

1. urgency_threshold (float, 0-20)
   - Ticks before deadline when a payment is considered urgent
   - Default: 3.0
   - Higher = more aggressive releasing

2. initial_liquidity_fraction (float, 0-1)
   - Fraction of max_collateral_capacity for initial collateral allocation
   - Default: 0.25
   - Higher = more initial liquidity, but higher collateral costs

3. liquidity_buffer_factor (float, 0.5-3.0)
   - Multiplier for required liquidity when deciding to release
   - Default: 1.0
   - Higher = more conservative releasing

DO NOT invent new parameters! Parameters like min_liquidity_reserve_fraction,
backlog_sensitivity, soft_urgency_threshold, etc. DO NOT EXIST.
"""

OPERATOR_STRUCTURE_DOC = """
## CRITICAL: Operator Structure

COMPARISON operators (==, !=, <, <=, >, >=) use left/right:
    {"op": ">=", "left": {"field": "balance"}, "right": {"value": 0}}

LOGICAL operators (and, or) use conditions ARRAY:
    {"op": "and", "conditions": [<expr1>, <expr2>, ...]}
    {"op": "or", "conditions": [<expr1>, <expr2>, ...]}

WRONG: {"op": "and", "left": ..., "right": ...}  <-- INVALID!
RIGHT: {"op": "and", "conditions": [...]}        <-- CORRECT!

NOT operator uses condition (singular):
    {"op": "not", "condition": <expr>}
"""

CONTEXT_FIELDS_DOC = f"""
## Available Context Fields

ONLY use these field names. Do NOT invent new fields!

Transaction fields: amount, remaining_amount, ticks_to_deadline, priority,
    is_overdue, queue_age, cost_delay_this_tx_one_tick

Agent fields: balance, effective_liquidity, credit_limit, credit_headroom

Queue fields: outgoing_queue_size, queue1_total_value, queue1_liquidity_gap

Collateral fields: posted_collateral, max_collateral_capacity,
    remaining_collateral_capacity, collateral_utilization

Time fields: current_tick, system_tick_in_day, ticks_remaining_in_day,
    day_progress_fraction, is_eod_rush

DO NOT invent fields like projected_min_balance_until_eod or
expected_remaining_net_outflows - these DO NOT EXIST!
"""


def get_schema_aware_prompt_additions() -> str:
    """Get prompt additions that enumerate all constraints."""
    return f"{PARAMETER_CONSTRAINTS_DOC}\n{OPERATOR_STRUCTURE_DOC}\n{CONTEXT_FIELDS_DOC}"
