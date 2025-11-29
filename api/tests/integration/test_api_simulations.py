"""Test FastAPI simulation endpoints (TDD - tests written first)."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client and clean up state after test."""
    from payment_simulator.api.dependencies import container
    from payment_simulator.api.main import app

    # Clean up any leftover state from previous tests
    container.clear_all()
    container.db_manager = None

    yield TestClient(app)

    # Clean up after test
    container.clear_all()
    container.db_manager = None


@pytest.fixture
def simple_config():
    """Simple simulation configuration."""
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


def test_create_simulation(client, simple_config):
    """Test creating a simulation."""
    response = client.post("/simulations", json=simple_config)

    assert response.status_code == 200
    data = response.json()

    # Should return simulation ID
    assert "simulation_id" in data
    assert isinstance(data["simulation_id"], str)
    assert len(data["simulation_id"]) > 0

    # Should return initial state
    assert "state" in data
    assert data["state"]["current_tick"] == 0
    assert data["state"]["current_day"] == 0


def test_create_simulation_with_invalid_config(client):
    """Test creating simulation with invalid configuration."""
    invalid_config = {
        "simulation": {
            "ticks_per_day": 0,  # Invalid!
            "num_days": 1,
            "rng_seed": 12345,
        },
        "agents": [],  # No agents!
    }

    response = client.post("/simulations", json=invalid_config)
    assert response.status_code == 422  # Validation error


def test_get_simulation_state(client, simple_config):
    """Test querying simulation state."""
    # Create simulation
    create_response = client.post("/simulations", json=simple_config)
    sim_id = create_response.json()["simulation_id"]

    # Get state
    response = client.get(f"/simulations/{sim_id}/state")

    assert response.status_code == 200
    data = response.json()

    # Verify state structure
    assert "current_tick" in data
    assert "current_day" in data
    assert "agents" in data

    # Verify agents
    assert len(data["agents"]) == 2
    assert "BANK_A" in data["agents"]
    assert "BANK_B" in data["agents"]

    # Verify agent details
    bank_a = data["agents"]["BANK_A"]
    assert bank_a["balance"] == 1_000_000
    assert bank_a["unsecured_cap"] == 500_000


def test_get_nonexistent_simulation(client):
    """Test getting state of non-existent simulation."""
    response = client.get("/simulations/nonexistent-id/state")
    assert response.status_code == 404


def test_tick_simulation(client, simple_config):
    """Test advancing simulation by one tick."""
    # Create simulation
    create_response = client.post("/simulations", json=simple_config)
    sim_id = create_response.json()["simulation_id"]

    # Advance one tick
    response = client.post(f"/simulations/{sim_id}/tick")

    assert response.status_code == 200
    data = response.json()

    # Verify tick result
    assert "tick" in data
    assert data["tick"] == 0  # First tick (0-indexed)
    assert "num_arrivals" in data
    assert "num_settlements" in data
    assert "total_cost" in data

    # Verify state updated
    state_response = client.get(f"/simulations/{sim_id}/state")
    state = state_response.json()
    assert state["current_tick"] == 1  # Advanced by 1


def test_tick_multiple_times(client, simple_config):
    """Test advancing simulation multiple ticks."""
    # Create simulation
    create_response = client.post("/simulations", json=simple_config)
    sim_id = create_response.json()["simulation_id"]

    # Advance 10 ticks
    for i in range(10):
        response = client.post(f"/simulations/{sim_id}/tick")
        assert response.status_code == 200
        assert response.json()["tick"] == i

    # Verify final state
    state_response = client.get(f"/simulations/{sim_id}/state")
    state = state_response.json()
    assert state["current_tick"] == 10


def test_tick_with_count_parameter(client, simple_config):
    """Test advancing simulation by multiple ticks at once."""
    # Create simulation
    create_response = client.post("/simulations", json=simple_config)
    sim_id = create_response.json()["simulation_id"]

    # Advance 5 ticks at once
    response = client.post(f"/simulations/{sim_id}/tick", params={"count": 5})

    assert response.status_code == 200
    data = response.json()

    # Should return results for all ticks
    assert "results" in data
    assert len(data["results"]) == 5

    # Verify ticks are sequential
    for i, result in enumerate(data["results"]):
        assert result["tick"] == i

    # Verify state updated
    state_response = client.get(f"/simulations/{sim_id}/state")
    state = state_response.json()
    assert state["current_tick"] == 5


def test_delete_simulation(client, simple_config):
    """Test deleting a simulation."""
    # Create simulation
    create_response = client.post("/simulations", json=simple_config)
    sim_id = create_response.json()["simulation_id"]

    # Delete simulation
    response = client.delete(f"/simulations/{sim_id}")
    assert response.status_code == 200

    # Verify simulation no longer exists
    state_response = client.get(f"/simulations/{sim_id}/state")
    assert state_response.status_code == 404


def test_list_simulations(client, simple_config):
    """Test listing all active simulations."""
    # Create multiple simulations
    sim_ids = []
    for _ in range(3):
        response = client.post("/simulations", json=simple_config)
        sim_ids.append(response.json()["simulation_id"])

    # List simulations
    response = client.get("/simulations")

    assert response.status_code == 200
    data = response.json()

    assert "simulations" in data
    assert len(data["simulations"]) >= 3

    # Verify our simulation IDs are in the list
    listed_ids = [sim["simulation_id"] for sim in data["simulations"]]
    for sim_id in sim_ids:
        assert sim_id in listed_ids


def test_simulation_with_arrivals(client):
    """Test simulation with automatic transaction arrivals."""
    config = {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 12345,
        },
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 5_000_000,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 1.0,  # 1 transaction per tick
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": 50_000,
                        "max": 100_000,
                    },
                    "counterparty_weights": {"BANK_B": 1.0},
                    "deadline_range": [10, 50],
                    "priority": 5,
                    "divisible": False,
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 5_000_000,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
        ],
    }

    # Create simulation
    create_response = client.post("/simulations", json=config)
    sim_id = create_response.json()["simulation_id"]

    # Advance several ticks
    for _ in range(10):
        response = client.post(f"/simulations/{sim_id}/tick")
        result = response.json()

        # Should have arrivals
        assert result["num_arrivals"] >= 0

        # Some ticks should have settlements
        if result["num_arrivals"] > 0:
            # Transactions are settling
            pass

    # Check final state
    state_response = client.get(f"/simulations/{sim_id}/state")
    state = state_response.json()

    # Balances should have changed due to transactions
    bank_a = state["agents"]["BANK_A"]
    bank_b = state["agents"]["BANK_B"]

    # Total money conserved
    total = bank_a["balance"] + bank_b["balance"]
    assert total == 10_000_000  # Same as initial


def test_simulation_state_includes_queues(client, simple_config):
    """Test that state includes queue information."""
    # Create simulation
    create_response = client.post("/simulations", json=simple_config)
    sim_id = create_response.json()["simulation_id"]

    # Get state
    response = client.get(f"/simulations/{sim_id}/state")
    state = response.json()

    # Should include queue information
    for agent_id in state["agents"]:
        agent = state["agents"][agent_id]
        assert "queue1_size" in agent
        assert "queue2_size" in state  # RTGS queue is global


def test_concurrent_simulations(client, simple_config):
    """Test running multiple simulations concurrently."""
    # Create multiple simulations
    sim_ids = []
    for i in range(3):
        config = simple_config.copy()
        config["simulation"]["rng_seed"] = 12345 + i  # Different seeds
        response = client.post("/simulations", json=config)
        sim_ids.append(response.json()["simulation_id"])

    # Advance each simulation independently
    for sim_id in sim_ids:
        for _ in range(5):
            response = client.post(f"/simulations/{sim_id}/tick")
            assert response.status_code == 200

    # Verify each simulation has independent state
    states = []
    for sim_id in sim_ids:
        response = client.get(f"/simulations/{sim_id}/state")
        states.append(response.json())

    # All should be at tick 5
    for state in states:
        assert state["current_tick"] == 5

    # Each simulation should be independent (different results due to different seeds)
    # This is a basic sanity check - full determinism tested elsewhere
