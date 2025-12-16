"""Integration tests for experiment simulation persistence.

TDD Tests for Phase 2: Integrate SimulationPersistenceProvider into experiment runner.

These tests verify:
1. Experiments with --persist-bootstrap write to simulations table
2. Experiments with --persist-bootstrap write to simulation_events table
3. Simulation IDs from experiments are discoverable via queries
4. Backward compatible: experiments without persistence flag still work
"""

import json
from pathlib import Path
from typing import Any

import duckdb
import pytest

from payment_simulator.experiments.persistence.repository import ExperimentRepository


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Create temporary database path."""
    return tmp_path / "test_experiment.db"


@pytest.fixture
def experiment_repository(temp_db_path: Path) -> ExperimentRepository:
    """Create ExperimentRepository with unified simulation schema."""
    repo = ExperimentRepository(temp_db_path)
    return repo


# =============================================================================
# Schema Tests - Verify simulation tables exist in experiment DB
# =============================================================================


class TestExperimentRepositorySchema:
    """Tests for ExperimentRepository schema including simulation tables."""

    def test_repository_creates_simulations_table(
        self,
        experiment_repository: ExperimentRepository,
    ) -> None:
        """ExperimentRepository should create simulations table."""
        # Query for simulations table
        result = experiment_repository._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='simulations'"
        ).fetchone()

        # In DuckDB we need to check differently
        result = experiment_repository._conn.execute(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_name = 'simulations'
            """
        ).fetchone()

        assert result is not None, "simulations table should exist"

    def test_repository_creates_simulation_events_table(
        self,
        experiment_repository: ExperimentRepository,
    ) -> None:
        """ExperimentRepository should create simulation_events table."""
        result = experiment_repository._conn.execute(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_name = 'simulation_events'
            """
        ).fetchone()

        assert result is not None, "simulation_events table should exist"

    def test_repository_creates_agent_state_registers_table(
        self,
        experiment_repository: ExperimentRepository,
    ) -> None:
        """ExperimentRepository should create agent_state_registers table."""
        result = experiment_repository._conn.execute(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_name = 'agent_state_registers'
            """
        ).fetchone()

        assert result is not None, "agent_state_registers table should exist"


# =============================================================================
# SimulationPersistenceProvider Access Tests
# =============================================================================


class TestRepositorySimulationPersistenceProvider:
    """Tests for getting SimulationPersistenceProvider from repository."""

    def test_get_simulation_persistence_provider(
        self,
        experiment_repository: ExperimentRepository,
    ) -> None:
        """Repository should provide SimulationPersistenceProvider."""
        from payment_simulator.persistence.simulation_persistence_provider import (
            SimulationPersistenceProvider,
        )

        provider = experiment_repository.get_simulation_persistence_provider(
            ticks_per_day=100
        )

        assert isinstance(provider, SimulationPersistenceProvider)

    def test_provider_writes_to_simulations_table(
        self,
        experiment_repository: ExperimentRepository,
    ) -> None:
        """Provider should write to simulations table."""
        provider = experiment_repository.get_simulation_persistence_provider(
            ticks_per_day=100
        )

        config = {"seed": 12345, "num_days": 5}
        provider.persist_simulation_start(
            simulation_id="exp-sim-001",
            config=config,
            experiment_run_id="exp-run-001",
            experiment_iteration=0,
        )

        result = experiment_repository._conn.execute(
            "SELECT simulation_id, experiment_run_id FROM simulations WHERE simulation_id = ?",
            ["exp-sim-001"],
        ).fetchone()

        assert result is not None
        assert result[0] == "exp-sim-001"
        assert result[1] == "exp-run-001"

    def test_provider_writes_events_to_simulation_events(
        self,
        experiment_repository: ExperimentRepository,
    ) -> None:
        """Provider should write events to simulation_events table."""
        provider = experiment_repository.get_simulation_persistence_provider(
            ticks_per_day=100
        )

        events = [
            {
                "event_type": "TransactionArrival",
                "tick": 0,
                "tx_id": "tx_001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 100000,
            }
        ]

        count = provider.persist_tick_events(
            simulation_id="exp-sim-002",
            tick=0,
            events=events,
        )

        assert count == 1

        result = experiment_repository._conn.execute(
            "SELECT event_type, tx_id FROM simulation_events WHERE simulation_id = ?",
            ["exp-sim-002"],
        ).fetchone()

        assert result is not None
        assert result[0] == "TransactionArrival"
        assert result[1] == "tx_001"


# =============================================================================
# Full Lifecycle Tests
# =============================================================================


class TestExperimentSimulationPersistenceLifecycle:
    """Tests for full experiment simulation persistence lifecycle."""

    def test_experiment_simulation_full_lifecycle(
        self,
        experiment_repository: ExperimentRepository,
    ) -> None:
        """Test complete lifecycle: start -> events -> complete."""
        provider = experiment_repository.get_simulation_persistence_provider(
            ticks_per_day=100
        )

        sim_id = "lifecycle-test-001"

        # 1. Start simulation
        provider.persist_simulation_start(
            simulation_id=sim_id,
            config={"seed": 42, "num_days": 3},
            experiment_run_id="exp-run-lifecycle",
            experiment_iteration=1,
        )

        # 2. Persist events for multiple ticks
        for tick in range(3):
            events = [
                {
                    "event_type": "TransactionArrival",
                    "tick": tick,
                    "tx_id": f"tx_{tick:03d}",
                    "sender_id": "BANK_A",
                    "amount": 1000 * (tick + 1),
                }
            ]
            provider.persist_tick_events(sim_id, tick, events)

        # 3. Complete simulation
        provider.persist_simulation_complete(
            simulation_id=sim_id,
            metrics={
                "total_arrivals": 3,
                "total_settlements": 3,
                "total_cost_cents": 5000,
                "duration_seconds": 0.5,
            },
        )

        # Verify simulations table
        sim_result = experiment_repository._conn.execute(
            """
            SELECT status, total_arrivals, experiment_run_id
            FROM simulations WHERE simulation_id = ?
            """,
            [sim_id],
        ).fetchone()

        assert sim_result is not None
        assert sim_result[0] == "completed"
        assert sim_result[1] == 3
        assert sim_result[2] == "exp-run-lifecycle"

        # Verify simulation_events table
        events_count = experiment_repository._conn.execute(
            "SELECT COUNT(*) FROM simulation_events WHERE simulation_id = ?",
            [sim_id],
        ).fetchone()

        assert events_count[0] == 3

    def test_multiple_simulations_per_experiment(
        self,
        experiment_repository: ExperimentRepository,
    ) -> None:
        """Test multiple simulations linked to same experiment."""
        provider = experiment_repository.get_simulation_persistence_provider(
            ticks_per_day=100
        )

        experiment_run_id = "exp-multi-sim"

        # Create 3 simulations for same experiment
        for i in range(3):
            sim_id = f"multi-sim-{i:03d}"
            provider.persist_simulation_start(
                simulation_id=sim_id,
                config={"seed": 1000 + i},
                experiment_run_id=experiment_run_id,
                experiment_iteration=i,
            )
            provider.persist_tick_events(
                sim_id,
                0,
                [{"event_type": "TransactionArrival", "tick": 0, "tx_id": f"tx_{i}"}],
            )
            provider.persist_simulation_complete(
                sim_id,
                {"total_arrivals": 1, "total_settlements": 1, "total_cost_cents": 100 * i, "duration_seconds": 0.1},
            )

        # Query simulations by experiment
        result = experiment_repository._conn.execute(
            """
            SELECT simulation_id, experiment_iteration
            FROM simulations
            WHERE experiment_run_id = ?
            ORDER BY experiment_iteration
            """,
            [experiment_run_id],
        ).fetchall()

        assert len(result) == 3
        assert result[0] == ("multi-sim-000", 0)
        assert result[1] == ("multi-sim-001", 1)
        assert result[2] == ("multi-sim-002", 2)


# =============================================================================
# Replay Query Tests - Verify simulation can be replayed
# =============================================================================


class TestExperimentSimulationReplayQueries:
    """Tests verifying experiment simulations support replay queries."""

    def test_query_simulation_events_by_tick(
        self,
        experiment_repository: ExperimentRepository,
    ) -> None:
        """Should be able to query events by tick for replay."""
        provider = experiment_repository.get_simulation_persistence_provider(
            ticks_per_day=100
        )

        sim_id = "replay-query-test"
        provider.persist_simulation_start(sim_id, {"seed": 123})

        # Create events at different ticks
        for tick in range(5):
            events = [
                {
                    "event_type": "TransactionArrival",
                    "tick": tick,
                    "tx_id": f"tx_{tick}",
                    "amount": 1000 * tick,
                }
            ]
            provider.persist_tick_events(sim_id, tick, events)

        # Query events for tick 2
        result = experiment_repository._conn.execute(
            """
            SELECT tick, tx_id, details
            FROM simulation_events
            WHERE simulation_id = ? AND tick = ?
            """,
            [sim_id, 2],
        ).fetchall()

        assert len(result) == 1
        assert result[0][0] == 2
        assert result[0][1] == "tx_2"

        details = json.loads(result[0][2])
        assert details["amount"] == 2000

    def test_query_simulation_events_by_event_type(
        self,
        experiment_repository: ExperimentRepository,
    ) -> None:
        """Should be able to filter events by type for replay."""
        provider = experiment_repository.get_simulation_persistence_provider(
            ticks_per_day=100
        )

        sim_id = "type-query-test"
        provider.persist_simulation_start(sim_id, {"seed": 456})

        events = [
            {"event_type": "TransactionArrival", "tick": 0, "tx_id": "tx_1"},
            {"event_type": "PolicySubmit", "tick": 0, "tx_id": "tx_1", "agent_id": "BANK_A"},
            {"event_type": "RtgsImmediateSettlement", "tick": 0, "tx_id": "tx_1", "amount": 1000},
        ]
        provider.persist_tick_events(sim_id, 0, events)

        # Query only PolicySubmit events
        result = experiment_repository._conn.execute(
            """
            SELECT event_type, agent_id
            FROM simulation_events
            WHERE simulation_id = ? AND event_type = 'PolicySubmit'
            """,
            [sim_id],
        ).fetchall()

        assert len(result) == 1
        assert result[0][0] == "PolicySubmit"
        assert result[0][1] == "BANK_A"


# =============================================================================
# INV-11: Persistence Identity Tests
# =============================================================================


class TestPersistenceIdentity:
    """Tests for INV-11: Simulation Persistence Identity.

    Verifies that experiment persistence produces same schema/structure
    as CLI persistence.
    """

    def test_simulation_record_has_required_fields(
        self,
        experiment_repository: ExperimentRepository,
    ) -> None:
        """Simulation record should have all required fields."""
        provider = experiment_repository.get_simulation_persistence_provider(
            ticks_per_day=100
        )

        sim_id = "field-test"
        provider.persist_simulation_start(
            sim_id,
            {"seed": 789, "num_days": 5},
            experiment_run_id="exp-001",
            experiment_iteration=2,
        )
        provider.persist_simulation_complete(
            sim_id,
            {
                "total_arrivals": 50,
                "total_settlements": 48,
                "total_cost_cents": 25000,
                "duration_seconds": 1.5,
            },
        )

        result = experiment_repository._conn.execute(
            """
            SELECT
                simulation_id,
                rng_seed,
                ticks_per_day,
                num_days,
                status,
                total_arrivals,
                total_settlements,
                total_cost_cents,
                config_json,
                experiment_run_id,
                experiment_iteration
            FROM simulations
            WHERE simulation_id = ?
            """,
            [sim_id],
        ).fetchone()

        assert result is not None
        # Core fields
        assert result[0] == "field-test"  # simulation_id
        assert result[1] == 789  # rng_seed
        assert result[2] == 100  # ticks_per_day
        assert result[3] == 5  # num_days
        assert result[4] == "completed"  # status
        # Metrics
        assert result[5] == 50  # total_arrivals
        assert result[6] == 48  # total_settlements
        assert result[7] == 25000  # total_cost_cents (integer - INV-1)
        # Config JSON
        config = json.loads(result[8])
        assert config["seed"] == 789
        # Experiment context
        assert result[9] == "exp-001"  # experiment_run_id
        assert result[10] == 2  # experiment_iteration

    def test_event_record_has_required_fields(
        self,
        experiment_repository: ExperimentRepository,
    ) -> None:
        """Event record should have all required fields."""
        provider = experiment_repository.get_simulation_persistence_provider(
            ticks_per_day=100
        )

        sim_id = "event-field-test"

        event = {
            "event_type": "RtgsImmediateSettlement",
            "tick": 42,
            "tx_id": "tx_test",
            "agent_id": "BANK_A",
            "amount": 100000,
            "sender_balance_before": 500000,
            "sender_balance_after": 400000,
        }

        provider.persist_tick_events(sim_id, 42, [event])

        result = experiment_repository._conn.execute(
            """
            SELECT
                event_id,
                simulation_id,
                tick,
                day,
                event_type,
                details,
                agent_id,
                tx_id
            FROM simulation_events
            WHERE simulation_id = ?
            """,
            [sim_id],
        ).fetchone()

        assert result is not None
        # event_id should be UUID
        assert result[0] is not None and len(result[0]) > 0
        assert result[1] == sim_id  # simulation_id
        assert result[2] == 42  # tick
        assert result[3] == 0  # day (42 // 100 = 0)
        assert result[4] == "RtgsImmediateSettlement"  # event_type
        # Check details JSON has extra fields
        details = json.loads(result[5])
        assert details["amount"] == 100000
        assert details["sender_balance_before"] == 500000
        assert details["sender_balance_after"] == 400000
        # Common fields in dedicated columns
        assert result[6] == "BANK_A"  # agent_id
        assert result[7] == "tx_test"  # tx_id
