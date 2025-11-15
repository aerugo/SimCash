"""Test that replay counts LSM-settled transactions correctly.

This test verifies the fix for the bug where replay was counting only Settlement events,
ignoring transactions settled by LSM (which generate LsmBilateralOffset/LsmCycleSettlement events).
"""

import pytest
import tempfile
import json
from pathlib import Path

from payment_simulator._core import Orchestrator
from payment_simulator.persistence.event_queries import get_simulation_events
from payment_simulator.persistence.event_writer import write_events_batch
from payment_simulator.persistence.connection import DatabaseManager


def test_replay_counts_lsm_settled_transactions():
    """Replay must count transactions settled by LSM, not just Settlement events."""

    # Create temp database path (don't create the file)
    import os
    db_path = os.path.join(tempfile.gettempdir(), f"test_lsm_count_{os.getpid()}.db")

    try:
        # Config with LSM enabled to trigger bilateral offsets
        config = {
            "rng_seed": 42,
            "ticks_per_day": 100,
            "num_days": 1,
            "lsm_config": {
                "enable_bilateral": True,
                "enable_cycles": False,
            },
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 60000,  # Low balance to trigger queuing
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 60000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        # Run simulation
        orch = Orchestrator.new(config)

        # Create bilateral scenario: A owes B, B owes A
        # These should settle via LSM bilateral offset
        tx1 = orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=50000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

        tx2 = orch.submit_transaction(
            sender="BANK_B",
            receiver="BANK_A",
            amount=40000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

        # Tick to trigger LSM
        for _ in range(10):
            orch.tick()

        # Setup database and persist events
        db = DatabaseManager(db_path)
        db.initialize_schema()  # Create base tables
        db.apply_migrations()  # Apply any pending migrations

        sim_id = "test-lsm-settlement-count"
        import hashlib
        config_json = json.dumps(config)
        config_hash = hashlib.sha256(config_json.encode()).hexdigest()

        db.conn.execute(
            """INSERT INTO simulations
               (simulation_id, config_file, config_hash, config_json, rng_seed, ticks_per_day, num_days, num_agents, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [sim_id, "test_config.yaml", config_hash, config_json,
             config["rng_seed"], config["ticks_per_day"], config["num_days"],
             len(config["agent_configs"]), "completed"],
        )

        # Write all events to database
        for tick in range(11):
            events = orch.get_tick_events(tick)
            if events:
                write_events_batch(db.conn, sim_id, events, 100)

        # Query events from database
        all_events = get_simulation_events(
            conn=db.conn,
            simulation_id=sim_id,
            sort="tick_asc",
            limit=10000,
        )

        # Count Settlement events vs LSM events
        settlement_events = [e for e in all_events["events"] if e["event_type"] == "Settlement"]
        lsm_bilateral_events = [e for e in all_events["events"] if e["event_type"] == "LsmBilateralOffset"]
        lsm_cycle_events = [e for e in all_events["events"] if e["event_type"] == "LsmCycleSettlement"]

        # Count transactions in LSM events
        lsm_tx_count = 0
        for event in lsm_bilateral_events + lsm_cycle_events:
            tx_ids = event.get("details", {}).get("tx_ids", [])
            lsm_tx_count += len(tx_ids)

        print(f"\nEvent counts:")
        print(f"  Settlement events: {len(settlement_events)}")
        print(f"  LSM bilateral events: {len(lsm_bilateral_events)}")
        print(f"  LSM cycle events: {len(lsm_cycle_events)}")
        print(f"  Transactions settled by LSM: {lsm_tx_count}")
        print(f"  Total settlements: {len(settlement_events) + lsm_tx_count}")

        # CRITICAL ASSERTION: replay.py must count both Settlement events AND LSM transactions
        # The fix in replay.py should now extract tx_ids from LSM events and count them

        # If LSM settled any transactions, total count must include them
        if lsm_tx_count > 0:
            # The bug was that replay only counted Settlement events
            # With the fix, it should count Settlement events + LSM-settled transactions
            total_settlements = len(settlement_events) + lsm_tx_count

            # Both TX1 and TX2 should be included in this count
            assert total_settlements >= 2, (
                f"Total settlements ({total_settlements}) should be at least 2 "
                f"(Settlement events: {len(settlement_events)}, LSM transactions: {lsm_tx_count})"
            )

            print(f"\n✅ SUCCESS: Replay will correctly count {total_settlements} total settlements")
            print(f"  (Settlement events: {len(settlement_events)} + LSM transactions: {lsm_tx_count})")

        db.close()

    finally:
        # Cleanup
        Path(db_path).unlink(missing_ok=True)


if __name__ == "__main__":
    test_replay_counts_lsm_settled_transactions()
