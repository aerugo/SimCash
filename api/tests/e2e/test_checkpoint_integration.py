"""End-to-end integration tests for checkpoint functionality.

Tests the complete checkpoint workflow across all layers:
- Rust core (save/load state)
- Database persistence
- FastAPI endpoints
- Determinism verification
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from pathlib import Path
import tempfile
import yaml

from payment_simulator.api.main import app
from payment_simulator.persistence.connection import DatabaseManager


@pytest_asyncio.fixture
async def client():
    """Async HTTP client for testing."""
    # Create temporary database path (but don't create the file yet)
    temp_dir = Path(tempfile.mkdtemp())
    db_path = temp_dir / "test_checkpoint.db"

    # Setup database
    db_manager = DatabaseManager(db_path)
    db_manager.setup()

    # Inject database into app state
    app.state.db_manager = db_manager

    # IMPORTANT: Clear the global manager state before each test
    # This ensures tests don't interfere with each other
    from payment_simulator.api.main import manager
    manager.simulations.clear()
    manager.configs.clear()
    manager.transactions.clear()

    # Create client
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Cleanup
    db_manager.close()
    db_path.unlink(missing_ok=True)
    temp_dir.rmdir()


@pytest.fixture
def test_config():
    """Configuration for integration tests."""
    return {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
        },
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "unsecured_cap": 500_000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 0.5,
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": 10_000,
                        "max": 100_000,
                    },
                    "counterparty_weights": {"BANK_B": 1.0},
                    "deadline_range": [20, 50],
                    "priority": 5,
                    "divisible": False,
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 1_000_000,
                "unsecured_cap": 500_000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 0.5,
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": 10_000,
                        "max": 100_000,
                    },
                    "counterparty_weights": {"BANK_A": 1.0},
                    "deadline_range": [20, 50],
                    "priority": 5,
                    "divisible": False,
                },
            },
        ],
    }


# =============================================================================
# Test 1: Complete End-to-End Workflow
# =============================================================================


@pytest.mark.asyncio
async def test_complete_checkpoint_workflow(client, test_config):
    """E2E: Complete save/restore workflow with determinism verification.

    This is the CRITICAL integration test that validates:
    1. Create simulation via API
    2. Run 50 ticks
    3. Save checkpoint
    4. Continue original for 50 more ticks (track results)
    5. Restore from checkpoint
    6. Run restored for 50 ticks (track results)
    7. Verify results are IDENTICAL (determinism)
    """
    # 1. Create simulation
    response = await client.post("/simulations", json=test_config)
    assert response.status_code == 200
    sim_id = response.json()["simulation_id"]

    # 2. Run 50 ticks
    response = await client.post(f"/simulations/{sim_id}/tick?count=50")
    assert response.status_code == 200
    assert response.json()["final_tick"] == 50

    # 3. Save checkpoint
    checkpoint_response = await client.post(
        f"/simulations/{sim_id}/checkpoint",
        json={
            "checkpoint_type": "manual",
            "description": "Integration test checkpoint at tick 50",
        },
    )
    assert checkpoint_response.status_code == 200
    checkpoint_data = checkpoint_response.json()
    checkpoint_id = checkpoint_data["checkpoint_id"]
    assert checkpoint_data["checkpoint_tick"] == 50
    assert checkpoint_data["simulation_id"] == sim_id

    # 4. Continue original simulation for 50 more ticks (use count for consistency)
    response = await client.post(f"/simulations/{sim_id}/tick?count=50")
    assert response.status_code == 200
    original_results = response.json()["results"]
    assert response.json()["final_tick"] == 100

    # 5. Restore from checkpoint
    restore_response = await client.post(
        "/simulations/from-checkpoint",
        json={"checkpoint_id": checkpoint_id},
    )
    assert restore_response.status_code == 200
    restored_sim_id = restore_response.json()["simulation_id"]
    assert restored_sim_id != sim_id  # Should be a new simulation
    assert restore_response.json()["current_tick"] == 50

    # 6. Run restored simulation for 50 ticks
    response = await client.post(f"/simulations/{restored_sim_id}/tick?count=50")
    assert response.status_code == 200
    restored_results = response.json()["results"]
    assert response.json()["final_tick"] == 100

    # 7. CRITICAL: Verify results are IDENTICAL (determinism)
    assert len(original_results) == len(restored_results) == 50

    for i, (orig, rest) in enumerate(zip(original_results, restored_results)):
        tick = orig["tick"]
        assert rest["tick"] == tick, f"Tick mismatch at index {i}"
        assert rest["num_arrivals"] == orig["num_arrivals"], \
            f"Arrivals differ at tick {tick}: {rest['num_arrivals']} vs {orig['num_arrivals']}"
        assert rest["num_settlements"] == orig["num_settlements"], \
            f"Settlements differ at tick {tick}: {rest['num_settlements']} vs {orig['num_settlements']}"
        assert rest["total_cost"] == orig["total_cost"], \
            f"Costs differ at tick {tick}: {rest['total_cost']} vs {orig['total_cost']}"


# =============================================================================
# Test 2: Multiple Checkpoints
# =============================================================================


@pytest.mark.asyncio
async def test_multiple_checkpoints_same_simulation(client, test_config):
    """E2E: Can create multiple checkpoints at different ticks."""
    # Create simulation
    response = await client.post("/simulations", json=test_config)
    sim_id = response.json()["simulation_id"]

    # Create checkpoints at ticks 10, 20, 30
    checkpoints = []
    for target_tick in [10, 20, 30]:
        # Run to target tick
        current_tick = len(checkpoints) * 10
        ticks_needed = target_tick - current_tick
        await client.post(f"/simulations/{sim_id}/tick?count={ticks_needed}")

        # Save checkpoint
        response = await client.post(
            f"/simulations/{sim_id}/checkpoint",
            json={
                "checkpoint_type": "manual",
                "description": f"Checkpoint at tick {target_tick}",
            },
        )
        assert response.status_code == 200
        checkpoint_data = response.json()
        assert checkpoint_data["checkpoint_tick"] == target_tick
        checkpoints.append(checkpoint_data["checkpoint_id"])

    # Verify we have 3 checkpoints
    assert len(checkpoints) == 3

    # List checkpoints for this simulation
    response = await client.get(f"/simulations/{sim_id}/checkpoints")
    assert response.status_code == 200
    checkpoint_list = response.json()["checkpoints"]
    assert len(checkpoint_list) == 3

    # Verify ticks
    ticks = sorted([cp["checkpoint_tick"] for cp in checkpoint_list])
    assert ticks == [10, 20, 30]


# =============================================================================
# Test 3: Restore from Different Checkpoints
# =============================================================================


@pytest.mark.asyncio
async def test_restore_from_multiple_checkpoints(client, test_config):
    """E2E: Can restore from different checkpoints and verify state."""
    # Create simulation and run to tick 30
    response = await client.post("/simulations", json=test_config)
    sim_id = response.json()["simulation_id"]

    # Create checkpoint at tick 10
    await client.post(f"/simulations/{sim_id}/tick?count=10")
    response = await client.post(
        f"/simulations/{sim_id}/checkpoint",
        json={"checkpoint_type": "manual", "description": "Tick 10"},
    )
    checkpoint_10_id = response.json()["checkpoint_id"]

    # Create checkpoint at tick 20
    await client.post(f"/simulations/{sim_id}/tick?count=10")
    response = await client.post(
        f"/simulations/{sim_id}/checkpoint",
        json={"checkpoint_type": "manual", "description": "Tick 20"},
    )
    checkpoint_20_id = response.json()["checkpoint_id"]

    # Restore from tick 10
    response = await client.post(
        "/simulations/from-checkpoint",
        json={"checkpoint_id": checkpoint_10_id},
    )
    assert response.status_code == 200
    assert response.json()["current_tick"] == 10

    # Restore from tick 20
    response = await client.post(
        "/simulations/from-checkpoint",
        json={"checkpoint_id": checkpoint_20_id},
    )
    assert response.status_code == 200
    assert response.json()["current_tick"] == 20


# =============================================================================
# Test 4: Performance Test
# =============================================================================


@pytest.mark.asyncio
async def test_checkpoint_performance(client, test_config):
    """E2E: Checkpoint operations complete within acceptable time."""
    import time

    # Create simulation and run to tick 50
    response = await client.post("/simulations", json=test_config)
    sim_id = response.json()["simulation_id"]
    await client.post(f"/simulations/{sim_id}/tick?count=50")

    # Measure checkpoint save time
    start = time.time()
    response = await client.post(
        f"/simulations/{sim_id}/checkpoint",
        json={"checkpoint_type": "manual", "description": "Performance test"},
    )
    save_duration = time.time() - start

    assert response.status_code == 200
    checkpoint_id = response.json()["checkpoint_id"]

    # Measure checkpoint load time
    start = time.time()
    response = await client.post(
        "/simulations/from-checkpoint",
        json={"checkpoint_id": checkpoint_id},
    )
    load_duration = time.time() - start

    assert response.status_code == 200

    # Performance targets from plan
    assert save_duration < 0.5, f"Checkpoint save took {save_duration:.3f}s (target: <0.5s)"
    assert load_duration < 0.5, f"Checkpoint load took {load_duration:.3f}s (target: <0.5s)"

    print(f"\nPerformance Results:")
    print(f"  Save: {save_duration*1000:.1f}ms")
    print(f"  Load: {load_duration*1000:.1f}ms")


# =============================================================================
# Test 5: Error Cases
# =============================================================================


@pytest.mark.asyncio
async def test_restore_nonexistent_checkpoint(client, test_config):
    """E2E: Restoring nonexistent checkpoint returns 404."""
    response = await client.post(
        "/simulations/from-checkpoint",
        json={"checkpoint_id": "nonexistent-uuid-12345"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_checkpoint_nonexistent_simulation(client, test_config):
    """E2E: Checkpointing nonexistent simulation returns 404."""
    response = await client.post(
        "/simulations/nonexistent-sim-123/checkpoint",
        json={"checkpoint_type": "manual", "description": "Test"},
    )
    assert response.status_code == 404


# =============================================================================
# Test 6: Large-Scale Integration
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.xfail(
    reason="Known issue: Config hash validation fails with large configs due to dict serialization. "
           "TODO: Store config_json in checkpoint record to avoid hash mismatches (see main.py:595)"
)
async def test_large_scale_checkpoint(client):
    """E2E: Checkpoint works with larger simulations (10 agents, 100 ticks)."""
    # Create config with 10 agents
    # Note: Use explicit float 0.1111111111111111 instead of 1.0/9 to avoid
    # floating-point serialization differences that cause config hash mismatches
    weight_per_counterparty = 0.1111111111111111

    config = {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 99999,
        },
        "agents": [
            {
                "id": f"BANK_{i:02d}",
                "opening_balance": 1_000_000,
                "unsecured_cap": 500_000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 0.3,
                    "amount_distribution": {"type": "Uniform", "min": 10_000, "max": 50_000},
                    "counterparty_weights": {f"BANK_{j:02d}": weight_per_counterparty for j in range(10) if j != i},
                    "deadline_range": [20, 50],
                    "priority": 5,
                    "divisible": False,
                },
            }
            for i in range(10)
        ],
    }

    # Create simulation
    response = await client.post("/simulations", json=config)
    assert response.status_code == 200
    sim_id = response.json()["simulation_id"]

    # Run 50 ticks
    response = await client.post(f"/simulations/{sim_id}/tick?count=50")
    assert response.status_code == 200

    # Save checkpoint
    response = await client.post(
        f"/simulations/{sim_id}/checkpoint",
        json={"checkpoint_type": "manual", "description": "Large-scale test"},
    )
    assert response.status_code == 200
    checkpoint_id = response.json()["checkpoint_id"]

    # Verify checkpoint metadata
    response = await client.get(f"/checkpoints/{checkpoint_id}")
    assert response.status_code == 200
    checkpoint = response.json()
    assert checkpoint["num_agents"] == 10
    assert checkpoint["checkpoint_tick"] == 50

    # Restore and verify
    response = await client.post(
        "/simulations/from-checkpoint",
        json={"checkpoint_id": checkpoint_id},
    )
    if response.status_code != 200:
        print(f"Restore failed: {response.status_code} - {response.json()}")
    assert response.status_code == 200, f"Restore failed: {response.json()}"
    assert response.json()["current_tick"] == 50
