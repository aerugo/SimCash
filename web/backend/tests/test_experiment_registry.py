"""TDD tests for experiment global registry.

Ensures all experiments are registered in the global registry so they're
accessible by direct URL regardless of who's viewing.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.storage import GameStorage


@pytest.fixture
def storage(tmp_path):
    """Create a local-only GameStorage for testing."""
    s = GameStorage(storage_mode="local")
    # Override DATA_DIR to use tmp_path
    import app.storage as storage_mod
    original_data_dir = storage_mod.DATA_DIR
    storage_mod.DATA_DIR = tmp_path
    yield s
    storage_mod.DATA_DIR = original_data_dir


class TestRegistryOnCreate:
    """Experiments must be registered in global registry when created."""

    def test_register_experiment_adds_to_registry(self, storage):
        storage.register_experiment("game-001", "uid-stefan", {
            "scenario_id": "sc1",
            "status": "created",
        })
        owner = storage.lookup_experiment_owner("game-001")
        assert owner == "uid-stefan"

    def test_registered_experiment_accessible_without_uid(self, storage):
        """Any user should be able to look up the owner of a registered experiment."""
        storage.register_experiment("game-001", "uid-stefan", {
            "scenario_id": "sc1",
            "status": "created",
        })
        # Different user can find the owner
        owner = storage.lookup_experiment_owner("game-001")
        assert owner == "uid-stefan"


class TestRegistryOnCheckpointLoad:
    """When loading a checkpoint, if the experiment isn't in the registry, register it."""

    def test_load_checkpoint_registers_missing_experiment(self, storage):
        """Loading a checkpoint should auto-register the experiment if not in registry."""
        uid = "uid-stefan"
        game_id = "game-auto-reg"

        # Create a checkpoint file manually (simulating migration)
        game_dir = storage._local_dir(uid)
        game_dir.mkdir(parents=True, exist_ok=True)
        checkpoint = {
            "game_id": game_id,
            "uid": uid,
            "scenario_id": "sc-test",
            "scenario_name": "Test Scenario",
            "status": "complete",
            "created_at": "2026-02-26T00:00:00Z",
            "config": {"rounds": 10, "use_llm": True},
            "progress": {"current_day": 10, "agent_ids": ["A", "B"]},
        }
        (game_dir / f"{game_id}.json").write_text(json.dumps(checkpoint))

        # Not in registry yet
        assert storage.lookup_experiment_owner(game_id) is None

        # Load checkpoint — should auto-register
        loaded = storage.load_checkpoint(uid, game_id)
        assert loaded is not None

        # Now should be in registry
        owner = storage.lookup_experiment_owner(game_id)
        assert owner == uid

    def test_load_checkpoint_does_not_overwrite_existing_registration(self, storage):
        """If already registered, loading shouldn't change the owner."""
        uid = "uid-stefan"
        game_id = "game-existing"

        # Pre-register under original owner
        storage.register_experiment(game_id, "uid-original", {"status": "running"})

        # Create checkpoint under stefan
        game_dir = storage._local_dir(uid)
        game_dir.mkdir(parents=True, exist_ok=True)
        checkpoint = {
            "game_id": game_id,
            "uid": uid,
            "scenario_id": "sc1",
            "status": "complete",
            "config": {"rounds": 5},
            "progress": {"current_day": 5, "agent_ids": ["A"]},
        }
        (game_dir / f"{game_id}.json").write_text(json.dumps(checkpoint))

        # Load — should NOT overwrite
        storage.load_checkpoint(uid, game_id)
        owner = storage.lookup_experiment_owner(game_id)
        assert owner == "uid-original"


class TestRegistryBackfill:
    """Batch backfill: register all experiments from a user's checkpoints."""

    def test_backfill_registers_all_unregistered(self, storage):
        """backfill_registry should register all experiments not yet in registry."""
        uid = "uid-stefan"
        game_dir = storage._local_dir(uid)
        game_dir.mkdir(parents=True, exist_ok=True)

        # Create 3 checkpoints
        for i in range(3):
            gid = f"game-{i:03d}"
            cp = {
                "game_id": gid,
                "uid": uid,
                "scenario_id": f"sc-{i}",
                "scenario_name": f"Scenario {i}",
                "status": "complete",
                "created_at": f"2026-02-{20+i}T00:00:00Z",
                "config": {"rounds": 10, "use_llm": True},
                "progress": {"current_day": 10, "agent_ids": ["A", "B"]},
            }
            (game_dir / f"{gid}.json").write_text(json.dumps(cp))

        # Pre-register one
        storage.register_experiment("game-001", uid, {"status": "complete"})

        # Backfill
        count = storage.backfill_registry(uid)
        assert count == 2  # Only the 2 unregistered ones

        # All 3 should be in registry
        for i in range(3):
            assert storage.lookup_experiment_owner(f"game-{i:03d}") == uid

    def test_backfill_returns_zero_when_all_registered(self, storage):
        uid = "uid-stefan"
        game_dir = storage._local_dir(uid)
        game_dir.mkdir(parents=True, exist_ok=True)

        gid = "game-already"
        cp = {
            "game_id": gid, "uid": uid, "scenario_id": "sc1",
            "status": "complete", "config": {"rounds": 1},
            "progress": {"current_day": 1, "agent_ids": ["A"]},
        }
        (game_dir / f"{gid}.json").write_text(json.dumps(cp))
        storage.register_experiment(gid, uid, {"status": "complete"})

        count = storage.backfill_registry(uid)
        assert count == 0


class TestListCheckpointsRegisters:
    """list_checkpoints should also backfill registry as a side effect."""

    def test_list_checkpoints_registers_unregistered(self, storage):
        uid = "uid-stefan"
        game_dir = storage._local_dir(uid)
        game_dir.mkdir(parents=True, exist_ok=True)

        gid = "game-list-test"
        cp = {
            "game_id": gid, "uid": uid, "scenario_id": "sc1",
            "scenario_name": "Test", "status": "complete",
            "created_at": "2026-02-26T00:00:00Z",
            "config": {"rounds": 5, "use_llm": True},
            "progress": {"current_day": 5, "agent_ids": ["A", "B"]},
        }
        (game_dir / f"{gid}.json").write_text(json.dumps(cp))

        assert storage.lookup_experiment_owner(gid) is None

        # Listing should trigger registration
        results = storage.list_checkpoints(uid)
        assert len(results) >= 1

        owner = storage.lookup_experiment_owner(gid)
        assert owner == uid
