"""End-to-end tests for checkpoint API endpoints (TDD - tests written first).

Sprint 4: API Layer Tests

Tests for checkpoint save/load via REST API.
Tests are written BEFORE implementation (TDD RED phase).
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient
from pathlib import Path

from payment_simulator.api.main import app
from payment_simulator.persistence.connection import DatabaseManager


@pytest_asyncio.fixture
async def client(tmp_path):
    """Async HTTP client for testing."""
    # Create test database
    db_path = tmp_path / "test_api.db"
    db_manager = DatabaseManager(str(db_path))
    db_manager.setup()

    # Inject database manager into app state
    app.state.db_manager = db_manager

    # Use ASGI transport for testing
    from httpx import ASGITransport
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    db_manager.close()


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


@pytest.fixture
def config_with_transactions():
    """Configuration with automatic transactions."""
    return {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
        },
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 5_000_000,
                "unsecured_cap": 1_000_000,
                "policy": {"type": "LiquidityAware", "target_buffer": 500_000, "urgency_threshold": 5},
                "arrival_config": {
                    "rate_per_tick": 0.5,
                    "amount_distribution": {"type": "Normal", "mean": 100_000, "std_dev": 50_000},
                    "counterparty_weights": {"BANK_B": 1.0},
                    "deadline_range": [10, 50],
                    "priority": 5,
                    "divisible": True,
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 3_000_000,
                "unsecured_cap": 500_000,
                "policy": {"type": "Deadline", "urgency_threshold": 10},
                "arrival_config": {
                    "rate_per_tick": 0.3,
                    "amount_distribution": {"type": "Uniform", "min": 50_000, "max": 200_000},
                    "counterparty_weights": {"BANK_A": 1.0},
                    "deadline_range": [5, 30],
                    "priority": 7,
                    "divisible": False,
                },
            },
        ],
    }


# =============================================================================
# Test 1: Save checkpoint endpoint
# =============================================================================


@pytest.mark.asyncio
async def test_save_checkpoint_endpoint(client: AsyncClient, simple_config):
    """POST /simulations/{id}/checkpoint saves state."""
    # Create simulation
    response = await client.post("/simulations", json=simple_config)
    assert response.status_code == 200
    sim_id = response.json()["simulation_id"]

    # Run a few ticks
    await client.post(f"/simulations/{sim_id}/tick?count=5")

    # Save checkpoint
    response = await client.post(
        f"/simulations/{sim_id}/checkpoint",
        json={
            "checkpoint_type": "manual",
            "description": "Test checkpoint"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert "checkpoint_id" in data
    assert data["simulation_id"] == sim_id
    assert data["checkpoint_tick"] == 5


@pytest.mark.asyncio
async def test_save_checkpoint_validates_type(client: AsyncClient, simple_config):
    """POST /simulations/{id}/checkpoint validates checkpoint_type."""
    response = await client.post("/simulations", json=simple_config)
    sim_id = response.json()["simulation_id"]

    # Invalid checkpoint type
    response = await client.post(
        f"/simulations/{sim_id}/checkpoint",
        json={
            "checkpoint_type": "invalid_type",
            "description": "Test"
        }
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_save_checkpoint_simulation_not_found(client: AsyncClient):
    """POST /simulations/{id}/checkpoint returns 404 for missing simulation."""
    response = await client.post(
        "/simulations/nonexistent/checkpoint",
        json={
            "checkpoint_type": "manual",
            "description": "Test"
        }
    )

    assert response.status_code == 404


# =============================================================================
# Test 2: Load checkpoint endpoint
# =============================================================================


@pytest.mark.asyncio
async def test_load_checkpoint_endpoint(client: AsyncClient, simple_config):
    """POST /simulations/from-checkpoint creates new simulation."""
    # Create and run simulation
    response = await client.post("/simulations", json=simple_config)
    sim_id = response.json()["simulation_id"]

    await client.post(f"/simulations/{sim_id}/tick?count=10")

    # Save checkpoint
    checkpoint_response = await client.post(
        f"/simulations/{sim_id}/checkpoint",
        json={"checkpoint_type": "manual", "description": "Test"}
    )
    checkpoint_id = checkpoint_response.json()["checkpoint_id"]

    # Load from checkpoint (creates new simulation)
    response = await client.post(
        "/simulations/from-checkpoint",
        json={"checkpoint_id": checkpoint_id}
    )

    assert response.status_code == 200
    data = response.json()
    assert "simulation_id" in data
    assert data["current_tick"] == 10
    assert data["current_day"] == 0

    # New simulation should have different ID
    assert data["simulation_id"] != sim_id


@pytest.mark.asyncio
async def test_load_checkpoint_not_found(client: AsyncClient):
    """POST /simulations/from-checkpoint returns 404 for missing checkpoint."""
    response = await client.post(
        "/simulations/from-checkpoint",
        json={"checkpoint_id": "nonexistent"}
    )

    assert response.status_code == 404


# =============================================================================
# Test 3: List checkpoints endpoint
# =============================================================================


@pytest.mark.asyncio
async def test_list_checkpoints_endpoint(client: AsyncClient, simple_config):
    """GET /simulations/{id}/checkpoints lists checkpoints."""
    # Create simulation
    response = await client.post("/simulations", json=simple_config)
    sim_id = response.json()["simulation_id"]

    # Create multiple checkpoints
    checkpoint_ids = []
    for i in range(3):
        await client.post(f"/simulations/{sim_id}/tick?count=2")

        response = await client.post(
            f"/simulations/{sim_id}/checkpoint",
            json={"checkpoint_type": "auto", "description": f"Checkpoint {i}"}
        )
        checkpoint_ids.append(response.json()["checkpoint_id"])

    # List checkpoints
    response = await client.get(f"/simulations/{sim_id}/checkpoints")

    assert response.status_code == 200
    data = response.json()
    assert "checkpoints" in data
    assert len(data["checkpoints"]) == 3

    # Should be ordered by tick
    ticks = [cp["checkpoint_tick"] for cp in data["checkpoints"]]
    assert ticks == sorted(ticks)


@pytest.mark.asyncio
async def test_list_checkpoints_empty(client: AsyncClient, simple_config):
    """GET /simulations/{id}/checkpoints returns empty list when no checkpoints."""
    response = await client.post("/simulations", json=simple_config)
    sim_id = response.json()["simulation_id"]

    response = await client.get(f"/simulations/{sim_id}/checkpoints")

    assert response.status_code == 200
    data = response.json()
    assert data["checkpoints"] == []


@pytest.mark.asyncio
async def test_list_checkpoints_simulation_not_found(client: AsyncClient):
    """GET /simulations/{id}/checkpoints returns 404 for missing simulation."""
    response = await client.get("/simulations/nonexistent/checkpoints")

    assert response.status_code == 404


# =============================================================================
# Test 4: Determinism after restore
# =============================================================================


@pytest.mark.asyncio
async def test_restored_simulation_continues_correctly(client: AsyncClient, config_with_transactions):
    """CRITICAL: Restored simulation produces identical results."""
    # Create simulation
    response = await client.post("/simulations", json=config_with_transactions)
    sim_id = response.json()["simulation_id"]

    # Run 10 ticks
    await client.post(f"/simulations/{sim_id}/tick?count=10")

    # Save checkpoint
    checkpoint_response = await client.post(
        f"/simulations/{sim_id}/checkpoint",
        json={"checkpoint_type": "manual", "description": "Determinism test"}
    )
    checkpoint_id = checkpoint_response.json()["checkpoint_id"]

    # Continue original for 10 more ticks
    response1 = await client.post(f"/simulations/{sim_id}/tick?count=10")
    results1 = response1.json()["results"]

    # Restore and run 10 ticks
    restore_response = await client.post(
        "/simulations/from-checkpoint",
        json={"checkpoint_id": checkpoint_id}
    )
    new_sim_id = restore_response.json()["simulation_id"]

    response2 = await client.post(f"/simulations/{new_sim_id}/tick?count=10")
    results2 = response2.json()["results"]

    # Results must be identical
    assert len(results1) == len(results2)
    for i, (r1, r2) in enumerate(zip(results1, results2)):
        assert r1["tick"] == r2["tick"], f"Tick {i}: tick numbers differ"
        assert r1["num_arrivals"] == r2["num_arrivals"], f"Tick {i}: arrivals differ"
        assert r1["num_settlements"] == r2["num_settlements"], f"Tick {i}: settlements differ"
        assert r1["num_lsm_releases"] == r2["num_lsm_releases"], f"Tick {i}: LSM releases differ"


# =============================================================================
# Test 5: Get checkpoint details
# =============================================================================


@pytest.mark.asyncio
async def test_get_checkpoint_details(client: AsyncClient, simple_config):
    """GET /checkpoints/{checkpoint_id} returns checkpoint metadata."""
    # Create simulation and checkpoint
    response = await client.post("/simulations", json=simple_config)
    sim_id = response.json()["simulation_id"]

    await client.post(f"/simulations/{sim_id}/tick?count=7")

    checkpoint_response = await client.post(
        f"/simulations/{sim_id}/checkpoint",
        json={"checkpoint_type": "manual", "description": "Test checkpoint"}
    )
    checkpoint_id = checkpoint_response.json()["checkpoint_id"]

    # Get checkpoint details
    response = await client.get(f"/checkpoints/{checkpoint_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["checkpoint_id"] == checkpoint_id
    assert data["simulation_id"] == sim_id
    assert data["checkpoint_tick"] == 7
    assert data["checkpoint_type"] == "manual"
    assert data["description"] == "Test checkpoint"
    assert "config_hash" in data
    assert "state_hash" in data


@pytest.mark.asyncio
async def test_get_checkpoint_not_found(client: AsyncClient):
    """GET /checkpoints/{checkpoint_id} returns 404 for missing checkpoint."""
    response = await client.get("/checkpoints/nonexistent")

    assert response.status_code == 404


# =============================================================================
# Test 6: Delete checkpoint
# =============================================================================


@pytest.mark.asyncio
async def test_delete_checkpoint(client: AsyncClient, simple_config):
    """DELETE /checkpoints/{checkpoint_id} deletes checkpoint."""
    # Create simulation and checkpoint
    response = await client.post("/simulations", json=simple_config)
    sim_id = response.json()["simulation_id"]

    checkpoint_response = await client.post(
        f"/simulations/{sim_id}/checkpoint",
        json={"checkpoint_type": "manual", "description": "To be deleted"}
    )
    checkpoint_id = checkpoint_response.json()["checkpoint_id"]

    # Delete checkpoint
    response = await client.delete(f"/checkpoints/{checkpoint_id}")

    assert response.status_code == 200

    # Verify deletion
    response = await client.get(f"/checkpoints/{checkpoint_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_checkpoint_idempotent(client: AsyncClient):
    """DELETE /checkpoints/{checkpoint_id} is idempotent."""
    # Delete non-existent checkpoint (should not error)
    response = await client.delete("/checkpoints/nonexistent")

    assert response.status_code == 200  # Idempotent - no error
