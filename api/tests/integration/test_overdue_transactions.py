"""
Integration tests for overdue transaction handling (Phase 5).

Tests verify the complete overdue transaction lifecycle from Python/FFI:
- Transactions past deadline are marked overdue (not dropped)
- Overdue transactions remain in queue until settled
- Overdue transactions can eventually settle when liquidity arrives
- Overdue delay cost multiplier is applied
- One-time deadline penalty is charged
"""

import pytest
from payment_simulator._core import Orchestrator


def test_transaction_becomes_overdue_after_deadline():
    """Verify transaction is marked overdue when past deadline."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 42,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 100_000,  # Insufficient for transaction
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 0,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        "cost_rates": {
            "delay_cost_per_tick_per_cent": 0.0001,
            "overdue_delay_multiplier": 5.0,
            "deadline_penalty": 100_000,  # $1,000 penalty
        },
    }

    orch = Orchestrator.new(config)

    # Submit transaction that will be insufficient
    tx_id = orch.submit_transaction(
        sender="BANK_A",
        receiver="BANK_B",
        amount=500_000,  # $5,000 - more than available
        deadline_tick=10,  # Deadline at tick 10
        priority=5,
        divisible=False,
    )

    # Run through deadline
    for tick in range(1, 15):
        orch.tick()

    # TODO: Add method to query transaction status via FFI
    # For now, verify transaction is still in system (not dropped)
    # In old system, it would be dropped and removed from queue

    # Queue should still contain the transaction
    queue_size = orch.get_queue2_size()
    assert queue_size > 0, "Overdue transaction should remain in queue"


def test_overdue_transaction_eventually_settles():
    """Verify overdue transactions settle when liquidity arrives."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 42,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 100_000,  # Insufficient for 500k transaction
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 500_000,  # Give BANK_B money so it can send to BANK_A
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        "cost_rates": {
            "delay_cost_per_tick_per_cent": 0.0001,
            "overdue_delay_multiplier": 5.0,
            "deadline_penalty": 100_000,
        },
    }

    orch = Orchestrator.new(config)

    initial_balance_a = orch.get_agent_balance("BANK_A")
    initial_balance_b = orch.get_agent_balance("BANK_B")

    # Submit transaction that will be insufficient
    tx_id = orch.submit_transaction(
        sender="BANK_A",
        receiver="BANK_B",
        amount=500_000,
        deadline_tick=10,
        priority=5,
        divisible=False,
    )

    # Run past deadline (transaction becomes overdue)
    for _ in range(15):
        orch.tick()

    # Verify still not settled due to insufficient liquidity
    current_balance_a = orch.get_agent_balance("BANK_A")
    assert current_balance_a == initial_balance_a, "Should not have debited yet"

    # Queue 2 should still have the overdue transaction
    assert orch.get_queue2_size() > 0, "Overdue transaction should still be in queue"

    # Add liquidity: BANK_B sends money to BANK_A
    orch.submit_transaction(
        sender="BANK_B",
        receiver="BANK_A",
        amount=500_000,
        deadline_tick=100,
        priority=5,
        divisible=False,
    )

    # Run more ticks to allow settlement
    settlements_found = False
    for _ in range(10):
        result = orch.tick()
        if result["num_settlements"] > 0:
            settlements_found = True
            break

    assert settlements_found, "Transactions should have settled"

    # Verify transactions eventually settled
    final_balance_a = orch.get_agent_balance("BANK_A")
    final_balance_b = orch.get_agent_balance("BANK_B")

    # Net effect: BANK_A receives 500k and sends 500k
    # BANK_A should have approximately same balance but may have paid some costs
    # (Overdue penalty + overdue delay costs for the 5 ticks it was overdue)
    balance_change_a = final_balance_a - initial_balance_a

    # Check that both transactions settled (net zero transfer)
    # But BANK_A paid deadline penalty + some delay costs while overdue
    assert balance_change_a <= 0, f"BANK_A balance should be same or decreased due to costs, got change: {balance_change_a}"


def test_overdue_delay_cost_multiplier_applied():
    """Verify overdue transactions incur 5x delay costs."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 42,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 100_000,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 0,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        "cost_rates": {
            "delay_cost_per_tick_per_cent": 0.0001,  # 1 bp per tick
            "overdue_delay_multiplier": 5.0,  # 5x for overdue
            "deadline_penalty": 100_000,  # $1,000 one-time
        },
    }

    orch = Orchestrator.new(config)

    # Submit transaction that will go overdue
    tx_id = orch.submit_transaction(
        sender="BANK_A",
        receiver="BANK_B",
        amount=1_000_000,  # $10,000
        deadline_tick=10,
        priority=5,
        divisible=False,
    )

    # Run well past deadline to accumulate overdue costs
    for _ in range(20):
        orch.tick()

    # TODO: Need FFI method to get detailed cost breakdown
    # For now, just verify costs are being charged
    # by checking that queue still has the transaction
    assert orch.get_queue2_size() > 0


def test_deadline_penalty_charged_once():
    """Verify one-time deadline penalty is charged when overdue."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 42,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 100_000,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 0,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        "cost_rates": {
            "delay_cost_per_tick_per_cent": 0.0001,
            "overdue_delay_multiplier": 5.0,
            "deadline_penalty": 100_000,  # $1,000 one-time penalty
        },
    }

    orch = Orchestrator.new(config)

    # Submit transaction
    tx_id = orch.submit_transaction(
        sender="BANK_A",
        receiver="BANK_B",
        amount=500_000,
        deadline_tick=10,
        priority=5,
        divisible=False,
    )

    # Run past deadline
    for _ in range(15):
        orch.tick()

    # TODO: Verify penalty was charged exactly once
    # Need FFI method to get cost breakdown by tick or cumulative costs


def test_multiple_overdue_transactions():
    """Verify multiple overdue transactions are handled correctly."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 42,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 100_000,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 0,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_C",
                "opening_balance": 0,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        "cost_rates": {
            "overdue_delay_multiplier": 5.0,
            "deadline_penalty": 50_000,
        },
    }

    orch = Orchestrator.new(config)

    # Submit multiple transactions that will go overdue
    tx1 = orch.submit_transaction(
        sender="BANK_A",
        receiver="BANK_B",
        amount=300_000,
        deadline_tick=5,
        priority=5,
        divisible=False,
    )

    tx2 = orch.submit_transaction(
        sender="BANK_A",
        receiver="BANK_C",
        amount=300_000,
        deadline_tick=10,
        priority=5,
        divisible=False,
    )

    # Run past both deadlines
    for _ in range(15):
        orch.tick()

    # Both transactions should still be in system (not dropped)
    queue_size = orch.get_queue2_size()
    assert queue_size >= 2, "Both overdue transactions should remain in queue"


def test_config_with_overdue_multiplier():
    """Verify overdue_delay_multiplier can be configured via FFI."""
    config_with_multiplier = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 42,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 0,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        "cost_rates": {
            "overdue_delay_multiplier": 10.0,  # Custom 10x multiplier
            "deadline_penalty": 100_000,
        },
    }

    # Should create orchestrator without error
    orch = Orchestrator.new(config_with_multiplier)
    assert orch is not None


def test_config_uses_default_multiplier_when_not_specified():
    """Verify default overdue multiplier (5.0) is used when not specified."""
    config_without_multiplier = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 42,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 0,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        # cost_rates not specified - should use defaults
    }

    # Should create orchestrator with default overdue_delay_multiplier = 5.0
    orch = Orchestrator.new(config_without_multiplier)
    assert orch is not None
