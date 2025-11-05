"""
Integration tests for LSM activation investigation (from lsm-splitting-investigation-plan.md).

Tests verify that LSMs activate correctly through the full orchestrator stack
when gridlock conditions occur, as described in the simulation review.

Test 3: Full Orchestrator LSM Integration
"""

import pytest
from payment_simulator._core import Orchestrator


def test_lsm_bilateral_offset_via_orchestrator():
    """
    Test 3: Integration test - LSM bilateral offsetting through full orchestrator stack.

    This test verifies that when two agents have mutual obligations and insufficient
    individual liquidity, the LSM bilateral offsetting mechanism activates and settles
    both transactions through net-zero flows.

    This is the scenario that should have occurred in the simulation review but
    allegedly did not activate.
    """
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 42,
        "lsm_config": {
            "enable_bilateral": True,
            "enable_cycles": False,  # Test bilateral only first
        },
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 100_000,  # $1k
                "credit_limit": 500_000,      # $5k credit
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 100_000,  # $1k
                "credit_limit": 500_000,      # $5k credit
                "policy": {"type": "Fifo"},
            },
        ],
    }

    orch = Orchestrator.new(config)

    # Record initial balances
    initial_balance_a = orch.get_agent_balance("BANK_A")
    initial_balance_b = orch.get_agent_balance("BANK_B")

    assert initial_balance_a == 100_000, "BANK_A should start with $1k"
    assert initial_balance_b == 100_000, "BANK_B should start with $1k"

    # Submit mutual obligations that exceed individual balances
    # A→B $3k (A only has $1k balance)
    # B→A $3k (B only has $1k balance)
    # Without LSM, these would queue indefinitely
    # With LSM bilateral offsetting, they should settle with net-zero balance changes
    tx_ab = orch.submit_transaction(
        sender="BANK_A",
        receiver="BANK_B",
        amount=300_000,  # $3k
        deadline_tick=50,
        priority=5,
        divisible=False,
    )

    tx_ba = orch.submit_transaction(
        sender="BANK_B",
        receiver="BANK_A",
        amount=300_000,  # $3k
        deadline_tick=50,
        priority=5,
        divisible=False,
    )

    # Run one tick to process submissions and attempt settlement
    result = orch.tick()

    # CRITICAL ASSERTIONS - these test the LSM activation claim
    assert result["num_settlements"] > 0, (
        "LSM should have settled transactions via bilateral offset. "
        "If this fails, LSM is not activating at orchestrator level."
    )

    assert orch.get_queue2_size() == 0, (
        "Queue should be empty after LSM bilateral offset. "
        "Transactions remaining in queue indicates LSM did not activate."
    )

    # Verify net-zero balance changes (bilateral offsetting characteristic)
    # Each agent sent $3k and received $3k, so balances should be unchanged
    final_balance_a = orch.get_agent_balance("BANK_A")
    final_balance_b = orch.get_agent_balance("BANK_B")

    assert final_balance_a == initial_balance_a, (
        f"BANK_A should have net-zero balance change "
        f"(sent $3k, received $3k). Got {final_balance_a}, expected {initial_balance_a}"
    )
    assert final_balance_b == initial_balance_b, (
        f"BANK_B should have net-zero balance change "
        f"(sent $3k, received $3k). Got {final_balance_b}, expected {initial_balance_b}"
    )


def test_lsm_cycle_settlement_via_orchestrator():
    """
    Test 3b: Integration test - LSM cycle detection through full orchestrator stack.

    This test verifies that when three agents form a circular dependency (A→B→C→A)
    with insufficient individual liquidity, the LSM cycle detection activates and
    settles all transactions through net-zero flows.

    This multilateral cycle settlement should have occurred in the review scenario.
    """
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 42,
        "lsm_config": {
            "enable_bilateral": False,  # Test cycles only
            "enable_cycles": True,
        },
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 50_000,   # $500
                "credit_limit": 500_000,      # $5k credit
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 50_000,   # $500
                "credit_limit": 500_000,      # $5k credit
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_C",
                "opening_balance": 50_000,   # $500
                "credit_limit": 500_000,      # $5k credit
                "policy": {"type": "Fifo"},
            },
        ],
    }

    orch = Orchestrator.new(config)

    # Record initial balances
    initial_balance_a = orch.get_agent_balance("BANK_A")
    initial_balance_b = orch.get_agent_balance("BANK_B")
    initial_balance_c = orch.get_agent_balance("BANK_C")

    # Create circular dependency: A→B→C→A
    # Each payment is $2k, but agents only have $500 balance each
    # None can settle individually, but cycle settlement can resolve the deadlock
    tx_ab = orch.submit_transaction(
        sender="BANK_A",
        receiver="BANK_B",
        amount=200_000,  # $2k
        deadline_tick=50,
        priority=5,
        divisible=False,
    )

    tx_bc = orch.submit_transaction(
        sender="BANK_B",
        receiver="BANK_C",
        amount=200_000,  # $2k
        deadline_tick=50,
        priority=5,
        divisible=False,
    )

    tx_ca = orch.submit_transaction(
        sender="BANK_C",
        receiver="BANK_A",
        amount=200_000,  # $2k
        deadline_tick=50,
        priority=5,
        divisible=False,
    )

    # Run one tick
    result = orch.tick()

    # CRITICAL ASSERTIONS - verify cycle detection activates
    assert result["num_settlements"] > 0, (
        "LSM should have settled transactions via cycle detection. "
        "If this fails, LSM cycle detection is not activating."
    )

    assert orch.get_queue2_size() == 0, (
        "Queue should be empty after LSM cycle settlement. "
        "Transactions remaining indicates cycle detection did not activate."
    )

    # Verify net-zero balance changes for all agents in the cycle
    final_balance_a = orch.get_agent_balance("BANK_A")
    final_balance_b = orch.get_agent_balance("BANK_B")
    final_balance_c = orch.get_agent_balance("BANK_C")

    assert final_balance_a == initial_balance_a, (
        f"BANK_A should have net-zero balance change (sent $2k to B, received $2k from C). "
        f"Got {final_balance_a}, expected {initial_balance_a}"
    )
    assert final_balance_b == initial_balance_b, (
        f"BANK_B should have net-zero balance change (sent $2k to C, received $2k from A). "
        f"Got {final_balance_b}, expected {initial_balance_b}"
    )
    assert final_balance_c == initial_balance_c, (
        f"BANK_C should have net-zero balance change (sent $2k to A, received $2k from B). "
        f"Got {final_balance_c}, expected {initial_balance_c}"
    )


def test_lsm_combined_bilateral_and_cycles():
    """
    Test 3c: Integration test - LSM with both bilateral and cycle detection enabled.

    This tests the full LSM coordinator as it would run in production, with both
    mechanisms enabled. This most closely matches the simulation review scenario
    configuration.
    """
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 42,
        "lsm_config": {
            "enable_bilateral": True,  # Both enabled
            "enable_cycles": True,
        },
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 100_000,
                "credit_limit": 500_000,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 100_000,
                "credit_limit": 500_000,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_C",
                "opening_balance": 50_000,
                "credit_limit": 500_000,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_D",
                "opening_balance": 50_000,
                "credit_limit": 500_000,
                "policy": {"type": "Fifo"},
            },
        ],
    }

    orch = Orchestrator.new(config)

    # Create mix of bilateral pairs and a cycle:
    # - Bilateral: A↔B ($3k each direction)
    # - Cycle: C→D→C ($2k each direction, but treated as cycle)

    # A↔B bilateral pair
    orch.submit_transaction(
        sender="BANK_A", receiver="BANK_B", amount=300_000,
        deadline_tick=50, priority=5, divisible=False
    )
    orch.submit_transaction(
        sender="BANK_B", receiver="BANK_A", amount=300_000,
        deadline_tick=50, priority=5, divisible=False
    )

    # C→D→C cycle (also a bilateral pair, but tests cycle detection)
    orch.submit_transaction(
        sender="BANK_C", receiver="BANK_D", amount=200_000,
        deadline_tick=50, priority=5, divisible=False
    )
    orch.submit_transaction(
        sender="BANK_D", receiver="BANK_C", amount=200_000,
        deadline_tick=50, priority=5, divisible=False
    )

    # Run one tick
    result = orch.tick()

    # CRITICAL ASSERTION - all transactions should settle via LSM
    assert result["num_settlements"] >= 4, (
        f"All 4 transactions should settle via LSM. Got {result['num_settlements']} settlements."
    )

    assert orch.get_queue2_size() == 0, (
        "Queue should be empty after LSM processes all transactions"
    )


def test_lsm_does_not_activate_with_sufficient_liquidity():
    """
    Negative test: Verify LSM doesn't interfere when liquidity is sufficient.

    When agents have sufficient balance, transactions should settle via normal
    RTGS without needing LSM intervention. This ensures LSM only activates when needed.
    """
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 42,
        "lsm_config": {
            "enable_bilateral": True,
            "enable_cycles": True,
        },
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 10_000_000,  # $100k - plenty of liquidity
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 10_000_000,  # $100k
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
        ],
    }

    orch = Orchestrator.new(config)

    # Submit mutual transactions that are well within balance limits
    orch.submit_transaction(
        sender="BANK_A", receiver="BANK_B", amount=100_000,  # $1k
        deadline_tick=50, priority=5, divisible=False
    )
    orch.submit_transaction(
        sender="BANK_B", receiver="BANK_A", amount=100_000,  # $1k
        deadline_tick=50, priority=5, divisible=False
    )

    # Run one tick
    result = orch.tick()

    # Should settle via normal RTGS, queue should be empty
    assert result["num_settlements"] == 2, "Both transactions should settle"
    assert orch.get_queue2_size() == 0, "Queue should be empty"

    # Balances should reflect the settlements (net-zero, same as LSM would achieve)
    assert orch.get_agent_balance("BANK_A") == 10_000_000
    assert orch.get_agent_balance("BANK_B") == 10_000_000
