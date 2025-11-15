"""Test CustomTransactionArrival scenario event.

This event schedules a transaction through the normal arrival path, unlike
DirectTransfer which bypasses settlement. This allows testing transaction
settlement behavior with precise control over arrival timing.
"""

import pytest
from payment_simulator._core import Orchestrator


def test_custom_transaction_arrival_creates_pending_transaction():
    """Test that CustomTransactionArrival creates a transaction in pending state.

    TDD: This test defines the expected behavior - the transaction should go
    through normal arrival → settlement flow, not instant transfer.
    """
    config = {
        "ticks_per_day": 20,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {"id": "BANK_A", "opening_balance": 1000000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "BANK_B", "opening_balance": 1000000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
        "scenario_events": [
            {
                "type": "CustomTransactionArrival",
                "from_agent": "BANK_A",
                "to_agent": "BANK_B",
                "amount": 50000,  # $500.00
                "priority": 7,
                "deadline": 10,  # 10 ticks from arrival
                "is_divisible": False,
                "schedule": "OneTime",
                "tick": 5,
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Before tick 5: no transaction exists
    for _ in range(5):
        orch.tick()

    # Check no transactions yet
    all_events = orch.get_all_events()
    arrival_events = [e for e in all_events if e.get("event_type") == "Arrival"]
    assert len(arrival_events) == 0, "No arrivals should exist before tick 5"

    # Tick 5: CustomTransactionArrival executes
    orch.tick()  # tick 5

    # Verify transaction arrived
    all_events = orch.get_all_events()
    arrival_events = [e for e in all_events if e.get("event_type") == "Arrival"]
    assert len(arrival_events) == 1, "Transaction should arrive at tick 5"

    arrival = arrival_events[0]
    assert arrival["tx_id"] is not None
    assert arrival["sender_id"] == "BANK_A"
    assert arrival["receiver_id"] == "BANK_B"
    assert arrival["amount"] == 50000
    assert arrival["priority"] == 7
    assert arrival["deadline"] == 15  # tick 5 + 10
    assert arrival.get("is_divisible") == False

    # Verify transaction settled immediately (BANK_A has sufficient liquidity)
    # BANK_A has 1M balance and transaction is only 50k, so it settles immediately
    all_events = orch.get_all_events()
    settlement_events = [e for e in all_events if e.get("event_type") == "Settlement"]
    assert len(settlement_events) == 1, "Transaction should settle immediately at tick 5"

    settlement = settlement_events[0]
    assert settlement["sender_id"] == "BANK_A"
    assert settlement["receiver_id"] == "BANK_B"
    assert settlement["amount"] == 50000

    # Verify balances changed immediately
    bank_a_balance = orch.get_agent_balance("BANK_A")
    bank_b_balance = orch.get_agent_balance("BANK_B")
    assert bank_a_balance == 950000, f"BANK_A should have 950000, got {bank_a_balance}"
    assert bank_b_balance == 1050000, f"BANK_B should have 1050000, got {bank_b_balance}"

    # Verify queue is empty (transaction settled immediately)
    queue_contents = orch.get_agent_queue1_contents("BANK_A")
    assert len(queue_contents) == 0, "Queue should be empty after immediate settlement"


def test_custom_transaction_arrival_with_defaults():
    """Test CustomTransactionArrival with optional fields using defaults."""
    config = {
        "ticks_per_day": 20,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {"id": "BANK_A", "opening_balance": 2000000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "BANK_B", "opening_balance": 1000000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
        "scenario_events": [
            {
                "type": "CustomTransactionArrival",
                "from_agent": "BANK_A",
                "to_agent": "BANK_B",
                "amount": 100000,
                # No priority, deadline, or is_divisible - should use defaults
                "schedule": "OneTime",
                "tick": 3,
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Run to tick 3
    for _ in range(3):
        orch.tick()

    # Tick 3: arrival
    orch.tick()

    all_events = orch.get_all_events()
    arrivals = [e for e in all_events if e.get("event_type") == "Arrival"]
    assert len(arrivals) == 1

    arrival = arrivals[0]
    # Check defaults are applied
    assert arrival["priority"] == 5, "Default priority should be 5"
    assert arrival.get("is_divisible") == False, "Default is_divisible should be False"
    # Deadline should be calculated based on config or reasonable default


def test_custom_transaction_arrival_repeating():
    """Test CustomTransactionArrival with repeating schedule."""
    config = {
        "ticks_per_day": 30,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {"id": "BANK_A", "opening_balance": 5000000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "BANK_B", "opening_balance": 1000000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
        "scenario_events": [
            {
                "type": "CustomTransactionArrival",
                "from_agent": "BANK_A",
                "to_agent": "BANK_B",
                "amount": 50000,
                "schedule": "Repeating",
                "start_tick": 5,
                "interval": 5,
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Run entire simulation
    for _ in range(30):
        orch.tick()

    # Verify multiple arrivals occurred at ticks 5, 10, 15, 20, 25
    all_events = orch.get_all_events()
    arrivals = [e for e in all_events if e.get("event_type") == "Arrival"]

    # Should have arrivals at ticks: 5, 10, 15, 20, 25 = 5 arrivals
    assert len(arrivals) == 5, f"Expected 5 arrivals, got {len(arrivals)}"

    # Verify arrivals happened at correct ticks
    arrival_ticks = [e["tick"] for e in arrivals]
    assert arrival_ticks == [5, 10, 15, 20, 25], f"Arrivals should be at ticks 5, 10, 15, 20, 25, got {arrival_ticks}"


def test_custom_transaction_arrival_vs_direct_transfer():
    """Test that CustomTransactionArrival uses settlement path unlike DirectTransfer.

    This test demonstrates the key difference: DirectTransfer is instant,
    CustomTransactionArrival goes through the normal settlement process.
    """
    config = {
        "ticks_per_day": 20,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {"id": "BANK_A", "opening_balance": 1000000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "BANK_B", "opening_balance": 1000000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
        "scenario_events": [
            # DirectTransfer: instant balance change
            {
                "type": "DirectTransfer",
                "from_agent": "BANK_A",
                "to_agent": "BANK_B",
                "amount": 50000,
                "schedule": "OneTime",
                "tick": 5,
            },
            # CustomTransactionArrival: goes through settlement
            {
                "type": "CustomTransactionArrival",
                "from_agent": "BANK_A",
                "to_agent": "BANK_B",
                "amount": 50000,
                "schedule": "OneTime",
                "tick": 10,
            },
        ],
    }

    orch = Orchestrator.new(config)

    # Run to tick 5
    for _ in range(5):
        orch.tick()

    # Tick 5: DirectTransfer executes
    orch.tick()

    # DirectTransfer should change balances immediately, no Arrival event
    all_events = orch.get_all_events()
    arrivals = [e for e in all_events if e.get("event_type") == "Arrival"]
    assert len(arrivals) == 0, "DirectTransfer should not create Arrival event"

    bank_a_balance_after_direct = orch.get_agent_balance("BANK_A")
    assert bank_a_balance_after_direct == 950000

    # Run to tick 10
    for _ in range(4):
        orch.tick()

    # Tick 10: CustomTransactionArrival executes
    orch.tick()

    # CustomTransactionArrival SHOULD create Arrival event
    all_events = orch.get_all_events()
    arrivals = [e for e in all_events if e.get("event_type") == "Arrival"]
    assert len(arrivals) == 1, "CustomTransactionArrival should create Arrival event"

    # Transaction should be pending in queue or settling
    # Run one more tick to allow settlement
    orch.tick()

    # Verify final settlement
    settlements = [e for e in all_events if e.get("event_type") == "Settlement"]
    # We might have settlements by now, verify balances are correct
    final_balance_a = orch.get_agent_balance("BANK_A")
    final_balance_b = orch.get_agent_balance("BANK_B")

    # BANK_A sent: 50k (DirectTransfer) + 50k (CustomTx) = 100k total
    # BANK_B received: 50k + 50k = 100k total
    assert final_balance_a == 900000, f"BANK_A should have 900000, got {final_balance_a}"
    assert final_balance_b == 1100000, f"BANK_B should have 1100000, got {final_balance_b}"


def test_custom_transaction_arrival_logged_to_events():
    """Test that CustomTransactionArrival execution is logged to events."""
    config = {
        "ticks_per_day": 20,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {"id": "BANK_A", "opening_balance": 2000000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "BANK_B", "opening_balance": 1000000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
        "scenario_events": [
            {
                "type": "CustomTransactionArrival",
                "from_agent": "BANK_A",
                "to_agent": "BANK_B",
                "amount": 75000,
                "priority": 8,
                "deadline": 15,
                "schedule": "OneTime",
                "tick": 7,
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Run to tick 8
    for _ in range(8):
        orch.tick()

    # Verify ScenarioEventExecuted was logged
    all_events = orch.get_all_events()
    scenario_events = [e for e in all_events if e.get("event_type") == "ScenarioEventExecuted"]

    assert len(scenario_events) == 1, "Should have 1 ScenarioEventExecuted event"

    scenario_event = scenario_events[0]
    assert scenario_event["scenario_event_type"] == "custom_transaction_arrival"

    # Verify event details (stored in details_json field as JSON string)
    import json
    details_json = scenario_event.get("details_json", "{}")
    details = json.loads(details_json)

    assert details.get("from_agent") == "BANK_A"
    assert details.get("to_agent") == "BANK_B"
    assert details.get("amount") == 75000
    assert details.get("priority") == 8
    assert details.get("tx_id") is not None, "Should include transaction ID"
