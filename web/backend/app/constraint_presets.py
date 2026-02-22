"""Constraint presets for LLM policy optimization.

Presets control WHAT the LLM is allowed to optimize:
- Simple: Just initial_liquidity_fraction (current behavior)
- Standard: Fraction + Release/Hold/Split with basic conditions
- Full: All actions, all context fields, full decision tree optimization

IMPORTANT: Field names MUST match the actual Rust engine context fields exactly.
See simulator/src/policy/tree/context.rs for:
  - EvalContext::build() — transaction-level fields (payment_tree)
  - EvalContext::bank_level() — bank-level fields (bank_tree, collateral trees)
See simulator/src/policy/tree/validation.rs:
  - is_bank_level_field() — allowlist for bank_tree field validation
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Lazy imports to avoid loading heavy modules at import time
_ScenarioConstraints = None
_ParameterSpec = None


def _ensure_imports():
    global _ScenarioConstraints, _ParameterSpec
    if _ScenarioConstraints is None:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "api"))
        from payment_simulator.ai_cash_mgmt.constraints.scenario_constraints import (
            ScenarioConstraints,
            ParameterSpec,
        )
        _ScenarioConstraints = ScenarioConstraints
        _ParameterSpec = ParameterSpec


@dataclass
class ConstraintPreset:
    id: str
    name: str
    description: str
    complexity: str  # "simple", "standard", "full"


PRESET_METADATA: list[dict[str, str]] = [
    {
        "id": "simple",
        "name": "Simple (Liquidity Only)",
        "description": "LLM tunes initial_liquidity_fraction only. Payment tree: Release or Hold. Fast convergence, limited strategy space.",
        "complexity": "simple",
    },
    {
        "id": "standard",
        "name": "Standard (Release/Hold/Split)",
        "description": "LLM can tune fraction + build conditional payment trees with Release, Hold, and Split actions. Uses balance, queue, and timing context fields.",
        "complexity": "standard",
    },
    {
        "id": "full",
        "name": "Full (All Actions & Fields)",
        "description": "LLM has access to all actions, all context fields, state registers, and all tree types. Maximum strategy space — slower convergence but richer policies.",
        "complexity": "full",
    },
]


def get_preset_metadata() -> list[dict[str, str]]:
    """Return metadata for all presets (no heavy imports needed)."""
    return PRESET_METADATA


def build_constraints(preset_id: str = "simple", scenario_config: dict | None = None) -> Any:
    """Build ScenarioConstraints for the given preset.
    
    Args:
        preset_id: One of "simple", "standard", "full"
        scenario_config: Raw scenario YAML dict, used to detect LSM features
    
    Returns:
        ScenarioConstraints instance
    """
    _ensure_imports()
    
    scenario_config = scenario_config or {}
    lsm_enabled = bool(
        scenario_config.get("lsm_config")
        or scenario_config.get("enable_bilateral_lsm")
        or scenario_config.get("enable_cycle_lsm")
    )
    
    if preset_id == "simple":
        return _build_simple(lsm_enabled)
    elif preset_id == "standard":
        return _build_standard(lsm_enabled)
    elif preset_id == "full":
        return _build_full(lsm_enabled)
    else:
        raise ValueError(f"Unknown constraint preset: {preset_id}")


def _build_simple(lsm_enabled: bool) -> Any:
    """Simple: just fraction + Release/Hold."""
    return _ScenarioConstraints(
        allowed_parameters=[
            _ParameterSpec(
                name="initial_liquidity_fraction",
                param_type="float",
                min_value=0.0,
                max_value=1.0,
                description="Fraction of liquidity_pool to allocate at simulation start.",
            ),
        ],
        allowed_fields=[
            # Verified against EvalContext::build() in context.rs
            "system_tick_in_day", "balance", "amount", "remaining_amount", "ticks_to_deadline",
        ],
        allowed_actions={"payment_tree": ["Release", "Hold"], "bank_tree": ["NoAction"]},
        lsm_enabled=lsm_enabled,
    )


def _build_standard(lsm_enabled: bool) -> Any:
    """Standard: fraction + Release/Hold/Split + conditions on balance/timing/queue."""
    return _ScenarioConstraints(
        allowed_parameters=[
            _ParameterSpec(
                name="initial_liquidity_fraction",
                param_type="float",
                min_value=0.0,
                max_value=1.0,
                description="Fraction of liquidity_pool to allocate at simulation start.",
            ),
            _ParameterSpec(
                name="split_threshold",
                param_type="float",
                min_value=0.0,
                max_value=1_000_000.0,
                description="Payment amount above which to consider splitting.",
            ),
            _ParameterSpec(
                name="urgency_threshold",
                param_type="float",
                min_value=0.0,
                max_value=20.0,
                description="Ticks-to-deadline below which payments become urgent.",
            ),
        ],
        allowed_fields=[
            # Balance & liquidity (from EvalContext::build)
            "balance", "available_liquidity", "effective_liquidity",
            # Payment attributes (transaction-level)
            "amount", "remaining_amount", "ticks_to_deadline", "is_eod_rush",
            # Queue & system state
            "outgoing_queue_size", "queue1_total_value", "system_tick_in_day",
            "system_ticks_per_day", "ticks_remaining_in_day",
            # Cost awareness
            "cost_delay_per_tick_per_cent", "cost_overdraft_bps_per_tick",
        ],
        allowed_actions={
            "payment_tree": ["Release", "Hold", "Split"],
            "bank_tree": ["NoAction"],
        },
        lsm_enabled=lsm_enabled,
    )


def _build_full(lsm_enabled: bool) -> Any:
    """Full: all actions, all fields, all trees.
    
    Every field name here has been verified against:
    - EvalContext::build() for payment_tree fields (context.rs)
    - EvalContext::bank_level() for bank_tree fields (context.rs)
    - is_bank_level_field() for bank_tree validation (validation.rs)
    """
    all_fields = [
        # === Transaction fields (payment_tree only) ===
        "amount", "remaining_amount", "settled_amount",
        "arrival_tick", "deadline_tick", "priority",
        "is_split", "is_past_deadline", "is_overdue", "is_in_queue2",
        "overdue_duration", "queue_age",
        
        # === Agent fields (both payment_tree and bank_tree) ===
        "balance", "available_liquidity", "effective_liquidity",
        "credit_limit", "credit_used", "credit_headroom",
        "is_using_credit", "is_overdraft_capped",
        "liquidity_buffer", "liquidity_pressure",
        "outgoing_queue_size", "incoming_expected_count",
        
        # === Queue 1 metrics ===
        "queue1_total_value", "queue1_liquidity_gap", "headroom",
        
        # === Queue 2 (RTGS) metrics ===
        "queue2_size", "queue2_count_for_agent",
        "queue2_nearest_deadline", "ticks_to_nearest_queue2_deadline",
        "rtgs_queue_size", "rtgs_queue_value",
        
        # === System fields ===
        "current_tick", "total_agents",
        "system_tick_in_day", "system_ticks_per_day", "system_current_day",
        "ticks_remaining_in_day", "day_progress_fraction", "is_eod_rush",
        
        # === Derived timing fields ===
        "ticks_to_deadline",
        
        # === Counterparty fields (payment_tree only) ===
        "tx_counterparty_id", "tx_is_top_counterparty",
        "my_bilateral_net_q2",
        "my_q2_out_value_to_counterparty", "my_q2_in_value_from_counterparty",
        
        # === Bilateral net top-N (payment_tree only) ===
        "my_bilateral_net_q2_top_1", "my_bilateral_net_q2_top_2",
        "my_bilateral_net_q2_top_3", "my_bilateral_net_q2_top_4",
        "my_bilateral_net_q2_top_5",
        
        # === Cost rate fields ===
        "cost_overdraft_bps_per_tick", "cost_delay_per_tick_per_cent",
        "cost_collateral_bps_per_tick", "cost_split_friction",
        "cost_deadline_penalty", "cost_eod_penalty",
        
        # === Per-transaction cost fields (payment_tree only) ===
        "cost_delay_this_tx_one_tick", "cost_overdraft_this_amount_one_tick",
        
        # === Collateral fields ===
        "posted_collateral", "max_collateral_capacity",
        "remaining_collateral_capacity", "collateral_utilization",
        "required_collateral_for_usage", "excess_collateral",
        "overdraft_utilization", "overdraft_headroom",
        "collateral_haircut", "unsecured_cap", "allowed_overdraft_limit",
        
        # === Public signal fields ===
        "system_queue2_pressure_index",
        "lsm_run_rate_last_10_ticks",
        
        # === Throughput progress fields ===
        "my_throughput_fraction_today",
        "expected_throughput_fraction_by_now",
        "throughput_gap",
        
        # Note: State registers (bank_state_*) are allowed automatically
        # by the validator — they don't need to be listed here.
    ]
    
    all_parameters = [
        _ParameterSpec(
            name="initial_liquidity_fraction",
            param_type="float",
            min_value=0.0,
            max_value=1.0,
            description="Fraction of liquidity_pool to allocate at simulation start.",
        ),
        _ParameterSpec(
            name="split_threshold",
            param_type="float",
            min_value=0.0,
            max_value=1_000_000.0,
            description="Payment amount above which to consider splitting.",
        ),
        _ParameterSpec(
            name="min_split_amount",
            param_type="float",
            min_value=0.0,
            max_value=500_000.0,
            description="Minimum amount for a split piece.",
        ),
        _ParameterSpec(
            name="max_splits",
            param_type="float",
            min_value=1.0,
            max_value=10.0,
            description="Maximum number of splits per payment.",
        ),
        _ParameterSpec(
            name="urgency_threshold",
            param_type="float",
            min_value=0.0,
            max_value=20.0,
            description="Ticks-to-deadline below which payments become urgent.",
        ),
        _ParameterSpec(
            name="hold_threshold",
            param_type="float",
            min_value=0.0,
            max_value=1_000_000.0,
            description="Balance threshold below which to hold non-urgent payments.",
        ),
    ]
    
    payment_actions = ["Release", "Hold", "Split", "Delay"]
    bank_actions = ["NoAction", "PostCollateral", "WithdrawCollateral", "HoldCollateral"]
    
    allowed_actions = {
        "payment_tree": payment_actions,
        "bank_tree": bank_actions,
    }
    
    if lsm_enabled:
        allowed_actions["payment_tree"].extend(["ReleaseWithCredit"])
    
    return _ScenarioConstraints(
        allowed_parameters=all_parameters,
        allowed_fields=all_fields,
        allowed_actions=allowed_actions,
        lsm_enabled=lsm_enabled,
    )
