"""Pre-defined parameter sets for common scenarios.

This module provides ready-to-use ScenarioConstraints configurations
at different levels of complexity:

- CASTRO_CONSTRAINTS: Aligned with Castro et al. (2025) paper rules
- MINIMAL_CONSTRAINTS: Bare minimum for simple policies
- STANDARD_CONSTRAINTS: Common parameters for typical experiments
- FULL_CONSTRAINTS: All SimCash capabilities for maximum flexibility

Usage:
    from experiments.castro.parameter_sets import CASTRO_CONSTRAINTS
    from experiments.castro.generator import RobustPolicyAgent

    # For Castro-aligned experiments:
    agent = RobustPolicyAgent(constraints=CASTRO_CONSTRAINTS)
    policy = agent.generate_policy("Optimize for low delay costs")
"""

from experiments.castro.schemas.parameter_config import (
    ParameterSpec,
    ScenarioConstraints,
)
from experiments.castro.schemas.registry import (
    BANK_ACTIONS,
    COLLATERAL_ACTIONS,
    PAYMENT_ACTIONS,
    PAYMENT_TREE_FIELDS,
)


# ============================================================================
# CASTRO_CONSTRAINTS - Aligned with Castro et al. (2025) paper
# ============================================================================
#
# This constraint set enforces the rules from "Estimating Policy Functions
# in Payment Systems Using Reinforcement Learning" (Castro et al., 2025):
#
# 1. Initial liquidity decision at t=0 ONLY (no mid-day collateral changes)
# 2. Payment decisions are Release (x_t=1) or Hold (x_t=0) - no splitting
# 3. No interbank credit lines (no ReleaseWithCredit)
# 4. No LSM/netting (disabled at scenario level)
# 5. Cost structure: r_c (collateral) < r_d (delay) < r_b (EOD borrowing)
#
# The LLM is constrained to generate policies matching Castro's model:
# - strategic_collateral_tree: Post at tick 0, hold otherwise
# - payment_tree: Release/Hold based on liquidity and urgency
# - No bank_tree complexity (simple NoAction)
# - No end_of_tick_collateral_tree (no reactive collateral)

CASTRO_CONSTRAINTS = ScenarioConstraints(
    allowed_parameters=[
        ParameterSpec(
            name="initial_liquidity_fraction",
            min_value=0.0,
            max_value=1.0,
            default=0.25,
            description=(
                "Fraction x_0 of collateral B to post as initial liquidity. "
                "Castro notation: ℓ₀ = x₀ · B. This is the ONLY collateral decision."
            ),
        ),
        ParameterSpec(
            name="urgency_threshold",
            min_value=0,
            max_value=20,
            default=3.0,
            description=(
                "Ticks before deadline when payment becomes urgent and must be released. "
                "Maps to Castro's intraday payment fraction x_t decision."
            ),
        ),
        ParameterSpec(
            name="liquidity_buffer",
            min_value=0.5,
            max_value=3.0,
            default=1.0,
            description=(
                "Multiplier for required liquidity before releasing. "
                "Helps enforce Castro's constraint: P_t · x_t ≤ ℓ_{t-1}."
            ),
        ),
    ],
    allowed_fields=[
        # Time context (critical for Castro's t=0 decision)
        "system_tick_in_day",
        "ticks_remaining_in_day",
        "day_progress_fraction",
        "current_tick",
        # Agent liquidity state (ℓ_t in Castro notation)
        "balance",
        "effective_liquidity",
        # Transaction context (P_t in Castro notation)
        "ticks_to_deadline",
        "remaining_amount",
        "amount",
        "priority",
        "is_past_deadline",
        # Queue state (accumulated demand Σ P_t)
        "queue1_total_value",
        "queue1_liquidity_gap",
        "outgoing_queue_size",
        # Collateral (B in Castro notation - for initial allocation)
        "max_collateral_capacity",
        "posted_collateral",
        "remaining_collateral_capacity",
        # EXCLUDED: credit_*, lsm_*, throughput_*, state_register_*
        # These features don't exist in Castro's model
    ],
    allowed_actions=[
        "Release",  # x_t = 1: send payment in full
        "Hold",     # x_t = 0: delay payment to next period
        # EXCLUDED: Split, ReleaseWithCredit, PaceAndRelease, StaggerSplit,
        #           Drop, Reprioritize, WithdrawFromRtgs, ResubmitToRtgs
    ],
    allowed_bank_actions=["NoAction"],  # Disable bank-level budgeting complexity
    allowed_collateral_actions=[
        "PostCollateral",   # For initial allocation at t=0
        "HoldCollateral",   # For all other ticks (no changes)
        # EXCLUDED: WithdrawCollateral (no mid-day collateral reduction in Castro)
    ],
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
    allowed_bank_actions=BANK_ACTIONS,
    allowed_collateral_actions=COLLATERAL_ACTIONS,
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
    allowed_bank_actions=BANK_ACTIONS,
    allowed_collateral_actions=COLLATERAL_ACTIONS,
)


# ============================================================================
# Convenience accessors
# ============================================================================

ALL_CONSTRAINT_SETS = {
    "castro": CASTRO_CONSTRAINTS,
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
