"""
TDD Cycle 1: Pydantic Model Metadata Tests

These tests define the requirements for Pydantic models that will be used
as the source of truth for database schema generation.

Following the RED phase: these tests will fail until we implement the models.
"""

import pytest


class TestTransactionRecordMetadata:
    """Test TransactionRecord model has proper metadata for DDL generation."""

    def test_transaction_record_has_table_metadata(self):
        """Verify Pydantic model includes table configuration."""
        from payment_simulator.persistence.models import TransactionRecord

        # Model should have Config class with table metadata
        assert hasattr(TransactionRecord, "model_config"), \
            "TransactionRecord should have model_config attribute"

        config = TransactionRecord.model_config
        assert "table_name" in config, "Config should specify table_name"
        assert config["table_name"] == "transactions", \
            "Table name should be 'transactions'"

        assert "primary_key" in config, "Config should specify primary_key"
        assert config["primary_key"] == ["simulation_id", "tx_id"], \
            "Primary key should be composite: simulation_id + tx_id"

    def test_transaction_record_has_required_fields(self):
        """Verify TransactionRecord has all required fields from schema."""
        from payment_simulator.persistence.models import TransactionRecord

        # Get field names from model
        fields = TransactionRecord.model_fields

        # Core identification fields
        assert "simulation_id" in fields
        assert "tx_id" in fields
        assert "sender_id" in fields
        assert "receiver_id" in fields

        # Transaction attributes
        assert "amount" in fields
        assert "arrival_tick" in fields
        assert "deadline_tick" in fields
        assert "priority" in fields
        assert "is_divisible" in fields

        # Status tracking
        assert "status" in fields
        assert "settlement_tick" in fields
        assert "amount_settled" in fields

    def test_transaction_record_field_types(self):
        """Verify TransactionRecord fields have correct types."""
        from payment_simulator.persistence.models import (
            TransactionRecord,
            TransactionStatus,
        )
        from enum import Enum

        fields = TransactionRecord.model_fields

        # String fields
        assert fields["simulation_id"].annotation in [str, str | None]
        assert fields["tx_id"].annotation in [str, str | None]
        assert fields["sender_id"].annotation in [str, str | None]
        assert fields["receiver_id"].annotation in [str, str | None]

        # Enum fields
        assert fields["status"].annotation == TransactionStatus
        assert issubclass(TransactionStatus, Enum)

        # Integer fields (money as cents)
        assert fields["amount"].annotation in [int, int | None]
        assert fields["amount_settled"].annotation in [int, int | None]
        assert fields["arrival_tick"].annotation in [int, int | None]
        assert fields["deadline_tick"].annotation in [int, int | None]
        assert fields["priority"].annotation in [int, int | None]

        # Boolean fields
        assert fields["is_divisible"].annotation in [bool, bool | None]


class TestSimulationRunRecordMetadata:
    """Test SimulationRunRecord model has proper metadata."""

    def test_simulation_run_record_has_table_metadata(self):
        """Verify SimulationRunRecord includes table configuration."""
        from payment_simulator.persistence.models import SimulationRunRecord

        config = SimulationRunRecord.model_config
        assert config["table_name"] == "simulation_runs"
        assert config["primary_key"] == ["simulation_id"]

    def test_simulation_run_record_has_required_fields(self):
        """Verify SimulationRunRecord has all required fields."""
        from payment_simulator.persistence.models import SimulationRunRecord

        fields = SimulationRunRecord.model_fields

        # Core identification
        assert "simulation_id" in fields
        assert "config_name" in fields
        assert "description" in fields

        # Timing
        assert "start_time" in fields
        assert "end_time" in fields

        # Configuration
        assert "ticks_per_day" in fields
        assert "num_days" in fields
        assert "rng_seed" in fields

        # Results
        assert "status" in fields
        assert "total_transactions" in fields


class TestDailyAgentMetricsRecordMetadata:
    """Test DailyAgentMetricsRecord model has proper metadata."""

    def test_daily_metrics_record_has_table_metadata(self):
        """Verify DailyAgentMetricsRecord includes table configuration."""
        from payment_simulator.persistence.models import DailyAgentMetricsRecord

        config = DailyAgentMetricsRecord.model_config
        assert config["table_name"] == "daily_agent_metrics"
        assert config["primary_key"] == ["simulation_id", "agent_id", "day"]

    def test_daily_metrics_record_has_collateral_fields(self):
        """Verify DailyAgentMetricsRecord includes Phase 8 collateral fields."""
        from payment_simulator.persistence.models import DailyAgentMetricsRecord

        fields = DailyAgentMetricsRecord.model_fields

        # Phase 8: Collateral management fields
        assert "opening_posted_collateral" in fields
        assert "closing_posted_collateral" in fields
        assert "peak_posted_collateral" in fields
        assert "collateral_capacity" in fields
        assert "num_collateral_posts" in fields
        assert "num_collateral_withdrawals" in fields
        assert "collateral_cost" in fields


class TestCollateralEventRecordMetadata:
    """Test CollateralEventRecord model has proper metadata (Phase 8)."""

    def test_collateral_event_record_has_table_metadata(self):
        """Verify CollateralEventRecord includes table configuration."""
        from payment_simulator.persistence.models import CollateralEventRecord

        config = CollateralEventRecord.model_config
        assert config["table_name"] == "collateral_events"
        assert config["primary_key"] == ["id"]

    def test_collateral_event_record_has_required_fields(self):
        """Verify CollateralEventRecord has all required fields."""
        from payment_simulator.persistence.models import CollateralEventRecord

        fields = CollateralEventRecord.model_fields

        # Identification
        assert "id" in fields
        assert "simulation_id" in fields
        assert "agent_id" in fields
        assert "tick" in fields
        assert "day" in fields

        # Event details
        assert "action" in fields
        assert "amount" in fields
        assert "reason" in fields
        assert "layer" in fields

        # State snapshots
        assert "balance_before" in fields
        assert "posted_collateral_before" in fields
        assert "posted_collateral_after" in fields
        assert "available_capacity_after" in fields
