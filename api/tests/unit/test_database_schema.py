"""Test database schema has all required fields for StateProvider protocol."""
import pytest
from payment_simulator.persistence.models import TickAgentStateRecord, TickQueueSnapshotRecord


class TestTickAgentStateSchema:
    """Test tick_agent_states table has all required columns for StateProvider."""

    def test_model_has_credit_limit_field(self):
        """TickAgentStateRecord must have credit_limit field for StateProvider."""
        # Check if field exists in model
        assert hasattr(TickAgentStateRecord, 'model_fields'), \
            "TickAgentStateRecord should be a Pydantic model"

        fields = TickAgentStateRecord.model_fields
        assert 'credit_limit' in fields, \
            "TickAgentStateRecord missing credit_limit field required for StateProvider.get_agent_credit_limit()"

    def test_model_has_collateral_field(self):
        """TickAgentStateRecord must have collateral field (already exists as posted_collateral)."""
        fields = TickAgentStateRecord.model_fields
        # Either posted_collateral or collateral_posted is fine
        assert 'posted_collateral' in fields or 'collateral_posted' in fields, \
            "TickAgentStateRecord missing collateral field"

    def test_can_create_record_with_credit_limit(self):
        """Should be able to create TickAgentStateRecord with credit_limit."""
        record = TickAgentStateRecord(
            simulation_id="test_sim",
            agent_id="BANK_A",
            tick=0,
            day=0,
            balance=1000000,
            balance_change=0,
            posted_collateral=0,
            credit_limit=500000,  # NEW FIELD
            liquidity_cost=0,
            delay_cost=0,
            collateral_cost=0,
            penalty_cost=0,
            split_friction_cost=0,
            liquidity_cost_delta=0,
            delay_cost_delta=0,
            collateral_cost_delta=0,
            penalty_cost_delta=0,
            split_friction_cost_delta=0,
        )

        assert record.credit_limit == 500000

    def test_credit_limit_field_is_integer(self):
        """credit_limit should be integer type (cents)."""
        fields = TickAgentStateRecord.model_fields
        assert 'credit_limit' in fields

        field_info = fields['credit_limit']
        # Check that it's an int annotation
        assert field_info.annotation == int, \
            f"credit_limit should be int, got {field_info.annotation}"


class TestTickQueueSnapshotSchema:
    """Test tick_queue_snapshots table schema."""

    def test_model_has_queue_type_field(self):
        """TickQueueSnapshotRecord must have queue_type field."""
        fields = TickQueueSnapshotRecord.model_fields
        assert 'queue_type' in fields

    def test_queue_type_supports_rtgs(self):
        """queue_type should support 'rtgs' value."""
        record = TickQueueSnapshotRecord(
            simulation_id="test_sim",
            agent_id="BANK_A",
            tick=0,
            queue_type="rtgs",  # Must support this
            position=0,
            tx_id="tx_001",
        )

        assert record.queue_type == "rtgs"

    def test_queue_type_supports_queue1(self):
        """queue_type should support 'queue1' value."""
        record = TickQueueSnapshotRecord(
            simulation_id="test_sim",
            agent_id="BANK_A",
            tick=0,
            queue_type="queue1",
            position=0,
            tx_id="tx_001",
        )

        assert record.queue_type == "queue1"


class TestSchemaIntegration:
    """Test that schema supports DatabaseStateProvider."""

    def test_agent_state_record_provides_all_stateprovider_data(self):
        """TickAgentStateRecord should have all fields needed by DatabaseStateProvider."""
        required_fields = [
            'balance',
            'credit_limit',
            'posted_collateral',
            'liquidity_cost',
            'delay_cost',
            'collateral_cost',
            'penalty_cost',
            'split_friction_cost',
        ]

        fields = TickAgentStateRecord.model_fields
        for field in required_fields:
            # Handle alternate naming
            if field == 'posted_collateral':
                assert 'posted_collateral' in fields or 'collateral_posted' in fields, \
                    f"Missing collateral field (need posted_collateral or collateral_posted)"
            else:
                assert field in fields, \
                    f"TickAgentStateRecord missing required field: {field}"
