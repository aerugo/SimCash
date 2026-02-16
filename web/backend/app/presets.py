"""Scenario presets based on the research paper experiments.

Note: scenario_events use the flat FFI format expected by the Rust orchestrator:
  {"type": "...", "schedule": "OneTime", "tick": N, ...}
NOT the nested YAML format from config files.
"""

from __future__ import annotations
from typing import Any


def _tx(from_a: str, to_a: str, amount: int, priority: int, deadline: int, tick: int) -> dict[str, Any]:
    """Helper to create a CustomTransactionArrival in FFI format."""
    return {
        "type": "CustomTransactionArrival",
        "from_agent": from_a,
        "to_agent": to_a,
        "amount": amount,
        "priority": priority,
        "deadline": deadline,
        "schedule": "OneTime",
        "tick": tick,
    }


PRESETS: list[dict[str, Any]] = [
    {
        "id": "exp1_2period",
        "name": "2-Period Deterministic (Castro Exp 1)",
        "description": "Simple 2-tick Nash equilibrium game. 2 banks, deterministic payments. Tests fundamental liquidity-delay tradeoff.",
        "scenario": {
            "ticks_per_day": 2,
            "num_days": 1,
            "rng_seed": 42,
            "deferred_crediting": True,
            "deadline_cap_at_eod": True,
            "cost_rates": {
                "liquidity_cost_per_tick_bps": 500,
                "delay_cost_per_tick_per_cent": 0.2,
                "overdraft_bps_per_tick": 0,
                "collateral_cost_per_tick_bps": 0,
                "eod_penalty_per_transaction": 100000,
                "deadline_penalty": 50000,
                "split_friction_cost": 0,
            },
            "lsm_config": {"enable_bilateral": False, "enable_cycles": False},
            "agents": [
                {"id": "BANK_A", "opening_balance": 0, "unsecured_cap": 0, "liquidity_pool": 100000},
                {"id": "BANK_B", "opening_balance": 0, "unsecured_cap": 0, "liquidity_pool": 100000},
            ],
            "scenario_events": [
                _tx("BANK_A", "BANK_B", 15000, 5, 2, 1),
                _tx("BANK_B", "BANK_A", 15000, 5, 2, 0),
                _tx("BANK_B", "BANK_A", 5000, 5, 2, 1),
            ],
        },
        "llm_prompt": """This scenario tests a fundamental tradeoff in payment systems:
- Allocating liquidity from the pool allows you to settle payments
- But allocated liquidity has an opportunity cost

The KEY DECISION: What fraction of the liquidity pool should be allocated at the START of the day?
Focus on the initial_liquidity_fraction parameter (0.0 to 1.0).
With a hard liquidity constraint (no overdraft), you must have sufficient balance to settle each payment.""",
    },
    {
        "id": "exp2_12period",
        "name": "12-Period Stochastic (LVTS-Style)",
        "description": "Realistic scenario with Poisson arrivals and LogNormal amounts. 12 ticks, 2 banks with stochastic payment flows.",
        "scenario": {
            "ticks_per_day": 12,
            "num_days": 1,
            "rng_seed": 42,
            "deferred_crediting": True,
            "deadline_cap_at_eod": True,
            "cost_rates": {
                "liquidity_cost_per_tick_bps": 83,
                "delay_cost_per_tick_per_cent": 0.2,
                "overdraft_bps_per_tick": 0,
                "collateral_cost_per_tick_bps": 0,
                "eod_penalty_per_transaction": 100000,
                "deadline_penalty": 50000,
                "split_friction_cost": 0,
            },
            "lsm_config": {"enable_bilateral": False, "enable_cycles": False},
            "agents": [
                {
                    "id": "BANK_A", "opening_balance": 0, "unsecured_cap": 0, "liquidity_pool": 1000000,
                    "arrival_config": {
                        "rate_per_tick": 2.0,
                        "amount_distribution": {"type": "LogNormal", "mean": 10000, "std_dev": 5000},
                        "counterparty_weights": {"BANK_B": 1.0},
                        "deadline_range": [3, 8],
                    },
                },
                {
                    "id": "BANK_B", "opening_balance": 0, "unsecured_cap": 0, "liquidity_pool": 1000000,
                    "arrival_config": {
                        "rate_per_tick": 2.0,
                        "amount_distribution": {"type": "LogNormal", "mean": 10000, "std_dev": 5000},
                        "counterparty_weights": {"BANK_A": 1.0},
                        "deadline_range": [3, 8],
                    },
                },
            ],
        },
        "llm_prompt": """This scenario tests liquidity optimization with stochastic payment flows.
Banks receive ~2 payments per tick with LogNormal amounts (mean $100, std $50).
Each bank has a $10,000 liquidity pool.

The KEY DECISION: What fraction of the liquidity pool to allocate at start?
Too much = high opportunity cost. Too little = payments fail and incur penalties.
Incoming payments from counterparty provide recyclable liquidity.""",
    },
    {
        "id": "exp3_3period",
        "name": "3-Period Joint Optimization",
        "description": "Symmetric 3-tick scenario testing joint liquidity allocation AND payment timing decisions.",
        "scenario": {
            "ticks_per_day": 3,
            "num_days": 1,
            "rng_seed": 42,
            "deferred_crediting": True,
            "deadline_cap_at_eod": True,
            "cost_rates": {
                "liquidity_cost_per_tick_bps": 333,
                "delay_cost_per_tick_per_cent": 0.2,
                "overdraft_bps_per_tick": 0,
                "collateral_cost_per_tick_bps": 0,
                "eod_penalty_per_transaction": 100000,
                "deadline_penalty": 50000,
                "split_friction_cost": 0,
            },
            "lsm_config": {"enable_bilateral": False, "enable_cycles": False},
            "agents": [
                {"id": "BANK_A", "opening_balance": 0, "unsecured_cap": 0, "liquidity_pool": 100000},
                {"id": "BANK_B", "opening_balance": 0, "unsecured_cap": 0, "liquidity_pool": 100000},
            ],
            "scenario_events": [
                _tx("BANK_A", "BANK_B", 20000, 5, 2, 0),
                _tx("BANK_B", "BANK_A", 20000, 5, 2, 0),
                _tx("BANK_A", "BANK_B", 20000, 5, 2, 1),
                _tx("BANK_B", "BANK_A", 20000, 5, 2, 1),
            ],
        },
        "llm_prompt": """This scenario tests JOINT optimization of liquidity AND timing.
Symmetric setup: both banks send $200 at tick 0 and tick 1. No payments at tick 2.

Two decisions to optimize:
1. initial_liquidity_fraction: How much of the $1,000 pool to allocate
2. Payment timing: Release immediately or Hold (wait for incoming liquidity)

With a hard liquidity constraint, you need balance to cover payments.
Incoming payments from counterparty provide recyclable liquidity.
Liquidity is cheaper than delay (r_c=0.1 < r_d=0.2).""",
    },
]


def get_preset_config(preset_id: str) -> dict[str, Any] | None:
    """Get a preset by ID, returning full config."""
    for p in PRESETS:
        if p["id"] == preset_id:
            return p
    return None
