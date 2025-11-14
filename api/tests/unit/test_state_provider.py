"""Test StateProvider protocol and implementations."""
import pytest
from payment_simulator.cli.execution.state_provider import (
    StateProvider,
    OrchestratorStateProvider,
    DatabaseStateProvider,
)
from payment_simulator._core import Orchestrator


class TestStateProviderProtocol:
    """Test that StateProvider protocol is properly defined."""

    def test_protocol_has_all_required_methods(self):
        """StateProvider protocol must define all required methods."""
        required_methods = [
            "get_transaction_details",
            "get_agent_balance",
            "get_agent_credit_limit",
            "get_agent_queue1_contents",
            "get_rtgs_queue_contents",
            "get_agent_collateral_posted",
            "get_agent_accumulated_costs",
            "get_queue1_size",
        ]

        for method_name in required_methods:
            assert hasattr(StateProvider, method_name), \
                f"StateProvider protocol missing method: {method_name}"


class TestOrchestratorStateProvider:
    """Test OrchestratorStateProvider wrapper."""

    @pytest.fixture
    def orchestrator(self):
        """Create test orchestrator."""
        config = {
            "rng_seed": 12345,
            "ticks_per_day": 100,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1000000,
                    "credit_limit": 500000,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 2000000,
                    "credit_limit": 1000000,
                    "policy": {"type": "Fifo"},
                },
            ],
        }
        return Orchestrator.new(config)

    @pytest.fixture
    def provider(self, orchestrator):
        """Create OrchestratorStateProvider."""
        return OrchestratorStateProvider(orchestrator)

    def test_get_transaction_details(self, provider, orchestrator):
        """Should delegate to orchestrator.get_transaction_details()."""
        # This will fail until we add a transaction
        result = provider.get_transaction_details("nonexistent")
        assert result is None

    def test_get_agent_balance(self, provider):
        """Should return agent balance from orchestrator."""
        balance = provider.get_agent_balance("BANK_A")
        assert balance == 1000000

    def test_get_agent_credit_limit(self, provider):
        """Should return agent credit limit from orchestrator."""
        limit = provider.get_agent_credit_limit("BANK_A")
        assert limit == 500000

    def test_get_agent_queue1_contents(self, provider):
        """Should return queue1 contents from orchestrator."""
        contents = provider.get_agent_queue1_contents("BANK_A")
        assert isinstance(contents, list)
        assert len(contents) == 0  # Empty initially

    def test_get_rtgs_queue_contents(self, provider):
        """Should return RTGS queue contents from orchestrator."""
        contents = provider.get_rtgs_queue_contents()
        assert isinstance(contents, list)
        assert len(contents) == 0  # Empty initially

    def test_get_agent_collateral_posted(self, provider):
        """Should return collateral posted from orchestrator."""
        collateral = provider.get_agent_collateral_posted("BANK_A")
        assert collateral == 0  # None posted initially

    def test_get_agent_accumulated_costs(self, provider):
        """Should return accumulated costs from orchestrator."""
        costs = provider.get_agent_accumulated_costs("BANK_A")
        assert isinstance(costs, dict)
        assert "liquidity_cost" in costs
        assert "delay_cost" in costs
        assert costs["liquidity_cost"] == 0  # No costs initially

    def test_get_queue1_size(self, provider):
        """Should return queue1 size from orchestrator."""
        size = provider.get_queue1_size("BANK_A")
        assert size == 0  # Empty initially


class TestDatabaseStateProvider:
    """Test DatabaseStateProvider for replay."""

    @pytest.fixture
    def mock_db_data(self):
        """Create mock database data for testing."""
        return {
            "tx_cache": {
                "tx_001": {
                    "tx_id": "tx_001",
                    "sender_id": "BANK_A",
                    "receiver_id": "BANK_B",
                    "amount": 100000,
                    "amount_settled": 0,
                    "priority": 5,
                    "deadline_tick": 50,
                    "status": "pending",
                    "is_divisible": False,
                }
            },
            "agent_states": {
                "BANK_A": {
                    "agent_id": "BANK_A",
                    "balance": 900000,  # After sending tx_001
                    "credit_limit": 500000,
                    "posted_collateral": 100000,
                    "liquidity_cost": 1000,
                    "delay_cost": 500,
                    "collateral_cost": 200,
                    "penalty_cost": 0,
                    "split_friction_cost": 0,
                },
                "BANK_B": {
                    "agent_id": "BANK_B",
                    "balance": 2000000,
                    "credit_limit": 1000000,
                    "posted_collateral": 0,
                    "liquidity_cost": 0,
                    "delay_cost": 0,
                    "collateral_cost": 0,
                    "penalty_cost": 0,
                    "split_friction_cost": 0,
                },
            },
            "queue_snapshots": {
                "BANK_A": {
                    "queue1": ["tx_001"],
                    "rtgs": [],
                },
                "BANK_B": {
                    "queue1": [],
                    "rtgs": [],
                },
            },
        }

    @pytest.fixture
    def provider(self, mock_db_data):
        """Create DatabaseStateProvider with mock data."""
        return DatabaseStateProvider(
            conn=None,  # Not needed for these tests
            simulation_id="sim_test",
            tick=42,
            tx_cache=mock_db_data["tx_cache"],
            agent_states=mock_db_data["agent_states"],
            queue_snapshots=mock_db_data["queue_snapshots"],
        )

    def test_get_transaction_details(self, provider):
        """Should return transaction from cache."""
        tx = provider.get_transaction_details("tx_001")
        assert tx is not None
        assert tx["tx_id"] == "tx_001"
        assert tx["sender_id"] == "BANK_A"
        assert tx["amount"] == 100000

    def test_get_transaction_details_nonexistent(self, provider):
        """Should return None for nonexistent transaction."""
        tx = provider.get_transaction_details("nonexistent")
        assert tx is None

    def test_get_agent_balance(self, provider):
        """Should return balance from agent_states."""
        balance = provider.get_agent_balance("BANK_A")
        assert balance == 900000

    def test_get_agent_credit_limit(self, provider):
        """Should return credit limit from agent_states."""
        limit = provider.get_agent_credit_limit("BANK_A")
        assert limit == 500000

    def test_get_agent_queue1_contents(self, provider):
        """Should return queue1 from queue_snapshots."""
        contents = provider.get_agent_queue1_contents("BANK_A")
        assert contents == ["tx_001"]

    def test_get_rtgs_queue_contents(self, provider):
        """Should aggregate RTGS queue from all agents."""
        contents = provider.get_rtgs_queue_contents()
        assert isinstance(contents, list)
        # In this test data, no transactions in RTGS
        assert len(contents) == 0

    def test_get_agent_collateral_posted(self, provider):
        """Should return collateral from agent_states."""
        collateral = provider.get_agent_collateral_posted("BANK_A")
        assert collateral == 100000

    def test_get_agent_accumulated_costs(self, provider):
        """Should return costs dict from agent_states."""
        costs = provider.get_agent_accumulated_costs("BANK_A")
        assert costs["liquidity_cost"] == 1000
        assert costs["delay_cost"] == 500
        assert costs["collateral_cost"] == 200
        assert costs["penalty_cost"] == 0

    def test_get_queue1_size(self, provider):
        """Should return queue1 size."""
        size = provider.get_queue1_size("BANK_A")
        assert size == 1


class TestStateProviderEquivalence:
    """Test that both providers return equivalent data for same state."""

    def test_orchestrator_and_database_providers_match(self):
        """Both providers should return same data for equivalent states."""
        # This is an integration test we'll implement after both providers work
        # For now, just a placeholder
        pass
