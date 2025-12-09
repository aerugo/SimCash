"""Castro-aligned constraints for policy generation.

These constraints enforce the rules from Castro et al. (2025):
1. Initial liquidity decision at t=0 ONLY
2. Payment actions: Release (x_t=1) or Hold (x_t=0) only
3. No LSM, no credit lines, no splitting
"""

from __future__ import annotations

from payment_simulator.ai_cash_mgmt import ParameterSpec, ScenarioConstraints

# Castro paper constraints
CASTRO_CONSTRAINTS = ScenarioConstraints(
    allowed_parameters=[
        ParameterSpec(
            name="initial_liquidity_fraction",
            param_type="float",
            min_value=0.0,
            max_value=1.0,
            description="Fraction of collateral to post at t=0",
        ),
        ParameterSpec(
            name="urgency_threshold",
            param_type="int",
            min_value=0,
            max_value=20,
            description="Ticks before deadline to release payment",
        ),
        ParameterSpec(
            name="liquidity_buffer",
            param_type="float",
            min_value=0.5,
            max_value=3.0,
            description="Multiplier for required liquidity",
        ),
    ],
    allowed_fields=[
        # Time context
        "system_tick_in_day",
        "ticks_remaining_in_day",
        "current_tick",
        # Agent liquidity state
        "balance",
        "effective_liquidity",
        # Transaction context
        "ticks_to_deadline",
        "remaining_amount",
        "amount",
        "priority",
        # Queue state
        "queue1_total_value",
        "outgoing_queue_size",
        # Collateral
        "max_collateral_capacity",
        "posted_collateral",
    ],
    allowed_actions={
        "payment_tree": ["Release", "Hold"],
        "bank_tree": ["NoAction"],
        "collateral_tree": ["PostCollateral", "HoldCollateral"],
    },
)

# Minimal constraints for simple testing
MINIMAL_CONSTRAINTS = ScenarioConstraints(
    allowed_parameters=[
        ParameterSpec(
            name="urgency_threshold",
            param_type="int",
            min_value=0,
            max_value=20,
            description="Ticks before deadline to release payment",
        ),
    ],
    allowed_fields=[
        "balance",
        "effective_liquidity",
        "ticks_to_deadline",
        "remaining_amount",
        "ticks_remaining_in_day",
    ],
    allowed_actions={
        "payment_tree": ["Release", "Hold"],
    },
)
