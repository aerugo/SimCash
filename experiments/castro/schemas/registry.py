"""Registry of fields and actions by tree type.

This module defines which fields and actions are available for each tree type,
along with their category mappings for feature toggle filtering.
"""

from __future__ import annotations


# ============================================================================
# Transaction-only fields (payment_tree only)
# ============================================================================

TRANSACTION_FIELDS = [
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
]

# ============================================================================
# Agent/Balance fields (all trees)
# ============================================================================

AGENT_FIELDS = [
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
]

# ============================================================================
# Queue 1 fields (all trees)
# ============================================================================

QUEUE_FIELDS = [
    "outgoing_queue_size",
    "queue1_total_value",
    "queue1_liquidity_gap",
    "headroom",
    "incoming_expected_count",
]

# ============================================================================
# Queue 2 (RTGS) fields (all trees)
# ============================================================================

QUEUE2_FIELDS = [
    "rtgs_queue_size",
    "rtgs_queue_value",
    "queue2_size",
    "queue2_count_for_agent",
    "queue2_nearest_deadline",
    "ticks_to_nearest_queue2_deadline",
]

# ============================================================================
# Collateral fields (all trees)
# ============================================================================

COLLATERAL_FIELDS = [
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
]

# ============================================================================
# Cost rate fields (all trees)
# ============================================================================

COST_FIELDS = [
    "cost_overdraft_bps_per_tick",
    "cost_delay_per_tick_per_cent",
    "cost_collateral_bps_per_tick",
    "cost_split_friction",
    "cost_deadline_penalty",
    "cost_eod_penalty",
]

# ============================================================================
# Time/System fields (all trees)
# ============================================================================

TIME_FIELDS = [
    "current_tick",
    "system_ticks_per_day",
    "system_current_day",
    "system_tick_in_day",
    "ticks_remaining_in_day",
    "day_progress_fraction",
    "is_eod_rush",
    "total_agents",
]

# ============================================================================
# LSM-Aware fields (payment_tree only)
# ============================================================================

LSM_FIELDS = [
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
]

# ============================================================================
# Throughput fields (all trees)
# ============================================================================

THROUGHPUT_FIELDS = [
    "system_queue2_pressure_index",
    "my_throughput_fraction_today",
    "expected_throughput_fraction_by_now",
    "throughput_gap",
]

# ============================================================================
# State register fields (all trees - user-defined prefix)
# ============================================================================

STATE_REGISTER_FIELDS = [
    "bank_state_cooldown",
    "bank_state_counter",
    "bank_state_budget_used",
    "bank_state_mode",
]

# ============================================================================
# Fields by tree type
# ============================================================================

# Common fields available in all trees
COMMON_FIELDS = (
    AGENT_FIELDS
    + QUEUE_FIELDS
    + QUEUE2_FIELDS
    + COLLATERAL_FIELDS
    + COST_FIELDS
    + TIME_FIELDS
    + THROUGHPUT_FIELDS
    + STATE_REGISTER_FIELDS
)

# Payment tree has transaction-specific and LSM fields
PAYMENT_TREE_FIELDS = TRANSACTION_FIELDS + COMMON_FIELDS + LSM_FIELDS

# Bank tree has agent-level fields only (no transaction context)
BANK_TREE_FIELDS = COMMON_FIELDS

# Collateral trees have same as bank tree
COLLATERAL_TREE_FIELDS = COMMON_FIELDS

# Fields by tree type
FIELDS_BY_TREE_TYPE: dict[str, list[str]] = {
    "payment_tree": PAYMENT_TREE_FIELDS,
    "bank_tree": BANK_TREE_FIELDS,
    "strategic_collateral_tree": COLLATERAL_TREE_FIELDS,
    "end_of_tick_collateral_tree": COLLATERAL_TREE_FIELDS,
}

# ============================================================================
# Field categories (for PolicyFeatureToggles)
# ============================================================================

FIELD_CATEGORIES: dict[str, str] = {}

# Transaction fields
for f in TRANSACTION_FIELDS:
    FIELD_CATEGORIES[f] = "TransactionField"

# Agent fields
for f in AGENT_FIELDS:
    FIELD_CATEGORIES[f] = "AgentField"

# Queue fields
for f in QUEUE_FIELDS:
    FIELD_CATEGORIES[f] = "QueueField"

# Queue 2 fields (also Queue category)
for f in QUEUE2_FIELDS:
    FIELD_CATEGORIES[f] = "QueueField"

# Collateral fields
for f in COLLATERAL_FIELDS:
    FIELD_CATEGORIES[f] = "CollateralField"

# Cost fields
for f in COST_FIELDS:
    FIELD_CATEGORIES[f] = "CostField"

# Time fields
for f in TIME_FIELDS:
    FIELD_CATEGORIES[f] = "TimeField"

# LSM fields
for f in LSM_FIELDS:
    FIELD_CATEGORIES[f] = "LsmField"

# Throughput fields
for f in THROUGHPUT_FIELDS:
    FIELD_CATEGORIES[f] = "ThroughputField"

# State register fields
for f in STATE_REGISTER_FIELDS:
    FIELD_CATEGORIES[f] = "StateRegisterField"


# ============================================================================
# Actions by tree type (re-exported from actions module)
# ============================================================================

from experiments.castro.schemas.actions import (
    ACTIONS_BY_TREE_TYPE,
    ACTION_CATEGORIES,
    PAYMENT_ACTIONS,
    BANK_ACTIONS,
    COLLATERAL_ACTIONS,
)

__all__ = [
    "FIELDS_BY_TREE_TYPE",
    "FIELD_CATEGORIES",
    "ACTIONS_BY_TREE_TYPE",
    "ACTION_CATEGORIES",
    "PAYMENT_ACTIONS",
    "BANK_ACTIONS",
    "COLLATERAL_ACTIONS",
    "TRANSACTION_FIELDS",
    "AGENT_FIELDS",
    "QUEUE_FIELDS",
    "COLLATERAL_FIELDS",
    "TIME_FIELDS",
    "LSM_FIELDS",
]
