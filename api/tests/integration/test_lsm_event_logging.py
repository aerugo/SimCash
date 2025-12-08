"""TDD Test: LSM events must be logged for replay to work.

FAILING TEST demonstrating the bug:
- LSM cycles ARE detected and settled (proven by metrics)
- LSM events ARE NOT logged to event log (proven by database query)
- Replay shows 0 LSM cycles because events were never persisted

This test follows TDD principles:
1. Write failing test that demonstrates the bug
2. Implement minimal fix in Rust backend
3. Verify test passes
"""

import pytest
import tempfile
import os
from payment_simulator._core import Orchestrator
from payment_simulator.persistence.connection import DatabaseManager
from payment_simulator.persistence.event_queries import get_simulation_events


class TestLsmEventLogging:
    """Test that LSM cycles generate Event::LsmBilateralOffset and Event::LsmCycleSettlement."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.unlink(db_path)
        yield db_path
        if os.path.exists(db_path):
            os.unlink(db_path)
        wal_path = db_path + ".wal"
        if os.path.exists(wal_path):
            os.unlink(wal_path)

    def test_lsm_bilateral_offset_events_are_logged(self, temp_db):
        """FAILING TEST: When LSM bilateral offset occurs, Event::LsmBilateralOffset should be logged.

        Configuration designed to trigger bilateral offsets:
        - 2 agents with tight liquidity (forcing queueing)
        - Transactions configured to create A→B and B→A pattern
        - LSM enabled to detect and settle bilateral offsets

        Expected behavior:
        1. Transactions queue due to insufficient liquidity
        2. LSM detects bilateral offset opportunities
        3. Events logged: Event::LsmBilateralOffset for each bilateral settlement
        4. Events persisted to simulation_events table
        5. Replay can reconstruct LSM cycles from persisted events

        Current behavior (BUG):
        - LSM bilateral offsets ARE detected and settled (metrics show this)
        - NO LsmBilateralOffset events are logged (event log is empty)
        - Database has 0 LSM events in simulation_events table
        - Replay shows 0 LSM cycles despite run showing 21
        """
        # Configuration designed to trigger LSM bilateral offsets
        config = {
            "rng_seed": 42,
            "ticks_per_day": 100,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100000,  # $1,000 - insufficient for $3,000 payment
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 100000,  # $1,000 - insufficient for $3,000 payment
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
            "lsm_config": {
                "enable_bilateral": True,
                "enable_cycles": True,
            },
        }

        # Run simulation
        orch = Orchestrator.new(config)

        # Submit transactions designed to create bilateral offset
        # A→B for $3,000 and B→A for $3,000 should offset
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=300000,
            deadline_tick=10,
            priority=5,
            divisible=False,
        )
        orch.submit_transaction(
            sender="BANK_B",
            receiver="BANK_A",
            amount=300000,
            deadline_tick=10,
            priority=5,
            divisible=False,
        )

        # Execute tick to process submissions - LSM should detect and settle
        result = orch.tick()

        # Note: Settlement count may vary depending on LSM timing,
        # but LSM events should be logged regardless

        # ═══════════════════════════════════════════════════════════
        # CRITICAL TEST: Check that LSM events were logged
        # ═══════════════════════════════════════════════════════════
        all_events = orch.get_all_events()

        # Filter for LSM events
        lsm_events = [
            e for e in all_events
            if e.get("event_type") in ["LsmBilateralOffset", "LsmCycleSettlement"]
        ]

        # THIS WILL FAIL because LSM events are NOT logged in simulator/src/settlement/lsm.rs
        assert len(lsm_events) > 0, (
            f"Expected at least 1 LSM event in event log, but found {len(lsm_events)}. "
            f"LSM bilateral offset occurred (queues are empty), but no events were logged. "
            f"This is the ROOT CAUSE of replay identity failure."
        )

        # Verify the LSM event has correct structure
        lsm_event = lsm_events[0]
        assert lsm_event["event_type"] == "LsmBilateralOffset"
        assert lsm_event["agent_a"] in ["BANK_A", "BANK_B"]
        assert lsm_event["agent_b"] in ["BANK_A", "BANK_B"]
        assert lsm_event["amount_a"] == 300000
        assert lsm_event["amount_b"] == 300000

    def test_lsm_events_are_persisted_to_database(self, temp_db):
        """FAILING TEST: LSM events should be persisted to simulation_events table.

        This test verifies the full persistence pipeline:
        1. LSM events logged in Rust backend
        2. Events retrieved via FFI (get_all_events)
        3. Events written to database by PersistenceManager
        4. Events queryable for replay

        Current behavior (BUG):
        - No LSM events in event log → no events persisted
        - simulation_events table has 0 LSM events
        - Replay cannot reconstruct LSM cycles
        """
        config = {
            "rng_seed": 42,
            "ticks_per_day": 100,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100000,  # $1,000 - insufficient for $3,000 payment
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 100000,  # $1,000 - insufficient for $3,000 payment
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
            "lsm_config": {
                "enable_bilateral": True,
                "enable_cycles": True,
            },
        }

        # Setup database
        db_manager = DatabaseManager(temp_db)
        db_manager.initialize_schema()

        # Run simulation with LSM
        orch = Orchestrator.new(config)
        orch.submit_transaction("BANK_A", "BANK_B", 300000, 10, 5, False)
        orch.submit_transaction("BANK_B", "BANK_A", 300000, 10, 5, False)
        orch.tick()  # Process submissions and settlement

        # Persist events to database
        from payment_simulator.persistence.event_writer import write_events_batch

        events = orch.get_all_events()
        event_count = write_events_batch(
            conn=db_manager.conn,
            simulation_id="test-lsm-001",
            events=events,
            ticks_per_day=100,
        )

        print(f"Persisted {event_count} events to database")

        # Query LSM events from database
        result = get_simulation_events(
            conn=db_manager.conn,
            simulation_id="test-lsm-001",
            event_type="LsmBilateralOffset",
        )

        lsm_events = result["events"]

        # THIS WILL FAIL because no LSM events were logged
        assert len(lsm_events) > 0, (
            f"Expected at least 1 LsmBilateralOffset event in database, found {len(lsm_events)}. "
            f"Total events persisted: {event_count}. "
            f"This proves LSM events are not being logged in the Rust backend."
        )

        # Verify event structure is correct for replay
        lsm_event = lsm_events[0]
        assert lsm_event["event_type"] == "LsmBilateralOffset"
        assert "details" in lsm_event
        details = lsm_event["details"]
        assert "agent_a" in details
        assert "agent_b" in details
        assert "amount_a" in details
        assert "amount_b" in details

        db_manager.close()

    def test_lsm_multilateral_cycle_events_are_logged(self, temp_db):
        """FAILING TEST: When LSM multilateral cycle occurs, Event::LsmCycleSettlement should be logged.

        Configuration designed to trigger multilateral cycles:
        - 3 agents with tight liquidity
        - Ring pattern: A→B→C→A
        - LSM detects cycle and settles all 3 transactions simultaneously

        Expected behavior:
        - Event::LsmCycleSettlement logged with cycle details
        - Event includes: tx_ids (all 3), cycle_value (settled amount)

        Current behavior (BUG):
        - NO LsmCycleSettlement events logged
        """
        config = {
            "rng_seed": 42,
            "ticks_per_day": 100,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100000,  # $1,000 - insufficient for $2,000 payment
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 100000,  # $1,000 - insufficient for $2,000 payment
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_C",
                    "opening_balance": 100000,  # $1,000 - insufficient for $2,000 payment
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
            "lsm_config": {
                "enable_bilateral": True,
                "enable_cycles": True,
            },
        }

        # Run simulation
        orch = Orchestrator.new(config)

        # Create ring cycle: A→B→C→A
        orch.submit_transaction("BANK_A", "BANK_B", 200000, 10, 5, False)  # A→B $2,000
        orch.submit_transaction("BANK_B", "BANK_C", 200000, 10, 5, False)  # B→C $2,000
        orch.submit_transaction("BANK_C", "BANK_A", 200000, 10, 5, False)  # C→A $2,000

        orch.tick()  # Process submissions - LSM should detect cycle and settle

        # All queues should be empty after LSM cycle settlement
        assert orch.get_queue1_size("BANK_A") == 0
        assert orch.get_queue1_size("BANK_B") == 0
        assert orch.get_queue1_size("BANK_C") == 0

        # Check event log
        all_events = orch.get_all_events()
        lsm_cycle_events = [
            e for e in all_events
            if e.get("event_type") == "LsmCycleSettlement"
        ]

        # THIS WILL FAIL - no cycle events logged
        assert len(lsm_cycle_events) > 0, (
            f"Expected at least 1 LsmCycleSettlement event, found {len(lsm_cycle_events)}. "
            f"Multilateral cycle WAS settled (all queues empty), but event was not logged."
        )

        # Verify event structure
        cycle_event = lsm_cycle_events[0]
        assert cycle_event["event_type"] == "LsmCycleSettlement"
        assert len(cycle_event["tx_ids"]) == 3, "Cycle should involve 3 transactions"
        assert cycle_event["cycle_value"] == 600000, "Cycle value should be $6,000 (sum of 3 × $2,000)"
