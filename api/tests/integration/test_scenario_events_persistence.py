"""
TDD tests for scenario event persistence to simulation_events table.

Following TDD RED-GREEN-REFACTOR:
1. Write tests first (expecting failures)
2. Implement persistence hooks
3. Verify all tests pass
"""
import tempfile
from pathlib import Path
import duckdb
import pytest

from payment_simulator._core import Orchestrator
from payment_simulator.persistence.connection import DatabaseManager
from payment_simulator.cli.execution.persistence import PersistenceManager
from payment_simulator.persistence.event_writer import write_events_batch


def _persist_events(orch: Orchestrator, db_manager: DatabaseManager, sim_id: str, ticks_per_day: int):
    """Helper to persist events to database."""
    events = orch.get_all_events()
    write_events_batch(
        conn=db_manager.get_connection(),
        simulation_id=sim_id,
        events=events,
        ticks_per_day=ticks_per_day,
    )


def test_scenario_event_persisted_to_database():
    """
    Test that ScenarioEventExecuted events are written to simulation_events table.

    TDD RED: This test should initially fail if persistence isn't hooked up.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()  # Create database tables
        sim_id = "test-scenario-persistence"

        # Config with one DirectTransfer event
        config = {
            "rng_seed": 12345,
            "ticks_per_day": 100,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
            "scenario_events": [
                {
                    "type": "DirectTransfer",
                    "from_agent": "BANK_A",
                    "to_agent": "BANK_B",
                    "amount": 100_000,
                    "schedule": "OneTime",
                    "tick": 10,
                }
            ],
        }

        # Create orchestrator and persistence manager
        orch = Orchestrator.new(config)
        persistence = PersistenceManager(db_manager, sim_id, full_replay=True)

        # Persist initial snapshots
        persistence.persist_initial_snapshots(orch)

        # Run simulation through tick 15 (past the event at tick 10)
        for tick in range(16):
            orch.tick()
            persistence.on_tick_complete(tick, orch)

        # Verify balances changed (sanity check)
        assert orch.get_agent_balance("BANK_A") == 900_000
        assert orch.get_agent_balance("BANK_B") == 1_100_000

        # Write events to database
        _persist_events(orch, db_manager, sim_id, 100)

        # Query simulation_events table for ScenarioEventExecuted
        conn = db_manager.get_connection()
        events = conn.execute("""
            SELECT event_type, tick, details, agent_id
            FROM simulation_events
            WHERE simulation_id = ?
              AND event_type = 'ScenarioEventExecuted'
            ORDER BY tick
        """, [sim_id]).fetchall()

        # Verify at least one scenario event was persisted
        assert len(events) > 0, "ScenarioEventExecuted events should be persisted"

        # Verify the event has correct structure
        event = events[0]
        assert event[0] == "ScenarioEventExecuted"  # event_type
        assert event[1] == 10  # tick
        # details is JSON string, should contain scenario_event_type
        import json
        details = json.loads(event[2])
        assert "scenario_event_type" in details or "event_type" in details


def test_multiple_scenario_events_persisted():
    """
    Test that multiple scenario events are all persisted correctly.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()
        sim_id = "test-multi-events"

        config = {
            "rng_seed": 12345,
            "ticks_per_day": 100,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 500_000,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 500_000,
                    "policy": {"type": "Fifo"},
                },
            ],
            "scenario_events": [
                {
                    "type": "DirectTransfer",
                    "from_agent": "BANK_A",
                    "to_agent": "BANK_B",
                    "amount": 100_000,
                    "schedule": "OneTime",
                    "tick": 10,
                },
                {
                    "type": "CollateralAdjustment",
                    "agent": "BANK_A",
                    "delta": 200_000,
                    "schedule": "OneTime",
                    "tick": 20,
                },
                {
                    "type": "DirectTransfer",
                    "from_agent": "BANK_B",
                    "to_agent": "BANK_A",
                    "amount": 50_000,
                    "schedule": "OneTime",
                    "tick": 30,
                },
            ],
        }

        orch = Orchestrator.new(config)
        persistence = PersistenceManager(db_manager, sim_id, full_replay=True)
        persistence.persist_initial_snapshots(orch)

        # Run through tick 35
        for tick in range(36):
            orch.tick()
            persistence.on_tick_complete(tick, orch)

        # Write events to database
        _persist_events(orch, db_manager, sim_id, 100)

        # Query all scenario events
        conn = db_manager.get_connection()
        events = conn.execute("""
            SELECT tick, details
            FROM simulation_events
            WHERE simulation_id = ?
              AND event_type = 'ScenarioEventExecuted'
            ORDER BY tick
        """, [sim_id]).fetchall()

        # Should have 3 events
        assert len(events) == 3, f"Expected 3 scenario events, got {len(events)}"

        # Verify ticks
        ticks = [e[0] for e in events]
        assert ticks == [10, 20, 30], f"Expected ticks [10, 20, 30], got {ticks}"


def test_repeating_scenario_events_persisted():
    """
    Test that repeating scenario events are persisted for each execution.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()
        sim_id = "test-repeating"

        config = {
            "rng_seed": 12345,
            "ticks_per_day": 100,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
            "scenario_events": [
                {
                    "type": "DirectTransfer",
                    "from_agent": "BANK_A",
                    "to_agent": "BANK_B",
                    "amount": 10_000,
                    "schedule": "Repeating",
                    "start_tick": 10,
                    "interval": 10,
                }
            ],
        }

        orch = Orchestrator.new(config)
        persistence = PersistenceManager(db_manager, sim_id, full_replay=True)
        persistence.persist_initial_snapshots(orch)

        # Run through tick 45 (should execute at ticks 10, 20, 30, 40)
        for tick in range(46):
            orch.tick()
            persistence.on_tick_complete(tick, orch)

        # Write events to database
        _persist_events(orch, db_manager, sim_id, 100)

        # Query all scenario events
        conn = db_manager.get_connection()
        events = conn.execute("""
            SELECT tick
            FROM simulation_events
            WHERE simulation_id = ?
              AND event_type = 'ScenarioEventExecuted'
            ORDER BY tick
        """, [sim_id]).fetchall()

        # Should have 4 executions (ticks 10, 20, 30, 40)
        ticks = [e[0] for e in events]
        assert len(ticks) == 4, f"Expected 4 executions, got {len(ticks)}"
        assert ticks == [10, 20, 30, 40], f"Expected [10, 20, 30, 40], got {ticks}"


def test_scenario_event_details_structure():
    """
    Test that persisted scenario events have correct details structure.

    Details should include:
    - scenario_event_type (or event_type): The inner event type
    - Event-specific fields (from_agent, to_agent, amount, etc.)
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()
        sim_id = "test-details"

        config = {
            "rng_seed": 12345,
            "ticks_per_day": 100,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 500_000,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
            "scenario_events": [
                {
                    "type": "DirectTransfer",
                    "from_agent": "BANK_A",
                    "to_agent": "BANK_B",
                    "amount": 100_000,
                    "schedule": "OneTime",
                    "tick": 10,
                },
                {
                    "type": "CollateralAdjustment",
                    "agent": "BANK_A",
                    "delta": 200_000,
                    "schedule": "OneTime",
                    "tick": 20,
                },
            ],
        }

        orch = Orchestrator.new(config)
        persistence = PersistenceManager(db_manager, sim_id, full_replay=True)
        persistence.persist_initial_snapshots(orch)

        for tick in range(25):
            orch.tick()
            persistence.on_tick_complete(tick, orch)

        # Write events to database
        _persist_events(orch, db_manager, sim_id, 100)

        # Query events with details
        conn = db_manager.get_connection()
        events = conn.execute("""
            SELECT tick, details
            FROM simulation_events
            WHERE simulation_id = ?
              AND event_type = 'ScenarioEventExecuted'
            ORDER BY tick
        """, [sim_id]).fetchall()

        assert len(events) == 2

        import json

        # Check DirectTransfer event details
        transfer_outer = json.loads(events[0][1])
        assert "scenario_event_type" in transfer_outer
        assert "details_json" in transfer_outer

        transfer_details = json.loads(transfer_outer["details_json"])
        assert transfer_details["from_agent"] == "BANK_A"
        assert transfer_details["to_agent"] == "BANK_B"
        assert transfer_details["amount"] == 100_000

        # Check CollateralAdjustment event details
        collateral_outer = json.loads(events[1][1])
        assert "scenario_event_type" in collateral_outer
        assert "details_json" in collateral_outer

        collateral_details = json.loads(collateral_outer["details_json"])
        assert collateral_details["agent"] == "BANK_A"
        assert collateral_details["delta"] == 200_000


def test_scenario_events_queryable_by_tick():
    """
    Test that scenario events can be queried by tick for replay.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()
        sim_id = "test-query"

        config = {
            "rng_seed": 12345,
            "ticks_per_day": 100,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
            "scenario_events": [
                {
                    "type": "DirectTransfer",
                    "from_agent": "BANK_A",
                    "to_agent": "BANK_B",
                    "amount": 100_000,
                    "schedule": "OneTime",
                    "tick": 10,
                },
                {
                    "type": "DirectTransfer",
                    "from_agent": "BANK_B",
                    "to_agent": "BANK_A",
                    "amount": 50_000,
                    "schedule": "OneTime",
                    "tick": 10,  # Same tick
                },
            ],
        }

        orch = Orchestrator.new(config)
        persistence = PersistenceManager(db_manager, sim_id, full_replay=True)
        persistence.persist_initial_snapshots(orch)

        for tick in range(15):
            orch.tick()
            persistence.on_tick_complete(tick, orch)

        # Write events to database
        _persist_events(orch, db_manager, sim_id, 100)

        # Query events for tick 10 specifically
        conn = db_manager.get_connection()
        tick_10_events = conn.execute("""
            SELECT event_type, details
            FROM simulation_events
            WHERE simulation_id = ?
              AND tick = 10
              AND event_type = 'ScenarioEventExecuted'
        """, [sim_id]).fetchall()

        # Should have both events at tick 10
        assert len(tick_10_events) == 2, f"Expected 2 events at tick 10, got {len(tick_10_events)}"

        # Query events for tick 11 (should be empty)
        tick_11_events = conn.execute("""
            SELECT event_type
            FROM simulation_events
            WHERE simulation_id = ?
              AND tick = 11
              AND event_type = 'ScenarioEventExecuted'
        """, [sim_id]).fetchall()

        assert len(tick_11_events) == 0, "Tick 11 should have no scenario events"
