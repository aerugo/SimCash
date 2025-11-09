"""End-to-end test for overdue transaction verbose output.

Validates that display functions work correctly for overdue scenarios:
1. Near-deadline warnings display
2. Overdue transactions summary display
3. TransactionWentOverdue event logging (when implemented)

Focuses on validating the display layer, not the core overdue logic
(which is tested in test_overdue_ffi_methods.py).
"""

from payment_simulator._core import Orchestrator
from payment_simulator.cli.execution.state_provider import OrchestratorStateProvider
from payment_simulator.cli.output import (
    log_overdue_transactions_summary,
    log_transactions_near_deadline,
)


def test_overdue_display_functions():
    """Test that overdue display functions work correctly."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 42,
        "agent_configs": [
            {"id": "A", "opening_balance": 0, "credit_limit": 0, "policy": {"type": "Fifo"}},
            {"id": "B", "opening_balance": 100_000_00, "credit_limit": 0, "policy": {"type": "Fifo"}},
        ],
        "cost_rates": {
            "deadline_penalty": 50_000_00,
        },
    }

    orch = Orchestrator.new(config)
    provider = OrchestratorStateProvider(orch)

    # Create transaction that will go overdue
    tx_id = orch.submit_transaction(
        sender="A",
        receiver="B",
        amount=10_000_00,
        deadline_tick=2,
        priority=5,
        divisible=False,
    )

    print("\n=== Test 1: Near-deadline warnings ===")
    # At tick 0, deadline is 2 ticks away - should appear in warnings
    near_deadline = provider.get_transactions_near_deadline(within_ticks=2)
    print(f"Near deadline transactions: {len(near_deadline)}")
    assert len(near_deadline) == 1, "Should have 1 transaction near deadline"

    # Display near-deadline warnings
    log_transactions_near_deadline(provider, within_ticks=2, current_tick=0, quiet=False)

    print("\n=== Test 2: Transaction goes overdue ===")
    # Advance past deadline
    orch.tick()  # tick 0
    orch.tick()  # tick 1
    orch.tick()  # tick 2 (deadline tick, still valid)
    orch.tick()  # tick 3 - becomes overdue

    # Check overdue status
    overdue = provider.get_overdue_transactions()
    print(f"Overdue transactions: {len(overdue)}")
    assert len(overdue) == 1, "Should have 1 overdue transaction"
    assert overdue[0]["tx_id"] == tx_id

    # Display overdue summary
    print("\n=== Test 3: Overdue transactions summary ===")
    log_overdue_transactions_summary(provider, quiet=False)

    # Verify overdue event was emitted
    events = orch.get_tick_events(3)
    overdue_events = [e for e in events if e.get("event_type") == "TransactionWentOverdue"]
    print(f"\nTransactionWentOverdue events: {len(overdue_events)}")
    assert len(overdue_events) == 1, "Should have TransactionWentOverdue event"

    print("\n=== TEST PASSED ===")
    print("All overdue display functions work correctly!")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "-s"])
