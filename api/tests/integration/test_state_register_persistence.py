"""
Phase 4.5: State Register Persistence Tests

Tests for state register persistence and replay.

This test suite verifies:
1. agent_state_registers table exists and has correct schema
2. StateRegisterSet events are persisted to database
3. State registers can be queried for replay
4. Replay identity: run vs replay outputs are identical

Status: RED - Implementation in progress
Following plan: docs/plans/phase-4-5-persistence-replay-plan.md
"""

import pytest
import json
from pathlib import Path
from payment_simulator.persistence.connection import DatabaseManager


@pytest.fixture
def db_path(tmp_path, request):
    """Create unique database for each test."""
    test_name = request.node.name
    db_file = tmp_path / f"{test_name}.db"
    return db_file


class TestAgentStateRegistersTableSchema:
    """Test that agent_state_registers table exists with correct schema.

    RED: Table does not exist yet.
    Next: Add table creation in models.py or migration
    """

    def test_agent_state_registers_table_exists(self, db_path):
        """Verify agent_state_registers table exists after setup.

        RED: Table not yet created.
        """
        manager = DatabaseManager(db_path)
        manager.setup()

        # Query information_schema to check if table exists (DuckDB compatible)
        result = manager.conn.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_name = 'agent_state_registers'
        """).fetchone()

        assert result is not None, "agent_state_registers table should exist after setup"
        assert result[0] == "agent_state_registers"

        manager.close()

    def test_agent_state_registers_table_has_required_columns(self, db_path):
        """Verify agent_state_registers table has all required columns.

        RED: Table doesn't exist yet.
        """
        manager = DatabaseManager(db_path)
        manager.setup()

        # Query information_schema for columns (DuckDB compatible)
        columns = manager.conn.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'agent_state_registers'
        """).fetchall()

        # Extract column names
        column_names = [col[0] for col in columns]

        # Required columns per plan document
        required_columns = [
            "simulation_id",
            "tick",
            "agent_id",
            "register_key",
            "register_value",
        ]

        for col in required_columns:
            assert col in column_names, f"Column '{col}' should exist in agent_state_registers table"

        manager.close()

    def test_agent_state_registers_table_has_primary_key(self, db_path):
        """Verify table has composite primary key.

        RED: Table doesn't exist yet.
        """
        manager = DatabaseManager(db_path)
        manager.setup()

        # DuckDB: Check constraints for primary key
        # Note: DuckDB information_schema differs from standard SQL
        # We verify by attempting to insert duplicate rows
        manager.conn.execute("""
            INSERT INTO agent_state_registers
            (simulation_id, tick, agent_id, register_key, register_value)
            VALUES ('sim1', 10, 'BANK_A', 'bank_state_cooldown', 42.0)
        """)

        # Attempting to insert duplicate should fail
        with pytest.raises(Exception):  # DuckDB raises constraint violation
            manager.conn.execute("""
                INSERT INTO agent_state_registers
                (simulation_id, tick, agent_id, register_key, register_value)
                VALUES ('sim1', 10, 'BANK_A', 'bank_state_cooldown', 99.0)
            """)

        manager.close()

    def test_agent_state_registers_table_has_index(self, db_path):
        """Verify table has index on (simulation_id, agent_id, tick).

        RED: Table doesn't exist yet.
        """
        manager = DatabaseManager(db_path)
        manager.setup()

        # DuckDB: Query duckdb_indexes system table
        indexes = manager.conn.execute("""
            SELECT index_name FROM duckdb_indexes()
            WHERE table_name = 'agent_state_registers'
        """).fetchall()

        index_names = [idx[0] for idx in indexes]

        # Should have idx_agent_state_tick index
        assert any('agent_state' in name or 'tick' in name for name in index_names), \
            "Should have index on agent_state_registers table"

        manager.close()


class TestStateRegisterEventPersistence:
    """Test StateRegisterSet event persistence to database.

    RED: EventWriter doesn't handle StateRegisterSet yet.
    Next: Extend EventWriter to persist to both tables
    """

    def test_state_register_set_event_persists_to_simulation_events(self, db_path):
        """Verify StateRegisterSet events are written to simulation_events.

        RED: EventWriter doesn't handle this event type yet.
        """
        from payment_simulator.persistence.event_writer import write_events_batch

        manager = DatabaseManager(db_path)
        manager.setup()

        # Create StateRegisterSet event
        events = [
            {
                "event_type": "StateRegisterSet",
                "tick": 10,
                "agent_id": "BANK_A",
                "register_key": "bank_state_cooldown",
                "old_value": 0.0,
                "new_value": 42.0,
                "reason": "policy_action",
            }
        ]

        # Write events
        count = write_events_batch(manager.conn, "sim1", events, ticks_per_day=100)
        assert count == 1

        # Verify event in simulation_events table
        result = manager.conn.execute("""
            SELECT event_type, tick, agent_id, details
            FROM simulation_events
            WHERE simulation_id = 'sim1' AND event_type = 'StateRegisterSet'
        """).fetchone()

        assert result is not None, "StateRegisterSet event should be in simulation_events"
        assert result[0] == "StateRegisterSet"
        assert result[1] == 10
        assert result[2] == "BANK_A"

        # Verify details JSON contains all fields
        import json
        details = json.loads(result[3])
        assert details["register_key"] == "bank_state_cooldown"
        assert details["old_value"] == 0.0
        assert details["new_value"] == 42.0
        assert details["reason"] == "policy_action"

        manager.close()

    def test_state_register_set_event_persists_to_agent_state_registers(self, db_path):
        """Verify StateRegisterSet events are ALSO written to agent_state_registers.

        RED: EventWriter doesn't handle dual-write yet.
        """
        from payment_simulator.persistence.event_writer import write_events_batch

        manager = DatabaseManager(db_path)
        manager.setup()

        # Create StateRegisterSet event
        events = [
            {
                "event_type": "StateRegisterSet",
                "tick": 10,
                "agent_id": "BANK_A",
                "register_key": "bank_state_cooldown",
                "old_value": 0.0,
                "new_value": 42.0,
                "reason": "policy_action",
            }
        ]

        # Write events
        count = write_events_batch(manager.conn, "sim1", events, ticks_per_day=100)
        assert count == 1

        # Verify event ALSO in agent_state_registers table
        result = manager.conn.execute("""
            SELECT simulation_id, tick, agent_id, register_key, register_value
            FROM agent_state_registers
            WHERE simulation_id = 'sim1' AND agent_id = 'BANK_A'
        """).fetchone()

        assert result is not None, "StateRegisterSet should ALSO be in agent_state_registers"
        assert result[0] == "sim1"
        assert result[1] == 10
        assert result[2] == "BANK_A"
        assert result[3] == "bank_state_cooldown"
        assert result[4] == 42.0

        manager.close()

    def test_state_register_eod_reset_events_persist(self, db_path):
        """Verify EOD reset events (reason='eod_reset') persist correctly.

        RED: Not implemented yet.
        """
        from payment_simulator.persistence.event_writer import write_events_batch

        manager = DatabaseManager(db_path)
        manager.setup()

        # Create EOD reset events (when registers reset to 0)
        events = [
            {
                "event_type": "StateRegisterSet",
                "tick": 100,  # End of day
                "agent_id": "BANK_A",
                "register_key": "bank_state_cooldown",
                "old_value": 42.0,
                "new_value": 0.0,
                "reason": "eod_reset",
            },
            {
                "event_type": "StateRegisterSet",
                "tick": 100,
                "agent_id": "BANK_A",
                "register_key": "bank_state_counter",
                "old_value": 10.0,
                "new_value": 0.0,
                "reason": "eod_reset",
            },
        ]

        # Write events
        count = write_events_batch(manager.conn, "sim1", events, ticks_per_day=100)
        assert count == 2

        # Verify both EOD reset events in simulation_events
        result = manager.conn.execute("""
            SELECT COUNT(*)
            FROM simulation_events
            WHERE simulation_id = 'sim1'
              AND event_type = 'StateRegisterSet'
              AND tick = 100
        """).fetchone()

        assert result[0] == 2, "Both EOD reset events should be in simulation_events"

        # Verify both events in agent_state_registers
        result = manager.conn.execute("""
            SELECT COUNT(*)
            FROM agent_state_registers
            WHERE simulation_id = 'sim1'
              AND agent_id = 'BANK_A'
              AND tick = 100
        """).fetchone()

        assert result[0] == 2, "Both EOD reset events should be in agent_state_registers"

        manager.close()

    def test_multiple_agents_state_registers_independent(self, db_path):
        """Verify different agents have independent state registers in database.

        RED: Not implemented yet.
        """
        from payment_simulator.persistence.event_writer import write_events_batch

        manager = DatabaseManager(db_path)
        manager.setup()

        # Create events for multiple agents with same register key
        events = [
            {
                "event_type": "StateRegisterSet",
                "tick": 10,
                "agent_id": "BANK_A",
                "register_key": "bank_state_cooldown",
                "old_value": 0.0,
                "new_value": 100.0,
                "reason": "policy_action",
            },
            {
                "event_type": "StateRegisterSet",
                "tick": 10,
                "agent_id": "BANK_B",
                "register_key": "bank_state_cooldown",
                "old_value": 0.0,
                "new_value": 200.0,
                "reason": "policy_action",
            },
        ]

        # Write events
        count = write_events_batch(manager.conn, "sim1", events, ticks_per_day=100)
        assert count == 2

        # Verify BANK_A has value 100.0
        result = manager.conn.execute("""
            SELECT register_value
            FROM agent_state_registers
            WHERE simulation_id = 'sim1'
              AND agent_id = 'BANK_A'
              AND register_key = 'bank_state_cooldown'
        """).fetchone()

        assert result is not None
        assert result[0] == 100.0

        # Verify BANK_B has value 200.0
        result = manager.conn.execute("""
            SELECT register_value
            FROM agent_state_registers
            WHERE simulation_id = 'sim1'
              AND agent_id = 'BANK_B'
              AND register_key = 'bank_state_cooldown'
        """).fetchone()

        assert result is not None
        assert result[0] == 200.0

        manager.close()


class TestStateRegisterRetrieval:
    """Test StateProvider can retrieve state registers for replay.

    RED: StateProvider.get_agent_state_registers() doesn't exist yet.
    Next: Implement method in DatabaseStateProvider
    """

    def test_state_provider_can_retrieve_registers_at_tick(self, db_path):
        """Verify StateProvider returns correct register values at specific tick.

        RED: Method doesn't exist yet.
        """
        from payment_simulator.persistence.event_writer import write_events_batch
        from payment_simulator.cli.execution.state_provider import DatabaseStateProvider

        manager = DatabaseManager(db_path)
        manager.setup()

        # Write StateRegisterSet events
        events = [
            {
                "event_type": "StateRegisterSet",
                "tick": 10,
                "agent_id": "BANK_A",
                "register_key": "bank_state_cooldown",
                "old_value": 0.0,
                "new_value": 42.0,
                "reason": "policy_action",
            },
            {
                "event_type": "StateRegisterSet",
                "tick": 10,
                "agent_id": "BANK_A",
                "register_key": "bank_state_counter",
                "old_value": 0.0,
                "new_value": 5.0,
                "reason": "policy_action",
            },
        ]
        write_events_batch(manager.conn, "sim1", events, ticks_per_day=100)

        # Create StateProvider
        provider = DatabaseStateProvider(
            conn=manager.conn,
            simulation_id="sim1",
            tick=10,
            tx_cache={},
            agent_states={},
            queue_snapshots={},
        )

        # Get registers for BANK_A at tick 10
        registers = provider.get_agent_state_registers("BANK_A", 10)

        assert isinstance(registers, dict)
        assert registers["bank_state_cooldown"] == 42.0
        assert registers["bank_state_counter"] == 5.0

        manager.close()

    def test_state_provider_returns_most_recent_values(self, db_path):
        """Verify StateProvider returns most recent value for each register up to tick.

        For example, if register set at tick 5 and 10, querying tick 8 should return tick 5 value.

        RED: Method doesn't exist yet.
        """
        from payment_simulator.persistence.event_writer import write_events_batch
        from payment_simulator.cli.execution.state_provider import DatabaseStateProvider

        manager = DatabaseManager(db_path)
        manager.setup()

        # Write StateRegisterSet events at different ticks
        events = [
            {
                "event_type": "StateRegisterSet",
                "tick": 5,
                "agent_id": "BANK_A",
                "register_key": "bank_state_cooldown",
                "old_value": 0.0,
                "new_value": 10.0,
                "reason": "policy_action",
            },
            {
                "event_type": "StateRegisterSet",
                "tick": 10,
                "agent_id": "BANK_A",
                "register_key": "bank_state_cooldown",
                "old_value": 10.0,
                "new_value": 20.0,
                "reason": "policy_action",
            },
            {
                "event_type": "StateRegisterSet",
                "tick": 15,
                "agent_id": "BANK_A",
                "register_key": "bank_state_cooldown",
                "old_value": 20.0,
                "new_value": 30.0,
                "reason": "policy_action",
            },
        ]
        write_events_batch(manager.conn, "sim1", events, ticks_per_day=100)

        provider = DatabaseStateProvider(
            conn=manager.conn,
            simulation_id="sim1",
            tick=8,  # Query at tick 8
            tx_cache={},
            agent_states={},
            queue_snapshots={},
        )

        # At tick 8, only tick 5 event has happened
        registers = provider.get_agent_state_registers("BANK_A", 8)

        assert registers["bank_state_cooldown"] == 10.0  # Value from tick 5, not tick 10

        # Now query at tick 12
        provider.tick = 12
        registers = provider.get_agent_state_registers("BANK_A", 12)

        assert registers["bank_state_cooldown"] == 20.0  # Value from tick 10, not tick 15

        manager.close()

    def test_state_provider_returns_empty_dict_for_no_registers(self, db_path):
        """Verify StateProvider returns empty dict if agent has no registers.

        RED: Method doesn't exist yet.
        """
        from payment_simulator.cli.execution.state_provider import DatabaseStateProvider

        manager = DatabaseManager(db_path)
        manager.setup()

        # No events written

        provider = DatabaseStateProvider(
            conn=manager.conn,
            simulation_id="sim1",
            tick=10,
            tx_cache={},
            agent_states={},
            queue_snapshots={},
        )

        # Agent with no registers should return empty dict
        registers = provider.get_agent_state_registers("BANK_A", 10)

        assert isinstance(registers, dict)
        assert len(registers) == 0

        manager.close()

    def test_state_provider_handles_multiple_agents(self, db_path):
        """Verify StateProvider returns correct registers for each agent independently.

        RED: Method doesn't exist yet.
        """
        from payment_simulator.persistence.event_writer import write_events_batch
        from payment_simulator.cli.execution.state_provider import DatabaseStateProvider

        manager = DatabaseManager(db_path)
        manager.setup()

        # Write events for multiple agents
        events = [
            {
                "event_type": "StateRegisterSet",
                "tick": 10,
                "agent_id": "BANK_A",
                "register_key": "bank_state_cooldown",
                "old_value": 0.0,
                "new_value": 100.0,
                "reason": "policy_action",
            },
            {
                "event_type": "StateRegisterSet",
                "tick": 10,
                "agent_id": "BANK_B",
                "register_key": "bank_state_cooldown",
                "old_value": 0.0,
                "new_value": 200.0,
                "reason": "policy_action",
            },
        ]
        write_events_batch(manager.conn, "sim1", events, ticks_per_day=100)

        provider = DatabaseStateProvider(
            conn=manager.conn,
            simulation_id="sim1",
            tick=10,
            tx_cache={},
            agent_states={},
            queue_snapshots={},
        )

        # Get registers for BANK_A
        registers_a = provider.get_agent_state_registers("BANK_A", 10)
        assert registers_a["bank_state_cooldown"] == 100.0

        # Get registers for BANK_B
        registers_b = provider.get_agent_state_registers("BANK_B", 10)
        assert registers_b["bank_state_cooldown"] == 200.0

        manager.close()


class TestStateRegisterDuplicateKey:
    """Test for Issue #1: Multiple state updates same tick cause duplicate key constraint.

    RED: This test reproduces the bug from advanced_policy_crisis.yaml where
    policy sets state AND EOD reset sets same state, causing duplicate key error.

    Expected fix: EventWriter should merge multiple updates to same register
    in same tick, storing only the final value.
    """

    def test_multiple_updates_same_register_same_tick_no_duplicate_key_error(self, db_path):
        """Test that multiple SetState operations on same register in same tick don't cause duplicate key error.

        This is the TDD RED test for Issue #1.

        Scenario:
        1. Policy executes SetState(bank_state_mode, 1.0) during tick 99
        2. EOD reset executes SetState(bank_state_mode, 0.0) during tick 99
        3. Both events try to insert into agent_state_registers with same PK
        4. Without fix: Duplicate key constraint error
        5. With fix: Only final value (0.0) stored in database

        Expected behavior: EventWriter merges updates, stores only final value.
        """
        from payment_simulator.persistence.event_writer import write_events_batch

        manager = DatabaseManager(db_path)
        manager.setup()

        # Simulate the exact scenario from advanced_policy_crisis.yaml
        # Two StateRegisterSet events for same register in same tick
        events = [
            {
                "event_type": "StateRegisterSet",
                "tick": 99,
                "agent_id": "REGIONAL_TRUST",
                "register_key": "bank_state_mode",
                "old_value": 2.0,
                "new_value": 1.0,
                "reason": "enter_normal_mode",
            },
            {
                "event_type": "StateRegisterSet",
                "tick": 99,
                "agent_id": "REGIONAL_TRUST",
                "register_key": "bank_state_mode",
                "old_value": 1.0,
                "new_value": 0.0,
                "reason": "eod_reset",
            },
        ]

        # Write events - this should NOT raise duplicate key error
        try:
            count = write_events_batch(manager.conn, "sim-test", events, ticks_per_day=100)
            print(f"✓ Successfully wrote {count} events without duplicate key error")
        except Exception as e:
            pytest.fail(f"Duplicate key error occurred (RED phase - expected): {e}")

        # Verify only ONE row in agent_state_registers for this register
        result = manager.conn.execute("""
            SELECT register_value, COUNT(*)
            FROM agent_state_registers
            WHERE simulation_id = 'sim-test'
              AND tick = 99
              AND agent_id = 'REGIONAL_TRUST'
              AND register_key = 'bank_state_mode'
            GROUP BY register_value
        """).fetchall()

        assert len(result) == 1, f"Should have exactly 1 row, got {len(result)}"

        # The final value should be 0.0 (EOD reset is last)
        assert result[0][0] == 0.0, f"Final value should be 0.0, got {result[0][0]}"
        assert result[0][1] == 1, "Should have count=1 (one row)"

        # Verify BOTH events still in simulation_events (for replay)
        events_count = manager.conn.execute("""
            SELECT COUNT(*)
            FROM simulation_events
            WHERE simulation_id = 'sim-test'
              AND tick = 99
              AND agent_id = 'REGIONAL_TRUST'
              AND event_type = 'StateRegisterSet'
        """).fetchone()[0]

        assert events_count == 2, f"Should have 2 events in simulation_events, got {events_count}"

        manager.close()

    def test_three_updates_same_register_same_tick_stores_final_value(self, db_path):
        """Test with three updates to same register in same tick.

        This tests the general case where multiple policy actions could set
        the same register multiple times before EOD.
        """
        from payment_simulator.persistence.event_writer import write_events_batch

        manager = DatabaseManager(db_path)
        manager.setup()

        events = [
            {
                "event_type": "StateRegisterSet",
                "tick": 50,
                "agent_id": "TEST_BANK",
                "register_key": "test_counter",
                "old_value": 0.0,
                "new_value": 5.0,
                "reason": "first_update",
            },
            {
                "event_type": "StateRegisterSet",
                "tick": 50,
                "agent_id": "TEST_BANK",
                "register_key": "test_counter",
                "old_value": 5.0,
                "new_value": 10.0,
                "reason": "second_update",
            },
            {
                "event_type": "StateRegisterSet",
                "tick": 50,
                "agent_id": "TEST_BANK",
                "register_key": "test_counter",
                "old_value": 10.0,
                "new_value": 15.0,
                "reason": "third_update",
            },
        ]

        # Write events - should NOT fail
        try:
            count = write_events_batch(manager.conn, "sim-test", events, ticks_per_day=100)
            print(f"✓ Successfully wrote {count} events")
        except Exception as e:
            pytest.fail(f"Unexpected error: {e}")

        # Verify only final value (15.0) in agent_state_registers
        result = manager.conn.execute("""
            SELECT register_value
            FROM agent_state_registers
            WHERE simulation_id = 'sim-test'
              AND tick = 50
              AND agent_id = 'TEST_BANK'
              AND register_key = 'test_counter'
        """).fetchone()

        assert result is not None, "Should have row in agent_state_registers"
        assert result[0] == 15.0, f"Final value should be 15.0, got {result[0]}"

        # Verify all 3 events still in simulation_events
        events_count = manager.conn.execute("""
            SELECT COUNT(*)
            FROM simulation_events
            WHERE simulation_id = 'sim-test'
              AND tick = 50
              AND agent_id = 'TEST_BANK'
              AND event_type = 'StateRegisterSet'
        """).fetchone()[0]

        assert events_count == 3, f"Should have 3 events in simulation_events, got {events_count}"

        manager.close()


class TestStateRegisterReplayIdentity:
    """Test replay identity: run vs replay outputs are identical.

    RED: Complete integration test - will fail until all pieces implemented.
    This is the GOLD STANDARD test that drives implementation.
    """

    def test_state_register_events_have_all_required_fields(self, db_path):
        """Verify StateRegisterSet events contain all required fields for replay.

        This test ensures events are self-contained (no DB lookups needed during replay).

        RED: Need to run actual simulation with state register policy.
        """
        pytest.skip("Not implemented yet - awaiting full integration")

    def test_state_register_replay_produces_identical_output(self, db_path):
        """GOLD STANDARD: Verify state register actions replay identically.

        This is the ultimate test that proves replay identity.

        RED: Requires all pieces (persistence + StateProvider + display).
        """
        pytest.skip("Not implemented yet - awaiting full integration")
