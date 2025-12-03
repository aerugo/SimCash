"""Depth-limited tree node models for policy generation.

This module implements the key innovation for working with OpenAI structured output:
depth-limited tree models that don't use recursive schemas ($ref).

OpenAI structured output doesn't support recursive schemas. Our policy DSL has
deeply nested trees (TreeNode contains TreeNode as on_true/on_false). To work
around this, we create explicit types for each depth level:

- TreeNodeL0 = ActionNode (leaf only)
- TreeNodeL1 = Action | ConditionL1 (condition with L0 children)
- TreeNodeL2 = Action | ConditionL2 (condition with L1 children)
- ... up to TreeNodeL5

This allows generating valid Pydantic models that OpenAI can use for
structured output, while supporting trees up to 5 levels deep.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field

from experiments.castro.schemas.actions import ActionNode
from experiments.castro.schemas.expressions import Expression


# ============================================================================
# Level 0: Leaf nodes only (just actions)
# ============================================================================

# TreeNodeL0 is simply an ActionNode - the base case
TreeNodeL0 = ActionNode


# ============================================================================
# Level 1: Actions OR conditions with L0 children
# ============================================================================

class ConditionNodeL1(BaseModel):
    """Condition node at depth 1 (children are L0 = actions only).

    Example:
        {
            "type": "condition",
            "condition": {"op": ">=", "left": {...}, "right": {...}},
            "on_true": {"type": "action", "action": "Release"},
            "on_false": {"type": "action", "action": "Hold"}
        }
    """

    type: Literal["condition"] = Field(
        "condition",
        description="Must be 'condition' to identify this as a condition node",
    )
    node_id: str | None = Field(
        None,
        description="Optional unique identifier for this node",
    )
    description: str | None = Field(
        None,
        description="Optional human-readable description",
    )
    condition: Expression = Field(
        ...,
        description="Boolean expression to evaluate",
    )
    on_true: TreeNodeL0 = Field(
        ...,
        description="Node to evaluate if condition is true (must be action at L1)",
    )
    on_false: TreeNodeL0 = Field(
        ...,
        description="Node to evaluate if condition is false (must be action at L1)",
    )


# TreeNodeL1 can be either an action or a condition with L0 children
TreeNodeL1 = Annotated[
    Union[ActionNode, ConditionNodeL1],
    Field(discriminator="type"),
]


# ============================================================================
# Level 2: Actions OR conditions with L1 children
# ============================================================================

class ConditionNodeL2(BaseModel):
    """Condition node at depth 2 (children are L1 = actions or L1 conditions)."""

    type: Literal["condition"] = Field(
        "condition",
        description="Must be 'condition'",
    )
    node_id: str | None = Field(None)
    description: str | None = Field(None)
    condition: Expression = Field(...)
    on_true: TreeNodeL1 = Field(
        ...,
        description="Node to evaluate if condition is true (L1 or action)",
    )
    on_false: TreeNodeL1 = Field(
        ...,
        description="Node to evaluate if condition is false (L1 or action)",
    )


TreeNodeL2 = Annotated[
    Union[ActionNode, ConditionNodeL2],
    Field(discriminator="type"),
]


# ============================================================================
# Level 3: Actions OR conditions with L2 children
# ============================================================================

class ConditionNodeL3(BaseModel):
    """Condition node at depth 3 (children are L2)."""

    type: Literal["condition"] = Field("condition")
    node_id: str | None = Field(None)
    description: str | None = Field(None)
    condition: Expression = Field(...)
    on_true: TreeNodeL2 = Field(...)
    on_false: TreeNodeL2 = Field(...)


TreeNodeL3 = Annotated[
    Union[ActionNode, ConditionNodeL3],
    Field(discriminator="type"),
]


# ============================================================================
# Level 4: Actions OR conditions with L3 children
# ============================================================================

class ConditionNodeL4(BaseModel):
    """Condition node at depth 4 (children are L3)."""

    type: Literal["condition"] = Field("condition")
    node_id: str | None = Field(None)
    description: str | None = Field(None)
    condition: Expression = Field(...)
    on_true: TreeNodeL3 = Field(...)
    on_false: TreeNodeL3 = Field(...)


TreeNodeL4 = Annotated[
    Union[ActionNode, ConditionNodeL4],
    Field(discriminator="type"),
]


# ============================================================================
# Level 5: Actions OR conditions with L4 children (max production depth)
# ============================================================================

class ConditionNodeL5(BaseModel):
    """Condition node at depth 5 (children are L4).

    This is the maximum depth for production use. 5 levels of nesting
    should be sufficient for most policy trees.
    """

    type: Literal["condition"] = Field("condition")
    node_id: str | None = Field(None)
    description: str | None = Field(None)
    condition: Expression = Field(...)
    on_true: TreeNodeL4 = Field(...)
    on_false: TreeNodeL4 = Field(...)


TreeNodeL5 = Annotated[
    Union[ActionNode, ConditionNodeL5],
    Field(discriminator="type"),
]


# ============================================================================
# PolicyTree: The main type for generating policies
# ============================================================================

# Default to L5 for maximum flexibility (5 levels of nesting)
PolicyTree = TreeNodeL5


# ============================================================================
# Depth-to-Type Mapping (for dynamic schema generation)
# ============================================================================

TREE_NODE_BY_DEPTH: dict[int, type] = {
    0: ActionNode,  # L0 is just actions
    1: ConditionNodeL1,
    2: ConditionNodeL2,
    3: ConditionNodeL3,
    4: ConditionNodeL4,
    5: ConditionNodeL5,
}

TREE_UNION_BY_DEPTH: dict[int, type] = {
    0: TreeNodeL0,
    1: TreeNodeL1,  # type: ignore[dict-item]
    2: TreeNodeL2,  # type: ignore[dict-item]
    3: TreeNodeL3,  # type: ignore[dict-item]
    4: TreeNodeL4,  # type: ignore[dict-item]
    5: TreeNodeL5,  # type: ignore[dict-item]
}


def get_tree_model(max_depth: int) -> type:
    """Get the appropriate tree model for a given max depth.

    Args:
        max_depth: Maximum depth of the tree (0-5)

    Returns:
        The appropriate TreeNodeLN type for that depth
    """
    if max_depth < 0 or max_depth > 5:
        raise ValueError(f"max_depth must be 0-5, got {max_depth}")
    return TREE_UNION_BY_DEPTH[max_depth]
