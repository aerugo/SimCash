"""
Integration Tests for Policy Snapshot Tracking (Phase 4)

Tests policy change tracking, file management, and hash-based deduplication.

TDD Phase: RED
These tests define requirements before implementation.
Expected to FAIL until Phase 4.2-4.3 implementation.
"""

import json
from pathlib import Path

import duckdb
import polars as pl
import pytest


class TestPolicySnapshotModel:
    """Test PolicySnapshotRecord Pydantic model."""

    def test_policy_snapshot_record_validates(self):
        """Verify PolicySnapshotRecord model validates correctly."""
        from payment_simulator.persistence.models import PolicySnapshotRecord

        record = PolicySnapshotRecord(
            simulation_id="test-sim-001",
            agent_id="BANK_A",
            snapshot_day=0,
            snapshot_tick=0,
            policy_hash="a" * 64,  # SHA256 hex string
            policy_file_path="backend/policies/BANK_A_policy_v1.json",
            policy_json='{"type": "fifo"}',
            created_by="init",
        )

        assert record.simulation_id == "test-sim-001"
        assert record.agent_id == "BANK_A"
        assert record.snapshot_day == 0
        assert len(record.policy_hash) == 64
        assert record.policy_json == '{"type": "fifo"}'

    def test_policy_snapshot_record_has_table_config(self):
        """Verify PolicySnapshotRecord has proper table configuration."""
        from payment_simulator.persistence.models import PolicySnapshotRecord

        config = PolicySnapshotRecord.model_config
        assert config.get("table_name") == "policy_snapshots"
        assert "primary_key" in config
        assert "indexes" in config


class TestPolicyHashComputation:
    """Test deterministic hash computation for policy deduplication."""

    def test_compute_policy_hash_deterministic(self):
        """Identical policies should produce identical hashes."""
        from payment_simulator.persistence.policy_tracking import compute_policy_hash

        policy_json = '{"type": "fifo", "threshold": 1000}'

        hash1 = compute_policy_hash(policy_json)
        hash2 = compute_policy_hash(policy_json)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 produces 64 hex chars

    def test_compute_policy_hash_different_policies(self):
        """Different policies should produce different hashes."""
        from payment_simulator.persistence.policy_tracking import compute_policy_hash

        policy1 = '{"type": "fifo"}'
        policy2 = '{"type": "priority"}'

        hash1 = compute_policy_hash(policy1)
        hash2 = compute_policy_hash(policy2)

        assert hash1 != hash2

    def test_compute_policy_hash_normalized(self):
        """Hash should be insensitive to whitespace differences."""
        from payment_simulator.persistence.policy_tracking import compute_policy_hash

        policy1 = '{"type":"fifo","threshold":1000}'
        policy2 = '{"type": "fifo", "threshold": 1000}'
        policy3 = '{\n  "type": "fifo",\n  "threshold": 1000\n}'

        hash1 = compute_policy_hash(policy1)
        hash2 = compute_policy_hash(policy2)
        hash3 = compute_policy_hash(policy3)

        # All should produce same hash (normalized)
        assert hash1 == hash2 == hash3


class TestPolicyFileManagement:
    """Test policy file storage and versioning."""

    def test_save_policy_file_creates_file(self, tmp_path):
        """Should save policy JSON to versioned file."""
        from payment_simulator.persistence.policy_tracking import save_policy_file

        policy_json = '{"type": "liquidity_aware", "threshold": 5000}'

        file_path = save_policy_file(
            agent_id="BANK_A",
            version="v1",
            policy_json=policy_json,
            base_dir=tmp_path,
        )

        assert file_path.exists()
        assert file_path.name == "BANK_A_policy_v1.json"
        assert file_path.parent == tmp_path

        # Verify content
        saved_content = file_path.read_text()
        assert json.loads(saved_content) == json.loads(policy_json)

    def test_save_policy_file_creates_directory(self, tmp_path):
        """Should create base directory if it doesn't exist."""
        from payment_simulator.persistence.policy_tracking import save_policy_file

        policy_dir = tmp_path / "policies"
        assert not policy_dir.exists()

        policy_json = '{"type": "fifo"}'

        file_path = save_policy_file(
            agent_id="BANK_B",
            version="v1",
            policy_json=policy_json,
            base_dir=policy_dir,
        )

        assert policy_dir.exists()
        assert file_path.exists()

    def test_save_policy_file_with_multiple_versions(self, tmp_path):
        """Should handle multiple versions of same agent's policy."""
        from payment_simulator.persistence.policy_tracking import save_policy_file

        policy_v1 = '{"type": "fifo"}'
        policy_v2 = '{"type": "priority"}'

        file_v1 = save_policy_file("BANK_A", "v1", policy_v1, tmp_path)
        file_v2 = save_policy_file("BANK_A", "v2", policy_v2, tmp_path)

        assert file_v1.exists()
        assert file_v2.exists()
        assert file_v1.name == "BANK_A_policy_v1.json"
        assert file_v2.name == "BANK_A_policy_v2.json"


class TestPolicySnapshotCreation:
    """Test policy snapshot record creation."""

    def test_create_policy_snapshot_with_hash(self, tmp_path):
        """Should create snapshot with computed hash and file path."""
        from payment_simulator.persistence.policy_tracking import create_policy_snapshot

        policy_json = '{"type": "fifo", "threshold": 1000}'

        snapshot = create_policy_snapshot(
            simulation_id="test-sim-001",
            agent_id="BANK_A",
            snapshot_day=0,
            snapshot_tick=0,
            policy_json=policy_json,
            created_by="init",
            policy_dir=tmp_path,
        )

        assert snapshot["simulation_id"] == "test-sim-001"
        assert snapshot["agent_id"] == "BANK_A"
        assert snapshot["snapshot_day"] == 0
        assert snapshot["policy_hash"] is not None
        assert len(snapshot["policy_hash"]) == 64
        assert snapshot["policy_json"] == policy_json
        assert snapshot["created_by"] == "init"

        # Verify file was created
        assert "policy_file_path" in snapshot
        file_path = Path(snapshot["policy_file_path"])
        assert file_path.exists()

    def test_create_policy_snapshot_deduplicates_by_hash(self, tmp_path):
        """Identical policies should reuse existing file."""
        from payment_simulator.persistence.policy_tracking import create_policy_snapshot

        policy_json = '{"type": "fifo"}'

        snapshot1 = create_policy_snapshot(
            simulation_id="sim-001",
            agent_id="BANK_A",
            snapshot_day=0,
            snapshot_tick=0,
            policy_json=policy_json,
            created_by="init",
            policy_dir=tmp_path,
        )

        snapshot2 = create_policy_snapshot(
            simulation_id="sim-001",
            agent_id="BANK_B",
            snapshot_day=0,
            snapshot_tick=0,
            policy_json=policy_json,  # Same policy
            created_by="init",
            policy_dir=tmp_path,
        )

        # Same hash
        assert snapshot1["policy_hash"] == snapshot2["policy_hash"]

        # Different file paths (agent-specific)
        assert snapshot1["policy_file_path"] != snapshot2["policy_file_path"]


class TestPolicySnapshotPersistence:
    """Test policy snapshot persistence to DuckDB."""

    def test_write_policy_snapshots_to_duckdb(self, db_path):
        """Should write policy snapshots to DuckDB."""
        from payment_simulator.persistence.connection import DatabaseManager
        from payment_simulator.persistence.writers import write_policy_snapshots

        # Setup database
        manager = DatabaseManager(db_path)
        manager.setup()

        # Create test snapshots
        snapshots = [
            {
                "simulation_id": "test-sim-001",
                "agent_id": "BANK_A",
                "snapshot_day": 0,
                "snapshot_tick": 0,
                "policy_hash": "a" * 64,
                "policy_file_path": "backend/policies/BANK_A_policy_v1.json",
                "policy_json": '{"type": "fifo"}',
                "created_by": "init",
            },
            {
                "simulation_id": "test-sim-001",
                "agent_id": "BANK_B",
                "snapshot_day": 0,
                "snapshot_tick": 0,
                "policy_hash": "b" * 64,
                "policy_file_path": "backend/policies/BANK_B_policy_v1.json",
                "policy_json": '{"type": "priority"}',
                "created_by": "init",
            },
        ]

        # Write to DuckDB
        write_policy_snapshots(manager.conn, snapshots)

        # Verify
        result = manager.conn.execute(
            "SELECT COUNT(*) as count FROM policy_snapshots"
        ).fetchone()
        assert result[0] == 2

        # Verify content
        df = manager.conn.execute("""
            SELECT simulation_id, agent_id, policy_hash, created_by
            FROM policy_snapshots
            ORDER BY agent_id
        """).pl()

        assert len(df) == 2
        assert df["agent_id"][0] == "BANK_A"
        assert df["policy_hash"][0] == "a" * 64
        assert df["created_by"][0] == "init"

        manager.close()

    def test_query_policy_snapshots_by_simulation(self, db_path):
        """Should query policy snapshots by simulation ID."""
        from payment_simulator.persistence.connection import DatabaseManager
        from payment_simulator.persistence.writers import write_policy_snapshots

        manager = DatabaseManager(db_path)
        manager.setup()

        # Write snapshots for two simulations
        snapshots_sim1 = [
            {
                "simulation_id": "sim-001",
                "agent_id": "BANK_A",
                "snapshot_day": 0,
                "snapshot_tick": 0,
                "policy_hash": "a" * 64,
                "policy_file_path": "backend/policies/BANK_A_policy_v1.json",
                "policy_json": '{"type": "fifo"}',
                "created_by": "init",
            },
        ]

        snapshots_sim2 = [
            {
                "simulation_id": "sim-002",
                "agent_id": "BANK_X",
                "snapshot_day": 0,
                "snapshot_tick": 0,
                "policy_hash": "x" * 64,
                "policy_file_path": "backend/policies/BANK_X_policy_v1.json",
                "policy_json": '{"type": "priority"}',
                "created_by": "init",
            },
        ]

        write_policy_snapshots(manager.conn, snapshots_sim1)
        write_policy_snapshots(manager.conn, snapshots_sim2)

        # Query sim-001 only
        df = manager.conn.execute("""
            SELECT agent_id, policy_hash
            FROM policy_snapshots
            WHERE simulation_id = 'sim-001'
        """).pl()

        assert len(df) == 1
        assert df["agent_id"][0] == "BANK_A"

        manager.close()


class TestPolicySnapshotIntegration:
    """Test policy snapshot integration with simulation lifecycle."""

    def test_capture_initial_policies_at_simulation_start(self, db_path, tmp_path):
        """Should capture all agent policies when simulation starts."""
        from payment_simulator.persistence.policy_tracking import capture_initial_policies

        # Agent configurations
        agent_configs = [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "credit_limit": 500_000,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 2_000_000,
                "credit_limit": 300_000,
                "policy": {"type": "Priority"},
            },
        ]

        # Capture initial policies
        snapshots = capture_initial_policies(
            agent_configs=agent_configs,
            simulation_id="test-sim-001",
            policy_dir=tmp_path,
        )

        assert len(snapshots) == 2
        assert all(s["snapshot_day"] == 0 for s in snapshots)
        assert all(s["snapshot_tick"] == 0 for s in snapshots)
        assert all(s["created_by"] == "init" for s in snapshots)

        # Verify all agents captured
        agent_ids = {s["agent_id"] for s in snapshots}
        assert agent_ids == {"BANK_A", "BANK_B"}

    def test_policy_snapshot_reconstructs_history(self, db_path, tmp_path):
        """Should reconstruct policy history for an agent."""
        from payment_simulator.persistence.connection import DatabaseManager
        from payment_simulator.persistence.writers import write_policy_snapshots

        manager = DatabaseManager(db_path)
        manager.setup()

        # Simulate policy changes over time
        snapshots = [
            {
                "simulation_id": "sim-001",
                "agent_id": "BANK_A",
                "snapshot_day": 0,
                "snapshot_tick": 0,
                "policy_hash": "a" * 64,
                "policy_file_path": "backend/policies/BANK_A_policy_v1.json",
                "policy_json": '{"type": "fifo"}',
                "created_by": "init",
            },
            {
                "simulation_id": "sim-001",
                "agent_id": "BANK_A",
                "snapshot_day": 5,
                "snapshot_tick": 50,
                "policy_hash": "b" * 64,
                "policy_file_path": "backend/policies/BANK_A_policy_v2.json",
                "policy_json": '{"type": "priority"}',
                "created_by": "llm",
            },
            {
                "simulation_id": "sim-001",
                "agent_id": "BANK_A",
                "snapshot_day": 10,
                "snapshot_tick": 100,
                "policy_hash": "c" * 64,
                "policy_file_path": "backend/policies/BANK_A_policy_v3.json",
                "policy_json": '{"type": "liquidity_aware"}',
                "created_by": "manual",
            },
        ]

        write_policy_snapshots(manager.conn, snapshots)

        # Query policy history
        df = manager.conn.execute("""
            SELECT snapshot_day, snapshot_tick, policy_hash, created_by
            FROM policy_snapshots
            WHERE simulation_id = 'sim-001' AND agent_id = 'BANK_A'
            ORDER BY snapshot_day, snapshot_tick
        """).pl()

        assert len(df) == 3
        assert df["snapshot_day"].to_list() == [0, 5, 10]
        assert df["created_by"].to_list() == ["init", "llm", "manual"]

        manager.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
