"""
Phase 4: Policy Snapshot Tracking Tests

Tests for policy snapshot capture and persistence.
Following TDD RED-GREEN-REFACTOR cycle.

Key Requirements:
- Capture initial policies at simulation start
- Track policy changes mid-simulation
- SHA256 hashing for deduplication
- Integration with Phase 9 DSL (three-tree structure)
"""

import pytest
import hashlib
import json
from pathlib import Path


class TestFFIPolicyRetrieval:
    """Test Rust FFI method get_agent_policies()."""

    def test_get_agent_policies_returns_list(self):
        """Verify get_agent_policies returns list of policy configs."""
        from payment_simulator._core import Orchestrator

        config = {
            "rng_seed": 12345,
            "ticks_per_day": 10,
            "num_days": 1,
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
                    "credit_limit": 300_000,
                    "policy": {"type": "LiquidityAware", "target_buffer": 500_000, "urgency_threshold": 5},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # RED: Method doesn't exist yet
        policies = orch.get_agent_policies()

        assert isinstance(policies, list)
        assert len(policies) == 2  # Two agents

    def test_get_agent_policies_returns_dicts_with_required_fields(self):
        """Verify each policy dict has required fields."""
        from payment_simulator._core import Orchestrator

        config = {
            "rng_seed": 12345,
            "ticks_per_day": 10,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_500_000,
                    "credit_limit": 400_000,
                    "policy": {"type": "Deadline", "urgency_threshold": 10},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Get policies
        policies = orch.get_agent_policies()

        assert len(policies) == 1
        policy = policies[0]

        # Required fields
        required_fields = [
            "agent_id",
            "policy_config",  # The policy dict itself
        ]

        for field in required_fields:
            assert field in policy, f"Missing field: {field}"

        # Verify policy_config is a dict
        assert isinstance(policy["policy_config"], dict)
        assert "type" in policy["policy_config"]

    def test_policy_config_matches_input(self):
        """Verify returned policy config matches input config."""
        from payment_simulator._core import Orchestrator

        config = {
            "rng_seed": 99999,
            "ticks_per_day": 10,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "TEST_BANK",
                    "opening_balance": 2_000_000,
                    "credit_limit": 600_000,
                    "policy": {"type": "LiquidityAware", "target_buffer": 300_000, "urgency_threshold": 7},
                },
            ],
        }

        orch = Orchestrator.new(config)
        policies = orch.get_agent_policies()

        assert len(policies) == 1
        policy = policies[0]

        assert policy["agent_id"] == "TEST_BANK"
        assert policy["policy_config"]["type"] == "LiquidityAware"
        assert policy["policy_config"]["target_buffer"] == 300_000
        assert policy["policy_config"]["urgency_threshold"] == 7


class TestPolicySnapshotHashCreation:
    """Test SHA256 hash generation for policy snapshots."""

    def test_create_policy_hash_from_json(self):
        """Verify SHA256 hash creation from policy JSON."""
        policy_config = {"type": "Fifo"}
        policy_json = json.dumps(policy_config, sort_keys=True)

        # Create SHA256 hash
        policy_hash = hashlib.sha256(policy_json.encode()).hexdigest()

        assert len(policy_hash) == 64  # SHA256 produces 64-char hex string
        assert all(c in "0123456789abcdef" for c in policy_hash)

    def test_same_policy_produces_same_hash(self):
        """Verify hash deduplication: same policy = same hash."""
        policy1 = {"type": "Fifo"}
        policy2 = {"type": "Fifo"}

        hash1 = hashlib.sha256(json.dumps(policy1, sort_keys=True).encode()).hexdigest()
        hash2 = hashlib.sha256(json.dumps(policy2, sort_keys=True).encode()).hexdigest()

        assert hash1 == hash2

    def test_different_policies_produce_different_hashes(self):
        """Verify different policies have different hashes."""
        policy1 = {"type": "Fifo"}
        policy2 = {"type": "Deadline", "urgency_threshold": 10}

        hash1 = hashlib.sha256(json.dumps(policy1, sort_keys=True).encode()).hexdigest()
        hash2 = hashlib.sha256(json.dumps(policy2, sort_keys=True).encode()).hexdigest()

        assert hash1 != hash2

    def test_policy_field_order_does_not_affect_hash(self):
        """Verify sort_keys ensures consistent hashing."""
        policy1 = {"urgency_threshold": 10, "type": "Deadline"}
        policy2 = {"type": "Deadline", "urgency_threshold": 10}

        hash1 = hashlib.sha256(json.dumps(policy1, sort_keys=True).encode()).hexdigest()
        hash2 = hashlib.sha256(json.dumps(policy2, sort_keys=True).encode()).hexdigest()

        assert hash1 == hash2  # Order shouldn't matter


class TestPolarsPolicySnapshotConversion:
    """Test Polars DataFrame creation from policy snapshots."""

    def test_create_polars_dataframe_from_policy_snapshots(self):
        """Verify we can create Polars DataFrame from policy data."""
        from payment_simulator._core import Orchestrator
        import polars as pl
        import hashlib
        import json

        config = {
            "rng_seed": 12345,
            "ticks_per_day": 10,
            "num_days": 1,
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
        policies = orch.get_agent_policies()

        # Convert to snapshot format
        snapshots = []
        for policy in policies:
            policy_json = json.dumps(policy["policy_config"], sort_keys=True)
            policy_hash = hashlib.sha256(policy_json.encode()).hexdigest()

            snapshots.append({
                "agent_id": policy["agent_id"],
                "snapshot_day": 0,
                "snapshot_tick": 0,
                "policy_hash": policy_hash,
                "policy_json": policy_json,
                "created_by": "init",
            })

        # Create DataFrame
        df = pl.DataFrame(snapshots)

        assert len(df) == 1
        assert "agent_id" in df.columns
        assert "policy_hash" in df.columns
        assert "policy_json" in df.columns
        assert "created_by" in df.columns

    def test_dataframe_matches_pydantic_model(self):
        """Verify DataFrame data validates with Pydantic model."""
        from payment_simulator._core import Orchestrator
        from payment_simulator.persistence.models import PolicySnapshotRecord
        import polars as pl
        import hashlib
        import json

        config = {
            "rng_seed": 99999,
            "ticks_per_day": 10,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "TEST_BANK",
                    "opening_balance": 2_000_000,
                    "credit_limit": 600_000,
                    "policy": {"type": "LiquidityAware", "target_buffer": 400_000, "urgency_threshold": 5},
                },
            ],
        }

        orch = Orchestrator.new(config)
        policies = orch.get_agent_policies()

        # Convert to snapshots
        snapshots = []
        for policy in policies:
            policy_json = json.dumps(policy["policy_config"], sort_keys=True)
            policy_hash = hashlib.sha256(policy_json.encode()).hexdigest()

            snapshots.append({
                "simulation_id": "test-sim-001",
                "agent_id": policy["agent_id"],
                "snapshot_day": 0,
                "snapshot_tick": 0,
                "policy_hash": policy_hash,
                "policy_json": policy_json,
                "created_by": "init",
            })

        df = pl.DataFrame(snapshots)

        # Validate each row with Pydantic
        for row in df.iter_rows(named=True):
            snapshot_record = PolicySnapshotRecord(**row)
            assert snapshot_record.agent_id == "TEST_BANK"
            assert snapshot_record.snapshot_day == 0
            assert snapshot_record.created_by == "init"
            assert len(snapshot_record.policy_hash) == 64


class TestDuckDBPolicySnapshotBatchWrite:
    """Test batch writing policy snapshots to DuckDB."""

    def test_insert_policy_snapshots_to_duckdb(self, tmp_path):
        """Verify we can batch insert policy snapshots to DuckDB."""
        from payment_simulator._core import Orchestrator
        from payment_simulator.persistence.connection import DatabaseManager
        from payment_simulator.persistence.writers import write_policy_snapshots
        import polars as pl
        import hashlib
        import json

        # Setup database
        db_path = tmp_path / "test_policy_snapshots.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        # Run simulation
        config = {
            "rng_seed": 12345,
            "ticks_per_day": 10,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "credit_limit": 500_000,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1_500_000,
                    "credit_limit": 400_000,
                    "policy": {"type": "Deadline", "urgency_threshold": 5},
                },
            ],
        }

        orch = Orchestrator.new(config)
        simulation_id = "sim-policy-001"

        # Get policies and create snapshots
        policies = orch.get_agent_policies()
        snapshots = []
        for policy in policies:
            policy_json = json.dumps(policy["policy_config"], sort_keys=True)
            policy_hash = hashlib.sha256(policy_json.encode()).hexdigest()

            snapshots.append({
                "simulation_id": simulation_id,
                "agent_id": policy["agent_id"],
                "snapshot_day": 0,
                "snapshot_tick": 0,
                "policy_hash": policy_hash,
                "policy_json": policy_json,
                "created_by": "init",
            })

        # Write to database
        count = write_policy_snapshots(db_manager.conn, snapshots)

        assert count == 2  # Two agents

        # Verify data was inserted
        result = db_manager.conn.execute(
            "SELECT COUNT(*) FROM policy_snapshots"
        ).fetchone()

        assert result[0] == 2

        # Verify we can query it
        query_result = db_manager.conn.execute("""
            SELECT agent_id, created_by, policy_hash
            FROM policy_snapshots
            WHERE simulation_id = 'sim-policy-001'
            ORDER BY agent_id
        """).fetchall()

        assert len(query_result) == 2
        assert query_result[0][0] == "BANK_A"
        assert query_result[0][1] == "init"  # created_by
        assert len(query_result[0][2]) == 64  # policy_hash length
        assert query_result[1][0] == "BANK_B"

    def test_batch_write_policy_hash_deduplication(self, tmp_path):
        """Verify same policy hash can be inserted multiple times (different agents/times)."""
        from payment_simulator.persistence.connection import DatabaseManager
        from payment_simulator.persistence.writers import write_policy_snapshots
        import hashlib
        import json

        # Setup database
        db_path = tmp_path / "test_dedup.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        # Create snapshots with same policy (different agents)
        policy_config = {"type": "Fifo"}
        policy_json = json.dumps(policy_config, sort_keys=True)
        policy_hash = hashlib.sha256(policy_json.encode()).hexdigest()

        snapshots = [
            {
                "simulation_id": "sim-001",
                "agent_id": "BANK_A",
                "snapshot_day": 0,
                "snapshot_tick": 0,
                "policy_hash": policy_hash,
                "policy_json": policy_json,
                "created_by": "init",
            },
            {
                "simulation_id": "sim-001",
                "agent_id": "BANK_B",
                "snapshot_day": 0,
                "snapshot_tick": 0,
                "policy_hash": policy_hash,  # Same hash
                "policy_json": policy_json,  # Same policy
                "created_by": "init",
            },
        ]

        write_policy_snapshots(db_manager.conn, snapshots)

        # Verify both inserted (same hash is allowed for different agents)
        count = db_manager.conn.execute(
            "SELECT COUNT(*) FROM policy_snapshots"
        ).fetchone()[0]

        assert count == 2

        # Verify we can query by hash
        hash_query = db_manager.conn.execute(
            f"SELECT agent_id FROM policy_snapshots WHERE policy_hash = '{policy_hash}' ORDER BY agent_id"
        ).fetchall()

        assert len(hash_query) == 2
        assert hash_query[0][0] == "BANK_A"
        assert hash_query[1][0] == "BANK_B"


class TestEndToEndPolicySnapshotPersistence:
    """Test complete end-to-end policy snapshot persistence workflow."""

    def test_initial_policy_capture_at_simulation_start(self, tmp_path):
        """Test capturing initial policies when simulation starts."""
        from payment_simulator._core import Orchestrator
        from payment_simulator.persistence.connection import DatabaseManager
        from payment_simulator.persistence.writers import write_policy_snapshots
        import hashlib
        import json

        # Initialize database
        db_path = tmp_path / "initial_policies.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        # Create simulation
        config = {
            "rng_seed": 99999,
            "ticks_per_day": 50,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 2_000_000,
                    "credit_limit": 800_000,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1_500_000,
                    "credit_limit": 600_000,
                    "policy": {"type": "LiquidityAware", "target_buffer": 500_000, "urgency_threshold": 5},
                },
            ],
        }

        orch = Orchestrator.new(config)
        simulation_id = "e2e-policy-001"

        # Capture initial policies (day 0, tick 0)
        policies = orch.get_agent_policies()
        snapshots = []
        for policy in policies:
            policy_json = json.dumps(policy["policy_config"], sort_keys=True)
            policy_hash = hashlib.sha256(policy_json.encode()).hexdigest()

            snapshots.append({
                "simulation_id": simulation_id,
                "agent_id": policy["agent_id"],
                "snapshot_day": 0,
                "snapshot_tick": 0,
                "policy_hash": policy_hash,
                "policy_json": policy_json,
                "created_by": "init",
            })

        # Persist initial policies
        write_policy_snapshots(db_manager.conn, snapshots)

        # Verify all policies persisted
        total_count = db_manager.conn.execute(
            f"SELECT COUNT(*) FROM policy_snapshots WHERE simulation_id = '{simulation_id}'"
        ).fetchone()[0]

        assert total_count == 2  # 2 agents

        # Verify we can query initial policies
        initial_policies = db_manager.conn.execute(f"""
            SELECT agent_id, policy_json, created_by
            FROM policy_snapshots
            WHERE simulation_id = '{simulation_id}' AND snapshot_day = 0 AND snapshot_tick = 0
            ORDER BY agent_id
        """).fetchall()

        assert len(initial_policies) == 2

        # Verify BANK_A has Fifo policy
        bank_a_policy_json = json.loads(initial_policies[0][1])
        assert bank_a_policy_json["type"] == "Fifo"
        assert initial_policies[0][2] == "init"

        # Verify BANK_B has LiquidityAware policy
        bank_b_policy_json = json.loads(initial_policies[1][1])
        assert bank_b_policy_json["type"] == "LiquidityAware"
        assert bank_b_policy_json["target_buffer"] == 500_000

    def test_policy_provenance_query(self, tmp_path):
        """Test answering: 'What policy was BANK_A using at day 3?'"""
        from payment_simulator.persistence.connection import DatabaseManager
        from payment_simulator.persistence.writers import write_policy_snapshots
        import hashlib
        import json

        # Initialize database
        db_path = tmp_path / "provenance.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        # Simulate policy evolution: BANK_A changes policy twice
        simulation_id = "provenance-test"

        # Day 0: Initial policy
        policy_v1 = {"type": "Fifo"}
        policy_v1_json = json.dumps(policy_v1, sort_keys=True)
        policy_v1_hash = hashlib.sha256(policy_v1_json.encode()).hexdigest()

        snapshots_day0 = [{
            "simulation_id": simulation_id,
            "agent_id": "BANK_A",
            "snapshot_day": 0,
            "snapshot_tick": 0,
            "policy_hash": policy_v1_hash,
            "policy_json": policy_v1_json,
            "created_by": "init",
        }]

        write_policy_snapshots(db_manager.conn, snapshots_day0)

        # Day 2: Manual policy change
        policy_v2 = {"type": "Deadline", "urgency_threshold": 10}
        policy_v2_json = json.dumps(policy_v2, sort_keys=True)
        policy_v2_hash = hashlib.sha256(policy_v2_json.encode()).hexdigest()

        snapshots_day2 = [{
            "simulation_id": simulation_id,
            "agent_id": "BANK_A",
            "snapshot_day": 2,
            "snapshot_tick": 0,
            "policy_hash": policy_v2_hash,
            "policy_json": policy_v2_json,
            "created_by": "manual",
        }]

        write_policy_snapshots(db_manager.conn, snapshots_day2)

        # Day 5: LLM-managed policy change
        policy_v3 = {"type": "LiquidityAware", "target_buffer": 300_000, "urgency_threshold": 7}
        policy_v3_json = json.dumps(policy_v3, sort_keys=True)
        policy_v3_hash = hashlib.sha256(policy_v3_json.encode()).hexdigest()

        snapshots_day5 = [{
            "simulation_id": simulation_id,
            "agent_id": "BANK_A",
            "snapshot_day": 5,
            "snapshot_tick": 0,
            "policy_hash": policy_v3_hash,
            "policy_json": policy_v3_json,
            "created_by": "llm",
        }]

        write_policy_snapshots(db_manager.conn, snapshots_day5)

        # Query: What policy was BANK_A using on day 3?
        # Answer: The most recent policy snapshot on or before day 3
        result = db_manager.conn.execute(f"""
            SELECT policy_json, created_by, snapshot_day
            FROM policy_snapshots
            WHERE simulation_id = '{simulation_id}'
              AND agent_id = 'BANK_A'
              AND snapshot_day <= 3
            ORDER BY snapshot_day DESC
            LIMIT 1
        """).fetchone()

        assert result is not None
        policy_at_day3 = json.loads(result[0])
        assert policy_at_day3["type"] == "Deadline"  # Changed on day 2
        assert result[1] == "manual"  # Created by manual change
        assert result[2] == 2  # Snapshot was on day 2

        # Query: What policy was BANK_A using on day 7?
        result_day7 = db_manager.conn.execute(f"""
            SELECT policy_json, created_by, snapshot_day
            FROM policy_snapshots
            WHERE simulation_id = '{simulation_id}'
              AND agent_id = 'BANK_A'
              AND snapshot_day <= 7
            ORDER BY snapshot_day DESC
            LIMIT 1
        """).fetchone()

        policy_at_day7 = json.loads(result_day7[0])
        assert policy_at_day7["type"] == "LiquidityAware"  # Changed on day 5
        assert result_day7[1] == "llm"  # Created by LLM
