"""Unit tests for SimulationPersistenceProvider protocol and implementation.

TDD Tests for Phase 1: Define SimulationPersistenceProvider protocol.

These tests ensure:
1. Protocol defines correct interface methods
2. StandardSimulationPersistenceProvider writes to correct tables
3. Events are correctly transformed for persistence
4. All costs remain as integer cents (INV-1)
"""

import json
import uuid
from typing import Any

import duckdb
import pytest

# Will be implemented - these imports will fail initially (TDD RED phase)
from payment_simulator.persistence.simulation_persistence_provider import (
    SimulationPersistenceProvider,
    StandardSimulationPersistenceProvider,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def in_memory_db() -> duckdb.DuckDBPyConnection:
    """Create in-memory DuckDB with required schema."""
    conn = duckdb.connect(":memory:")

    # Create simulations table (minimal schema for testing)
    conn.execute("""
        CREATE TABLE simulations (
            simulation_id VARCHAR PRIMARY KEY,
            config_file VARCHAR,
            config_name VARCHAR,
            description VARCHAR,
            rng_seed BIGINT,
            ticks_per_day INTEGER,
            num_days INTEGER,
            num_agents INTEGER,
            status VARCHAR DEFAULT 'running',
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ended_at TIMESTAMP,
            total_arrivals INTEGER,
            total_settlements INTEGER,
            total_cost_cents BIGINT,
            duration_seconds DOUBLE,
            ticks_per_second DOUBLE,
            config_json TEXT,
            experiment_run_id VARCHAR,
            experiment_iteration INTEGER
        )
    """)

    # Create simulation_events table
    conn.execute("""
        CREATE TABLE simulation_events (
            event_id VARCHAR PRIMARY KEY,
            simulation_id VARCHAR,
            tick INTEGER,
            day INTEGER,
            event_timestamp TIMESTAMP,
            event_type VARCHAR,
            details TEXT,
            agent_id VARCHAR,
            tx_id VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create agent_state_registers table (for StateRegisterSet dual-write)
    conn.execute("""
        CREATE TABLE agent_state_registers (
            simulation_id VARCHAR,
            tick INTEGER,
            agent_id VARCHAR,
            register_key VARCHAR,
            register_value DOUBLE,
            PRIMARY KEY (simulation_id, tick, agent_id, register_key)
        )
    """)

    return conn


@pytest.fixture
def sample_events() -> list[dict[str, Any]]:
    """Sample events matching Rust FFI format."""
    return [
        {
            "event_type": "TransactionArrival",
            "tick": 0,
            "tx_id": "tx_001",
            "sender_id": "BANK_A",
            "receiver_id": "BANK_B",
            "amount": 100000,  # Integer cents (INV-1)
            "priority": 5,
            "deadline_tick": 50,
        },
        {
            "event_type": "PolicySubmit",
            "tick": 1,
            "tx_id": "tx_001",
            "agent_id": "BANK_A",
        },
        {
            "event_type": "RtgsImmediateSettlement",
            "tick": 1,
            "tx_id": "tx_001",
            "sender_id": "BANK_A",
            "receiver_id": "BANK_B",
            "amount": 100000,
            "sender_balance_before": 500000,
            "sender_balance_after": 400000,
        },
        {
            "event_type": "StateRegisterSet",
            "tick": 2,
            "agent_id": "BANK_A",
            "register_key": "cooldown",
            "old_value": 0.0,
            "new_value": 5.0,
        },
    ]


@pytest.fixture
def sample_config() -> dict[str, Any]:
    """Sample simulation configuration."""
    return {
        "seed": 12345,
        "num_days": 5,
        "ticks_per_day": 100,
        "agents": [
            {"id": "BANK_A", "opening_balance": 1000000},
            {"id": "BANK_B", "opening_balance": 1000000},
        ],
    }


# =============================================================================
# Protocol Contract Tests (TDD RED phase)
# =============================================================================


class TestSimulationPersistenceProviderProtocol:
    """Tests for SimulationPersistenceProvider protocol definition."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """Protocol should be runtime checkable for isinstance checks."""
        from typing import runtime_checkable

        # Protocol should be decorated with @runtime_checkable
        assert hasattr(SimulationPersistenceProvider, "__protocol_attrs__") or isinstance(
            SimulationPersistenceProvider, type
        )

    def test_protocol_defines_persist_simulation_start(self) -> None:
        """Protocol should define persist_simulation_start method."""
        # Check method exists in protocol
        assert hasattr(SimulationPersistenceProvider, "persist_simulation_start")

    def test_protocol_defines_persist_tick_events(self) -> None:
        """Protocol should define persist_tick_events method."""
        assert hasattr(SimulationPersistenceProvider, "persist_tick_events")

    def test_protocol_defines_persist_simulation_complete(self) -> None:
        """Protocol should define persist_simulation_complete method."""
        assert hasattr(SimulationPersistenceProvider, "persist_simulation_complete")

    def test_standard_implementation_satisfies_protocol(
        self, in_memory_db: duckdb.DuckDBPyConnection
    ) -> None:
        """StandardSimulationPersistenceProvider should satisfy the protocol."""
        provider = StandardSimulationPersistenceProvider(
            conn=in_memory_db,
            ticks_per_day=100,
        )

        # Should be instance of protocol
        assert isinstance(provider, SimulationPersistenceProvider)


# =============================================================================
# StandardSimulationPersistenceProvider Tests
# =============================================================================


class TestStandardSimulationPersistenceProvider:
    """Tests for StandardSimulationPersistenceProvider implementation."""

    def test_persist_simulation_start_creates_record(
        self,
        in_memory_db: duckdb.DuckDBPyConnection,
        sample_config: dict[str, Any],
    ) -> None:
        """persist_simulation_start should create simulation record."""
        provider = StandardSimulationPersistenceProvider(
            conn=in_memory_db,
            ticks_per_day=100,
        )

        sim_id = "test-sim-001"
        provider.persist_simulation_start(
            simulation_id=sim_id,
            config=sample_config,
        )

        # Verify record created
        result = in_memory_db.execute(
            "SELECT simulation_id, status, rng_seed FROM simulations WHERE simulation_id = ?",
            [sim_id],
        ).fetchone()

        assert result is not None
        assert result[0] == sim_id
        assert result[1] == "running"
        assert result[2] == 12345  # seed from config

    def test_persist_simulation_start_with_experiment_context(
        self,
        in_memory_db: duckdb.DuckDBPyConnection,
        sample_config: dict[str, Any],
    ) -> None:
        """persist_simulation_start should store experiment context if provided."""
        provider = StandardSimulationPersistenceProvider(
            conn=in_memory_db,
            ticks_per_day=100,
        )

        sim_id = "exp-sim-001"
        provider.persist_simulation_start(
            simulation_id=sim_id,
            config=sample_config,
            experiment_run_id="exp-run-001",
            experiment_iteration=3,
        )

        # Verify experiment context stored
        result = in_memory_db.execute(
            "SELECT experiment_run_id, experiment_iteration FROM simulations WHERE simulation_id = ?",
            [sim_id],
        ).fetchone()

        assert result is not None
        assert result[0] == "exp-run-001"
        assert result[1] == 3

    def test_persist_tick_events_writes_to_simulation_events(
        self,
        in_memory_db: duckdb.DuckDBPyConnection,
        sample_events: list[dict[str, Any]],
    ) -> None:
        """persist_tick_events should write events to simulation_events table."""
        provider = StandardSimulationPersistenceProvider(
            conn=in_memory_db,
            ticks_per_day=100,
        )

        sim_id = "test-sim-002"
        count = provider.persist_tick_events(
            simulation_id=sim_id,
            tick=0,
            events=sample_events[:1],  # Just first event
        )

        assert count == 1

        # Verify event in table
        result = in_memory_db.execute(
            "SELECT event_type, tick, tx_id FROM simulation_events WHERE simulation_id = ?",
            [sim_id],
        ).fetchone()

        assert result is not None
        assert result[0] == "TransactionArrival"
        assert result[1] == 0
        assert result[2] == "tx_001"

    def test_persist_tick_events_calculates_day_correctly(
        self,
        in_memory_db: duckdb.DuckDBPyConnection,
    ) -> None:
        """persist_tick_events should calculate day from tick and ticks_per_day."""
        provider = StandardSimulationPersistenceProvider(
            conn=in_memory_db,
            ticks_per_day=100,
        )

        sim_id = "test-sim-003"

        # Event at tick 150 should be day 1 (150 // 100 = 1)
        event = {
            "event_type": "PolicyHold",
            "tick": 150,
            "tx_id": "tx_002",
            "agent_id": "BANK_B",
        }

        provider.persist_tick_events(
            simulation_id=sim_id,
            tick=150,
            events=[event],
        )

        result = in_memory_db.execute(
            "SELECT day FROM simulation_events WHERE simulation_id = ?",
            [sim_id],
        ).fetchone()

        assert result is not None
        assert result[0] == 1

    def test_persist_tick_events_stores_details_as_json(
        self,
        in_memory_db: duckdb.DuckDBPyConnection,
        sample_events: list[dict[str, Any]],
    ) -> None:
        """persist_tick_events should store non-common fields in details JSON."""
        provider = StandardSimulationPersistenceProvider(
            conn=in_memory_db,
            ticks_per_day=100,
        )

        sim_id = "test-sim-004"

        # Use arrival event which has amount, priority, etc.
        arrival_event = sample_events[0]
        provider.persist_tick_events(
            simulation_id=sim_id,
            tick=0,
            events=[arrival_event],
        )

        result = in_memory_db.execute(
            "SELECT details FROM simulation_events WHERE simulation_id = ?",
            [sim_id],
        ).fetchone()

        assert result is not None
        details = json.loads(result[0])

        # Amount should be in details (integer cents - INV-1)
        assert details["amount"] == 100000
        assert details["priority"] == 5
        assert details["deadline_tick"] == 50

    def test_persist_tick_events_dual_writes_state_registers(
        self,
        in_memory_db: duckdb.DuckDBPyConnection,
        sample_events: list[dict[str, Any]],
    ) -> None:
        """StateRegisterSet events should also write to agent_state_registers."""
        provider = StandardSimulationPersistenceProvider(
            conn=in_memory_db,
            ticks_per_day=100,
        )

        sim_id = "test-sim-005"

        # Use StateRegisterSet event
        state_event = sample_events[3]
        provider.persist_tick_events(
            simulation_id=sim_id,
            tick=2,
            events=[state_event],
        )

        # Should be in simulation_events
        event_result = in_memory_db.execute(
            "SELECT event_type FROM simulation_events WHERE simulation_id = ?",
            [sim_id],
        ).fetchone()
        assert event_result is not None
        assert event_result[0] == "StateRegisterSet"

        # Should ALSO be in agent_state_registers (dual-write)
        register_result = in_memory_db.execute(
            """SELECT agent_id, register_key, register_value
               FROM agent_state_registers
               WHERE simulation_id = ?""",
            [sim_id],
        ).fetchone()

        assert register_result is not None
        assert register_result[0] == "BANK_A"
        assert register_result[1] == "cooldown"
        assert register_result[2] == 5.0

    def test_persist_simulation_complete_updates_status(
        self,
        in_memory_db: duckdb.DuckDBPyConnection,
        sample_config: dict[str, Any],
    ) -> None:
        """persist_simulation_complete should update simulation status."""
        provider = StandardSimulationPersistenceProvider(
            conn=in_memory_db,
            ticks_per_day=100,
        )

        sim_id = "test-sim-006"

        # First create the simulation
        provider.persist_simulation_start(
            simulation_id=sim_id,
            config=sample_config,
        )

        # Then complete it
        provider.persist_simulation_complete(
            simulation_id=sim_id,
            metrics={
                "total_arrivals": 100,
                "total_settlements": 95,
                "total_cost_cents": 50000,
                "duration_seconds": 2.5,
            },
        )

        result = in_memory_db.execute(
            """SELECT status, total_arrivals, total_settlements,
                      total_cost_cents, duration_seconds
               FROM simulations WHERE simulation_id = ?""",
            [sim_id],
        ).fetchone()

        assert result is not None
        assert result[0] == "completed"
        assert result[1] == 100
        assert result[2] == 95
        assert result[3] == 50000  # Integer cents (INV-1)
        assert result[4] == 2.5

    def test_persist_tick_events_returns_count(
        self,
        in_memory_db: duckdb.DuckDBPyConnection,
        sample_events: list[dict[str, Any]],
    ) -> None:
        """persist_tick_events should return number of events written."""
        provider = StandardSimulationPersistenceProvider(
            conn=in_memory_db,
            ticks_per_day=100,
        )

        sim_id = "test-sim-007"
        count = provider.persist_tick_events(
            simulation_id=sim_id,
            tick=0,
            events=sample_events,
        )

        assert count == len(sample_events)

    def test_persist_tick_events_empty_list_returns_zero(
        self,
        in_memory_db: duckdb.DuckDBPyConnection,
    ) -> None:
        """persist_tick_events with empty list should return 0."""
        provider = StandardSimulationPersistenceProvider(
            conn=in_memory_db,
            ticks_per_day=100,
        )

        count = provider.persist_tick_events(
            simulation_id="test-sim-008",
            tick=0,
            events=[],
        )

        assert count == 0


# =============================================================================
# INV-1: Money as Integer Cents Tests
# =============================================================================


class TestMoneyInvariant:
    """Tests ensuring money values are always integer cents (INV-1)."""

    def test_event_amounts_stored_as_integers(
        self,
        in_memory_db: duckdb.DuckDBPyConnection,
    ) -> None:
        """All money amounts in events should be stored as integers."""
        provider = StandardSimulationPersistenceProvider(
            conn=in_memory_db,
            ticks_per_day=100,
        )

        event = {
            "event_type": "RtgsImmediateSettlement",
            "tick": 0,
            "tx_id": "tx_money_test",
            "amount": 123456,  # Integer cents
            "sender_balance_before": 999999,
            "sender_balance_after": 876543,
        }

        provider.persist_tick_events(
            simulation_id="money-test-001",
            tick=0,
            events=[event],
        )

        result = in_memory_db.execute(
            "SELECT details FROM simulation_events WHERE simulation_id = ?",
            ["money-test-001"],
        ).fetchone()

        details = json.loads(result[0])

        # Verify all money values are integers, not floats
        assert isinstance(details["amount"], int)
        assert isinstance(details["sender_balance_before"], int)
        assert isinstance(details["sender_balance_after"], int)

    def test_total_cost_stored_as_integer(
        self,
        in_memory_db: duckdb.DuckDBPyConnection,
        sample_config: dict[str, Any],
    ) -> None:
        """Total cost in metrics should be stored as integer cents."""
        provider = StandardSimulationPersistenceProvider(
            conn=in_memory_db,
            ticks_per_day=100,
        )

        sim_id = "money-test-002"
        provider.persist_simulation_start(sim_id, sample_config)

        provider.persist_simulation_complete(
            simulation_id=sim_id,
            metrics={
                "total_arrivals": 50,
                "total_settlements": 48,
                "total_cost_cents": 12345678,  # Integer cents
                "duration_seconds": 1.0,
            },
        )

        result = in_memory_db.execute(
            "SELECT total_cost_cents FROM simulations WHERE simulation_id = ?",
            [sim_id],
        ).fetchone()

        # Should be stored as integer
        assert result[0] == 12345678
        assert isinstance(result[0], int)


# =============================================================================
# Batch Event Persistence Tests
# =============================================================================


class TestBatchEventPersistence:
    """Tests for batch event persistence (matching existing write_events_batch)."""

    def test_persist_multiple_events_at_once(
        self,
        in_memory_db: duckdb.DuckDBPyConnection,
        sample_events: list[dict[str, Any]],
    ) -> None:
        """Should persist multiple events in a single call efficiently."""
        provider = StandardSimulationPersistenceProvider(
            conn=in_memory_db,
            ticks_per_day=100,
        )

        sim_id = "batch-test-001"
        count = provider.persist_tick_events(
            simulation_id=sim_id,
            tick=0,
            events=sample_events,
        )

        assert count == 4

        # Verify all events in database
        result = in_memory_db.execute(
            "SELECT COUNT(*) FROM simulation_events WHERE simulation_id = ?",
            [sim_id],
        ).fetchone()

        assert result[0] == 4

    def test_persist_events_from_multiple_ticks(
        self,
        in_memory_db: duckdb.DuckDBPyConnection,
    ) -> None:
        """Should handle events from multiple ticks correctly."""
        provider = StandardSimulationPersistenceProvider(
            conn=in_memory_db,
            ticks_per_day=100,
        )

        sim_id = "batch-test-002"

        # Events from tick 0
        provider.persist_tick_events(
            simulation_id=sim_id,
            tick=0,
            events=[{"event_type": "TransactionArrival", "tick": 0, "tx_id": "tx_1"}],
        )

        # Events from tick 1
        provider.persist_tick_events(
            simulation_id=sim_id,
            tick=1,
            events=[{"event_type": "PolicySubmit", "tick": 1, "tx_id": "tx_1", "agent_id": "BANK_A"}],
        )

        # Verify tick distribution
        result = in_memory_db.execute(
            """SELECT tick, COUNT(*) FROM simulation_events
               WHERE simulation_id = ? GROUP BY tick ORDER BY tick""",
            [sim_id],
        ).fetchall()

        assert len(result) == 2
        assert result[0] == (0, 1)
        assert result[1] == (1, 1)
