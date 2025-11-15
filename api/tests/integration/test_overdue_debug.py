"""Debug test to understand transaction state during ticks."""

from payment_simulator._core import Orchestrator


def test_debug_transaction_state():
    """Debug: Track transaction state through ticks."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {"id": "A", "opening_balance": 0, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "B", "opening_balance": 100_000_00, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
        "cost_rates": {
            "deadline_penalty": 50_000_00,
        },
    }

    orch = Orchestrator.new(config)

    print(f"\n=== Initial state (tick 0) ===")
    print(f"Current tick: {orch.current_tick()}")

    # Create transaction with deadline at tick 2
    tx_id = orch.submit_transaction(
        sender="A",
        receiver="B",
        amount=10_000_00,
        deadline_tick=2,
        priority=5,
        divisible=False,
    )

    print(f"Created transaction: {tx_id}")
    print(f"Deadline tick: 2")

    # Check events after submission
    events = orch.get_tick_events(0)
    print(f"Tick 0 events: {[e.get('event_type') for e in events]}")

    # Tick 1
    orch.tick()
    print(f"\n=== After tick 1 ===")
    print(f"Current tick: {orch.current_tick()}")
    events = orch.get_tick_events(1)
    print(f"Tick 1 events: {[e.get('event_type') for e in events]}")

    # Tick 2 (deadline tick)
    orch.tick()
    print(f"\n=== After tick 2 (deadline tick) ===")
    print(f"Current tick: {orch.current_tick()}")
    events = orch.get_tick_events(2)
    print(f"Tick 2 events: {[e.get('event_type') for e in events]}")

    # Tick 3 (one tick past deadline - should detect and mark overdue)
    orch.tick()
    print(f"\n=== After tick 3 (one tick past deadline) ===")
    print(f"Current tick: {orch.current_tick()}")
    events = orch.get_tick_events(3)
    print(f"Tick 3 events: {[e.get('event_type') for e in events]}")

    # Note: Processing happens at tick N, but current_tick() returns N+1 after advance
    # So we need to check tick 2 (the processing tick) for overdue detection
    # Actually, at tick 2, current_tick IN THE PROCESSING is 2, which is NOT > deadline (2)
    # At tick 3, current_tick IN THE PROCESSING is 3, which IS > deadline (2)
    # So we need to check tick 3 for overdue events

    overdue_events = [e for e in events if e.get("event_type") == "TransactionWentOverdue"]
    print(f"TransactionWentOverdue events: {len(overdue_events)}")

    if overdue_events:
        print(f"Overdue event details: {overdue_events[0]}")

    # Wait - we haven't PROCESSED tick 3 yet! We need another tick() call
    print(f"\n=== Processing tick 3 (fourth tick() call) ===")
    orch.tick()
    print(f"Current tick after 4th tick(): {orch.current_tick()}")
    events_tick3 = orch.get_tick_events(3)
    print(f"Tick 3 events: {[e.get('event_type') for e in events_tick3]}")

    overdue_events_tick3 = [e for e in events_tick3 if e.get("event_type") == "TransactionWentOverdue"]
    print(f"TransactionWentOverdue events at tick 3: {len(overdue_events_tick3)}")
    if overdue_events_tick3:
        print(f"FOUND IT! Overdue event: {overdue_events_tick3[0]}")

    # Check overdue transactions query
    overdue = orch.get_overdue_transactions()
    print(f"Overdue transactions count: {len(overdue)}")
    if overdue:
        print(f"Overdue transaction: {overdue[0]}")

    # Get all events to see full history
    all_events = orch.get_all_events()
    print(f"\n=== All events summary ===")
    event_counts = {}
    for e in all_events:
        etype = e.get('event_type', 'unknown')
        event_counts[etype] = event_counts.get(etype, 0) + 1
    for etype, count in sorted(event_counts.items()):
        print(f"  {etype}: {count}")

    # Print CostAccrual events to see details
    print(f"\n=== CostAccrual events details ===")
    cost_events = [e for e in all_events if e.get('event_type') == 'CostAccrual']
    for e in cost_events:
        print(f"Tick {e['tick']}: agent={e['agent_id']}, penalty_cost={e['costs'].get('penalty_cost', 0)}")

    # Print ALL events at tick 3
    print(f"\n=== All tick 3 events ===")
    tick3_events = [e for e in all_events if e.get('tick') == 3]
    for e in tick3_events:
        print(f"  {e.get('event_type')}: {e}")


if __name__ == "__main__":
    test_debug_transaction_state()
