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
        "description": "Can AI agents find a Nash equilibrium in the simplest possible setting? With only 2 periods and 2 banks, this minimal scenario isolates the core strategic tension between paying early (costly liquidity) and paying late (deadline risk).",
        "num_agents": 2,
        "ticks_per_day": 2,
        "scenario": generate_scenario(num_agents=2, ticks_per_day=2, deadline_range=[1, 2],
                                      liquidity_bps=500),  # r_c=0.1 over 2 ticks
    },
    {
        "id": "2bank_12tick",
        "name": "2 Banks, 12 Ticks",
        "description": "How do two banks optimise the liquidity-delay trade-off over a realistic trading day? Based on Castro (2024) Experiment 2, this scenario tests whether AI agents discover the same intraday liquidity patterns observed in real RTGS systems — early caution followed by end-of-day urgency.",
        "num_agents": 2,
        "ticks_per_day": 12,
        "scenario": generate_scenario(num_agents=2, ticks_per_day=12),
    },
    {
        "id": "2bank_3tick",
        "name": "2 Banks, 3 Ticks",
        "description": "When do agents learn to split liquidity across periods versus concentrating payments? This compact 3-tick scenario creates a tight decision space where the optimal strategy requires balancing immediate release against holding reserves for later, higher-urgency payments.",
        "num_agents": 2,
        "ticks_per_day": 3,
        "scenario": generate_scenario(num_agents=2, ticks_per_day=3, deadline_range=[1, 3],
                                      liquidity_bps=333),  # r_c=0.1 over 3 ticks
    },
    {
        "id": "3bank_6tick",
        "name": "3 Banks, 6 Ticks",
        "description": "How does adding a third bank change strategic dynamics? With trilateral payment flows, agents can no longer rely on bilateral reciprocity alone. Tests whether AI discovers free-rider incentives and multilateral coordination patterns in a small network.",
        "num_agents": 3,
        "ticks_per_day": 6,
        "scenario": generate_scenario(num_agents=3, ticks_per_day=6),
    },
    {
        "id": "4bank_8tick",
        "name": "4 Banks, 8 Ticks",
        "description": "Does coordination break down as the network grows? Four interconnected banks create complex payment chains where one agent's delay cascades through the system. Tests whether AI can learn network-aware strategies rather than optimising in isolation.",
        "num_agents": 4,
        "ticks_per_day": 8,
        "scenario": generate_scenario(num_agents=4, ticks_per_day=8),
    },
    {
        "id": "2bank_stress",
        "name": "2 Banks, High Stress",
        "description": "What happens when penalty rates are 5× normal? With deadline penalties at $2,500 and end-of-day penalties at $5,000, this scenario tests whether AI agents learn to be more conservative under extreme cost pressure — or whether they over-correct and waste liquidity.",
        "num_agents": 2,
        "ticks_per_day": 12,
        "scenario": generate_scenario(num_agents=2, ticks_per_day=12,
                                      deadline_penalty=250_000, eod_penalty=500_000),
    },
    {
        "id": "5bank_12tick",
        "name": "5 Banks, 12 Ticks",
        "description": "Can AI scale to a full 5-bank network over a complete trading day? This maximum-complexity scenario tests whether optimisation strategies that work for 2-3 banks still hold when payment flows are distributed across a larger, more interconnected system.",
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
