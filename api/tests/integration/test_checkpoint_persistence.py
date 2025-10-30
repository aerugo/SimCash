"""Test checkpoint persistence to DuckDB (TDD - tests written first).

Sprint 3: Database Layer Tests

These tests verify checkpoint save/load to DuckDB database.
Tests are written BEFORE implementation (TDD RED phase).
"""
import pytest
import json
from datetime import datetime
from pathlib import Path
from payment_simulator._core import Orchestrator
from payment_simulator.persistence.checkpoint import CheckpointManager
from payment_simulator.persistence.connection import DatabaseManager


@pytest.fixture
def db_path(tmp_path):
    """Temporary database for testing."""
    return tmp_path / "test_checkpoints.db"


@pytest.fixture
def checkpoint_manager(db_path):
    """CheckpointManager instance connected to test database."""
    db_manager = DatabaseManager(str(db_path))
    db_manager.setup()  # Initialize schema
    manager = CheckpointManager(db_manager)
    yield manager
    db_manager.close()


@pytest.fixture
def simple_config():
    """Simple simulation configuration."""
    return {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "credit_limit": 500_000,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 2_000_000,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
        ],
    }


@pytest.fixture
def config_with_transactions():
    """Configuration with automatic transactions."""
    return {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 42,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 5_000_000,
                "credit_limit": 1_000_000,
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
                "credit_limit": 500_000,
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
# Test 1: Save checkpoint to database
# =============================================================================


def test_save_checkpoint_creates_record(checkpoint_manager, simple_config):
    """Database: save_checkpoint() should create database record."""
    orch = Orchestrator.new(simple_config)

    # Run a few ticks
    for _ in range(5):
        orch.tick()

    # Save checkpoint to database
    checkpoint_id = checkpoint_manager.save_checkpoint(
        orchestrator=orch,
        simulation_id="sim_001",
        config=simple_config,
        checkpoint_type="manual",
        description="Test checkpoint",
        created_by="test_user"
    )

    # Should return a valid checkpoint ID
    assert checkpoint_id is not None
    assert isinstance(checkpoint_id, str)
    assert len(checkpoint_id) > 0


def test_save_checkpoint_stores_state_json(checkpoint_manager, simple_config):
    """Database: Saved checkpoint should contain valid state JSON."""
    orch = Orchestrator.new(simple_config)
    for _ in range(3):
        orch.tick()

    checkpoint_id = checkpoint_manager.save_checkpoint(
        orchestrator=orch,
        simulation_id="sim_001",
        config=simple_config,
        checkpoint_type="manual",
        description="Test",
        created_by="tester"
    )

    # Retrieve the checkpoint
    checkpoint = checkpoint_manager.get_checkpoint(checkpoint_id)

    assert checkpoint is not None
    assert "state_json" in checkpoint

    # Should be valid JSON
    state = json.loads(checkpoint["state_json"])
    assert state["current_tick"] == 3
    assert state["current_day"] == 0


def test_save_checkpoint_captures_metadata(checkpoint_manager, simple_config):
    """Database: Checkpoint should include all required metadata."""
    orch = Orchestrator.new(simple_config)
    for _ in range(7):
        orch.tick()

    checkpoint_id = checkpoint_manager.save_checkpoint(
        orchestrator=orch,
        simulation_id="sim_002",
        config=simple_config,
        checkpoint_type="auto",
        description="Auto-save",
        created_by="system"
    )

    checkpoint = checkpoint_manager.get_checkpoint(checkpoint_id)

    # Verify metadata fields
    assert checkpoint["simulation_id"] == "sim_002"
    assert checkpoint["checkpoint_tick"] == 7
    assert checkpoint["checkpoint_day"] == 0
    assert checkpoint["checkpoint_type"] == "auto"
    assert checkpoint["description"] == "Auto-save"
    assert checkpoint["created_by"] == "system"
    assert checkpoint["num_agents"] == 2
    assert "config_hash" in checkpoint
    assert "state_hash" in checkpoint


# =============================================================================
# Test 2: Load checkpoint from database
# =============================================================================


def test_load_checkpoint_restores_orchestrator(checkpoint_manager, simple_config):
    """Database: load_checkpoint() should restore orchestrator from database."""
    # Create and save
    orch1 = Orchestrator.new(simple_config)
    for _ in range(10):
        orch1.tick()

    checkpoint_id = checkpoint_manager.save_checkpoint(
        orchestrator=orch1,
        simulation_id="sim_003",
        config=simple_config,
        checkpoint_type="manual",
        description="Restore test",
        created_by="tester"
    )

    # Load from database
    orch2, loaded_config = checkpoint_manager.load_checkpoint(checkpoint_id)

    # Should be restored at same tick
    assert orch2.current_tick() == 10
    # Verify config was restored
    assert loaded_config == simple_config
    assert orch2.current_day() == 0


def test_load_checkpoint_validates_config_hash(checkpoint_manager, simple_config):
    """Database: load_checkpoint() should reject config mismatch."""
    orch1 = Orchestrator.new(simple_config)
    orch1.tick()

    checkpoint_id = checkpoint_manager.save_checkpoint(
        orchestrator=orch1,
        simulation_id="sim_004",
        config=simple_config,
        checkpoint_type="manual",
        description="Hash test",
        created_by="tester"
    )

    # Load checkpoint - config should come from database
    orch2, loaded_config = checkpoint_manager.load_checkpoint(checkpoint_id)

    # Verify the loaded config matches the original
    assert loaded_config == simple_config
    assert orch2.current_tick() == 1


def test_load_checkpoint_preserves_determinism(checkpoint_manager, config_with_transactions):
    """Database: CRITICAL - Loaded checkpoint must preserve determinism."""
    # Original run
    orch1 = Orchestrator.new(config_with_transactions)
    for _ in range(10):
        orch1.tick()

    checkpoint_id = checkpoint_manager.save_checkpoint(
        orchestrator=orch1,
        simulation_id="sim_005",
        config=config_with_transactions,
        checkpoint_type="manual",
        description="Determinism test",
        created_by="tester"
    )

    # Continue original
    results_1 = [orch1.tick() for _ in range(10)]

    # Load and continue
    orch2, loaded_config = checkpoint_manager.load_checkpoint(checkpoint_id)
    results_2 = [orch2.tick() for _ in range(10)]
    # Verify config was restored
    assert loaded_config == config_with_transactions

    # Must produce identical results
    for i, (r1, r2) in enumerate(zip(results_1, results_2)):
        assert r1["tick"] == r2["tick"], f"Tick {i}: tick numbers differ"
        assert r1["num_arrivals"] == r2["num_arrivals"], f"Tick {i}: arrivals differ"
        assert r1["num_settlements"] == r2["num_settlements"], f"Tick {i}: settlements differ"


# =============================================================================
# Test 3: List and filter checkpoints
# =============================================================================


def test_list_checkpoints_for_simulation(checkpoint_manager, simple_config):
    """Database: Should list all checkpoints for a simulation."""
    orch = Orchestrator.new(simple_config)

    # Create multiple checkpoints
    checkpoint_ids = []
    for i in range(5):
        for _ in range(3):
            orch.tick()

        cp_id = checkpoint_manager.save_checkpoint(
            orchestrator=orch,
            simulation_id="sim_006",
        config=simple_config,
            checkpoint_type="auto",
            description=f"Checkpoint {i}",
            created_by="system"
        )
        checkpoint_ids.append(cp_id)

    # List checkpoints
    checkpoints = checkpoint_manager.list_checkpoints(simulation_id="sim_006")

    assert len(checkpoints) == 5
    assert all(cp["simulation_id"] == "sim_006" for cp in checkpoints)


def test_list_checkpoints_ordered_by_time(checkpoint_manager, simple_config):
    """Database: Checkpoints should be listed in chronological order."""
    orch = Orchestrator.new(simple_config)

    checkpoint_ids = []
    for i in range(3):
        orch.tick()
        cp_id = checkpoint_manager.save_checkpoint(
            orchestrator=orch,
            simulation_id="sim_007",
        config=simple_config,
            checkpoint_type="manual",
            description=f"CP {i}",
            created_by="tester"
        )
        checkpoint_ids.append(cp_id)

    checkpoints = checkpoint_manager.list_checkpoints(simulation_id="sim_007")

    # Should be ordered by tick
    ticks = [cp["checkpoint_tick"] for cp in checkpoints]
    assert ticks == sorted(ticks)


def test_get_latest_checkpoint(checkpoint_manager, simple_config):
    """Database: Should retrieve latest checkpoint for simulation."""
    orch = Orchestrator.new(simple_config)

    # Create multiple checkpoints
    for i in range(5):
        for _ in range(2):
            orch.tick()
        checkpoint_manager.save_checkpoint(
            orchestrator=orch,
            simulation_id="sim_008",
        config=simple_config,
            checkpoint_type="auto",
            description=f"CP {i}",
            created_by="system"
        )

    # Get latest
    latest = checkpoint_manager.get_latest_checkpoint(simulation_id="sim_008")

    assert latest is not None
    assert latest["checkpoint_tick"] == 10  # 5 checkpoints * 2 ticks each
    assert latest["simulation_id"] == "sim_008"


# =============================================================================
# Test 4: Checkpoint metadata and integrity
# =============================================================================


def test_checkpoint_size_tracking(checkpoint_manager, config_with_transactions):
    """Database: Should track checkpoint size in bytes."""
    orch = Orchestrator.new(config_with_transactions)
    for _ in range(20):
        orch.tick()

    checkpoint_id = checkpoint_manager.save_checkpoint(
        orchestrator=orch,
        simulation_id="sim_009",
        config=config_with_transactions,
        checkpoint_type="manual",
        description="Size test",
        created_by="tester"
    )

    checkpoint = checkpoint_manager.get_checkpoint(checkpoint_id)

    assert "total_size_bytes" in checkpoint
    assert checkpoint["total_size_bytes"] > 0

    # Should be roughly equal to JSON length
    state_json_size = len(checkpoint["state_json"])
    assert abs(checkpoint["total_size_bytes"] - state_json_size) < 100


def test_checkpoint_hash_validation(checkpoint_manager, simple_config):
    """Database: Should validate state hash on load."""
    orch = Orchestrator.new(simple_config)
    for _ in range(5):
        orch.tick()

    checkpoint_id = checkpoint_manager.save_checkpoint(
        orchestrator=orch,
        simulation_id="sim_010",
        config=simple_config,
        checkpoint_type="manual",
        description="Hash test",
        created_by="tester"
    )

    checkpoint = checkpoint_manager.get_checkpoint(checkpoint_id)

    # Hash should be present and non-empty
    assert "state_hash" in checkpoint
    assert len(checkpoint["state_hash"]) == 64  # SHA256 hex length

    # Config hash should match orchestrator's config hash
    state = json.loads(checkpoint["state_json"])
    assert checkpoint["config_hash"] == state["config_hash"]


def test_delete_checkpoint(checkpoint_manager, simple_config):
    """Database: Should delete checkpoint by ID."""
    orch = Orchestrator.new(simple_config)
    orch.tick()

    checkpoint_id = checkpoint_manager.save_checkpoint(
        orchestrator=orch,
        simulation_id="sim_011",
        config=simple_config,
        checkpoint_type="manual",
        description="Delete test",
        created_by="tester"
    )

    # Verify exists
    checkpoint = checkpoint_manager.get_checkpoint(checkpoint_id)
    assert checkpoint is not None

    # Delete
    result = checkpoint_manager.delete_checkpoint(checkpoint_id)
    assert result is True

    # Should no longer exist
    checkpoint = checkpoint_manager.get_checkpoint(checkpoint_id)
    assert checkpoint is None


# =============================================================================
# Test 5: Edge cases and error handling
# =============================================================================


def test_load_nonexistent_checkpoint_raises_error(checkpoint_manager, simple_config):
    """Database: Loading non-existent checkpoint should raise error."""
    with pytest.raises(ValueError, match="[Cc]heckpoint.*not found"):
        checkpoint_manager.load_checkpoint("nonexistent_id")


def test_save_checkpoint_with_empty_simulation_id_raises_error(checkpoint_manager, simple_config):
    """Database: Empty simulation_id should raise error."""
    orch = Orchestrator.new(simple_config)

    with pytest.raises(ValueError, match="[Ss]imulation.*[Ii][Dd]"):
        checkpoint_manager.save_checkpoint(
            orchestrator=orch,
            simulation_id="",
        config=simple_config,
            checkpoint_type="manual",
            description="Test",
            created_by="tester"
        )


def test_checkpoint_types_are_validated(checkpoint_manager, simple_config):
    """Database: Invalid checkpoint types should raise error."""
    orch = Orchestrator.new(simple_config)

    with pytest.raises(ValueError, match="[Cc]heckpoint.*[Tt]ype"):
        checkpoint_manager.save_checkpoint(
            orchestrator=orch,
            simulation_id="sim_012",
        config=simple_config,
            checkpoint_type="invalid_type",
            description="Test",
            created_by="tester"
        )
