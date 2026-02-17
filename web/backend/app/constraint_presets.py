"""Constraint presets for LLM policy optimization.

Presets control WHAT the LLM is allowed to optimize:
- Simple: Just initial_liquidity_fraction (current behavior)
- Standard: Fraction + Release/Hold/Split with basic conditions
- Full: All actions, all context fields, full decision tree optimization
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
        "description": "LLM has access to all 16 actions, 140+ context fields, state registers, and all 4 tree types. Maximum strategy space — slower convergence but richer policies.",
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
            # Balance & liquidity
            "balance", "available_liquidity", "liquidity_pool",
            # Payment attributes
            "amount", "remaining_amount", "ticks_to_deadline", "is_eod_rush",
            # Queue & system state
            "queue_size", "queue_total_amount", "system_tick_in_day",
            "total_ticks_in_day", "ticks_remaining_in_day",
            # Cost awareness
            "delay_cost_rate", "overdraft_cost_rate",
        ],
        allowed_actions={
            "payment_tree": ["Release", "Hold", "Split"],
            "bank_tree": ["NoAction"],
        },
        lsm_enabled=lsm_enabled,
    )


def _build_full(lsm_enabled: bool) -> Any:
    """Full: all actions, all fields, all trees."""
    all_fields = [
        # Balance & liquidity
        "balance", "available_liquidity", "liquidity_pool",
        "opening_balance", "net_position",
        # Payment attributes
        "amount", "remaining_amount", "ticks_to_deadline",
        "is_eod_rush", "is_deadline_payment", "priority",
        "payment_count_today", "payment_value_today",
        # Queue state
        "queue_size", "queue_total_amount",
        "queue_urgent_count", "queue_urgent_amount",
        # System timing
        "system_tick_in_day", "total_ticks_in_day",
        "ticks_remaining_in_day", "day_progress",
        # Counterparty
        "counterparty_balance", "counterparty_queue_size",
        "bilateral_net_position",
        # Cost rates
        "delay_cost_rate", "overdraft_cost_rate",
        "deadline_penalty_rate", "eod_penalty_rate",
        "liquidity_cost_rate",
        # Accumulated costs
        "cumulative_delay_cost", "cumulative_overdraft_cost",
        "cumulative_penalty_cost", "total_cost_so_far",
        # LSM fields (if enabled)
        "bilateral_offset_available", "cycle_offset_available",
        "lsm_queue_size",
        # State registers
        "register_0", "register_1", "register_2", "register_3",
        "register_4", "register_5", "register_6", "register_7",
        "register_8", "register_9",
        # Budget tracking
        "budget_remaining", "budget_utilization",
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
