"""Constraint presets for LLM policy optimization.

Presets control WHAT the LLM is allowed to optimize:
- Simple: Just initial_liquidity_fraction (current behavior)
- Standard: Fraction + Release/Hold/Split with basic conditions
- Full: All actions, all context fields, full decision tree optimization

Field names are organized into semantic GROUPS. The "full" preset auto-infers
which groups to include based on scenario config (LSM, collateral, agents, etc.).

IMPORTANT: Field names MUST match the actual Rust engine context fields exactly.
See simulator/src/policy/tree/context.rs for:
  - EvalContext::build() — transaction-level fields (payment_tree)
  - EvalContext::bank_level() — bank-level fields (bank_tree, collateral trees)
See simulator/src/policy/tree/validation.rs:
  - is_bank_level_field() — allowlist for bank_tree field validation
"""
from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
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


# ─── Field Groups ────────────────────────────────────────────────────────────
# Each group maps to a set of actual Rust engine context fields.
# Groups are the unit of inclusion/exclusion — users toggle groups, not fields.

FIELD_GROUPS: dict[str, list[str]] = {
    # Always included
    "core": [
        # Agent basics
        "balance", "available_liquidity", "effective_liquidity",
        "credit_limit", "credit_used", "credit_headroom",
        "is_using_credit", "is_overdraft_capped",
        "liquidity_buffer", "liquidity_pressure",
        # Transaction basics (payment_tree only, harmless in bank_tree — validator handles it)
        "amount", "remaining_amount", "ticks_to_deadline",
        "priority", "is_eod_rush",
    ],

    "queue": [
        # Queue 1 (agent's outgoing)
        "outgoing_queue_size", "incoming_expected_count",
        "queue1_total_value", "queue1_liquidity_gap", "headroom",
        # Queue 2 (RTGS system)
        "queue2_size", "queue2_count_for_agent",
        "queue2_nearest_deadline", "ticks_to_nearest_queue2_deadline",
        "rtgs_queue_size", "rtgs_queue_value",
    ],

    "timing": [
        "current_tick", "total_agents",
        "system_tick_in_day", "system_ticks_per_day", "system_current_day",
        "ticks_remaining_in_day", "day_progress_fraction",
    ],

    "cost": [
        "cost_overdraft_bps_per_tick", "cost_delay_per_tick_per_cent",
        "cost_collateral_bps_per_tick", "cost_split_friction",
        "cost_deadline_penalty", "cost_eod_penalty",
        # Per-transaction cost calculations (payment_tree only)
        "cost_delay_this_tx_one_tick", "cost_overdraft_this_amount_one_tick",
    ],

    "throughput": [
        "my_throughput_fraction_today",
        "expected_throughput_fraction_by_now",
        "throughput_gap",
        "system_queue2_pressure_index",
    ],

    # Conditionally included based on scenario
    "transaction_detail": [
        "settled_amount", "arrival_tick", "deadline_tick",
        "is_split", "is_past_deadline", "is_overdue", "is_in_queue2",
        "overdue_duration", "queue_age",
    ],

    "collateral": [
        "posted_collateral", "max_collateral_capacity",
        "remaining_collateral_capacity", "collateral_utilization",
        "required_collateral_for_usage", "excess_collateral",
        "overdraft_utilization", "overdraft_headroom",
        "collateral_haircut", "unsecured_cap", "allowed_overdraft_limit",
    ],

    "lsm": [
        "my_bilateral_net_q2",
        "my_q2_out_value_to_counterparty", "my_q2_in_value_from_counterparty",
        "lsm_run_rate_last_10_ticks",
    ],

    "counterparty": [
        "tx_counterparty_id", "tx_is_top_counterparty",
        "my_bilateral_net_q2_top_1", "my_bilateral_net_q2_top_2",
        "my_bilateral_net_q2_top_3", "my_bilateral_net_q2_top_4",
        "my_bilateral_net_q2_top_5",
    ],

    # Note: State registers (bank_state_*) are dynamically named and
    # auto-allowed by the Rust validator. They don't need field entries.
    # But we include the group flag so the prompt can mention them.
}

# Groups that are always included regardless of scenario
ALWAYS_GROUPS = {"core", "queue", "timing", "cost", "throughput"}


# ─── Scenario Feature Detection ─────────────────────────────────────────────

@dataclass
class ScenarioFeatures:
    """Features detected from a scenario config dict."""
    lsm_enabled: bool = False
    collateral_configured: bool = False
    num_agents: int = 2
    multi_day: bool = False
    has_events: bool = False
    has_credit: bool = False

    @classmethod
    def from_config(cls, config: dict) -> "ScenarioFeatures":
        """Detect features from a raw scenario YAML dict."""
        features = cls()
        if not isinstance(config, dict):
            return features

        # LSM detection
        lsm = config.get("lsm_config", {})
        if isinstance(lsm, dict):
            features.lsm_enabled = bool(
                lsm.get("enable_bilateral")
                or lsm.get("enable_cycles")
            )
        # Legacy flags
        if config.get("enable_bilateral_lsm") or config.get("enable_cycle_lsm"):
            features.lsm_enabled = True

        # Agent count
        agents = config.get("agents", [])
        features.num_agents = len(agents) if isinstance(agents, list) else 2

        # Collateral detection: any agent has max_collateral_capacity > 0
        for agent in (agents if isinstance(agents, list) else []):
            if isinstance(agent, dict):
                if agent.get("max_collateral_capacity", 0) > 0:
                    features.collateral_configured = True
                if agent.get("unsecured_cap", 0) > 0:
                    features.has_credit = True

        # Multi-day detection
        sim = config.get("simulation", {})
        if isinstance(sim, dict):
            features.multi_day = (sim.get("num_days", 1) or 1) > 1
        # Also check top-level
        if (config.get("num_days", 1) or 1) > 1:
            features.multi_day = True

        # Events detection
        events = config.get("scenario_events", config.get("events", []))
        if isinstance(events, list) and len(events) > 0:
            features.has_events = True

        return features


def _select_groups(
    features: ScenarioFeatures,
    preset: str = "full",
    include_groups: list[str] | None = None,
    exclude_groups: list[str] | None = None,
) -> set[str]:
    """Select which field groups to include based on features and overrides.
    
    Args:
        features: Detected scenario features
        preset: Base preset ("simple", "standard", "full")
        include_groups: Extra groups to force-include
        exclude_groups: Groups to force-exclude
    
    Returns:
        Set of group names to include
    """
    if preset == "simple":
        return {"core"}
    
    if preset == "standard":
        return {"core", "queue", "timing"}

    # Full preset: start with always-on groups
    groups = set(ALWAYS_GROUPS)

    # Always include transaction detail in full mode
    groups.add("transaction_detail")

    # Conditional groups
    if features.collateral_configured or features.has_credit:
        groups.add("collateral")

    if features.lsm_enabled:
        groups.add("lsm")

    if features.num_agents >= 3:
        groups.add("counterparty")

    # Apply overrides
    if include_groups:
        groups.update(include_groups)
    if exclude_groups:
        groups -= set(exclude_groups)

    return groups


def _groups_to_fields(groups: set[str]) -> list[str]:
    """Flatten a set of group names into a deduplicated field list."""
    fields = []
    seen = set()
    for group in sorted(groups):  # Sort for deterministic output
        for field in FIELD_GROUPS.get(group, []):
            if field not in seen:
                fields.append(field)
                seen.add(field)
    return fields


# ─── Preset Metadata ─────────────────────────────────────────────────────────

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
        "description": "LLM has access to all actions and context fields relevant to your scenario. Fields are auto-selected based on scenario features (LSM, collateral, agent count).",
        "complexity": "full",
    },
]


def get_preset_metadata() -> list[dict[str, str]]:
    """Return metadata for all presets (no heavy imports needed)."""
    return PRESET_METADATA


def get_field_groups() -> dict[str, list[str]]:
    """Return all field groups and their fields (for UI display)."""
    return dict(FIELD_GROUPS)


def detect_features(scenario_config: dict | None = None) -> dict:
    """Detect scenario features and return auto-selected groups.
    
    Returns a dict suitable for the frontend to display group toggles:
    {
        "features": {"lsm_enabled": true, ...},
        "auto_groups": ["core", "queue", "timing", "cost", "throughput", "lsm"],
        "available_groups": ["core", "queue", ..., "counterparty"],
        "field_count": 42
    }
    """
    features = ScenarioFeatures.from_config(scenario_config or {})
    auto_groups = _select_groups(features)
    fields = _groups_to_fields(auto_groups)
    
    return {
        "features": {
            "lsm_enabled": features.lsm_enabled,
            "collateral_configured": features.collateral_configured,
            "num_agents": features.num_agents,
            "multi_day": features.multi_day,
            "has_events": features.has_events,
            "has_credit": features.has_credit,
        },
        "auto_groups": sorted(auto_groups),
        "available_groups": sorted(FIELD_GROUPS.keys()),
        "field_count": len(fields),
    }


# ─── Constraint Builders ─────────────────────────────────────────────────────

def build_constraints(
    preset_id: str = "simple",
    scenario_config: dict | None = None,
    include_groups: list[str] | None = None,
    exclude_groups: list[str] | None = None,
) -> Any:
    """Build ScenarioConstraints for the given preset.
    
    Args:
        preset_id: One of "simple", "standard", "full"
        scenario_config: Raw scenario YAML dict, used to auto-detect features
        include_groups: Extra field groups to force-include (full preset only)
        exclude_groups: Field groups to force-exclude (full preset only)
    
    Returns:
        ScenarioConstraints instance
    """
    _ensure_imports()
    
    scenario_config = scenario_config or {}
    features = ScenarioFeatures.from_config(scenario_config)
    
    if preset_id == "simple":
        return _build_simple(features)
    elif preset_id == "standard":
        return _build_standard(features)
    elif preset_id == "full":
        return _build_full(features, include_groups, exclude_groups)
    else:
        raise ValueError(f"Unknown constraint preset: {preset_id}")


def _build_simple(features: ScenarioFeatures) -> Any:
    """Simple: just fraction + Release/Hold."""
    groups = _select_groups(features, "simple")
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
        allowed_fields=_groups_to_fields(groups),
        allowed_actions={"payment_tree": ["Release", "Hold"], "bank_tree": ["NoAction"]},
        lsm_enabled=features.lsm_enabled,
    )


def _build_standard(features: ScenarioFeatures) -> Any:
    """Standard: fraction + Release/Hold/Split + conditions on balance/timing/queue."""
    groups = _select_groups(features, "standard")
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
        allowed_fields=_groups_to_fields(groups),
        allowed_actions={
            "payment_tree": ["Release", "Hold", "Split"],
            "bank_tree": ["NoAction"],
        },
        lsm_enabled=features.lsm_enabled,
    )


def _build_full(
    features: ScenarioFeatures,
    include_groups: list[str] | None = None,
    exclude_groups: list[str] | None = None,
) -> Any:
    """Full: all actions, scenario-aware fields, all trees."""
    groups = _select_groups(features, "full", include_groups, exclude_groups)
    
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
    bank_actions = ["NoAction"]
    
    # Only offer collateral actions if collateral is configured
    if "collateral" in groups:
        bank_actions.extend(["PostCollateral", "WithdrawCollateral", "HoldCollateral"])
    
    allowed_actions = {
        "payment_tree": payment_actions,
        "bank_tree": bank_actions,
    }
    
    if features.lsm_enabled:
        allowed_actions["payment_tree"].append("ReleaseWithCredit")
    
    return _ScenarioConstraints(
        allowed_parameters=all_parameters,
        allowed_fields=_groups_to_fields(groups),
        allowed_actions=allowed_actions,
        lsm_enabled=features.lsm_enabled,
    )
