"""Unit test for Issue #3 fix: Queue-1 amounts showing $0.00.

Tests that DatabaseStateProvider correctly calculates remaining_amount
based on settlement_tick vs current tick.
"""

import pytest
from payment_simulator.cli.execution.state_provider import DatabaseStateProvider


def test_remaining_amount_respects_current_tick():
    """
    GIVEN a transaction that will be settled at tick 270
    WHEN viewing at tick 250 (before settlement)
    THEN remaining_amount should equal the full amount (not zero)
    """
    # Create mock tx_cache with a transaction that's settled at tick 270
    tx_cache = {
        "tx123": {
            "tx_id": "tx123",
            "sender_id": "BANK_A",
            "receiver_id": "BANK_B",
            "amount": 100000,  # $1000 in cents
            "amount_settled": 100000,  # Full amount will be settled
            "settlement_tick": 270,  # But not until tick 270!
            "priority": 5,
            "deadline_tick": 300,
            "status": "settled",  # Eventually settled
            "is_divisible": False,
        }
    }

    # Create provider at tick 250 (BEFORE settlement)
    provider_before = DatabaseStateProvider(
        conn=None,
        simulation_id="test",
        tick=250,  # Current tick is BEFORE settlement
        tx_cache=tx_cache,
        agent_states={},
        queue_snapshots={},
    )

    tx_details = provider_before.get_transaction_details("tx123")

    # ASSERTION: At tick 250, transaction is NOT yet settled, so remaining_amount = full amount
    assert tx_details is not None, "Transaction should be found"
    assert tx_details["remaining_amount"] == 100000, (
        f"At tick 250 (before settlement at 270), remaining_amount should be $1000 (100000 cents), "
        f"but got {tx_details['remaining_amount']}"
    )


def test_remaining_amount_after_settlement():
    """
    GIVEN a transaction settled at tick 270
    WHEN viewing at tick 280 (after settlement)
    THEN remaining_amount should be zero
    """
    tx_cache = {
        "tx123": {
            "tx_id": "tx123",
            "sender_id": "BANK_A",
            "receiver_id": "BANK_B",
            "amount": 100000,
            "amount_settled": 100000,
            "settlement_tick": 270,
            "priority": 5,
            "deadline_tick": 300,
            "status": "settled",
            "is_divisible": False,
        }
    }

    # Create provider at tick 280 (AFTER settlement)
    provider_after = DatabaseStateProvider(
        conn=None,
        simulation_id="test",
        tick=280,  # Current tick is AFTER settlement
        tx_cache=tx_cache,
        agent_states={},
        queue_snapshots={},
    )

    tx_details = provider_after.get_transaction_details("tx123")

    # ASSERTION: At tick 280, transaction IS settled, so remaining_amount = 0
    assert tx_details is not None
    assert tx_details["remaining_amount"] == 0, (
        f"At tick 280 (after settlement at 270), remaining_amount should be $0, "
        f"but got {tx_details['remaining_amount']}"
    )


def test_remaining_amount_at_settlement_tick():
    """
    GIVEN a transaction settled at tick 270
    WHEN viewing at tick 270 (exact settlement tick)
    THEN remaining_amount should be zero (settlement has occurred)
    """
    tx_cache = {
        "tx123": {
            "tx_id": "tx123",
            "sender_id": "BANK_A",
            "receiver_id": "BANK_B",
            "amount": 100000,
            "amount_settled": 100000,
            "settlement_tick": 270,
            "priority": 5,
            "deadline_tick": 300,
            "status": "settled",
            "is_divisible": False,
        }
    }

    # Create provider AT settlement tick
    provider_at = DatabaseStateProvider(
        conn=None,
        simulation_id="test",
        tick=270,  # Current tick IS settlement tick
        tx_cache=tx_cache,
        agent_states={},
        queue_snapshots={},
    )

    tx_details = provider_at.get_transaction_details("tx123")

    # ASSERTION: At tick 270 (settlement tick), settlement has occurred, so remaining_amount = 0
    assert tx_details is not None
    assert tx_details["remaining_amount"] == 0, (
        f"At tick 270 (settlement tick), remaining_amount should be $0, "
        f"but got {tx_details['remaining_amount']}"
    )


def test_unsettled_transaction():
    """
    GIVEN a transaction that is NEVER settled (settlement_tick = None)
    WHEN viewing at any tick
    THEN remaining_amount should always equal full amount
    """
    tx_cache = {
        "tx456": {
            "tx_id": "tx456",
            "sender_id": "BANK_A",
            "receiver_id": "BANK_B",
            "amount": 50000,
            "amount_settled": 0,  # Not settled
            "settlement_tick": None,  # Never settled!
            "priority": 5,
            "deadline_tick": 300,
            "status": "pending",
            "is_divisible": False,
        }
    }

    # Test at multiple ticks
    for tick in [100, 250, 400]:
        provider = DatabaseStateProvider(
            conn=None,
            simulation_id="test",
            tick=tick,
            tx_cache=tx_cache,
            agent_states={},
            queue_snapshots={},
        )

        tx_details = provider.get_transaction_details("tx456")

        assert tx_details is not None
        assert tx_details["remaining_amount"] == 50000, (
            f"Unsettled transaction at tick {tick} should have full remaining_amount, "
            f"but got {tx_details['remaining_amount']}"
        )


def test_partial_settlement():
    """
    GIVEN a divisible transaction with partial settlement
    WHEN viewing before full settlement
    THEN remaining_amount should reflect partial amount
    """
    tx_cache = {
        "tx789": {
            "tx_id": "tx789",
            "sender_id": "BANK_A",
            "receiver_id": "BANK_B",
            "amount": 100000,  # $1000
            "amount_settled": 60000,  # $600 settled
            "settlement_tick": 250,  # Partial settlement at tick 250
            "priority": 5,
            "deadline_tick": 300,
            "status": "partially_settled",
            "is_divisible": True,
        }
    }

    # Before partial settlement
    provider_before = DatabaseStateProvider(
        conn=None,
        simulation_id="test",
        tick=240,
        tx_cache=tx_cache,
        agent_states={},
        queue_snapshots={},
    )
    tx_before = provider_before.get_transaction_details("tx789")
    assert tx_before["remaining_amount"] == 100000, "Before settlement, should have full amount"

    # After partial settlement
    provider_after = DatabaseStateProvider(
        conn=None,
        simulation_id="test",
        tick=260,
        tx_cache=tx_cache,
        agent_states={},
        queue_snapshots={},
    )
    tx_after = provider_after.get_transaction_details("tx789")
    assert tx_after["remaining_amount"] == 40000, (
        f"After partial settlement, remaining should be $400 (100000 - 60000), "
        f"but got {tx_after['remaining_amount']}"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
