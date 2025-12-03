"""Pre-defined parameter sets for common scenarios.

This module provides ready-to-use ScenarioConstraints configurations
at different levels of complexity:

- MINIMAL_CONSTRAINTS: Bare minimum for simple policies
- STANDARD_CONSTRAINTS: Common parameters for typical experiments
- FULL_CONSTRAINTS: All SimCash capabilities for maximum flexibility

Usage:
    from experiments.castro.parameter_sets import STANDARD_CONSTRAINTS
    from experiments.castro.generator import RobustPolicyAgent

    agent = RobustPolicyAgent(constraints=STANDARD_CONSTRAINTS)
    policy = agent.generate_policy("Optimize for low delay costs")
"""

from experiments.castro.schemas.parameter_config import (
    ParameterSpec,
    ScenarioConstraints,
)
from experiments.castro.schemas.registry import (
    PAYMENT_TREE_FIELDS,
    PAYMENT_ACTIONS,
)


# ============================================================================
# MINIMAL_CONSTRAINTS - Bare minimum for simple policies
# ============================================================================

MINIMAL_CONSTRAINTS = ScenarioConstraints(
    allowed_parameters=[
        ParameterSpec(
            name="urgency_threshold",
            min_value=0,
            max_value=20,
            default=3.0,
            description="Ticks before deadline when payment becomes urgent",
        ),
    ],
    allowed_fields=[
        # Basic agent state
        "balance",
        "effective_liquidity",
        # Transaction info
        "ticks_to_deadline",
        "remaining_amount",
        # Time
        "ticks_remaining_in_day",
    ],
    allowed_actions=[
        "Release",
        "Hold",
    ],
)


# ============================================================================
# STANDARD_CONSTRAINTS - Common parameters for typical experiments
# ============================================================================

STANDARD_CONSTRAINTS = ScenarioConstraints(
    allowed_parameters=[
        ParameterSpec(
            name="urgency_threshold",
            min_value=0,
            max_value=20,
            default=3.0,
            description="Ticks before deadline when payment becomes urgent",
        ),
        ParameterSpec(
            name="liquidity_buffer",
            min_value=0.5,
            max_value=3.0,
            default=1.0,
            description="Multiplier for required liquidity before releasing",
        ),
        ParameterSpec(
            name="initial_collateral_fraction",
            min_value=0,
            max_value=1.0,
            default=0.25,
            description="Fraction of max collateral to post at day start",
        ),
        ParameterSpec(
            name="eod_urgency_boost",
            min_value=0,
            max_value=10,
            default=2.0,
            description="Extra urgency threshold added near end of day",
        ),
    ],
    allowed_fields=[
        # Basic agent state
        "balance",
        "effective_liquidity",
        "credit_limit",
        "credit_headroom",
        # Transaction info
        "ticks_to_deadline",
        "remaining_amount",
        "amount",
        "priority",
        "is_past_deadline",
        # Queue info
        "queue1_total_value",
        "queue1_liquidity_gap",
        "outgoing_queue_size",
        # Time
        "ticks_remaining_in_day",
        "day_progress_fraction",
        "is_eod_rush",
        "current_tick",
        # Collateral
        "posted_collateral",
        "max_collateral_capacity",
        "remaining_collateral_capacity",
    ],
    allowed_actions=[
        "Release",
        "Hold",
        "Split",
    ],
)


# ============================================================================
# FULL_CONSTRAINTS - All SimCash capabilities
# ============================================================================

FULL_CONSTRAINTS = ScenarioConstraints(
    allowed_parameters=[
        # Core parameters
        ParameterSpec(
            name="urgency_threshold",
            min_value=0,
            max_value=20,
            default=3.0,
            description="Ticks before deadline when payment becomes urgent",
        ),
        ParameterSpec(
            name="liquidity_buffer",
            min_value=0.5,
            max_value=3.0,
            default=1.0,
            description="Multiplier for required liquidity before releasing",
        ),
        ParameterSpec(
            name="initial_collateral_fraction",
            min_value=0,
            max_value=1.0,
            default=0.25,
            description="Fraction of max collateral to post at day start",
        ),
        # Time-based parameters
        ParameterSpec(
            name="eod_urgency_boost",
            min_value=0,
            max_value=10,
            default=2.0,
            description="Extra urgency threshold added near end of day",
        ),
        ParameterSpec(
            name="eod_start_fraction",
            min_value=0.5,
            max_value=1.0,
            default=0.8,
            description="Day progress fraction when EOD rush begins",
        ),
        # Liquidity management
        ParameterSpec(
            name="queue_pressure_threshold",
            min_value=0,
            max_value=1.0,
            default=0.7,
            description="Queue-to-liquidity ratio triggering conservative mode",
        ),
        ParameterSpec(
            name="min_reserve_fraction",
            min_value=0,
            max_value=0.5,
            default=0.1,
            description="Minimum balance to keep in reserve",
        ),
        # Split parameters
        ParameterSpec(
            name="split_threshold_fraction",
            min_value=0.1,
            max_value=0.9,
            default=0.5,
            description="Payment-to-liquidity ratio to trigger split",
        ),
        ParameterSpec(
            name="split_count",
            min_value=2,
            max_value=10,
            default=2,
            description="Number of parts to split large payments into",
        ),
        # Priority parameters
        ParameterSpec(
            name="high_priority_threshold",
            min_value=1,
            max_value=10,
            default=7,
            description="Priority level above which payment is high priority",
        ),
    ],
    allowed_fields=PAYMENT_TREE_FIELDS,
    allowed_actions=PAYMENT_ACTIONS,
)


# ============================================================================
# Convenience accessors
# ============================================================================

ALL_CONSTRAINT_SETS = {
    "minimal": MINIMAL_CONSTRAINTS,
    "standard": STANDARD_CONSTRAINTS,
    "full": FULL_CONSTRAINTS,
}


def get_constraints(name: str) -> ScenarioConstraints:
    """Get a constraint set by name.

    Args:
        name: One of 'minimal', 'standard', or 'full'

    Returns:
        The corresponding ScenarioConstraints

    Raises:
        KeyError: If name is not recognized
    """
    return ALL_CONSTRAINT_SETS[name]
