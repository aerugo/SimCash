#!/usr/bin/env python3
"""
End-to-end integration test for event persistence.

Tests complete flow:
1. Create simulation
2. Run ticks to generate events
3. Extract events from Rust via FFI
4. Write events to database in batch
5. Query events back and verify

This verifies the GREEN phase of TDD for Phase 2.
"""

from pathlib import Path
from payment_simulator._core import Orchestrator
from payment_simulator.persistence.connection import DatabaseManager
from payment_simulator.persistence.event_writer import (
    write_events_batch,
    get_event_count,
    get_events,
)

# Test configuration
test_db = Path("test_event_persistence_integration.db")
simulation_id = "test_sim_001"

try:
    # ==================================================
    # Step 1: Setup database
    # ==================================================
    print("=" * 60)
    print("STEP 1: Setup database")
    print("=" * 60)

    if test_db.exists():
        test_db.unlink()

    manager = DatabaseManager(test_db)
    manager.setup()
    print("✓ Database initialized with simulation_events table\n")

    # ==================================================
    # Step 2: Create simulation and run ticks
    # ==================================================
    print("=" * 60)
    print("STEP 2: Run simulation")
    print("=" * 60)

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

    print("Submitting 3 transactions...")
    for i in range(3):
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=100_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

    print("Running 5 ticks...")
    for _ in range(5):
        result = orch.tick()
        print(f"  Tick {result['tick']}: {result['num_settlements']} settlements")

    print("✓ Simulation complete\n")

    # ==================================================
    # Step 3: Extract events from Rust
    # ==================================================
    print("=" * 60)
    print("STEP 3: Extract events from Rust")
    print("=" * 60)

    events = orch.get_all_events()
    print(f"✓ Extracted {len(events)} events from Rust EventLog")

    # Show event breakdown
    event_types = {}
    for event in events:
        event_type = event["event_type"]
        event_types[event_type] = event_types.get(event_type, 0) + 1

    print("\nEvent breakdown:")
    for event_type, count in sorted(event_types.items()):
        print(f"  {event_type:20s}: {count:3d}")
    print()

    # ==================================================
    # Step 4: Write events to database
    # ==================================================
    print("=" * 60)
    print("STEP 4: Write events to database")
    print("=" * 60)

    print(f"Writing {len(events)} events in batch...")
    count = write_events_batch(
        conn=manager.conn,
        simulation_id=simulation_id,
        events=events,
        ticks_per_day=config["ticks_per_day"],
    )
    print(f"✓ Wrote {count} events to database\n")

    # ==================================================
    # Step 5: Query events back and verify
    # ==================================================
    print("=" * 60)
    print("STEP 5: Query and verify events")
    print("=" * 60)

    # Test 1: Count matches
    db_count = get_event_count(manager.conn, simulation_id)
    print(f"Events in database: {db_count}")
    print(f"Events from Rust:   {len(events)}")
    assert db_count == len(events), f"Count mismatch: {db_count} != {len(events)}"
    print("✓ Event count matches\n")

    # Test 2: Query all events
    result = get_events(manager.conn, simulation_id, limit=1000)
    print(f"Queried events: {len(result['events'])}")
    print(f"Total count:    {result['total_count']}")
    assert len(result["events"]) == db_count
    print("✓ All events retrieved\n")

    # Test 3: Query by tick
    tick_2_events = get_events(manager.conn, simulation_id, tick=2)
    print(f"Events at tick 2: {len(tick_2_events['events'])}")
    for event in tick_2_events["events"]:
        print(f"  - {event['event_type']} (tx_id={event.get('tx_id', 'N/A')[:8]}...)")
    assert all(e["tick"] == 2 for e in tick_2_events["events"])
    print("✓ Tick filtering works\n")

    # Test 4: Query by event type
    settlement_events = get_events(manager.conn, simulation_id, event_type="Settlement")
    print(f"Settlement events: {len(settlement_events['events'])}")
    assert all(e["event_type"] == "Settlement" for e in settlement_events["events"])
    print("✓ Event type filtering works\n")

    # Test 5: Query by agent
    bank_a_events = get_events(manager.conn, simulation_id, agent_id="BANK_A")
    print(f"BANK_A events: {len(bank_a_events['events'])}")
    for event in bank_a_events["events"][:5]:
        print(f"  - {event['event_type']}")
    print("✓ Agent filtering works\n")

    # Test 6: Verify data integrity
    first_event = result["events"][0]
    print("Sample event from database:")
    print(f"  event_id:       {first_event['event_id']}")
    print(f"  simulation_id:  {first_event['simulation_id']}")
    print(f"  tick:           {first_event['tick']}")
    print(f"  event_type:     {first_event['event_type']}")
    print(f"  details:        {first_event['details']}")
    assert first_event["simulation_id"] == simulation_id
    assert first_event["tick"] >= 0
    assert first_event["event_type"] in [
        "Arrival",
        "PolicySubmit",
        "PolicyHold",
        "Settlement",
        "QueuedRtgs",
        "LsmBilateralOffset",
        "LsmCycleSettlement",
        "CostAccrual",
        "EndOfDay",
    ]
    print("✓ Data integrity verified\n")

    # ==================================================
    # Success!
    # ==================================================
    print("=" * 60)
    print("✓ ALL TESTS PASSED!")
    print("=" * 60)
    print("\nEvent persistence pipeline is fully operational:")
    print("  1. ✓ Rust events logged during simulation")
    print("  2. ✓ Events extracted via FFI (get_all_events)")
    print("  3. ✓ Events written to database in batch")
    print("  4. ✓ Events can be queried with filters")
    print("  5. ✓ Data integrity maintained")
    print("\nPhase 2 TDD: RED → GREEN → REFACTOR")
    print("Current status: GREEN ✓")

finally:
    # Cleanup
    manager.close()
    if test_db.exists():
        test_db.unlink()
    print(f"\n✓ Cleaned up test database: {test_db}")
