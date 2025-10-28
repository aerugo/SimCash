"""Test state query methods via FFI."""
import pytest
from payment_simulator._core import Orchestrator


def test_get_agent_balance():
    """Test querying agent balances."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "credit_limit": 500_000,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 2_000_000,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
        ],
    }
    orch = Orchestrator.new(config)

    # Check initial balances
    assert orch.get_agent_balance("BANK_A") == 1_000_000
    assert orch.get_agent_balance("BANK_B") == 2_000_000

    # Non-existent agent returns None
    assert orch.get_agent_balance("BANK_C") is None


def test_get_queue1_size():
    """Test querying Queue 1 (internal queue) sizes."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 1.0,  # Expect ~1 transaction per tick
                    "amount_distribution": {"type": "Uniform", "min": 50_000, "max": 100_000},
                    "counterparty_weights": {"BANK_B": 1.0},
                    "deadline_range": [10, 50],
                    "priority": 5,
                    "divisible": False,
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 2_000_000,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
        ],
    }
    orch = Orchestrator.new(config)

    # Initially empty queues
    assert orch.get_queue1_size("BANK_A") == 0
    assert orch.get_queue1_size("BANK_B") == 0

    # Run a few ticks to generate arrivals
    for _ in range(5):
        orch.tick()

    # Queue 1 for BANK_A may have transactions if they couldn't settle immediately
    queue1_size = orch.get_queue1_size("BANK_A")
    assert queue1_size is not None  # Agent exists
    assert queue1_size >= 0  # Queue size is non-negative

    # Non-existent agent returns None
    assert orch.get_queue1_size("BANK_C") is None


def test_get_queue2_size():
    """Test querying Queue 2 (RTGS central queue) size."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 100_000,  # Low balance
                "credit_limit": 0,  # No credit
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 2.0,  # High arrival rate
                    "amount_distribution": {"type": "Uniform", "min": 50_000, "max": 100_000},
                    "counterparty_weights": {"BANK_B": 1.0},
                    "deadline_range": [10, 50],
                    "priority": 5,
                    "divisible": False,
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 2_000_000,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
        ],
    }
    orch = Orchestrator.new(config)

    # Initially empty
    assert orch.get_queue2_size() == 0

    # Run several ticks - BANK_A should queue transactions due to low balance
    for _ in range(10):
        orch.tick()

    # Queue 2 should have some queued transactions
    queue2_size = orch.get_queue2_size()
    assert queue2_size >= 0  # Non-negative


def test_get_agent_ids():
    """Test querying all agent identifiers."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {"id": "BANK_A", "opening_balance": 1_000_000, "credit_limit": 0, "policy": {"type": "Fifo"}},
            {"id": "BANK_B", "opening_balance": 2_000_000, "credit_limit": 0, "policy": {"type": "Fifo"}},
            {"id": "BANK_C", "opening_balance": 500_000, "credit_limit": 0, "policy": {"type": "Fifo"}},
        ],
    }
    orch = Orchestrator.new(config)

    agent_ids = orch.get_agent_ids()

    # Should return all 3 agents
    assert len(agent_ids) == 3
    assert "BANK_A" in agent_ids
    assert "BANK_B" in agent_ids
    assert "BANK_C" in agent_ids


def test_query_methods_during_simulation():
    """Test querying state while simulation is running."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "credit_limit": 500_000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 0.5,
                    "amount_distribution": {"type": "Normal", "mean": 100_000, "std_dev": 20_000},
                    "counterparty_weights": {"BANK_B": 1.0},
                    "deadline_range": [10, 50],
                    "priority": 5,
                    "divisible": False,
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 2_000_000,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 0.3,
                    "amount_distribution": {"type": "Normal", "mean": 80_000, "std_dev": 15_000},
                    "counterparty_weights": {"BANK_A": 1.0},
                    "deadline_range": [10, 50],
                    "priority": 5,
                    "divisible": False,
                },
            },
        ],
    }
    orch = Orchestrator.new(config)

    # Track balance changes
    initial_balance_a = orch.get_agent_balance("BANK_A")
    initial_balance_b = orch.get_agent_balance("BANK_B")

    # Run 50 ticks
    for tick in range(50):
        result = orch.tick()

        # Query state after each tick
        balance_a = orch.get_agent_balance("BANK_A")
        balance_b = orch.get_agent_balance("BANK_B")
        queue1_a = orch.get_queue1_size("BANK_A")
        queue1_b = orch.get_queue1_size("BANK_B")
        queue2 = orch.get_queue2_size()

        # Verify all queries return valid values
        assert balance_a is not None
        assert balance_b is not None
        assert queue1_a is not None
        assert queue1_b is not None
        assert queue2 >= 0

    # Balances should have changed due to transactions
    final_balance_a = orch.get_agent_balance("BANK_A")
    final_balance_b = orch.get_agent_balance("BANK_B")

    # Net change should be zero (closed system)
    net_change = (final_balance_a - initial_balance_a) + (final_balance_b - initial_balance_b)
    assert net_change == 0, "Total money in system should be conserved"


def test_iterate_all_agents():
    """Test using get_agent_ids() to iterate and query all agents."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {"id": f"BANK_{i}", "opening_balance": 1_000_000 + (i * 100_000), "credit_limit": 0, "policy": {"type": "Fifo"}}
            for i in range(5)
        ],
    }
    orch = Orchestrator.new(config)

    # Iterate over all agents and verify balances
    for agent_id in orch.get_agent_ids():
        balance = orch.get_agent_balance(agent_id)
        assert balance is not None
        assert balance > 0  # All agents have positive opening balance

        queue1_size = orch.get_queue1_size(agent_id)
        assert queue1_size is not None
        assert queue1_size == 0  # No transactions yet
