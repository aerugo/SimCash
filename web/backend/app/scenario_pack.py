"""Scenario pack — pre-built scenarios for the multi-day game."""
from __future__ import annotations
from typing import Any


def _build_agents(num_agents: int, liquidity_pool: int = 1_000_000,
                  rate_per_tick: float = 2.0, amount_mean: int = 10000,
                  amount_std: int = 5000, deadline_range: list[int] | None = None) -> list[dict]:
    deadline_range = deadline_range or [3, 8]
    ids = [f"BANK_{chr(65 + i)}" for i in range(num_agents)]
    agents = []
    for aid in ids:
        others = {o: 1.0 for o in ids if o != aid}
        agents.append({
            "id": aid,
            "opening_balance": 0,
            "unsecured_cap": 0,
            "liquidity_pool": liquidity_pool,
            "arrival_config": {
                "rate_per_tick": rate_per_tick,
                "amount_distribution": {"type": "LogNormal", "mean": amount_mean, "std_dev": amount_std},
                "counterparty_weights": others,
                "deadline_range": deadline_range,
            },
        })
    return agents


def generate_scenario(num_agents: int = 2, ticks_per_day: int = 12,
                      liquidity_pool: int = 1_000_000,
                      rate_per_tick: float = 2.0,
                      deadline_penalty: int = 50_000,
                      eod_penalty: int = 100_000,
                      liquidity_bps: int = 83,
                      delay_cost: float = 0.2,
                      rng_seed: int = 42,
                      deadline_range: list[int] | None = None) -> dict[str, Any]:
    agents = _build_agents(num_agents, liquidity_pool, rate_per_tick,
                           deadline_range=deadline_range)
    return {
        "simulation": {
            "ticks_per_day": ticks_per_day,
            "num_days": 1,
            "rng_seed": rng_seed,
        },
        "deferred_crediting": True,
        "deadline_cap_at_eod": True,
        "cost_rates": {
            "liquidity_cost_per_tick_bps": liquidity_bps,
            "delay_cost_per_tick_per_cent": delay_cost,
            "overdraft_bps_per_tick": 0,
            "collateral_cost_per_tick_bps": 0,
            "eod_penalty_per_transaction": eod_penalty,
            "deadline_penalty": deadline_penalty,
            "split_friction_cost": 0,
        },
        "lsm_config": {
            "enable_bilateral": False,
            "enable_cycles": False,
        },
        "agents": agents,
    }


SCENARIO_PACK: list[dict[str, Any]] = [
    {
        "id": "2bank_2tick",
        "name": "2 Banks, 2 Ticks",
        "description": "Deterministic-style. Quick Nash equilibrium test.",
        "num_agents": 2,
        "ticks_per_day": 2,
        "scenario": generate_scenario(num_agents=2, ticks_per_day=2, deadline_range=[1, 2]),
    },
    {
        "id": "2bank_12tick",
        "name": "2 Banks, 12 Ticks",
        "description": "Castro Experiment 2 baseline. Stochastic arrivals over 12 periods.",
        "num_agents": 2,
        "ticks_per_day": 12,
        "scenario": generate_scenario(num_agents=2, ticks_per_day=12),
    },
    {
        "id": "2bank_3tick",
        "name": "2 Banks, 3 Ticks",
        "description": "Joint liquidity & timing optimization. Compact scenario.",
        "num_agents": 2,
        "ticks_per_day": 3,
        "scenario": generate_scenario(num_agents=2, ticks_per_day=3, deadline_range=[1, 3]),
    },
    {
        "id": "3bank_6tick",
        "name": "3 Banks, 6 Ticks",
        "description": "Multilateral: three banks with symmetric payment flows.",
        "num_agents": 3,
        "ticks_per_day": 6,
        "scenario": generate_scenario(num_agents=3, ticks_per_day=6),
    },
    {
        "id": "4bank_8tick",
        "name": "4 Banks, 8 Ticks",
        "description": "Complex network with four interconnected banks.",
        "num_agents": 4,
        "ticks_per_day": 8,
        "scenario": generate_scenario(num_agents=4, ticks_per_day=8),
    },
    {
        "id": "2bank_stress",
        "name": "2 Banks, High Stress",
        "description": "5x penalties — punishes delays harshly. Tests aggressive optimization.",
        "num_agents": 2,
        "ticks_per_day": 12,
        "scenario": generate_scenario(num_agents=2, ticks_per_day=12,
                                      deadline_penalty=250_000, eod_penalty=500_000),
    },
    {
        "id": "5bank_12tick",
        "name": "5 Banks, 12 Ticks",
        "description": "Full network: 5 banks, 12 periods. Maximum complexity.",
        "num_agents": 5,
        "ticks_per_day": 12,
        "scenario": generate_scenario(num_agents=5, ticks_per_day=12),
    },
]


def get_scenario_pack() -> list[dict[str, Any]]:
    """Return scenario pack metadata (without full scenario dicts)."""
    return [
        {
            "id": s["id"],
            "name": s["name"],
            "description": s["description"],
            "num_agents": s["num_agents"],
            "ticks_per_day": s["ticks_per_day"],
        }
        for s in SCENARIO_PACK
    ]


def get_scenario_by_id(scenario_id: str) -> dict[str, Any] | None:
    for s in SCENARIO_PACK:
        if s["id"] == scenario_id:
            return s["scenario"]
    return None
