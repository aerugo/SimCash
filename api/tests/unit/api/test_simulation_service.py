"""Tests for SimulationService (TDD - tests written first).

Following TDD principles, these tests define the expected behavior
of the SimulationService before implementation.
"""

import pytest

from payment_simulator.api.services.simulation_service import (
    SimulationNotFoundError,
    SimulationService,
)


@pytest.fixture
def simple_config() -> dict:
    """Simple valid simulation configuration."""
    return {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 12345,
        },
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "unsecured_cap": 500_000,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 2_000_000,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
        ],
    }


@pytest.fixture
def service() -> SimulationService:
    """Create a fresh SimulationService instance."""
    return SimulationService()


class TestSimulationServiceCreate:
    """Tests for simulation creation."""

    def test_create_simulation_returns_id_and_orchestrator(
        self, service: SimulationService, simple_config: dict
    ) -> None:
        """Creating a simulation returns a simulation ID and orchestrator."""
        sim_id, orchestrator = service.create_simulation(simple_config)

        assert isinstance(sim_id, str)
        assert len(sim_id) > 0
        assert orchestrator is not None

    def test_create_simulation_starts_at_tick_zero(
        self, service: SimulationService, simple_config: dict
    ) -> None:
        """New simulations start at tick 0."""
        sim_id, orchestrator = service.create_simulation(simple_config)

        assert orchestrator.current_tick() == 0
        assert orchestrator.current_day() == 0

    def test_create_simulation_with_invalid_config_raises_value_error(
        self, service: SimulationService
    ) -> None:
        """Invalid configuration raises ValueError."""
        invalid_config = {
            "simulation": {
                "ticks_per_day": 0,  # Invalid: must be > 0
                "num_days": 1,
                "rng_seed": 12345,
            },
            "agents": [],  # Invalid: need at least 2 agents
        }

        with pytest.raises(ValueError, match="Invalid configuration"):
            service.create_simulation(invalid_config)

    def test_each_simulation_gets_unique_id(
        self, service: SimulationService, simple_config: dict
    ) -> None:
        """Each simulation gets a unique ID."""
        sim_id_1, _ = service.create_simulation(simple_config)
        sim_id_2, _ = service.create_simulation(simple_config)

        assert sim_id_1 != sim_id_2


class TestSimulationServiceGet:
    """Tests for retrieving simulations."""

    def test_get_simulation_returns_orchestrator(
        self, service: SimulationService, simple_config: dict
    ) -> None:
        """Can retrieve orchestrator by simulation ID."""
        sim_id, _ = service.create_simulation(simple_config)

        orchestrator = service.get_simulation(sim_id)

        assert orchestrator is not None
        assert orchestrator.current_tick() == 0

    def test_get_nonexistent_simulation_raises_error(
        self, service: SimulationService
    ) -> None:
        """Retrieving non-existent simulation raises SimulationNotFoundError."""
        with pytest.raises(SimulationNotFoundError):
            service.get_simulation("nonexistent-id")

    def test_get_config_returns_stored_config(
        self, service: SimulationService, simple_config: dict
    ) -> None:
        """Can retrieve the original config by simulation ID."""
        sim_id, _ = service.create_simulation(simple_config)

        config = service.get_config(sim_id)

        assert config["original"] == simple_config
        assert "ffi" in config


class TestSimulationServiceState:
    """Tests for simulation state queries."""

    def test_get_state_returns_complete_state(
        self, service: SimulationService, simple_config: dict
    ) -> None:
        """get_state returns complete simulation state."""
        sim_id, _ = service.create_simulation(simple_config)

        state = service.get_state(sim_id)

        assert "simulation_id" in state
        assert "current_tick" in state
        assert "current_day" in state
        assert "agents" in state
        assert "queue2_size" in state

    def test_get_state_includes_agent_balances(
        self, service: SimulationService, simple_config: dict
    ) -> None:
        """get_state includes agent balance information."""
        sim_id, _ = service.create_simulation(simple_config)

        state = service.get_state(sim_id)

        assert "BANK_A" in state["agents"]
        assert state["agents"]["BANK_A"]["balance"] == 1_000_000
        assert state["agents"]["BANK_B"]["balance"] == 2_000_000


class TestSimulationServiceList:
    """Tests for listing simulations."""

    def test_list_simulations_returns_all_active(
        self, service: SimulationService, simple_config: dict
    ) -> None:
        """list_simulations returns all active simulations."""
        sim_id_1, _ = service.create_simulation(simple_config)
        sim_id_2, _ = service.create_simulation(simple_config)

        simulations = service.list_simulations()

        sim_ids = [s["simulation_id"] for s in simulations]
        assert sim_id_1 in sim_ids
        assert sim_id_2 in sim_ids

    def test_list_simulations_empty_when_no_simulations(
        self, service: SimulationService
    ) -> None:
        """list_simulations returns empty list when no simulations."""
        simulations = service.list_simulations()

        assert simulations == []


class TestSimulationServiceDelete:
    """Tests for deleting simulations."""

    def test_delete_removes_simulation(
        self, service: SimulationService, simple_config: dict
    ) -> None:
        """Deleting removes simulation from service."""
        sim_id, _ = service.create_simulation(simple_config)

        service.delete_simulation(sim_id)

        with pytest.raises(SimulationNotFoundError):
            service.get_simulation(sim_id)

    def test_delete_nonexistent_is_idempotent(
        self, service: SimulationService
    ) -> None:
        """Deleting non-existent simulation doesn't raise error."""
        # Should not raise
        service.delete_simulation("nonexistent-id")


class TestSimulationServiceTick:
    """Tests for tick execution."""

    def test_tick_advances_simulation(
        self, service: SimulationService, simple_config: dict
    ) -> None:
        """Executing a tick advances the simulation."""
        sim_id, _ = service.create_simulation(simple_config)

        result = service.tick(sim_id)

        assert result["tick"] == 0  # First tick is tick 0
        orch = service.get_simulation(sim_id)
        assert orch.current_tick() == 1

    def test_tick_returns_expected_fields(
        self, service: SimulationService, simple_config: dict
    ) -> None:
        """Tick result contains expected fields."""
        sim_id, _ = service.create_simulation(simple_config)

        result = service.tick(sim_id)

        assert "tick" in result
        assert "num_arrivals" in result
        assert "num_settlements" in result
        assert "num_lsm_releases" in result
        assert "total_cost" in result

    def test_tick_multiple_returns_list(
        self, service: SimulationService, simple_config: dict
    ) -> None:
        """Executing multiple ticks returns list of results."""
        sim_id, _ = service.create_simulation(simple_config)

        results = service.tick_multiple(sim_id, count=5)

        assert len(results) == 5
        assert results[0]["tick"] == 0
        assert results[4]["tick"] == 4

    def test_tick_nonexistent_raises_error(
        self, service: SimulationService
    ) -> None:
        """Ticking non-existent simulation raises error."""
        with pytest.raises(SimulationNotFoundError):
            service.tick("nonexistent-id")
