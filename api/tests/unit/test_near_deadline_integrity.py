"""Unit test for Issue #12 fix: Near-deadline list integrity.

Tests that near-deadline warnings only show transactions that are ACTUALLY
in Queue-1 or Queue-2 at the current tick, not phantom transactions.
"""

import pytest
from payment_simulator.cli.execution.state_provider import DatabaseStateProvider


def test_near_deadline_only_shows_queued_transactions():
    """
    GIVEN transactions in tx_cache with near deadlines
    AND only some are in Queue-1/Queue-2 at current tick
    WHEN get_transactions_near_deadline() is called
    THEN only queued transactions should be returned

    Issue #12: Near-deadline scanner was showing ALL transactions with near
    deadlines from global cache, including those already submitted to Queue-2
    or settled, causing phantom transactions in the display.
    """
    # Mock data
    tx_cache = {
        "tx_001": {
            "tx_id": "tx_001",
            "sender_id": "BANK_A",
            "receiver_id": "BANK_B",
            "amount": 100000,
            "amount_settled": 0,
            "deadline_tick": 252,  # Within 2 ticks of current (250)
            "status": "pending",
            "settlement_tick": None,
        },
        "tx_002": {
            "tx_id": "tx_002",
            "sender_id": "BANK_A",
            "receiver_id": "BANK_B",
            "amount": 200000,
            "amount_settled": 0,
            "deadline_tick": 251,  # Within 2 ticks
            "status": "pending",
            "settlement_tick": None,
        },
        "tx_003": {
            "tx_id": "tx_003",
            "sender_id": "BANK_C",
            "receiver_id": "BANK_A",
            "amount": 300000,
            "amount_settled": 0,
            "deadline_tick": 252,  # Within 2 ticks
            "status": "pending",
            "settlement_tick": None,
        },
        "tx_004": {
            "tx_id": "tx_004",
            "sender_id": "BANK_A",
            "receiver_id": "BANK_B",
            "amount": 400000,
            "amount_settled": 400000,  # Fully settled at tick 270
            "deadline_tick": 251,  # Near deadline but SETTLED
            "status": "settled",
            "settlement_tick": 270,  # Settled in the future (beyond current tick 250)
        },
    }

    queue_snapshots = {
        "BANK_A": {
            "queue1": ["tx_001"],  # Only tx_001 in Queue-1
            "rtgs": ["tx_002"],     # tx_002 in Queue-2 (RTGS)
        },
        "BANK_C": {
            "queue1": [],           # tx_003 NOT in Queue-1 (already submitted)
            "rtgs": [],             # tx_003 NOT in Queue-2 either (settled elsewhere)
        },
    }

    agent_states = {
        "BANK_A": {"balance": 50000},
        "BANK_C": {"balance": 75000},
    }

    provider = DatabaseStateProvider(
        conn=None,  # Not needed for this test
        simulation_id="test_sim",
        tick=250,
        tx_cache=tx_cache,
        agent_states=agent_states,
        queue_snapshots=queue_snapshots,
    )

    # Act
    near_deadline = provider.get_transactions_near_deadline(within_ticks=2)

    # Assert: Should only include tx_001 and tx_002
    # tx_001: In Queue-1, deadline 252 (within 2 ticks)
    # tx_002: In Queue-2, deadline 251 (within 2 ticks)
    # tx_003: NOT in any queue -> should NOT appear
    # tx_004: Settled -> should NOT appear

    tx_ids = {tx["tx_id"] for tx in near_deadline}
    assert tx_ids == {"tx_001", "tx_002"}, (
        f"Near-deadline should only show queued transactions. "
        f"Expected: {{'tx_001', 'tx_002'}}, Got: {tx_ids}"
    )


def test_near_deadline_respects_settlement_timing():
    """
    GIVEN a transaction with settlement_tick > current_tick
    WHEN near deadline check runs at current tick
    THEN transaction should show as NOT settled (remaining_amount > 0)

    This is the same temporal consistency issue as Issue #3.
    """
    tx_cache = {
        "tx_future_settle": {
            "tx_id": "tx_future_settle",
            "sender_id": "BANK_A",
            "receiver_id": "BANK_B",
            "amount": 100000,
            "amount_settled": 100000,  # Will be settled at tick 270
            "deadline_tick": 252,
            "status": "pending",  # Not marked settled yet
            "settlement_tick": 270,  # Settlement happens AFTER current tick 250
        },
    }

    queue_snapshots = {
        "BANK_A": {
            "queue1": ["tx_future_settle"],  # Still in Queue-1 at tick 250
            "rtgs": [],
        },
    }

    agent_states = {"BANK_A": {"balance": 50000}}

    provider = DatabaseStateProvider(
        conn=None,
        simulation_id="test_sim",
        tick=250,  # Current tick BEFORE settlement
        tx_cache=tx_cache,
        agent_states=agent_states,
        queue_snapshots=queue_snapshots,
    )

    near_deadline = provider.get_transactions_near_deadline(within_ticks=2)

    # Should include tx because it's NOT settled at tick 250
    # (even though amount_settled=100000 in cache, settlement_tick=270 > 250)
    assert len(near_deadline) == 1, "Transaction should appear as unsettled at tick 250"
    assert near_deadline[0]["tx_id"] == "tx_future_settle"
    assert near_deadline[0]["remaining_amount"] == 100000, "Full amount should remain at tick 250"


def test_near_deadline_excludes_settled_before_current_tick():
    """
    GIVEN a transaction settled BEFORE current tick
    WHEN near deadline check runs
    THEN transaction should NOT appear (correctly filtered out)
    """
    tx_cache = {
        "tx_already_settled": {
            "tx_id": "tx_already_settled",
            "sender_id": "BANK_A",
            "receiver_id": "BANK_B",
            "amount": 100000,
            "amount_settled": 100000,
            "deadline_tick": 252,
            "status": "settled",
            "settlement_tick": 240,  # Settled BEFORE current tick 250
        },
    }

    queue_snapshots = {
        "BANK_A": {
            "queue1": [],  # Not in queue (correctly)
            "rtgs": [],
        },
    }

    agent_states = {"BANK_A": {"balance": 50000}}

    provider = DatabaseStateProvider(
        conn=None,
        simulation_id="test_sim",
        tick=250,
        tx_cache=tx_cache,
        agent_states=agent_states,
        queue_snapshots=queue_snapshots,
    )

    near_deadline = provider.get_transactions_near_deadline(within_ticks=2)

    # Should be empty - transaction settled before current tick
    assert len(near_deadline) == 0, "Settled transaction should not appear in near-deadline list"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
