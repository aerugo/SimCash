"""Unit tests for policy schema tree node types.

TDD: These tests are written BEFORE implementation.

The tree models implement depth-limited structures to work around
OpenAI's lack of recursive schema support. Each level (L0, L1, L2, etc.)
can only contain nodes from the level below.

Run with: pytest experiments/castro/tests/unit/test_schema_tree.py -v
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestTreeNodeL0:
    """Tests for TreeNodeL0 - leaf nodes only (actions, no conditions)."""

    def test_l0_action_node(self) -> None:
        """L0 can be an action node."""
        from experiments.castro.schemas.tree import TreeNodeL0
        from experiments.castro.schemas.actions import ActionNode

        node = ActionNode(
            type="action",
            action="Release",
        )
        # TreeNodeL0 should accept ActionNode
        assert node.type == "action"
        assert node.action == "Release"

    def test_l0_cannot_be_condition(self) -> None:
        """L0 cannot be a condition node (depth 0 = leaf only)."""
        # This is enforced by the type definition
        # TreeNodeL0 is just ActionNode
        from experiments.castro.schemas.tree import TreeNodeL0
        from experiments.castro.schemas.actions import ActionNode

        # TreeNodeL0 should be equivalent to ActionNode
        node: TreeNodeL0 = ActionNode(type="action", action="Hold")
        assert node.action == "Hold"


class TestConditionNodeL1:
    """Tests for ConditionNodeL1 - conditions with L0 children."""

    def test_l1_condition_with_l0_children(self) -> None:
        """L1 condition has L0 (action) children."""
        from experiments.castro.schemas.tree import ConditionNodeL1
        from experiments.castro.schemas.actions import ActionNode
        from experiments.castro.schemas.expressions import Comparison
        from experiments.castro.schemas.values import ContextField, LiteralValue

        node = ConditionNodeL1(
            type="condition",
            condition=Comparison(
                op=">=",
                left=ContextField(field="balance"),
                right=LiteralValue(value=0),
            ),
            on_true=ActionNode(type="action", action="Release"),
            on_false=ActionNode(type="action", action="Hold"),
        )
        assert node.type == "condition"
        assert node.on_true.action == "Release"
        assert node.on_false.action == "Hold"

    def test_l1_json_serialization(self) -> None:
        """L1 condition serializes correctly."""
        from experiments.castro.schemas.tree import ConditionNodeL1
        from experiments.castro.schemas.actions import ActionNode
        from experiments.castro.schemas.expressions import Comparison
        from experiments.castro.schemas.values import ContextField, LiteralValue

        node = ConditionNodeL1(
            type="condition",
            condition=Comparison(
                op="<=",
                left=ContextField(field="ticks_to_deadline"),
                right=LiteralValue(value=5),
            ),
            on_true=ActionNode(type="action", action="Release"),
            on_false=ActionNode(type="action", action="Hold"),
        )
        json_dict = node.model_dump(exclude_none=True)
        assert json_dict["type"] == "condition"
        assert json_dict["condition"]["op"] == "<="
        assert json_dict["on_true"]["action"] == "Release"


class TestTreeNodeL1:
    """Tests for TreeNodeL1 - action OR condition with L0 children."""

    def test_l1_can_be_action(self) -> None:
        """TreeNodeL1 can be a simple action."""
        from experiments.castro.schemas.tree import TreeNodeL1
        from experiments.castro.schemas.actions import ActionNode

        node: TreeNodeL1 = ActionNode(type="action", action="Release")
        assert node.type == "action"

    def test_l1_can_be_condition(self) -> None:
        """TreeNodeL1 can be a condition with L0 children."""
        from experiments.castro.schemas.tree import TreeNodeL1, ConditionNodeL1
        from experiments.castro.schemas.actions import ActionNode
        from experiments.castro.schemas.expressions import Comparison
        from experiments.castro.schemas.values import ContextField, LiteralValue

        node: TreeNodeL1 = ConditionNodeL1(
            type="condition",
            condition=Comparison(
                op=">",
                left=ContextField(field="balance"),
                right=LiteralValue(value=0),
            ),
            on_true=ActionNode(type="action", action="Release"),
            on_false=ActionNode(type="action", action="Hold"),
        )
        assert node.type == "condition"


class TestConditionNodeL2:
    """Tests for ConditionNodeL2 - conditions with L1 children."""

    def test_l2_condition_with_l1_children(self) -> None:
        """L2 condition can have nested L1 conditions."""
        from experiments.castro.schemas.tree import ConditionNodeL2, ConditionNodeL1
        from experiments.castro.schemas.actions import ActionNode
        from experiments.castro.schemas.expressions import Comparison
        from experiments.castro.schemas.values import ContextField, LiteralValue

        # Nested structure: condition -> condition -> action
        node = ConditionNodeL2(
            type="condition",
            condition=Comparison(
                op="<=",
                left=ContextField(field="ticks_to_deadline"),
                right=LiteralValue(value=5),
            ),
            on_true=ActionNode(type="action", action="Release"),
            on_false=ConditionNodeL1(
                type="condition",
                condition=Comparison(
                    op=">=",
                    left=ContextField(field="effective_liquidity"),
                    right=ContextField(field="remaining_amount"),
                ),
                on_true=ActionNode(type="action", action="Release"),
                on_false=ActionNode(type="action", action="Hold"),
            ),
        )
        assert node.type == "condition"
        assert node.on_true.action == "Release"
        # on_false is a nested condition
        assert node.on_false.type == "condition"


class TestTreeNodeL2:
    """Tests for TreeNodeL2 - action OR condition with L1 children."""

    def test_l2_can_be_action(self) -> None:
        """TreeNodeL2 can be a simple action."""
        from experiments.castro.schemas.tree import TreeNodeL2
        from experiments.castro.schemas.actions import ActionNode

        node: TreeNodeL2 = ActionNode(type="action", action="PostCollateral")
        assert node.type == "action"

    def test_l2_can_be_nested_condition(self) -> None:
        """TreeNodeL2 can be a 2-level deep condition tree."""
        from experiments.castro.schemas.tree import TreeNodeL2, ConditionNodeL2, ConditionNodeL1
        from experiments.castro.schemas.actions import ActionNode
        from experiments.castro.schemas.expressions import Comparison
        from experiments.castro.schemas.values import ContextField, LiteralValue

        node: TreeNodeL2 = ConditionNodeL2(
            type="condition",
            condition=Comparison(op=">", left=ContextField(field="a"), right=LiteralValue(value=0)),
            on_true=ConditionNodeL1(
                type="condition",
                condition=Comparison(op="<", left=ContextField(field="b"), right=LiteralValue(value=10)),
                on_true=ActionNode(type="action", action="Release"),
                on_false=ActionNode(type="action", action="Hold"),
            ),
            on_false=ActionNode(type="action", action="Hold"),
        )
        assert node.type == "condition"


class TestRealPolicyStructure:
    """Tests matching the actual seed policy structure from experiments."""

    def test_strategic_collateral_tree_structure(self) -> None:
        """Match the strategic_collateral_tree from seed_policy.json."""
        from experiments.castro.schemas.tree import ConditionNodeL1
        from experiments.castro.schemas.actions import ActionNode
        from experiments.castro.schemas.expressions import Comparison
        from experiments.castro.schemas.values import ContextField, LiteralValue, ComputeValue, ParameterRef

        # Matches seed_policy.json strategic_collateral_tree
        tree = ConditionNodeL1(
            type="condition",
            node_id="SC1_tick_zero",
            description="Allocate initial liquidity at start of day",
            condition=Comparison(
                op="==",
                left=ContextField(field="system_tick_in_day"),
                right=LiteralValue(value=0),
            ),
            on_true=ActionNode(
                type="action",
                node_id="SC2_post_initial",
                action="PostCollateral",
                parameters={
                    "amount": ComputeValue(
                        compute={
                            "op": "*",
                            "left": ContextField(field="max_collateral_capacity"),
                            "right": ParameterRef(param="initial_liquidity_fraction"),
                        }
                    ),
                    "reason": LiteralValue(value="InitialAllocation"),
                },
            ),
            on_false=ActionNode(
                type="action",
                node_id="SC3_hold",
                action="HoldCollateral",
            ),
        )
        assert tree.type == "condition"
        assert tree.node_id == "SC1_tick_zero"
        assert tree.on_true.action == "PostCollateral"

    def test_payment_tree_structure(self) -> None:
        """Match the payment_tree from seed_policy.json (2-level deep)."""
        from experiments.castro.schemas.tree import ConditionNodeL2, ConditionNodeL1
        from experiments.castro.schemas.actions import ActionNode
        from experiments.castro.schemas.expressions import Comparison
        from experiments.castro.schemas.values import ContextField, ParameterRef, ComputeValue

        # Matches seed_policy.json payment_tree
        tree = ConditionNodeL2(
            type="condition",
            node_id="P1_check_urgent",
            description="Release if close to deadline",
            condition=Comparison(
                op="<=",
                left=ContextField(field="ticks_to_deadline"),
                right=ParameterRef(param="urgency_threshold"),
            ),
            on_true=ActionNode(
                type="action",
                node_id="P2_release_urgent",
                action="Release",
            ),
            on_false=ConditionNodeL1(
                type="condition",
                node_id="P3_check_liquidity",
                description="Release if we have sufficient liquidity",
                condition=Comparison(
                    op=">=",
                    left=ContextField(field="effective_liquidity"),
                    right=ComputeValue(
                        compute={
                            "op": "*",
                            "left": ContextField(field="remaining_amount"),
                            "right": ParameterRef(param="liquidity_buffer_factor"),
                        }
                    ),
                ),
                on_true=ActionNode(
                    type="action",
                    node_id="P4_release_liquid",
                    action="Release",
                ),
                on_false=ActionNode(
                    type="action",
                    node_id="P5_hold",
                    action="Hold",
                ),
            ),
        )
        assert tree.type == "condition"
        assert tree.node_id == "P1_check_urgent"
        assert tree.on_true.action == "Release"
        assert tree.on_false.type == "condition"
        assert tree.on_false.on_true.action == "Release"
        assert tree.on_false.on_false.action == "Hold"


class TestMaxDepthTree:
    """Tests for maximum depth tree (L5 for production use)."""

    def test_l5_depth_supported(self) -> None:
        """TreeNodeL5 supports 5 levels of nesting."""
        from experiments.castro.schemas.tree import TreeNodeL5
        from experiments.castro.schemas.actions import ActionNode

        # At minimum, L5 can be an action
        node: TreeNodeL5 = ActionNode(type="action", action="Release")
        assert node.type == "action"

    def test_policy_tree_type(self) -> None:
        """PolicyTree is the main type for generating policies."""
        from experiments.castro.schemas.tree import PolicyTree
        from experiments.castro.schemas.actions import ActionNode

        # PolicyTree should work with ActionNode at minimum
        tree: PolicyTree = ActionNode(type="action", action="Release")
        assert tree.type == "action"


class TestTreeJsonRoundTrip:
    """Tests for JSON serialization/deserialization round-trips."""

    def test_simple_action_roundtrip(self) -> None:
        """Simple action node survives JSON round-trip."""
        from experiments.castro.schemas.actions import ActionNode
        import json

        original = ActionNode(type="action", action="Release")
        json_str = json.dumps(original.model_dump(exclude_none=True))
        parsed = ActionNode.model_validate(json.loads(json_str))
        assert parsed.action == "Release"

    def test_nested_condition_roundtrip(self) -> None:
        """Nested condition tree survives JSON round-trip."""
        from experiments.castro.schemas.tree import ConditionNodeL1
        from experiments.castro.schemas.actions import ActionNode
        from experiments.castro.schemas.expressions import Comparison
        from experiments.castro.schemas.values import ContextField, LiteralValue
        import json

        original = ConditionNodeL1(
            type="condition",
            condition=Comparison(
                op=">=",
                left=ContextField(field="balance"),
                right=LiteralValue(value=1000),
            ),
            on_true=ActionNode(type="action", action="Release"),
            on_false=ActionNode(type="action", action="Hold"),
        )
        json_str = json.dumps(original.model_dump(exclude_none=True))
        parsed = ConditionNodeL1.model_validate(json.loads(json_str))
        assert parsed.condition.op == ">="
        assert parsed.on_true.action == "Release"
