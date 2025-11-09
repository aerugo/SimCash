"""
Integration tests for overdue transaction FFI methods.

Tests the new FFI methods added to support overdue transaction verbose output:
- get_transactions_near_deadline()
- get_overdue_transactions()
- TransactionWentOverdue event emission
- OverdueTransactionSettled event emission

Following TDD principles: write tests first, then implement display layer.
"""

import pytest
from payment_simulator._core import Orchestrator


def test_get_transactions_near_deadline_empty():
    """When no transactions are near deadline, should return empty list."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "seed": 12345,
        "agent_configs": [
            {"id": "A", "opening_balance": 100_000_00, "credit_limit": 0},
            {"id": "B", "opening_balance": 100_000_00, "credit_limit": 0},
        ],
    }

    orch = Orchestrator.new(config)

    # No transactions yet
    near_deadline = orch.get_transactions_near_deadline(within_ticks=2)
    assert isinstance(near_deadline, list)
    assert len(near_deadline) == 0


def test_get_transactions_near_deadline_with_transactions():
    """Should return transactions approaching their deadline."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {"id": "A", "opening_balance": 0, "credit_limit": 0, "policy": {"type": "Fifo"}},  # No liquidity
            {"id": "B", "opening_balance": 100_000_00, "credit_limit": 0, "policy": {"type": "Fifo"}},
        ],
    }

    orch = Orchestrator.new(config)

    # Create transaction with deadline at tick 5
    tx_id = orch.submit_transaction(
        sender="A",
        receiver="B",
        amount=10_000_00,
        deadline_tick=5,
        priority=5,
        divisible=False,
    )

    # At tick 0, deadline is 5 ticks away - NOT near
    near_deadline = orch.get_transactions_near_deadline(within_ticks=2)
    assert len(near_deadline) == 0

    # Advance to tick 3 - now deadline is 2 ticks away
    orch.tick()  # tick 1
    orch.tick()  # tick 2
    orch.tick()  # tick 3

    near_deadline = orch.get_transactions_near_deadline(within_ticks=2)
    assert len(near_deadline) == 1

    tx = near_deadline[0]
    assert tx["tx_id"] == tx_id
    assert tx["sender_id"] == "A"
    assert tx["receiver_id"] == "B"
    assert tx["amount"] == 10_000_00
    assert tx["deadline_tick"] == 5
    assert tx["ticks_until_deadline"] == 2


def test_get_transactions_near_deadline_excludes_settled():
    """Should not include settled transactions even if they had near deadlines."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {"id": "A", "opening_balance": 100_000_00, "credit_limit": 0, "policy": {"type": "Fifo"}},
            {"id": "B", "opening_balance": 100_000_00, "credit_limit": 0, "policy": {"type": "Fifo"}},
        ],
    }

    orch = Orchestrator.new(config)

    # Create transaction with near deadline
    tx_id = orch.submit_transaction(
        sender="A",
        receiver="B",
        amount=10_000_00,
        deadline_tick=3,
        priority=10,  # High priority for immediate settlement
        divisible=False,
    )

    # Process - should settle immediately with sufficient liquidity
    orch.tick()  # tick 1

    # Even though deadline is near (2 ticks away), settled tx should not appear
    near_deadline = orch.get_transactions_near_deadline(within_ticks=2)
    assert len(near_deadline) == 0


def test_get_transactions_near_deadline_excludes_overdue():
    """Should not include transactions that are already overdue."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {"id": "A", "opening_balance": 0, "credit_limit": 0, "policy": {"type": "Fifo"}},  # No liquidity
            {"id": "B", "opening_balance": 100_000_00, "credit_limit": 0, "policy": {"type": "Fifo"}},
        ],
    }

    orch = Orchestrator.new(config)

    # Create transaction that will go overdue
    tx_id = orch.submit_transaction(
        sender="A",
        receiver="B",
        amount=10_000_00,
        deadline_tick=2,
        priority=5,
        divisible=False,
    )

    # Advance past deadline
    orch.tick()  # tick 1
    orch.tick()  # tick 2
    orch.tick()  # tick 3 - now overdue

    # Overdue transactions should NOT appear in near_deadline
    near_deadline = orch.get_transactions_near_deadline(within_ticks=2)
    assert len(near_deadline) == 0


def test_get_overdue_transactions_empty():
    """When no transactions are overdue, should return empty list."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "seed": 12345,
        "agent_configs": [
            {"id": "A", "opening_balance": 100_000_00, "credit_limit": 0},
            {"id": "B", "opening_balance": 100_000_00, "credit_limit": 0},
        ],
    }

    orch = Orchestrator.new(config)

    overdue = orch.get_overdue_transactions()
    assert isinstance(overdue, list)
    assert len(overdue) == 0


def test_get_overdue_transactions_with_overdue_tx():
    """Should return overdue transactions with cost calculations."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "seed": 12345,
        "agent_configs": [
            {"id": "A", "opening_balance": 0, "credit_limit": 0},  # No liquidity
            {"id": "B", "opening_balance": 100_000_00, "credit_limit": 0},
        ],
        "cost_config": {
            "deadline_penalty": 50_000_00,  # $500 penalty
            "delay_cost_per_tick_per_cent": 0.0001,  # 1 bp per tick
            "overdue_delay_multiplier": 5.0,  # 5x multiplier
        },
    }

    orch = Orchestrator.new(config)

    # Create transaction that will go overdue
    orch.inject_transaction({
        "tx_id": "tx_overdue",
        "sender_id": "A",
        "receiver_id": "B",
        "amount": 10_000_00,
        "deadline_tick": 2,
        "priority": 5,
        "is_divisible": False,
    })

    # Advance past deadline
    orch.tick()  # tick 1
    orch.tick()  # tick 2
    orch.tick()  # tick 3 - now overdue

    overdue = orch.get_overdue_transactions()
    assert len(overdue) == 1

    tx = overdue[0]
    assert tx["tx_id"] == "tx_overdue"
    assert tx["sender_id"] == "A"
    assert tx["receiver_id"] == "B"
    assert tx["amount"] == 10_000_00
    assert tx["remaining_amount"] == 10_000_00
    assert tx["deadline_tick"] == 2
    assert tx["overdue_since_tick"] == 3
    assert tx["ticks_overdue"] == 1
    assert tx["deadline_penalty_cost"] == 50_000_00  # $500
    assert "estimated_delay_cost" in tx
    assert "total_overdue_cost" in tx

    # Total cost should be penalty + delay cost
    total = tx["deadline_penalty_cost"] + tx["estimated_delay_cost"]
    assert tx["total_overdue_cost"] == total


def test_get_overdue_transactions_accumulates_delay_cost():
    """Should show increasing delay costs as ticks pass."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "seed": 12345,
        "agent_configs": [
            {"id": "A", "opening_balance": 0, "credit_limit": 0},  # No liquidity
            {"id": "B", "opening_balance": 100_000_00, "credit_limit": 0},
        ],
        "cost_config": {
            "deadline_penalty": 50_000_00,
            "delay_cost_per_tick_per_cent": 0.0001,
            "overdue_delay_multiplier": 5.0,
        },
    }

    orch = Orchestrator.new(config)

    # Create overdue transaction
    orch.inject_transaction({
        "tx_id": "tx_overdue",
        "sender_id": "A",
        "receiver_id": "B",
        "amount": 10_000_00,
        "deadline_tick": 2,
        "priority": 5,
        "is_divisible": False,
    })

    # Advance to tick 3 (1 tick overdue)
    orch.tick()
    orch.tick()
    orch.tick()

    overdue_1 = orch.get_overdue_transactions()[0]
    assert overdue_1["ticks_overdue"] == 1
    delay_cost_1 = overdue_1["estimated_delay_cost"]

    # Advance to tick 5 (3 ticks overdue)
    orch.tick()
    orch.tick()

    overdue_3 = orch.get_overdue_transactions()[0]
    assert overdue_3["ticks_overdue"] == 3
    delay_cost_3 = overdue_3["estimated_delay_cost"]

    # Delay cost should increase with ticks
    assert delay_cost_3 > delay_cost_1
    # Should be roughly 3x (3 ticks vs 1 tick)
    assert abs(delay_cost_3 - delay_cost_1 * 3) < 100  # Small rounding tolerance


def test_transaction_went_overdue_event_emitted():
    """Should emit TransactionWentOverdue event when deadline is crossed."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "seed": 12345,
        "agent_configs": [
            {"id": "A", "opening_balance": 0, "credit_limit": 0},  # No liquidity
            {"id": "B", "opening_balance": 100_000_00, "credit_limit": 0},
        ],
        "cost_config": {
            "deadline_penalty": 50_000_00,
        },
    }

    orch = Orchestrator.new(config)

    # Create transaction with deadline at tick 2
    orch.inject_transaction({
        "tx_id": "tx_will_be_overdue",
        "sender_id": "A",
        "receiver_id": "B",
        "amount": 10_000_00,
        "deadline_tick": 2,
        "priority": 5,
        "is_divisible": False,
    })

    # Process up to deadline
    orch.tick()  # tick 1
    orch.tick()  # tick 2

    # Should emit event when going overdue
    orch.tick()  # tick 3 - becomes overdue

    events = orch.get_tick_events(3)
    overdue_events = [e for e in events if e.get("event_type") == "TransactionWentOverdue"]

    assert len(overdue_events) == 1
    event = overdue_events[0]

    assert event["tick"] == 3
    assert event["tx_id"] == "tx_will_be_overdue"
    assert event["sender_id"] == "A"
    assert event["receiver_id"] == "B"
    assert event["amount"] == 10_000_00
    assert event["remaining_amount"] == 10_000_00
    assert event["deadline_tick"] == 2
    assert event["ticks_overdue"] == 1  # 3 - 2
    assert event["deadline_penalty_cost"] == 50_000_00


def test_overdue_transaction_settled_event_emitted():
    """Should emit OverdueTransactionSettled event when overdue tx settles."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "seed": 12345,
        "agent_configs": [
            {"id": "A", "opening_balance": 0, "credit_limit": 0},
            {"id": "B", "opening_balance": 100_000_00, "credit_limit": 0},
        ],
        "cost_config": {
            "deadline_penalty": 50_000_00,
            "delay_cost_per_tick_per_cent": 0.0001,
            "overdue_delay_multiplier": 5.0,
        },
    }

    orch = Orchestrator.new(config)

    # Create transaction
    orch.inject_transaction({
        "tx_id": "tx_overdue_then_settle",
        "sender_id": "A",
        "receiver_id": "B",
        "amount": 10_000_00,
        "deadline_tick": 2,
        "priority": 5,
        "is_divisible": False,
    })

    # Let it go overdue
    orch.tick()  # tick 1
    orch.tick()  # tick 2
    orch.tick()  # tick 3 - overdue
    orch.tick()  # tick 4

    # Give A liquidity so it can settle
    a = orch.get_agent("A")
    orch.adjust_agent_balance("A", 20_000_00)  # Add funds

    # Process settlement
    orch.tick()  # tick 5 - should settle

    events = orch.get_tick_events(5)
    overdue_settled_events = [e for e in events if e.get("event_type") == "OverdueTransactionSettled"]

    assert len(overdue_settled_events) == 1
    event = overdue_settled_events[0]

    assert event["tick"] == 5
    assert event["tx_id"] == "tx_overdue_then_settle"
    assert event["sender_id"] == "A"
    assert event["receiver_id"] == "B"
    assert event["amount"] == 10_000_00
    assert event["settled_amount"] == 10_000_00
    assert event["deadline_tick"] == 2
    assert event["overdue_since_tick"] == 3
    assert event["total_ticks_overdue"] == 2  # ticks 3-4
    assert event["deadline_penalty_cost"] == 50_000_00
    assert "estimated_delay_cost" in event


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
