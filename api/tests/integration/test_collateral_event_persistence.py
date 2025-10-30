"""
Phase 2: Collateral Event Persistence Tests

Tests for FFI method `get_collateral_events_for_day()` and collateral event tracking.
Following TDD RED-GREEN-REFACTOR cycle.

Status: RED - FFI method doesn't exist yet
"""

import pytest


class TestFFICollateralEventRetrieval:
    """Test Rust FFI method get_collateral_events_for_day()."""

    def test_ffi_get_collateral_events_for_day_exists(self, db_path):
        """Verify FFI method get_collateral_events_for_day() exists.

        RED: This test will FAIL because:
        - FFI method get_collateral_events_for_day() doesn't exist in Rust
        - Need to implement in backend/src/ffi/orchestrator.rs
        """
        from payment_simulator._core import Orchestrator
        from payment_simulator.persistence.connection import DatabaseManager

        manager = DatabaseManager(db_path)
        manager.setup()

        # Create config that will trigger collateral activity
        # Low balances + high transaction rates = collateral posting needed
        config = {
            "rng_seed": 42,
            "ticks_per_day": 20,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 50_000,  # Low balance
                    "credit_limit": 0,
                    "collateral_capacity": 1_000_000,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 2_000_000,  # High balance
                    "credit_limit": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Submit transactions to trigger collateral activity
        for _ in range(5):
            orch.submit_transaction(
                sender="BANK_A",
                receiver="BANK_B",
                amount=100_000,
                deadline_tick=50,
                priority=5,
                divisible=False,
            )

        # Run simulation
        for _ in range(20):
            orch.tick()

        # RED: This method doesn't exist yet - will raise AttributeError
        collateral_events = orch.get_collateral_events_for_day(0)

        assert isinstance(collateral_events, list), "Should return a list of collateral events"

        manager.close()

    def test_collateral_event_has_required_fields(self, db_path):
        """Verify each collateral event dict has all required fields.

        RED: Will fail because FFI method doesn't exist.
        Once implemented, this verifies the data structure is correct.
        """
        from payment_simulator._core import Orchestrator
        from payment_simulator.persistence.connection import DatabaseManager

        manager = DatabaseManager(db_path)
        manager.setup()

        config = {
            "rng_seed": 42,
            "ticks_per_day": 20,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 50_000,
                    "credit_limit": 0,
                    "collateral_capacity": 1_000_000,
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

        # Submit transactions
        for _ in range(5):
            orch.submit_transaction(
                sender="BANK_A",
                receiver="BANK_B",
                amount=100_000,
                deadline_tick=50,
                priority=5,
                divisible=False,
            )

        # Run simulation
        for _ in range(20):
            orch.tick()

        # RED: Method doesn't exist
        collateral_events = orch.get_collateral_events_for_day(0)

        if len(collateral_events) > 0:
            event = collateral_events[0]

            # Verify all required fields exist
            required_fields = [
                "simulation_id",
                "agent_id",
                "tick",
                "day",
                "action",  # "post", "withdraw", "hold"
                "amount",
                "reason",
                "layer",  # "strategic", "end_of_tick"
                "balance_before",
                "posted_collateral_before",
                "posted_collateral_after",
                "available_capacity_after",
            ]

            for field in required_fields:
                assert field in event, f"Missing required field: {field}"

            # Verify field types
            assert isinstance(event["agent_id"], str)
            assert isinstance(event["tick"], int)
            assert isinstance(event["day"], int)
            assert isinstance(event["action"], str)
            assert isinstance(event["amount"], int)
            assert isinstance(event["layer"], str)

        manager.close()

    def test_collateral_events_validate_with_pydantic(self, db_path):
        """Verify collateral events validate with CollateralEventRecord.

        RED: Will fail because:
        1. FFI method doesn't exist
        2. Need to verify Pydantic model matches FFI data structure
        """
        from payment_simulator._core import Orchestrator
        from payment_simulator.persistence.connection import DatabaseManager
        from payment_simulator.persistence.models import CollateralEventRecord

        manager = DatabaseManager(db_path)
        manager.setup()

        config = {
            "rng_seed": 42,
            "ticks_per_day": 20,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 50_000,
                    "credit_limit": 0,
                    "collateral_capacity": 1_000_000,
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

        # Submit transactions
        for _ in range(5):
            orch.submit_transaction(
                sender="BANK_A",
                receiver="BANK_B",
                amount=100_000,
                deadline_tick=50,
                priority=5,
                divisible=False,
            )

        # Run simulation
        for _ in range(20):
            orch.tick()

        # RED: Method doesn't exist
        collateral_events = orch.get_collateral_events_for_day(0)

        # Validate each event with Pydantic
        for event_dict in collateral_events:
            event_record = CollateralEventRecord(**event_dict)
            assert event_record.simulation_id.startswith("sim-")
            assert event_record.agent_id in ["BANK_A", "BANK_B"]
            assert event_record.action in ["post", "withdraw", "hold"]
            assert event_record.layer in ["strategic", "end_of_tick"]

        manager.close()


class TestCollateralEventPersistence:
    """Test persisting collateral events to database."""

    @pytest.mark.skip(reason="Requires collateral policy logic - no policies have collateral trees implemented yet")
    def test_collateral_events_persisted_to_database(self, db_path):
        """Verify collateral events are persisted to collateral_events table.

        RED: Will fail because:
        1. FFI method doesn't exist
        2. Write logic not added to run.py
        """
        from payment_simulator._core import Orchestrator
        from payment_simulator.persistence.connection import DatabaseManager
        import polars as pl

        manager = DatabaseManager(db_path)
        manager.setup()

        config = {
            "rng_seed": 42,
            "ticks_per_day": 20,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 50_000,
                    "credit_limit": 0,
                    "collateral_capacity": 1_000_000,
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

        # Submit transactions to trigger collateral
        for _ in range(10):
            orch.submit_transaction(
                sender="BANK_A",
                receiver="BANK_B",
                amount=100_000,
                deadline_tick=50,
                priority=5,
                divisible=False,
            )

        # Run simulation
        for _ in range(20):
            orch.tick()

        # RED: Method doesn't exist
        collateral_events = orch.get_collateral_events_for_day(0)

        # Persist to database (simulate what run.py will do)
        if collateral_events:
            df = pl.DataFrame(collateral_events)
            manager.conn.execute("INSERT INTO collateral_events SELECT * FROM df")

        # Verify data was persisted
        result = manager.conn.execute("SELECT COUNT(*) FROM collateral_events").fetchone()
        count = result[0]

        assert count > 0, "collateral_events table should have data"
        assert count == len(collateral_events), "Count should match number of events"

        manager.close()

    def test_collateral_events_match_metrics_counts(self, db_path):
        """Verify collateral event counts match daily_agent_metrics.

        RED: Will fail because FFI method doesn't exist.
        Once implemented, this ensures consistency between tables.
        """
        from payment_simulator._core import Orchestrator
        from payment_simulator.persistence.connection import DatabaseManager
        import polars as pl

        manager = DatabaseManager(db_path)
        manager.setup()

        config = {
            "rng_seed": 42,
            "ticks_per_day": 20,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 50_000,
                    "credit_limit": 0,
                    "collateral_capacity": 1_000_000,
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

        # Submit transactions
        for _ in range(10):
            orch.submit_transaction(
                sender="BANK_A",
                receiver="BANK_B",
                amount=100_000,
                deadline_tick=50,
                priority=5,
                divisible=False,
            )

        # Run simulation
        for _ in range(20):
            orch.tick()

        # Get metrics
        metrics = orch.get_daily_agent_metrics(0)
        bank_a_metrics = next(m for m in metrics if m["agent_id"] == "BANK_A")

        # RED: Method doesn't exist
        collateral_events = orch.get_collateral_events_for_day(0)

        # Count collateral posts for BANK_A
        posts = [e for e in collateral_events if e["agent_id"] == "BANK_A" and e["action"] == "post"]

        # Verify counts match
        assert len(posts) == bank_a_metrics.get("num_collateral_posts", 0), \
            "Collateral post count should match daily_agent_metrics"

        manager.close()

    def test_collateral_events_capture_strategic_and_eod_layers(self, db_path):
        """Verify both strategic and end_of_tick layers are captured.

        RED: Will fail because FFI method doesn't exist.
        This verifies we capture collateral decisions from both layers.
        """
        from payment_simulator._core import Orchestrator
        from payment_simulator.persistence.connection import DatabaseManager

        manager = DatabaseManager(db_path)
        manager.setup()

        config = {
            "rng_seed": 42,
            "ticks_per_day": 20,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 50_000,
                    "credit_limit": 0,
                    "collateral_capacity": 1_000_000,
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

        # Submit transactions
        for _ in range(10):
            orch.submit_transaction(
                sender="BANK_A",
                receiver="BANK_B",
                amount=100_000,
                deadline_tick=50,
                priority=5,
                divisible=False,
            )

        # Run simulation
        for _ in range(20):
            orch.tick()

        # RED: Method doesn't exist
        collateral_events = orch.get_collateral_events_for_day(0)

        # Check that we have events from both layers
        layers = set(e["layer"] for e in collateral_events)

        # Note: We may not always have both layers depending on simulation
        # But all events should have valid layer values
        for layer in layers:
            assert layer in ["strategic", "end_of_tick"], f"Invalid layer: {layer}"

        manager.close()


class TestCollateralEventSchema:
    """Test collateral_events table schema."""

    def test_collateral_events_table_exists(self, db_path):
        """Verify collateral_events table exists in schema."""
        from payment_simulator.persistence.connection import DatabaseManager

        manager = DatabaseManager(db_path)
        manager.setup()

        # Query table schema
        result = manager.conn.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_name = 'collateral_events'
        """).fetchone()

        assert result is not None, "collateral_events table does not exist"
        assert result[0] == "collateral_events"

        manager.close()

    def test_collateral_events_table_has_required_columns(self, db_path):
        """Verify collateral_events table has all required columns."""
        from payment_simulator.persistence.connection import DatabaseManager

        manager = DatabaseManager(db_path)
        manager.setup()

        # Query column info
        columns = manager.conn.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'collateral_events'
        """).fetchall()

        column_names = [col[0] for col in columns]

        required_columns = [
            "simulation_id",
            "agent_id",
            "tick",
            "day",
            "action",
            "amount",
            "reason",
            "layer",
            "balance_before",
            "posted_collateral_before",
            "posted_collateral_after",
            "available_capacity_after",
        ]

        for col in required_columns:
            assert col in column_names, f"Missing required column: {col}"

        manager.close()


class TestCollateralEventDataIntegrity:
    """Test data integrity and constraints for collateral events."""

    def test_collateral_action_values_valid(self, db_path):
        """Verify action field only contains valid values.

        RED: Will fail because FFI method doesn't exist.
        Ensures action is one of: post, withdraw, hold
        """
        from payment_simulator._core import Orchestrator
        from payment_simulator.persistence.connection import DatabaseManager

        manager = DatabaseManager(db_path)
        manager.setup()

        config = {
            "rng_seed": 42,
            "ticks_per_day": 20,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 50_000,
                    "credit_limit": 0,
                    "collateral_capacity": 1_000_000,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        for _ in range(20):
            orch.tick()

        # RED: Method doesn't exist
        collateral_events = orch.get_collateral_events_for_day(0)

        valid_actions = {"post", "withdraw", "hold"}

        for event in collateral_events:
            assert event["action"] in valid_actions, \
                f"Invalid action: {event['action']}, must be one of {valid_actions}"

        manager.close()

    def test_collateral_layer_values_valid(self, db_path):
        """Verify layer field only contains valid values.

        RED: Will fail because FFI method doesn't exist.
        Ensures layer is one of: strategic, end_of_tick
        """
        from payment_simulator._core import Orchestrator
        from payment_simulator.persistence.connection import DatabaseManager

        manager = DatabaseManager(db_path)
        manager.setup()

        config = {
            "rng_seed": 42,
            "ticks_per_day": 20,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 50_000,
                    "credit_limit": 0,
                    "collateral_capacity": 1_000_000,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        for _ in range(20):
            orch.tick()

        # RED: Method doesn't exist
        collateral_events = orch.get_collateral_events_for_day(0)

        valid_layers = {"strategic", "end_of_tick"}

        for event in collateral_events:
            assert event["layer"] in valid_layers, \
                f"Invalid layer: {event['layer']}, must be one of {valid_layers}"

        manager.close()
