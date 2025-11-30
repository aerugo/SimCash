"""Policy analysis utilities for extracting categories used by a policy.

This module provides functions to analyze policy JSON files and extract
which schema categories (PaymentAction, CollateralAction, etc.) are used.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from payment_simulator.backends import get_policy_schema


# ============================================================================
# Hardcoded Field Mappings
# ============================================================================
# These mappings define which category each field belongs to.
# The schema generator doesn't expose individual field names, so we maintain
# this mapping manually based on the Rust source code.

FIELD_CATEGORY_MAP: dict[str, str] = {
    # TransactionField - Fields related to the current transaction
    "remaining_amount": "TransactionField",
    "amount": "TransactionField",
    "original_amount": "TransactionField",
    "priority": "TransactionField",
    "is_divisible": "TransactionField",
    "split_count": "TransactionField",
    "parent_tx_id": "TransactionField",
    "arrival_tick": "TransactionField",
    "deadline_tick": "TransactionField",
    "sender_id": "TransactionField",
    "receiver_id": "TransactionField",
    "tx_id": "TransactionField",
    "is_overdue": "TransactionField",
    "ticks_overdue": "TransactionField",

    # AgentField - Fields related to the current agent/bank
    "balance": "AgentField",
    "effective_liquidity": "AgentField",
    "credit_limit": "AgentField",
    "unsecured_cap": "AgentField",
    "agent_id": "AgentField",
    "available_credit": "AgentField",
    "opening_balance": "AgentField",
    "net_position": "AgentField",
    "inbound_today": "AgentField",
    "outbound_today": "AgentField",

    # QueueField - Queue-related fields
    "queue1_size": "QueueField",
    "queue1_value": "QueueField",
    "queue1_liquidity_gap": "QueueField",
    "queue1_oldest_wait_time": "QueueField",
    "queue2_size": "QueueField",
    "queue2_value": "QueueField",
    "queue_depth": "QueueField",
    "queue_wait_time": "QueueField",

    # TimeField - Time-related fields
    "current_tick": "TimeField",
    "current_day": "TimeField",
    "ticks_to_deadline": "TimeField",
    "ticks_to_eod": "TimeField",
    "is_eod_rush": "TimeField",
    "is_past_deadline": "TimeField",
    "ticks_per_day": "TimeField",
    "arrival_day": "TimeField",

    # CollateralField - Collateral-related fields
    "posted_collateral": "CollateralField",
    "available_collateral": "CollateralField",
    "collateral_haircut": "CollateralField",
    "remaining_collateral_capacity": "CollateralField",
    "collateral_credit_limit": "CollateralField",
    "total_credit_limit": "CollateralField",

    # CostField - Cost calculation fields
    "cost_delay_this_tx_one_tick": "CostField",
    "cost_overdraft_this_amount_one_tick": "CostField",
    "cost_deadline_penalty": "CostField",
    "cost_eod_penalty": "CostField",
    "cost_split_friction": "CostField",
    "accumulated_delay_cost": "CostField",
    "accumulated_overdraft_cost": "CostField",

    # LsmField - Liquidity-saving mechanism fields
    "bilateral_pairs_available": "LsmField",
    "bilateral_offset_potential": "LsmField",
    "cycle_count": "LsmField",
    "lsm_savings_potential": "LsmField",

    # ThroughputField - Transaction throughput fields
    "arrivals_this_tick": "ThroughputField",
    "settlements_this_tick": "ThroughputField",
    "payments_settled_today": "ThroughputField",
    "volume_settled_today": "ThroughputField",

    # StateRegisterField - User-defined state registers
    "register_a": "StateRegisterField",
    "register_b": "StateRegisterField",
    "register_c": "StateRegisterField",
    "register_d": "StateRegisterField",

    # SystemField - Global system fields
    "total_system_liquidity": "SystemField",
    "num_agents": "SystemField",
    "gridlock_indicator": "SystemField",

    # DerivedField - Computed/derived fields
    "urgency_score": "DerivedField",
    "liquidity_pressure": "DerivedField",
    "settlement_probability": "DerivedField",
}

# Additional operator mappings not in schema (e.g., aliases)
ADDITIONAL_OPERATOR_MAP: dict[str, str] = {
    "sum": "NaryArithmetic",
    "product": "NaryArithmetic",
    "avg": "NaryArithmetic",
    "neg": "UnaryMath",
    "negate": "UnaryMath",
}


@lru_cache(maxsize=1)
def _load_schema_mappings() -> (
    tuple[dict[str, str], dict[str, str], dict[str, str]]
):
    """Load and cache schema element-to-category mappings.

    Returns:
        Tuple of (action_map, field_map, operator_map) dicts.
    """
    schema_json = get_policy_schema()
    schema = json.loads(schema_json)

    action_map: dict[str, str] = {}
    operator_map: dict[str, str] = {}

    # Build action mapping from schema
    for action in schema.get("actions", []):
        json_key = action.get("json_key", action.get("name"))
        category = action.get("category")
        if json_key and category:
            action_map[json_key] = category

    # Build operator mapping from expressions and computations
    for expr in schema.get("expressions", []):
        json_key = expr.get("json_key", expr.get("name"))
        category = expr.get("category")
        if json_key and category:
            operator_map[json_key] = category

    for comp in schema.get("computations", []):
        json_key = comp.get("json_key", comp.get("name"))
        category = comp.get("category")
        if json_key and category:
            operator_map[json_key] = category

    # Add additional operators not in schema
    operator_map.update(ADDITIONAL_OPERATOR_MAP)

    # Use hardcoded field map (schema doesn't expose individual fields)
    field_map = FIELD_CATEGORY_MAP.copy()

    return action_map, field_map, operator_map


def get_category_for_action(action_name: str) -> str | None:
    """Get the category for an action name.

    Args:
        action_name: The action name (e.g., "Release", "PostCollateral").

    Returns:
        The category name or None if unknown.
    """
    action_map, _, _ = _load_schema_mappings()
    return action_map.get(action_name)


def get_category_for_field(field_name: str) -> str | None:
    """Get the category for a field name.

    Args:
        field_name: The field name (e.g., "balance", "ticks_to_deadline").

    Returns:
        The category name or None if unknown.
    """
    _, field_map, _ = _load_schema_mappings()
    return field_map.get(field_name)


def get_category_for_operator(operator: str) -> str | None:
    """Get the category for an operator.

    Args:
        operator: The operator (e.g., "+", "*", "min", "and", "<=").

    Returns:
        The category name or None if unknown.
    """
    _, _, operator_map = _load_schema_mappings()
    return operator_map.get(operator)


def extract_categories_from_policy(policy_json: str) -> set[str]:
    """Extract all schema categories used by a policy.

    Parses the policy JSON and identifies which categories
    (PaymentAction, CollateralAction, etc.) are used.

    Args:
        policy_json: The policy JSON content as a string.

    Returns:
        Set of category names used in the policy.

    Raises:
        ValueError: If the policy JSON is invalid.
    """
    try:
        policy = json.loads(policy_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}") from e

    categories: set[str] = set()

    # Process each tree type
    tree_keys = [
        "payment_tree",
        "bank_tree",
        "strategic_collateral_tree",
        "end_of_tick_collateral_tree",
    ]

    for tree_key in tree_keys:
        if tree_key in policy:
            _extract_from_node(policy[tree_key], categories)

    return categories


def _extract_from_node(node: dict[str, Any], categories: set[str]) -> None:
    """Recursively extract categories from a policy tree node.

    Args:
        node: The policy node dict.
        categories: Set to add discovered categories to.
    """
    if not isinstance(node, dict):
        return

    node_type = node.get("type")

    if node_type == "action":
        # Extract action category
        action_name = node.get("action")
        if action_name:
            category = get_category_for_action(action_name)
            if category:
                categories.add(category)

        # Process action parameters (may contain field refs, computations)
        if "parameters" in node:
            _extract_from_value(node["parameters"], categories)

    elif node_type == "condition":
        # Extract condition categories
        if "condition" in node:
            _extract_from_condition(node["condition"], categories)

        # Recursively process branches
        if "on_true" in node:
            _extract_from_node(node["on_true"], categories)
        if "on_false" in node:
            _extract_from_node(node["on_false"], categories)


def _extract_from_condition(condition: dict[str, Any], categories: set[str]) -> None:
    """Extract categories from a condition expression.

    Args:
        condition: The condition dict (operator + operands).
        categories: Set to add discovered categories to.
    """
    if not isinstance(condition, dict):
        return

    # Extract operator category
    op = condition.get("op")
    if op:
        category = get_category_for_operator(op)
        if category:
            categories.add(category)

    # Process left/right operands
    if "left" in condition:
        _extract_from_value(condition["left"], categories)
    if "right" in condition:
        _extract_from_value(condition["right"], categories)

    # Process array-form conditions (for "and"/"or")
    if "conditions" in condition:
        for sub_cond in condition["conditions"]:
            _extract_from_condition(sub_cond, categories)

    # Process n-ary operand values
    if "values" in condition:
        for val in condition["values"]:
            _extract_from_value(val, categories)


def _extract_from_value(value: Any, categories: set[str]) -> None:
    """Extract categories from a value expression.

    A value can be:
    - A literal: {"value": 5}
    - A field reference: {"field": "balance"}
    - A parameter reference: {"param": "threshold"}
    - A computation: {"compute": {"op": "*", ...}}
    - A dict of values (for action parameters)

    Args:
        value: The value expression.
        categories: Set to add discovered categories to.
    """
    if not isinstance(value, dict):
        return

    # Field reference
    if "field" in value:
        field_name = value["field"]
        category = get_category_for_field(field_name)
        if category:
            categories.add(category)

    # Computation
    if "compute" in value:
        _extract_from_computation(value["compute"], categories)

    # Nested values in action parameters
    for key, val in value.items():
        if key not in ("field", "value", "param", "compute"):
            _extract_from_value(val, categories)


def _extract_from_computation(compute: dict[str, Any], categories: set[str]) -> None:
    """Extract categories from a computation expression.

    Args:
        compute: The computation dict (operator + operands).
        categories: Set to add discovered categories to.
    """
    if not isinstance(compute, dict):
        return

    # Extract operator category
    op = compute.get("op")
    if op:
        category = get_category_for_operator(op)
        if category:
            categories.add(category)

    # Process operands
    if "left" in compute:
        _extract_from_value(compute["left"], categories)
    if "right" in compute:
        _extract_from_value(compute["right"], categories)

    # Process n-ary operand values
    if "values" in compute:
        for val in compute["values"]:
            _extract_from_value(val, categories)
