"""Action types for policy trees.

Actions are the terminal nodes in policy trees - they specify what to do
when a branch is taken. Different tree types support different action types.

Tree Types and Actions:
- payment_tree: Release, Hold, Split, etc.
- bank_tree: SetReleaseBudget, SetState, AddState, NoAction
- strategic_collateral_tree / end_of_tick_collateral_tree: PostCollateral, WithdrawCollateral, HoldCollateral
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field

from experiments.castro.schemas.values import PolicyValue


# ============================================================================
# Action Type Definitions
# ============================================================================

# Payment tree actions (payment_tree)
PAYMENT_ACTIONS = [
    "Release",
    "ReleaseWithCredit",
    "Split",
    "PaceAndRelease",
    "StaggerSplit",
    "Hold",
    "Drop",
    "Reprioritize",
    "WithdrawFromRtgs",
    "ResubmitToRtgs",
]

# Bank tree actions (bank_tree)
BANK_ACTIONS = [
    "SetReleaseBudget",
    "SetState",
    "AddState",
    "NoAction",
]

# Collateral tree actions (strategic_collateral_tree, end_of_tick_collateral_tree)
COLLATERAL_ACTIONS = [
    "PostCollateral",
    "WithdrawCollateral",
    "HoldCollateral",
]

# All action types
ALL_ACTIONS = PAYMENT_ACTIONS + BANK_ACTIONS + COLLATERAL_ACTIONS

# Action type as Literal
ActionType = Literal[
    # Payment actions
    "Release",
    "ReleaseWithCredit",
    "Split",
    "PaceAndRelease",
    "StaggerSplit",
    "Hold",
    "Drop",
    "Reprioritize",
    "WithdrawFromRtgs",
    "ResubmitToRtgs",
    # Bank actions
    "SetReleaseBudget",
    "SetState",
    "AddState",
    "NoAction",
    # Collateral actions
    "PostCollateral",
    "WithdrawCollateral",
    "HoldCollateral",
]

# Actions by tree type
ACTIONS_BY_TREE_TYPE: dict[str, list[str]] = {
    "payment_tree": PAYMENT_ACTIONS,
    "bank_tree": BANK_ACTIONS,
    "strategic_collateral_tree": COLLATERAL_ACTIONS,
    "end_of_tick_collateral_tree": COLLATERAL_ACTIONS,
}


# ============================================================================
# Action Node Model
# ============================================================================

class ActionNode(BaseModel):
    """An action node in the policy tree.

    Action nodes are the leaf nodes - they specify what decision to make
    when this branch is reached.

    Examples:
        {"type": "action", "action": "Release"}
        {"type": "action", "action": "Hold", "parameters": {"reason": {"value": "LowPriority"}}}
        {"type": "action", "action": "PostCollateral", "parameters": {"amount": {"field": "queue1_liquidity_gap"}}}
    """

    type: Literal["action"] = Field(
        "action",
        description="Must be 'action' to identify this as an action node",
    )
    node_id: str | None = Field(
        None,
        description="Optional unique identifier for this node",
    )
    description: str | None = Field(
        None,
        description="Optional human-readable description of this action",
    )
    action: ActionType = Field(
        ...,
        description="The action type to execute",
    )
    parameters: dict[str, PolicyValue | dict[str, Any]] = Field(
        default_factory=dict,
        description="Action-specific parameters",
    )


# ============================================================================
# Action Category Mappings (for feature toggles)
# ============================================================================

# Map action types to their categories (for PolicyFeatureToggles)
ACTION_CATEGORIES: dict[str, str] = {
    # Payment actions
    "Release": "PaymentAction",
    "ReleaseWithCredit": "PaymentAction",
    "Split": "PaymentAction",
    "PaceAndRelease": "PaymentAction",
    "StaggerSplit": "PaymentAction",
    "Hold": "PaymentAction",
    "Drop": "PaymentAction",
    "Reprioritize": "PaymentAction",
    "WithdrawFromRtgs": "PaymentAction",
    "ResubmitToRtgs": "PaymentAction",
    # Bank actions
    "SetReleaseBudget": "BankAction",
    "SetState": "BankAction",
    "AddState": "BankAction",
    "NoAction": "BankAction",
    # Collateral actions
    "PostCollateral": "CollateralAction",
    "WithdrawCollateral": "CollateralAction",
    "HoldCollateral": "CollateralAction",
}
