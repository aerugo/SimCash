"""Unit tests for policy schema action types.

TDD: These tests are written BEFORE implementation.
Run with: pytest experiments/castro/tests/unit/test_schema_actions.py -v
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestPaymentActions:
    """Tests for payment tree actions."""

    def test_release_action_no_params(self) -> None:
        """Release action with no parameters."""
        from experiments.castro.schemas.actions import ActionNode

        action = ActionNode(
            type="action",
            action="Release",
        )
        assert action.action == "Release"
        assert action.parameters == {}

    def test_release_action_with_priority_flag(self) -> None:
        """Release action with priority flag parameter."""
        from experiments.castro.schemas.actions import ActionNode
        from experiments.castro.schemas.values import LiteralValue

        action = ActionNode(
            type="action",
            action="Release",
            parameters={"priority_flag": LiteralValue(value="HIGH")},
        )
        assert action.parameters["priority_flag"].value == "HIGH"

    def test_hold_action_with_reason(self) -> None:
        """Hold action with reason parameter."""
        from experiments.castro.schemas.actions import ActionNode
        from experiments.castro.schemas.values import LiteralValue

        action = ActionNode(
            type="action",
            action="Hold",
            parameters={"reason": LiteralValue(value="InsufficientLiquidity")},
        )
        assert action.action == "Hold"
        assert action.parameters["reason"].value == "InsufficientLiquidity"

    def test_split_action_with_num_splits(self) -> None:
        """Split action with num_splits parameter."""
        from experiments.castro.schemas.actions import ActionNode
        from experiments.castro.schemas.values import LiteralValue

        action = ActionNode(
            type="action",
            action="Split",
            parameters={"num_splits": LiteralValue(value=4)},
        )
        assert action.action == "Split"
        assert action.parameters["num_splits"].value == 4

    def test_split_action_with_computed_splits(self) -> None:
        """Split action with dynamically computed num_splits."""
        from experiments.castro.schemas.actions import ActionNode
        from experiments.castro.schemas.values import ComputeValue, ContextField, LiteralValue

        action = ActionNode(
            type="action",
            action="Split",
            parameters={
                "num_splits": ComputeValue(
                    compute={
                        "op": "max",
                        "values": [
                            ComputeValue(
                                compute={
                                    "op": "ceil",
                                    "value": ComputeValue(
                                        compute={
                                            "op": "/",
                                            "left": ContextField(field="remaining_amount"),
                                            "right": ContextField(field="effective_liquidity"),
                                        }
                                    ),
                                }
                            ),
                            LiteralValue(value=2),
                        ],
                    }
                )
            },
        )
        assert action.action == "Split"

    def test_reprioritize_action(self) -> None:
        """Reprioritize action with new_priority."""
        from experiments.castro.schemas.actions import ActionNode
        from experiments.castro.schemas.values import LiteralValue

        action = ActionNode(
            type="action",
            action="Reprioritize",
            parameters={"new_priority": LiteralValue(value=10)},
        )
        assert action.action == "Reprioritize"
        assert action.parameters["new_priority"].value == 10

    def test_stagger_split_action(self) -> None:
        """StaggerSplit action with all parameters."""
        from experiments.castro.schemas.actions import ActionNode
        from experiments.castro.schemas.values import LiteralValue

        action = ActionNode(
            type="action",
            action="StaggerSplit",
            parameters={
                "num_splits": LiteralValue(value=5),
                "stagger_first_now": LiteralValue(value=2),
                "stagger_gap_ticks": LiteralValue(value=3),
                "priority_boost_children": LiteralValue(value=2),
            },
        )
        assert action.action == "StaggerSplit"
        assert len(action.parameters) == 4


class TestCollateralActions:
    """Tests for collateral tree actions."""

    def test_post_collateral_action(self) -> None:
        """PostCollateral action with amount."""
        from experiments.castro.schemas.actions import ActionNode
        from experiments.castro.schemas.values import ContextField

        action = ActionNode(
            type="action",
            action="PostCollateral",
            parameters={"amount": ContextField(field="queue1_liquidity_gap")},
        )
        assert action.action == "PostCollateral"
        assert action.parameters["amount"].field == "queue1_liquidity_gap"

    def test_post_collateral_with_computed_amount(self) -> None:
        """PostCollateral with computed amount."""
        from experiments.castro.schemas.actions import ActionNode
        from experiments.castro.schemas.values import ComputeValue, ContextField, ParameterRef

        action = ActionNode(
            type="action",
            action="PostCollateral",
            parameters={
                "amount": ComputeValue(
                    compute={
                        "op": "*",
                        "left": ContextField(field="max_collateral_capacity"),
                        "right": ParameterRef(param="initial_liquidity_fraction"),
                    }
                ),
                "reason": {"value": "InitialAllocation"},
            },
        )
        assert action.action == "PostCollateral"

    def test_withdraw_collateral_action(self) -> None:
        """WithdrawCollateral action."""
        from experiments.castro.schemas.actions import ActionNode
        from experiments.castro.schemas.values import ContextField, LiteralValue

        action = ActionNode(
            type="action",
            action="WithdrawCollateral",
            parameters={
                "amount": ContextField(field="excess_collateral"),
                "reason": LiteralValue(value="CostOptimization"),
            },
        )
        assert action.action == "WithdrawCollateral"

    def test_hold_collateral_action(self) -> None:
        """HoldCollateral action (no parameters)."""
        from experiments.castro.schemas.actions import ActionNode

        action = ActionNode(
            type="action",
            action="HoldCollateral",
        )
        assert action.action == "HoldCollateral"
        assert action.parameters == {}


class TestBankActions:
    """Tests for bank tree actions."""

    def test_set_release_budget_action(self) -> None:
        """SetReleaseBudget action."""
        from experiments.castro.schemas.actions import ActionNode
        from experiments.castro.schemas.values import LiteralValue

        action = ActionNode(
            type="action",
            action="SetReleaseBudget",
            parameters={
                "max_value_to_release": LiteralValue(value=500000),
            },
        )
        assert action.action == "SetReleaseBudget"

    def test_set_state_action(self) -> None:
        """SetState action."""
        from experiments.castro.schemas.actions import ActionNode
        from experiments.castro.schemas.values import LiteralValue

        action = ActionNode(
            type="action",
            action="SetState",
            parameters={
                "key": LiteralValue(value="bank_state_cooldown"),
                "value": LiteralValue(value=5.0),
            },
        )
        assert action.action == "SetState"

    def test_add_state_action(self) -> None:
        """AddState action."""
        from experiments.castro.schemas.actions import ActionNode
        from experiments.castro.schemas.values import LiteralValue

        action = ActionNode(
            type="action",
            action="AddState",
            parameters={
                "key": LiteralValue(value="bank_state_counter"),
                "value": LiteralValue(value=1.0),
            },
        )
        assert action.action == "AddState"

    def test_no_action(self) -> None:
        """NoAction action."""
        from experiments.castro.schemas.actions import ActionNode

        action = ActionNode(
            type="action",
            action="NoAction",
        )
        assert action.action == "NoAction"


class TestActionNodeSerialization:
    """Tests for action node JSON serialization."""

    def test_action_node_json_serialization(self) -> None:
        """Action node serializes to expected JSON structure."""
        from experiments.castro.schemas.actions import ActionNode

        action = ActionNode(
            type="action",
            action="Release",
        )
        json_dict = action.model_dump(exclude_none=True)
        assert json_dict == {
            "type": "action",
            "action": "Release",
            "parameters": {},
        }

    def test_action_node_with_params_serialization(self) -> None:
        """Action node with parameters serializes correctly."""
        from experiments.castro.schemas.actions import ActionNode
        from experiments.castro.schemas.values import LiteralValue

        action = ActionNode(
            type="action",
            action="Hold",
            parameters={"reason": LiteralValue(value="LowPriority")},
        )
        json_dict = action.model_dump()
        assert json_dict["action"] == "Hold"
        assert json_dict["parameters"]["reason"] == {"value": "LowPriority"}

    def test_action_node_from_json(self) -> None:
        """Action node can be parsed from JSON."""
        from experiments.castro.schemas.actions import ActionNode

        json_data = {
            "type": "action",
            "action": "Release",
            "parameters": {},
        }
        action = ActionNode.model_validate(json_data)
        assert action.action == "Release"

    def test_action_node_with_node_id(self) -> None:
        """Action node can have optional node_id."""
        from experiments.castro.schemas.actions import ActionNode

        action = ActionNode(
            type="action",
            node_id="P1_release",
            action="Release",
        )
        assert action.node_id == "P1_release"

    def test_action_node_with_description(self) -> None:
        """Action node can have optional description."""
        from experiments.castro.schemas.actions import ActionNode

        action = ActionNode(
            type="action",
            action="Release",
            description="Release payment immediately",
        )
        assert action.description == "Release payment immediately"


class TestActionTypeRegistry:
    """Tests for action type registry by tree type."""

    def test_payment_actions_list(self) -> None:
        """Payment tree has expected action types."""
        from experiments.castro.schemas.actions import PAYMENT_ACTIONS

        expected = {
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
        }
        assert expected.issubset(set(PAYMENT_ACTIONS))

    def test_collateral_actions_list(self) -> None:
        """Collateral trees have expected action types."""
        from experiments.castro.schemas.actions import COLLATERAL_ACTIONS

        expected = {"PostCollateral", "WithdrawCollateral", "HoldCollateral"}
        assert expected == set(COLLATERAL_ACTIONS)

    def test_bank_actions_list(self) -> None:
        """Bank tree has expected action types."""
        from experiments.castro.schemas.actions import BANK_ACTIONS

        expected = {"SetReleaseBudget", "SetState", "AddState", "NoAction"}
        assert expected == set(BANK_ACTIONS)

    def test_actions_by_tree_type(self) -> None:
        """Get actions for specific tree type."""
        from experiments.castro.schemas.actions import ACTIONS_BY_TREE_TYPE

        assert "Release" in ACTIONS_BY_TREE_TYPE["payment_tree"]
        assert "PostCollateral" in ACTIONS_BY_TREE_TYPE["strategic_collateral_tree"]
        assert "SetState" in ACTIONS_BY_TREE_TYPE["bank_tree"]
