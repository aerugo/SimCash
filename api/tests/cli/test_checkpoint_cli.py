"""CLI tests for checkpoint commands (TDD - tests written first).

Sprint 5: CLI Layer Tests

Tests for checkpoint save/load/list via CLI commands.
Tests are written BEFORE implementation (TDD RED phase).
"""
import pytest
from typer.testing import CliRunner
from pathlib import Path
import json

from payment_simulator.cli.main import app
from payment_simulator.persistence.connection import DatabaseManager
from payment_simulator._core import Orchestrator
import yaml


def create_test_checkpoint(tmp_path, sim_id="test_sim", num_ticks=10):
    """Helper to create a checkpoint for testing.

    Returns: (config_file, state_file, checkpoint_id)
    """
    state_file = tmp_path / f"{sim_id}_state.json"
    config_file = tmp_path / f"{sim_id}_config.yaml"

    # Create YAML config
    yaml_config = {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 12345,
        },
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "credit_limit": 500_000,
                "policy": {"type": "Fifo"},
            },
        ],
    }
    with open(config_file, 'w') as f:
        yaml.dump(yaml_config, f)

    # Create FFI config for orchestrator
    ffi_config = {
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
        ],
    }
    orch = Orchestrator.new(ffi_config)
    for _ in range(num_ticks):
        orch.tick()

    state_json = orch.save_state()
    with open(state_file, 'w') as f:
        f.write(state_json)

    return config_file, state_file


@pytest.fixture
def runner():
    """CLI test runner."""
    return CliRunner()


@pytest.fixture
def db_path(tmp_path):
    """Temporary database for testing."""
    db_file = tmp_path / "test_cli.db"
    db_manager = DatabaseManager(str(db_file))
    db_manager.setup()
    db_manager.close()
    return db_file


@pytest.fixture
def simple_config_file(tmp_path):
    """Simple simulation configuration file."""
    config = {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 12345,
        },
        "agents": [
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

    config_file = tmp_path / "test_config.yaml"
    import yaml
    with open(config_file, 'w') as f:
        yaml.dump(config, f)

    return config_file


@pytest.fixture
def simulation_state_json():
    """Mock simulation state JSON for testing."""
    # Create a simple orchestrator and get its state
    config = {
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
        ],
    }

    orch = Orchestrator.new(config)
    for _ in range(5):
        orch.tick()

    return orch.save_state()


# =============================================================================
# Test 1: Checkpoint save command
# =============================================================================


def test_checkpoint_save_command_displays_help(runner):
    """CLI: checkpoint save --help displays usage information."""
    result = runner.invoke(app, ["checkpoint", "save", "--help"])

    assert result.exit_code == 0
    assert "Save" in result.output or "save" in result.output
    assert "simulation" in result.output.lower()


def test_checkpoint_save_requires_simulation_id(runner):
    """CLI: checkpoint save requires --simulation-id flag."""
    result = runner.invoke(app, ["checkpoint", "save"])

    # Should fail with missing argument error
    assert result.exit_code != 0


def test_checkpoint_save_creates_checkpoint(runner, db_path, tmp_path):
    """CLI: checkpoint save creates checkpoint in database."""
    # This test will fail until we implement the command
    # For now, we're just defining the expected behavior

    # Set environment variable for database path
    import os
    os.environ["PAYMENT_SIM_DB_PATH"] = str(db_path)

    # Create a temporary state file and config file
    state_file = tmp_path / "sim_state.json"
    config_file = tmp_path / "config.yaml"

    config = {
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
        ],
    }

    # Write config to YAML file in the format that SimulationConfig.from_dict expects
    import yaml
    yaml_config = {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 12345,
        },
        "agents": [  # Note: YAML uses "agents", FFI uses "agent_configs"
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "credit_limit": 500_000,
                "policy": {"type": "Fifo"},
            },
        ],
    }
    with open(config_file, 'w') as f:
        yaml.dump(yaml_config, f)

    # Create orchestrator and save state
    orch = Orchestrator.new(config)
    for _ in range(5):
        orch.tick()

    state_json = orch.save_state()
    with open(state_file, 'w') as f:
        f.write(state_json)

    # Run checkpoint save command
    result = runner.invoke(app, [
        "checkpoint", "save",
        "--simulation-id", "test_sim_001",
        "--state-file", str(state_file),
        "--config", str(config_file),
        "--description", "Test checkpoint from CLI"
    ])

    # Should succeed
    if result.exit_code != 0:
        print(f"Command failed with exit code {result.exit_code}")
        print(f"Output: {result.output}")
        if result.exception:
            print(f"Exception: {result.exception}")
    assert result.exit_code == 0
    assert "saved" in result.output.lower() or "checkpoint" in result.output.lower()


# =============================================================================
# Test 2: Checkpoint load command
# =============================================================================


def test_checkpoint_load_command_displays_help(runner):
    """CLI: checkpoint load --help displays usage information."""
    result = runner.invoke(app, ["checkpoint", "load", "--help"])

    assert result.exit_code == 0
    assert "Load" in result.output or "load" in result.output
    assert "checkpoint" in result.output.lower()


def test_checkpoint_load_requires_checkpoint_id(runner):
    """CLI: checkpoint load requires --checkpoint-id flag."""
    result = runner.invoke(app, ["checkpoint", "load"])

    # Should fail with missing argument error
    assert result.exit_code != 0


def test_checkpoint_load_requires_config_file(runner):
    """CLI: checkpoint load requires --config flag."""
    result = runner.invoke(app, [
        "checkpoint", "load",
        "--checkpoint-id", "some_id"
    ])

    # Should fail with missing config error
    assert result.exit_code != 0


def test_checkpoint_load_restores_simulation(runner, db_path, simple_config_file, tmp_path):
    """CLI: checkpoint load restores and displays simulation state."""
    import os
    import yaml
    os.environ["PAYMENT_SIM_DB_PATH"] = str(db_path)

    # First, save a checkpoint
    state_file = tmp_path / "sim_state.json"
    config_file = tmp_path / "config.yaml"

    # Create YAML config
    yaml_config = {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 12345,
        },
        "agents": [
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
    with open(config_file, 'w') as f:
        yaml.dump(yaml_config, f)

    # Create FFI config for orchestrator
    config = {
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
    orch = Orchestrator.new(config)
    for _ in range(10):
        orch.tick()

    state_json = orch.save_state()
    with open(state_file, 'w') as f:
        f.write(state_json)

    # Save checkpoint
    save_result = runner.invoke(app, [
        "checkpoint", "save",
        "--simulation-id", "test_sim_002",
        "--state-file", str(state_file),
        "--config", str(config_file),
        "--description", "Before load test"
    ])

    # Extract checkpoint ID from output (will need to parse)
    # For now, assume first checkpoint

    # Load checkpoint
    result = runner.invoke(app, [
        "checkpoint", "load",
        "--checkpoint-id", "latest",  # Use "latest" as shortcut
        "--simulation-id", "test_sim_002",
        "--config", str(simple_config_file)
    ])

    assert result.exit_code == 0
    assert "restored" in result.output.lower() or "loaded" in result.output.lower()
    assert "tick" in result.output.lower()


# =============================================================================
# Test 3: Checkpoint list command
# =============================================================================


def test_checkpoint_list_command_displays_help(runner):
    """CLI: checkpoint list --help displays usage information."""
    result = runner.invoke(app, ["checkpoint", "list", "--help"])

    assert result.exit_code == 0
    assert "List" in result.output or "list" in result.output


def test_checkpoint_list_shows_empty_message(runner, db_path):
    """CLI: checkpoint list shows message when no checkpoints exist."""
    import os
    os.environ["PAYMENT_SIM_DB_PATH"] = str(db_path)

    result = runner.invoke(app, ["checkpoint", "list"])

    assert result.exit_code == 0
    assert "no checkpoints" in result.output.lower() or "0 checkpoint" in result.output.lower()


def test_checkpoint_list_displays_checkpoints(runner, db_path, tmp_path):
    """CLI: checkpoint list displays table of checkpoints."""
    import os
    os.environ["PAYMENT_SIM_DB_PATH"] = str(db_path)

    # Create multiple checkpoints
    for i in range(3):
        config_file, state_file = create_test_checkpoint(tmp_path, sim_id=f"test_sim_003_{i}", num_ticks=i * 2)

        runner.invoke(app, [
            "checkpoint", "save",
            "--simulation-id", "test_sim_003",
            "--state-file", str(state_file),
            "--config", str(config_file),
            "--description", f"Checkpoint {i}"
        ])

    # List checkpoints
    result = runner.invoke(app, ["checkpoint", "list"])

    assert result.exit_code == 0
    assert "test_sim_003" in result.output
    # Should display in table format
    assert "checkpoint" in result.output.lower()


def test_checkpoint_list_filters_by_simulation(runner, db_path, tmp_path):
    """CLI: checkpoint list --simulation-id filters results."""
    import os
    os.environ["PAYMENT_SIM_DB_PATH"] = str(db_path)

    # Create checkpoints for different simulations
    for sim_id in ["sim_A", "sim_B"]:
        config_file, state_file = create_test_checkpoint(tmp_path, sim_id=sim_id, num_ticks=1)

        runner.invoke(app, [
            "checkpoint", "save",
            "--simulation-id", sim_id,
            "--state-file", str(state_file),
            "--config", str(config_file),
        ])

    # List only sim_A checkpoints
    result = runner.invoke(app, [
        "checkpoint", "list",
        "--simulation-id", "sim_A"
    ])

    assert result.exit_code == 0
    assert "sim_A" in result.output
    assert "sim_B" not in result.output


# =============================================================================
# Test 4: Checkpoint delete command
# =============================================================================


def test_checkpoint_delete_command_displays_help(runner):
    """CLI: checkpoint delete --help displays usage information."""
    result = runner.invoke(app, ["checkpoint", "delete", "--help"])

    assert result.exit_code == 0
    assert "delete" in result.output.lower()


def test_checkpoint_delete_removes_checkpoint(runner, db_path, tmp_path):
    """CLI: checkpoint delete removes checkpoint from database."""
    import os
    os.environ["PAYMENT_SIM_DB_PATH"] = str(db_path)

    # Create a checkpoint
    config_file, state_file = create_test_checkpoint(tmp_path, sim_id="test_sim_delete", num_ticks=1)

    save_result = runner.invoke(app, [
        "checkpoint", "save",
        "--simulation-id", "test_sim_delete",
        "--state-file", str(state_file),
        "--config", str(config_file),
    ])

    # List to verify it exists
    list_before = runner.invoke(app, ["checkpoint", "list"])
    assert "test_sim_delete" in list_before.output

    # Get checkpoint ID (for simplicity, use pattern matching or assume first)
    # For this test, we'll use a helper or assume we can get it

    # Delete - using simulation ID to delete all checkpoints for that sim
    result = runner.invoke(app, [
        "checkpoint", "delete",
        "--simulation-id", "test_sim_delete",
        "--confirm"  # Skip interactive confirmation
    ])

    assert result.exit_code == 0
    assert "deleted" in result.output.lower()

    # Verify it's gone
    list_after = runner.invoke(app, ["checkpoint", "list"])
    # Should not show deleted simulation
    assert "test_sim_delete" not in list_after.output or "0 checkpoint" in list_after.output.lower()


# =============================================================================
# Test 5: Integration tests
# =============================================================================


def test_checkpoint_workflow_save_list_load(runner, db_path, tmp_path):
    """CLI: Complete workflow - save, list, load."""
    import os
    import yaml
    os.environ["PAYMENT_SIM_DB_PATH"] = str(db_path)

    # 1. Save checkpoint - create config file
    config_file = tmp_path / "workflow_config.yaml"
    yaml_config = {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
        },
        "agents": [
            {"id": "BANK_A", "opening_balance": 1_000_000, "credit_limit": 500_000, "policy": {"type": "Fifo"}},
            {"id": "BANK_B", "opening_balance": 2_000_000, "credit_limit": 0, "policy": {"type": "Fifo"}},
        ],
    }
    with open(config_file, 'w') as f:
        yaml.dump(yaml_config, f)

    # Create orchestrator and state
    state_file = tmp_path / "workflow_state.json"
    ffi_config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 42,
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
    orch = Orchestrator.new(ffi_config)
    for _ in range(15):
        orch.tick()

    state_json = orch.save_state()
    with open(state_file, 'w') as f:
        f.write(state_json)

    save_result = runner.invoke(app, [
        "checkpoint", "save",
        "--simulation-id", "workflow_test",
        "--state-file", str(state_file),
        "--config", str(config_file),
        "--description", "Workflow checkpoint"
    ])
    assert save_result.exit_code == 0

    # 2. List checkpoints
    list_result = runner.invoke(app, ["checkpoint", "list"])
    assert list_result.exit_code == 0
    assert "workflow_test" in list_result.output

    # 3. Load checkpoint (config_file already created above)
    load_result = runner.invoke(app, [
        "checkpoint", "load",
        "--checkpoint-id", "latest",
        "--simulation-id", "workflow_test",
        "--config", str(config_file)
    ])
    assert load_result.exit_code == 0
    assert "tick" in load_result.output.lower()
