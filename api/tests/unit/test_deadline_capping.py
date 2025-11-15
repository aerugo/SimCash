"""Unit test for Issue #6 fix: Deadlines beyond episode end.

Tests that generated transaction deadlines are capped at the episode end tick,
preventing impossible deadlines.
"""

import pytest
from payment_simulator._core import Orchestrator


def test_deadlines_capped_at_episode_end():
    """
    GIVEN a simulation with episode ending at a specific tick
    WHEN transactions are generated near the end
    THEN all deadlines must be <= episode_end_tick

    Issue #6: Transactions at tick 250 were getting deadlines at 309-328,
    but episode ends at 299.
    """
    config = {
        "rng_seed": 42,
        "ticks_per_day": 100,
        "num_days": 3,  # Episode ends at tick 299
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1000000,
                "unsecured_cap": 0,
                "collateral_pool": 0,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 1000000,
                "unsecured_cap": 0,
                "collateral_pool": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        "arrival_configs": [
            {
                "agent_id": "BANK_A",
                "rate_per_tick": 5.0,
                "amount_distribution": {
                    "type": "Normal",
                    "mean": 10000,
                    "std_dev": 1000,
                },
                "counterparty_weights": {"BANK_B": 1.0},
                "time_window_pattern": {"type": "Uniform"},
            },
        ],
        "cost_model": {
            "overdraft_bps_per_tick": 0.8,
            "delay_per_tick_bps": 0.01,
            "deadline_penalty_bps": 5.0,
            "eod_penalty": 100000,
            "collateral_cost_per_tick_bps": 0.0005,
            "overdue_delay_multiplier": 5,
        },
        "settlement_config": {
            "lsm_enabled": False,
        },
    }

    orch = Orchestrator.new(config)

    episode_end_tick = 3 * 100  # 3 days × 100 ticks/day = 299 (ticks 0-299)

    # Run simulation near the end of the episode
    for tick in range(1, 290):  # Run up to tick 289
        orch.tick()

    # Now check tick 289 arrivals
    events_289 = orch.get_tick_events(289)
    arrival_events = [e for e in events_289 if e.get("event_type") == "arrival"]

    if not arrival_events:
        pytest.skip("No arrivals at tick 289, adjust config to ensure arrivals near episode end")

    # ASSERTION: All deadlines must be <= episode_end_tick
    for arrival in arrival_events:
        deadline = arrival["deadline"]
        assert deadline <= episode_end_tick, (
            f"Transaction {arrival['tx_id']} at tick {arrival['tick']} "
            f"has deadline {deadline}, which exceeds episode end {episode_end_tick}"
        )


def test_deadline_offset_respects_episode_boundary():
    """
    GIVEN transactions generated with large deadline offsets
    WHEN those offsets would push deadline past episode end
    THEN deadlines are capped to episode_end_tick, not raw arrival_tick + offset
    """
    config = {
        "rng_seed": 12345,
        "ticks_per_day": 20,
        "num_days": 2,  # Episode ends at tick 39 (ticks 0-39)
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1000000,
                "unsecured_cap": 0,
                "collateral_pool": 0,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 3.0,
                    "amount_distribution": {
                        "type": "Normal",
                        "mean": 10000,
                        "std_dev": 500,
                    },
                    "counterparty_weights": {"BANK_B": 1.0},
                    "deadline_range": [5, 30],  # Add deadline range for arrival generation
                    "priority": 5,
                    "divisible": False,
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 1000000,
                "unsecured_cap": 0,
                "collateral_pool": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        "cost_model": {
            "overdraft_bps_per_tick": 0.8,
            "delay_per_tick_bps": 0.01,
            "deadline_penalty_bps": 5.0,
            "eod_penalty": 100000,
            "collateral_cost_per_tick_bps": 0.0005,
            "overdue_delay_multiplier": 5,
        },
        "settlement_config": {
            "lsm_enabled": False,
        },
    }

    orch = Orchestrator.new(config)

    episode_end_tick = 2 * 20  # 2 days × 20 ticks/day = 39

    # Run entire episode
    for tick in range(episode_end_tick):
        orch.tick()

    # Get all transactions created during the episode
    all_transactions = []
    for day in range(2):  # 2 days
        day_txs = orch.get_transactions_for_day(day)
        all_transactions.extend(day_txs)

    assert len(all_transactions) > 0, "Should have generated transactions"

    # ASSERTION: NONE of the deadlines should exceed episode_end_tick
    invalid_deadlines = [
        (tx["arrival_tick"], tx["deadline_tick"])
        for tx in all_transactions
        if tx["deadline_tick"] > episode_end_tick
    ]

    assert len(invalid_deadlines) == 0, (
        f"Found {len(invalid_deadlines)} transactions with deadlines beyond episode end ({episode_end_tick}). "
        f"Examples: {invalid_deadlines[:5]}"
    )


def test_deadlines_reasonable_within_episode():
    """
    GIVEN a simulation with normal episode length
    WHEN transactions are generated early in the episode
    THEN deadlines should be reasonable (not all capped at episode end)

    This test ensures the capping logic doesn't break normal deadline generation.
    """
    config = {
        "rng_seed": 999,
        "ticks_per_day": 100,
        "num_days": 3,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1000000,
                "unsecured_cap": 0,
                "collateral_pool": 0,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 5.0,
                    "amount_distribution": {
                        "type": "Normal",
                        "mean": 10000,
                        "std_dev": 1000,
                    },
                    "counterparty_weights": {"BANK_B": 1.0},
                    "deadline_range": [10, 50],  # Add deadline range for arrival generation
                    "priority": 5,
                    "divisible": False,
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 1000000,
                "unsecured_cap": 0,
                "collateral_pool": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        "cost_model": {
            "overdraft_bps_per_tick": 0.8,
            "delay_per_tick_bps": 0.01,
            "deadline_penalty_bps": 5.0,
            "eod_penalty": 100000,
            "collateral_cost_per_tick_bps": 0.0005,
            "overdue_delay_multiplier": 5,
        },
        "settlement_config": {
            "lsm_enabled": False,
        },
    }

    orch = Orchestrator.new(config)

    # Run just first 50 ticks (early in episode)
    for tick in range(50):
        orch.tick()

    # Get all transactions from day 0
    all_transactions = orch.get_transactions_for_day(0)

    assert len(all_transactions) > 0, "Should have generated transactions"

    # Check that NOT ALL deadlines are at episode_end_tick
    episode_end = 299  # 3 days * 100 ticks/day - 1
    capped_count = sum(1 for tx in all_transactions if tx["deadline_tick"] == episode_end)

    # Most deadlines should NOT be capped when generated early in the episode
    capped_ratio = capped_count / len(all_transactions)
    assert capped_ratio < 0.1, (
        f"Too many deadlines capped at episode end: {capped_count}/{len(all_transactions)} = {capped_ratio:.1%}. "
        f"This suggests deadline generation is broken, not just capping."
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
