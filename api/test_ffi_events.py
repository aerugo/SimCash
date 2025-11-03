#!/usr/bin/env python3
"""
Quick test of new get_all_events() FFI method.
"""

from payment_simulator._core import Orchestrator

# Create simple test configuration
config = {
    "rng_seed": 42,
    "ticks_per_day": 10,
    "num_days": 1,
    "agent_configs": [
        {
            "id": "BANK_A",
            "opening_balance": 1_000_000,
            "credit_limit": 0,
            "policy": {"type": "Fifo"},
        },
        {
            "id": "BANK_B",
            "opening_balance": 1_000_000,
            "credit_limit": 0,
            "policy": {"type": "Fifo"},
        },
    ],
}

print("Creating orchestrator...")
orch = Orchestrator.new(config)

print("Submitting test transaction...")
orch.submit_transaction(
    sender="BANK_A",
    receiver="BANK_B",
    amount=100_000,
    deadline_tick=50,
    priority=5,
    divisible=False,
)

print("Running one tick...")
result = orch.tick()
print(f"Tick result: {result['num_settlements']} settlements")

print("\nCalling get_all_events()...")
events = orch.get_all_events()

print(f"✓ Got {len(events)} events")
print("\nFirst 10 events:")
for i, event in enumerate(events[:10]):
    event_type = event.get("event_type")
    tick = event.get("tick")

    # Build detail string based on event type
    if event_type == "Arrival":
        detail = f"{event.get('sender_id')} → {event.get('receiver_id')}: ${event.get('amount') / 100:.2f}"
    elif event_type in ("PolicySubmit", "PolicyHold"):
        detail = f"agent={event.get('agent_id')}, tx={event.get('tx_id')[:8]}..."
    elif event_type == "Settlement":
        detail = f"{event.get('sender_id')} → {event.get('receiver_id')}: ${event.get('amount') / 100:.2f}"
    elif event_type == "CostAccrual":
        costs = event.get('costs', {})
        total = costs.get('total', 0)
        detail = f"agent={event.get('agent_id')}, total=${total / 100:.2f}"
    else:
        detail = str(event)[:60]

    print(f"  {i+1}. Tick {tick:3d}: {event_type:20s} {detail}")

print(f"\n✓ FFI method works! Retrieved {len(events)} events.")
print("  Each event has:")
print(f"    - event_type: {events[0].get('event_type')}")
print(f"    - tick: {events[0].get('tick')}")
print("    - event-specific fields...")

print("\nReady to integrate with database persistence!")
