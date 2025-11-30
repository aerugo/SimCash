"""Tests for extracting categories from policy JSON (TDD - tests written first).

These tests validate the ability to analyze a policy JSON and extract
all the schema categories it uses (actions, fields, computations, etc.).
"""

from __future__ import annotations

import json

import pytest


class TestExtractCategoriesFromPolicy:
    """Test the extract_categories_from_policy function."""

    def test_extract_simple_action_only_policy(self) -> None:
        """Policy with only a simple action extracts PaymentAction category."""
        from payment_simulator.policy.analysis import extract_categories_from_policy

        policy_json = json.dumps({
            "version": "1.0",
            "policy_id": "simple_fifo",
            "payment_tree": {
                "type": "action",
                "node_id": "A1",
                "action": "Release"
            }
        })

        categories = extract_categories_from_policy(policy_json)

        assert "PaymentAction" in categories

    def test_extract_field_reference(self) -> None:
        """Policy with field references extracts field category."""
        from payment_simulator.policy.analysis import extract_categories_from_policy

        policy_json = json.dumps({
            "version": "1.0",
            "policy_id": "deadline_aware",
            "payment_tree": {
                "type": "condition",
                "node_id": "C1",
                "condition": {
                    "op": "<=",
                    "left": {"field": "ticks_to_deadline"},
                    "right": {"value": 5}
                },
                "on_true": {"type": "action", "node_id": "A1", "action": "Release"},
                "on_false": {"type": "action", "node_id": "A2", "action": "Hold"}
            }
        })

        categories = extract_categories_from_policy(policy_json)

        assert "PaymentAction" in categories  # Release, Hold
        assert "TimeField" in categories  # ticks_to_deadline
        assert "ComparisonOperator" in categories  # <=

    def test_extract_computation(self) -> None:
        """Policy with computations extracts computation category."""
        from payment_simulator.policy.analysis import extract_categories_from_policy

        policy_json = json.dumps({
            "version": "1.0",
            "policy_id": "compute_test",
            "payment_tree": {
                "type": "condition",
                "node_id": "C1",
                "condition": {
                    "op": "<",
                    "left": {"field": "remaining_amount"},
                    "right": {
                        "compute": {
                            "op": "*",
                            "left": {"field": "balance"},
                            "right": {"value": 2}
                        }
                    }
                },
                "on_true": {"type": "action", "node_id": "A1", "action": "Release"},
                "on_false": {"type": "action", "node_id": "A2", "action": "Hold"}
            }
        })

        categories = extract_categories_from_policy(policy_json)

        assert "BinaryArithmetic" in categories  # * operator
        assert "TransactionField" in categories  # remaining_amount
        assert "AgentField" in categories  # balance

    def test_extract_collateral_action(self) -> None:
        """Policy with collateral actions extracts CollateralAction category."""
        from payment_simulator.policy.analysis import extract_categories_from_policy

        policy_json = json.dumps({
            "version": "1.0",
            "policy_id": "collateral_test",
            "end_of_tick_collateral_tree": {
                "type": "action",
                "node_id": "A1",
                "action": "PostCollateral",
                "parameters": {
                    "amount": {"field": "queue1_liquidity_gap"}
                }
            }
        })

        categories = extract_categories_from_policy(policy_json)

        assert "CollateralAction" in categories  # PostCollateral
        assert "QueueField" in categories  # queue1_liquidity_gap

    def test_extract_logical_operator(self) -> None:
        """Policy with logical operators extracts LogicalOperator category."""
        from payment_simulator.policy.analysis import extract_categories_from_policy

        policy_json = json.dumps({
            "version": "1.0",
            "policy_id": "logic_test",
            "payment_tree": {
                "type": "condition",
                "node_id": "C1",
                "condition": {
                    "op": "and",
                    "conditions": [
                        {"op": ">", "left": {"field": "balance"}, "right": {"value": 0}},
                        {"op": "<", "left": {"field": "remaining_amount"}, "right": {"value": 1000}}
                    ]
                },
                "on_true": {"type": "action", "node_id": "A1", "action": "Release"},
                "on_false": {"type": "action", "node_id": "A2", "action": "Hold"}
            }
        })

        categories = extract_categories_from_policy(policy_json)

        assert "LogicalOperator" in categories  # and

    def test_extract_n_ary_arithmetic(self) -> None:
        """Policy with n-ary arithmetic extracts NaryArithmetic category."""
        from payment_simulator.policy.analysis import extract_categories_from_policy

        policy_json = json.dumps({
            "version": "1.0",
            "policy_id": "nary_test",
            "payment_tree": {
                "type": "condition",
                "node_id": "C1",
                "condition": {
                    "op": "<=",
                    "left": {"field": "remaining_amount"},
                    "right": {
                        "compute": {
                            "op": "min",
                            "values": [
                                {"field": "balance"},
                                {"value": 100000}
                            ]
                        }
                    }
                },
                "on_true": {"type": "action", "node_id": "A1", "action": "Release"},
                "on_false": {"type": "action", "node_id": "A2", "action": "Hold"}
            }
        })

        categories = extract_categories_from_policy(policy_json)

        assert "NaryArithmetic" in categories  # min

    def test_extract_split_action(self) -> None:
        """Policy with Split action extracts PaymentAction category."""
        from payment_simulator.policy.analysis import extract_categories_from_policy

        policy_json = json.dumps({
            "version": "1.0",
            "policy_id": "split_test",
            "payment_tree": {
                "type": "action",
                "node_id": "A1",
                "action": "Split",
                "parameters": {
                    "num_splits": {"value": 3}
                }
            }
        })

        categories = extract_categories_from_policy(policy_json)

        assert "PaymentAction" in categories  # Split

    def test_extract_bank_tree(self) -> None:
        """Policy with bank_tree extracts BankAction category."""
        from payment_simulator.policy.analysis import extract_categories_from_policy

        policy_json = json.dumps({
            "version": "1.0",
            "policy_id": "bank_test",
            "bank_tree": {
                "type": "action",
                "node_id": "A1",
                "action": "SetReleaseBudget",
                "parameters": {
                    "budget": {"field": "balance"}
                }
            }
        })

        categories = extract_categories_from_policy(policy_json)

        assert "BankAction" in categories  # SetReleaseBudget

    def test_extract_complex_policy(self) -> None:
        """Complex policy with multiple categories."""
        from payment_simulator.policy.analysis import extract_categories_from_policy

        # A policy using multiple trees and features
        policy_json = json.dumps({
            "version": "1.0",
            "policy_id": "complex_test",
            "payment_tree": {
                "type": "condition",
                "node_id": "C1",
                "condition": {
                    "op": "and",
                    "conditions": [
                        {"op": "<=", "left": {"field": "ticks_to_deadline"}, "right": {"value": 10}},
                        {"op": ">=", "left": {"field": "balance"}, "right": {"field": "remaining_amount"}}
                    ]
                },
                "on_true": {"type": "action", "node_id": "A1", "action": "Release"},
                "on_false": {
                    "type": "condition",
                    "node_id": "C2",
                    "condition": {
                        "op": "<",
                        "left": {"field": "cost_delay_this_tx_one_tick"},
                        "right": {"field": "cost_overdraft_this_amount_one_tick"}
                    },
                    "on_true": {"type": "action", "node_id": "A2", "action": "Hold"},
                    "on_false": {"type": "action", "node_id": "A3", "action": "Split", "parameters": {"num_splits": {"value": 2}}}
                }
            },
            "end_of_tick_collateral_tree": {
                "type": "action",
                "node_id": "A4",
                "action": "PostCollateral",
                "parameters": {
                    "amount": {"compute": {"op": "*", "left": {"field": "queue1_liquidity_gap"}, "right": {"value": 1.1}}}
                }
            }
        })

        categories = extract_categories_from_policy(policy_json)

        # Check for expected categories
        assert "PaymentAction" in categories  # Release, Hold, Split
        assert "CollateralAction" in categories  # PostCollateral
        assert "LogicalOperator" in categories  # and
        assert "ComparisonOperator" in categories  # <=, >=, <
        assert "BinaryArithmetic" in categories  # *
        assert "TimeField" in categories  # ticks_to_deadline
        assert "AgentField" in categories  # balance
        assert "TransactionField" in categories  # remaining_amount
        assert "CostField" in categories  # cost_delay_this_tx_one_tick
        assert "QueueField" in categories  # queue1_liquidity_gap

    def test_empty_policy(self) -> None:
        """Empty policy returns empty set."""
        from payment_simulator.policy.analysis import extract_categories_from_policy

        policy_json = json.dumps({
            "version": "1.0",
            "policy_id": "empty_test"
        })

        categories = extract_categories_from_policy(policy_json)

        # Empty policy should have no categories
        assert len(categories) == 0

    def test_invalid_json_raises_error(self) -> None:
        """Invalid JSON raises appropriate error."""
        from payment_simulator.policy.analysis import extract_categories_from_policy

        with pytest.raises(ValueError, match="Invalid JSON"):
            extract_categories_from_policy("not valid json {")

    def test_extract_state_register_field(self) -> None:
        """Policy with state register access extracts StateRegisterField."""
        from payment_simulator.policy.analysis import extract_categories_from_policy

        policy_json = json.dumps({
            "version": "1.0",
            "policy_id": "register_test",
            "payment_tree": {
                "type": "condition",
                "node_id": "C1",
                "condition": {
                    "op": ">",
                    "left": {"field": "register_a"},
                    "right": {"value": 0}
                },
                "on_true": {"type": "action", "node_id": "A1", "action": "Release"},
                "on_false": {"type": "action", "node_id": "A2", "action": "Hold"}
            }
        })

        categories = extract_categories_from_policy(policy_json)

        assert "StateRegisterField" in categories  # register_a


class TestGetCategoryForElement:
    """Test looking up category for individual elements."""

    def test_action_category_lookup(self) -> None:
        """Can look up category for action names."""
        from payment_simulator.policy.analysis import get_category_for_action

        assert get_category_for_action("Release") == "PaymentAction"
        assert get_category_for_action("Hold") == "PaymentAction"
        assert get_category_for_action("Split") == "PaymentAction"
        assert get_category_for_action("PostCollateral") == "CollateralAction"
        assert get_category_for_action("WithdrawCollateral") == "CollateralAction"
        assert get_category_for_action("SetReleaseBudget") == "BankAction"

    def test_field_category_lookup(self) -> None:
        """Can look up category for field names."""
        from payment_simulator.policy.analysis import get_category_for_field

        assert get_category_for_field("remaining_amount") == "TransactionField"
        assert get_category_for_field("balance") == "AgentField"
        assert get_category_for_field("ticks_to_deadline") == "TimeField"
        assert get_category_for_field("posted_collateral") == "CollateralField"
        assert get_category_for_field("queue1_value") == "QueueField"
        assert get_category_for_field("cost_delay_this_tx_one_tick") == "CostField"
        assert get_category_for_field("register_a") == "StateRegisterField"

    def test_operator_category_lookup(self) -> None:
        """Can look up category for operators."""
        from payment_simulator.policy.analysis import get_category_for_operator

        # Comparison operators
        assert get_category_for_operator("==") == "ComparisonOperator"
        assert get_category_for_operator("<") == "ComparisonOperator"
        assert get_category_for_operator("<=") == "ComparisonOperator"
        assert get_category_for_operator(">") == "ComparisonOperator"
        assert get_category_for_operator(">=") == "ComparisonOperator"
        assert get_category_for_operator("!=") == "ComparisonOperator"

        # Logical operators
        assert get_category_for_operator("and") == "LogicalOperator"
        assert get_category_for_operator("or") == "LogicalOperator"
        assert get_category_for_operator("not") == "LogicalOperator"

        # Binary arithmetic
        assert get_category_for_operator("+") == "BinaryArithmetic"
        assert get_category_for_operator("-") == "BinaryArithmetic"
        assert get_category_for_operator("*") == "BinaryArithmetic"
        assert get_category_for_operator("/") == "BinaryArithmetic"

        # N-ary arithmetic
        assert get_category_for_operator("min") == "NaryArithmetic"
        assert get_category_for_operator("max") == "NaryArithmetic"
        assert get_category_for_operator("sum") == "NaryArithmetic"

    def test_unknown_element_returns_none(self) -> None:
        """Unknown elements return None."""
        from payment_simulator.policy.analysis import (
            get_category_for_action,
            get_category_for_field,
            get_category_for_operator,
        )

        assert get_category_for_action("FakeAction") is None
        assert get_category_for_field("fake_field") is None
        assert get_category_for_operator("fake_op") is None
