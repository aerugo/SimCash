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
        pytest.skip("Not implemented yet - awaiting StateProvider extension")

    def test_state_provider_returns_most_recent_values(self, db_path):
        """Verify StateProvider returns most recent value for each register up to tick.

        For example, if register set at tick 5 and 10, querying tick 8 should return tick 5 value.

        RED: Method doesn't exist yet.
        """
        pytest.skip("Not implemented yet - awaiting StateProvider extension")

    def test_state_provider_returns_empty_dict_for_no_registers(self, db_path):
        """Verify StateProvider returns empty dict if agent has no registers.

        RED: Method doesn't exist yet.
        """
        pytest.skip("Not implemented yet - awaiting StateProvider extension")


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
