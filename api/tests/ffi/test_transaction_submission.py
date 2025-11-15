"""Test transaction submission via FFI (TDD - tests written first)."""
import pytest
from payment_simulator._core import Orchestrator


def test_submit_simple_transaction():
    """Test submitting a basic transaction."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {"id": "BANK_A", "opening_balance": 1_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "BANK_B", "opening_balance": 2_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    }
    orch = Orchestrator.new(config)

    # Submit transaction
    tx_id = orch.submit_transaction(
        sender="BANK_A",
        receiver="BANK_B",
        amount=100_000,  # $1,000.00
        deadline_tick=50,
        priority=5,
        divisible=False,
    )

    # Verify transaction ID returned
    assert tx_id is not None
    assert isinstance(tx_id, str)
    assert len(tx_id) > 0

    # Verify transaction is in BANK_A's Queue 1
    assert orch.get_queue1_size("BANK_A") == 1


def test_submit_transaction_settles():
    """Test that submitted transaction actually settles."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {"id": "BANK_A", "opening_balance": 1_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "BANK_B", "opening_balance": 500_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    }
    orch = Orchestrator.new(config)

    initial_balance_a = orch.get_agent_balance("BANK_A")
    initial_balance_b = orch.get_agent_balance("BANK_B")

    # Submit transaction
    tx_id = orch.submit_transaction(
        sender="BANK_A",
        receiver="BANK_B",
        amount=200_000,  # $2,000.00
        deadline_tick=50,
        priority=5,
        divisible=False,
    )

    # Tick until settled (FIFO policy should submit immediately)
    for _ in range(10):
        result = orch.tick()
        if result["num_settlements"] > 0:
            break

    # Verify balances changed
    final_balance_a = orch.get_agent_balance("BANK_A")
    final_balance_b = orch.get_agent_balance("BANK_B")

    assert final_balance_a == initial_balance_a - 200_000
    assert final_balance_b == initial_balance_b + 200_000


def test_submit_transaction_invalid_sender():
    """Test error when sender doesn't exist."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {"id": "BANK_A", "opening_balance": 1_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    }
    orch = Orchestrator.new(config)

    # Submit with non-existent sender
    with pytest.raises(Exception) as exc_info:
        orch.submit_transaction(
            sender="BANK_X",  # Doesn't exist
            receiver="BANK_A",
            amount=100_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

    assert "not found" in str(exc_info.value).lower() or "agent" in str(exc_info.value).lower()


def test_submit_transaction_invalid_receiver():
    """Test error when receiver doesn't exist."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {"id": "BANK_A", "opening_balance": 1_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    }
    orch = Orchestrator.new(config)

    # Submit with non-existent receiver
    with pytest.raises(Exception) as exc_info:
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_X",  # Doesn't exist
            amount=100_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

    assert "not found" in str(exc_info.value).lower() or "agent" in str(exc_info.value).lower()


def test_submit_transaction_invalid_amount():
    """Test error when amount is negative or zero."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {"id": "BANK_A", "opening_balance": 1_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "BANK_B", "opening_balance": 2_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    }
    orch = Orchestrator.new(config)

    # Zero amount
    with pytest.raises(Exception) as exc_info:
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=0,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
    assert "amount" in str(exc_info.value).lower()

    # Negative amount
    with pytest.raises(Exception) as exc_info:
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=-100_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
    assert "amount" in str(exc_info.value).lower()


def test_submit_multiple_transactions():
    """Test submitting multiple transactions."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {"id": "BANK_A", "opening_balance": 5_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "BANK_B", "opening_balance": 2_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "BANK_C", "opening_balance": 3_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    }
    orch = Orchestrator.new(config)

    # Submit multiple transactions
    tx_ids = []
    tx_ids.append(
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=100_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
    )
    tx_ids.append(
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_C",
            amount=150_000,
            deadline_tick=50,
            priority=7,
            divisible=True,
        )
    )
    tx_ids.append(
        orch.submit_transaction(
            sender="BANK_B",
            receiver="BANK_C",
            amount=200_000,
            deadline_tick=50,
            priority=3,
            divisible=False,
        )
    )

    # Verify all unique IDs
    assert len(tx_ids) == 3
    assert len(set(tx_ids)) == 3  # All unique

    # Verify queued correctly
    assert orch.get_queue1_size("BANK_A") == 2  # A sent 2 transactions
    assert orch.get_queue1_size("BANK_B") == 1  # B sent 1 transaction
    assert orch.get_queue1_size("BANK_C") == 0  # C sent none


def test_submit_transaction_with_insufficient_funds():
    """Test submitting transaction when sender has insufficient funds."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {"id": "BANK_A", "opening_balance": 100_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "BANK_B", "opening_balance": 2_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    }
    orch = Orchestrator.new(config)

    # Submit transaction larger than balance
    tx_id = orch.submit_transaction(
        sender="BANK_A",
        receiver="BANK_B",
        amount=500_000,  # More than BANK_A has
        deadline_tick=50,
        priority=5,
        divisible=False,
    )

    # Transaction should still be accepted and queued
    assert tx_id is not None
    assert orch.get_queue1_size("BANK_A") == 1

    # But it shouldn't settle immediately
    initial_balance_a = orch.get_agent_balance("BANK_A")
    orch.tick()

    # Should be queued in Queue 2 (RTGS queue) after policy submits it
    queue2_size = orch.get_queue2_size()
    assert queue2_size > 0  # Transaction waiting for liquidity


def test_submit_transaction_priority_levels():
    """Test submitting transactions with different priority levels."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {"id": "BANK_A", "opening_balance": 1_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "BANK_B", "opening_balance": 2_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    }
    orch = Orchestrator.new(config)

    # Submit transactions with different priorities
    low_priority = orch.submit_transaction(
        sender="BANK_A", receiver="BANK_B", amount=50_000, deadline_tick=50, priority=1, divisible=False
    )
    high_priority = orch.submit_transaction(
        sender="BANK_A", receiver="BANK_B", amount=50_000, deadline_tick=50, priority=10, divisible=False
    )

    # Both should be accepted
    assert low_priority is not None
    assert high_priority is not None
    assert orch.get_queue1_size("BANK_A") == 2


def test_submit_divisible_transaction():
    """Test submitting a divisible transaction."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 500_000,
                "unsecured_cap": 0,
                "policy": {
                    "type": "LiquiditySplitting",
                    "max_splits": 3,
                    "min_split_amount": 10_000,
                },
            },
            {"id": "BANK_B", "opening_balance": 2_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    }
    orch = Orchestrator.new(config)

    # Submit large divisible transaction
    tx_id = orch.submit_transaction(
        sender="BANK_A",
        receiver="BANK_B",
        amount=400_000,  # Large amount, might be split
        deadline_tick=50,
        priority=5,
        divisible=True,  # Allow splitting
    )

    assert tx_id is not None
    assert orch.get_queue1_size("BANK_A") == 1

    # After ticking, policy may split it
    orch.tick()

    # If split, children go directly to settlement (bypass Queue 1)
    # Original behavior depends on policy decision


def test_submit_transaction_deadline_in_past():
    """Test submitting transaction with deadline already passed."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {"id": "BANK_A", "opening_balance": 1_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "BANK_B", "opening_balance": 2_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    }
    orch = Orchestrator.new(config)

    # Advance to tick 20
    for _ in range(20):
        orch.tick()

    current_tick = orch.current_tick()
    assert current_tick == 20

    # Try to submit with deadline in the past
    with pytest.raises(Exception) as exc_info:
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=100_000,
            deadline_tick=10,  # In the past
            priority=5,
            divisible=False,
        )

    assert "deadline" in str(exc_info.value).lower() or "past" in str(exc_info.value).lower()


def test_transaction_ids_are_unique():
    """Test that transaction IDs are unique within an orchestrator instance."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {"id": "BANK_A", "opening_balance": 1_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "BANK_B", "opening_balance": 2_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    }

    orch = Orchestrator.new(config)

    # Submit multiple transactions
    tx_ids = []
    for _ in range(5):
        tx_id = orch.submit_transaction(
            sender="BANK_A", receiver="BANK_B", amount=100_000, deadline_tick=50, priority=5, divisible=False
        )
        tx_ids.append(tx_id)

    # All IDs should be unique
    assert len(tx_ids) == 5
    assert len(set(tx_ids)) == 5, "Transaction IDs should all be unique"

    # IDs should be valid strings (UUIDs in current implementation)
    for tx_id in tx_ids:
        assert isinstance(tx_id, str)
        assert len(tx_id) > 0
