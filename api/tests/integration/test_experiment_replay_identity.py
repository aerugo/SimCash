"""Integration tests for experiment replay identity (INV-5).

TDD Tests for Phase 3: Verify replay identity for experiment simulations.

These tests verify:
1. Replay command finds simulation from experiment database
2. Events are complete (no missing fields)
3. Events can be queried using standard replay queries
4. INV-5: Replay output structure matches run output structure
"""

import json
from pathlib import Path
from typing import Any

import pytest

from payment_simulator.experiments.persistence.repository import ExperimentRepository
from payment_simulator.persistence.queries import get_simulation_summary


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Create temporary database path."""
    return tmp_path / "test_replay.db"


@pytest.fixture
def experiment_repository(temp_db_path: Path) -> ExperimentRepository:
    """Create ExperimentRepository with unified simulation schema."""
    repo = ExperimentRepository(temp_db_path)
    return repo


@pytest.fixture
def persisted_simulation(
    experiment_repository: ExperimentRepository,
) -> tuple[str, ExperimentRepository]:
    """Create a persisted simulation with realistic events."""
    provider = experiment_repository.get_simulation_persistence_provider(
        ticks_per_day=100
    )

    sim_id = "replay-test-sim-001"

    # Persist simulation start
    provider.persist_simulation_start(
        simulation_id=sim_id,
        config={
            "seed": 12345,
            "num_days": 1,
            "agents": [
                {"id": "BANK_A", "opening_balance": 1000000},
                {"id": "BANK_B", "opening_balance": 1000000},
            ],
        },
        experiment_run_id="replay-test-exp",
        experiment_iteration=0,
    )

    # Persist realistic events (matching what Rust FFI produces)
    events_tick_0 = [
        {
            "event_type": "TransactionArrival",
            "tick": 0,
            "tx_id": "tx_001",
            "sender_id": "BANK_A",
            "receiver_id": "BANK_B",
            "amount": 100000,
            "priority": 5,
            "deadline_tick": 50,
            "is_divisible": False,
        },
        {
            "event_type": "TransactionArrival",
            "tick": 0,
            "tx_id": "tx_002",
            "sender_id": "BANK_B",
            "receiver_id": "BANK_A",
            "amount": 75000,
            "priority": 3,
            "deadline_tick": 60,
            "is_divisible": True,
        },
    ]

    events_tick_1 = [
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
            "sender_balance_before": 1000000,
            "sender_balance_after": 900000,
        },
    ]

    events_tick_2 = [
        {
            "event_type": "PolicySubmit",
            "tick": 2,
            "tx_id": "tx_002",
            "agent_id": "BANK_B",
        },
        {
            "event_type": "RtgsImmediateSettlement",
            "tick": 2,
            "tx_id": "tx_002",
            "sender_id": "BANK_B",
            "receiver_id": "BANK_A",
            "amount": 75000,
            "sender_balance_before": 1100000,
            "sender_balance_after": 1025000,
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

    # Persist events
    provider.persist_tick_events(sim_id, 0, events_tick_0)
    provider.persist_tick_events(sim_id, 1, events_tick_1)
    provider.persist_tick_events(sim_id, 2, events_tick_2)

    # Persist simulation complete
    provider.persist_simulation_complete(
        simulation_id=sim_id,
        metrics={
            "total_arrivals": 2,
            "total_settlements": 2,
            "total_cost_cents": 5000,
            "duration_seconds": 0.5,
        },
    )

    return sim_id, experiment_repository


# =============================================================================
# Replay Discovery Tests
# =============================================================================


class TestReplayDiscovery:
    """Tests for discovering simulations for replay."""

    def test_simulation_discoverable_via_get_simulation_summary(
        self,
        persisted_simulation: tuple[str, ExperimentRepository],
    ) -> None:
        """Simulation should be discoverable via standard query."""
        sim_id, repo = persisted_simulation

        # Use standard query function
        summary = get_simulation_summary(repo._conn, sim_id)

        assert summary is not None
        assert summary["simulation_id"] == sim_id
        assert summary["status"] == "completed"
        assert summary["total_arrivals"] == 2
        assert summary["total_settlements"] == 2

    def test_simulation_has_experiment_context(
        self,
        persisted_simulation: tuple[str, ExperimentRepository],
    ) -> None:
        """Simulation should have experiment context for cross-referencing."""
        sim_id, repo = persisted_simulation

        result = repo._conn.execute(
            """
            SELECT experiment_run_id, experiment_iteration
            FROM simulations WHERE simulation_id = ?
            """,
            [sim_id],
        ).fetchone()

        assert result is not None
        assert result[0] == "replay-test-exp"
        assert result[1] == 0


# =============================================================================
# Event Completeness Tests (INV-6)
# =============================================================================


class TestEventCompleteness:
    """Tests for event completeness (INV-6)."""

    def test_transaction_arrival_has_all_fields(
        self,
        persisted_simulation: tuple[str, ExperimentRepository],
    ) -> None:
        """TransactionArrival events should have all required fields."""
        sim_id, repo = persisted_simulation

        result = repo._conn.execute(
            """
            SELECT details, tx_id
            FROM simulation_events
            WHERE simulation_id = ? AND event_type = 'TransactionArrival'
            LIMIT 1
            """,
            [sim_id],
        ).fetchone()

        assert result is not None
        details = json.loads(result[0])

        # Required fields for display
        assert "sender_id" in details
        assert "receiver_id" in details
        assert "amount" in details
        assert "priority" in details
        assert "deadline_tick" in details

    def test_rtgs_settlement_has_all_fields(
        self,
        persisted_simulation: tuple[str, ExperimentRepository],
    ) -> None:
        """RtgsImmediateSettlement events should have all required fields."""
        sim_id, repo = persisted_simulation

        result = repo._conn.execute(
            """
            SELECT details, tx_id
            FROM simulation_events
            WHERE simulation_id = ? AND event_type = 'RtgsImmediateSettlement'
            LIMIT 1
            """,
            [sim_id],
        ).fetchone()

        assert result is not None
        details = json.loads(result[0])

        # Required fields for settlement display
        assert "sender_id" in details
        assert "receiver_id" in details
        assert "amount" in details
        assert "sender_balance_before" in details
        assert "sender_balance_after" in details

    def test_state_register_set_has_all_fields(
        self,
        persisted_simulation: tuple[str, ExperimentRepository],
    ) -> None:
        """StateRegisterSet events should have all required fields."""
        sim_id, repo = persisted_simulation

        result = repo._conn.execute(
            """
            SELECT details, agent_id
            FROM simulation_events
            WHERE simulation_id = ? AND event_type = 'StateRegisterSet'
            LIMIT 1
            """,
            [sim_id],
        ).fetchone()

        assert result is not None
        details = json.loads(result[0])
        agent_id = result[1]

        # Required fields for register display
        assert "register_key" in details
        assert "old_value" in details
        assert "new_value" in details
        assert agent_id == "BANK_A"

    def test_state_register_dual_written(
        self,
        persisted_simulation: tuple[str, ExperimentRepository],
    ) -> None:
        """StateRegisterSet should also write to agent_state_registers table."""
        sim_id, repo = persisted_simulation

        result = repo._conn.execute(
            """
            SELECT agent_id, register_key, register_value
            FROM agent_state_registers
            WHERE simulation_id = ?
            """,
            [sim_id],
        ).fetchone()

        assert result is not None
        assert result[0] == "BANK_A"
        assert result[1] == "cooldown"
        assert result[2] == 5.0


# =============================================================================
# Replay Query Tests
# =============================================================================


class TestReplayQueries:
    """Tests for queries used during replay."""

    def test_query_events_by_tick(
        self,
        persisted_simulation: tuple[str, ExperimentRepository],
    ) -> None:
        """Should be able to query events by tick for replay."""
        sim_id, repo = persisted_simulation

        # Query tick 1 events
        result = repo._conn.execute(
            """
            SELECT event_type, tick, tx_id
            FROM simulation_events
            WHERE simulation_id = ? AND tick = ?
            ORDER BY event_type
            """,
            [sim_id, 1],
        ).fetchall()

        assert len(result) == 2

        event_types = [r[0] for r in result]
        assert "PolicySubmit" in event_types
        assert "RtgsImmediateSettlement" in event_types

    def test_query_events_by_type(
        self,
        persisted_simulation: tuple[str, ExperimentRepository],
    ) -> None:
        """Should be able to filter events by type."""
        sim_id, repo = persisted_simulation

        # Query all PolicySubmit events
        result = repo._conn.execute(
            """
            SELECT tick, tx_id, agent_id
            FROM simulation_events
            WHERE simulation_id = ? AND event_type = 'PolicySubmit'
            ORDER BY tick
            """,
            [sim_id],
        ).fetchall()

        assert len(result) == 2
        assert result[0][0] == 1  # tick
        assert result[0][1] == "tx_001"  # tx_id
        assert result[1][0] == 2  # tick
        assert result[1][1] == "tx_002"  # tx_id

    def test_query_all_events_for_simulation(
        self,
        persisted_simulation: tuple[str, ExperimentRepository],
    ) -> None:
        """Should be able to query all events for a simulation."""
        sim_id, repo = persisted_simulation

        result = repo._conn.execute(
            """
            SELECT COUNT(*) FROM simulation_events WHERE simulation_id = ?
            """,
            [sim_id],
        ).fetchone()

        # 2 arrivals + 2 policy submits + 2 settlements + 1 state register = 7
        assert result[0] == 7

    def test_events_ordered_by_tick(
        self,
        persisted_simulation: tuple[str, ExperimentRepository],
    ) -> None:
        """Events should be queryable in tick order."""
        sim_id, repo = persisted_simulation

        result = repo._conn.execute(
            """
            SELECT tick, event_type
            FROM simulation_events
            WHERE simulation_id = ?
            ORDER BY tick, event_type
            """,
            [sim_id],
        ).fetchall()

        # Verify tick ordering
        ticks = [r[0] for r in result]
        assert ticks == sorted(ticks)


# =============================================================================
# Replay Identity Structure Tests (INV-5)
# =============================================================================


class TestReplayIdentityStructure:
    """Tests for replay identity structure (INV-5).

    Verifies that event structure from experiments matches what CLI produces.
    """

    def test_event_has_standard_columns(
        self,
        persisted_simulation: tuple[str, ExperimentRepository],
    ) -> None:
        """Events should have all standard columns."""
        sim_id, repo = persisted_simulation

        result = repo._conn.execute(
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
            LIMIT 1
            """,
            [sim_id],
        ).fetchone()

        assert result is not None
        # All columns should be present
        assert result[0] is not None  # event_id (UUID)
        assert result[1] == sim_id  # simulation_id
        assert result[2] >= 0  # tick
        assert result[3] >= 0  # day
        assert result[4] is not None  # event_type
        assert result[5] is not None  # details (JSON)

    def test_day_calculated_correctly(
        self,
        persisted_simulation: tuple[str, ExperimentRepository],
    ) -> None:
        """Day should be calculated correctly from tick."""
        sim_id, repo = persisted_simulation

        result = repo._conn.execute(
            """
            SELECT tick, day FROM simulation_events
            WHERE simulation_id = ?
            ORDER BY tick
            """,
            [sim_id],
        ).fetchall()

        # All ticks 0-2 should be day 0 (with ticks_per_day=100)
        for tick, day in result:
            expected_day = tick // 100
            assert day == expected_day, f"tick {tick} should be day {expected_day}"

    def test_money_values_are_integers(
        self,
        persisted_simulation: tuple[str, ExperimentRepository],
    ) -> None:
        """Money values in events should be integers (INV-1)."""
        sim_id, repo = persisted_simulation

        result = repo._conn.execute(
            """
            SELECT details
            FROM simulation_events
            WHERE simulation_id = ? AND event_type = 'RtgsImmediateSettlement'
            """,
            [sim_id],
        ).fetchall()

        for (details_json,) in result:
            details = json.loads(details_json)

            # All money values should be integers
            assert isinstance(details["amount"], int)
            assert isinstance(details["sender_balance_before"], int)
            assert isinstance(details["sender_balance_after"], int)

    def test_simulation_metadata_complete(
        self,
        persisted_simulation: tuple[str, ExperimentRepository],
    ) -> None:
        """Simulation metadata should be complete for replay."""
        sim_id, repo = persisted_simulation

        result = repo._conn.execute(
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
                config_json
            FROM simulations
            WHERE simulation_id = ?
            """,
            [sim_id],
        ).fetchone()

        assert result is not None

        # Core metadata
        assert result[0] == sim_id
        assert result[1] == 12345  # rng_seed
        assert result[2] == 100  # ticks_per_day
        assert result[3] == 1  # num_days
        assert result[4] == "completed"

        # Metrics
        assert result[5] == 2  # total_arrivals
        assert result[6] == 2  # total_settlements
        assert result[7] == 5000  # total_cost_cents (integer!)

        # Config JSON should be parseable
        config = json.loads(result[8])
        assert config["seed"] == 12345
        assert len(config["agents"]) == 2
