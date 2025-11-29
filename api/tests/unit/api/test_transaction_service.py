"""Tests for TransactionService (TDD - tests written first).

Following TDD principles, these tests define the expected behavior
of the TransactionService before implementation.
"""

import pytest

from payment_simulator.api.services.simulation_service import (
    SimulationNotFoundError,
    SimulationService,
)
from payment_simulator.api.services.transaction_service import (
    TransactionNotFoundError,
    TransactionService,
)


@pytest.fixture
def simple_config() -> dict:
    """Simple valid simulation configuration."""
    return {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 12345,
        },
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "unsecured_cap": 500_000,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 2_000_000,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
        ],
    }


@pytest.fixture
def simulation_service() -> SimulationService:
    """Create a fresh SimulationService instance."""
    return SimulationService()


@pytest.fixture
def transaction_service(simulation_service: SimulationService) -> TransactionService:
    """Create a TransactionService linked to simulation service."""
    return TransactionService(simulation_service)


@pytest.fixture
def sim_with_agents(
    simulation_service: SimulationService, simple_config: dict
) -> str:
    """Create a simulation with agents and return its ID."""
    sim_id, _ = simulation_service.create_simulation(simple_config)
    return sim_id


class TestTransactionSubmission:
    """Tests for transaction submission."""

    def test_submit_transaction_returns_id(
        self,
        transaction_service: TransactionService,
        sim_with_agents: str,
    ) -> None:
        """Submitting a transaction returns a transaction ID."""
        tx_id = transaction_service.submit_transaction(
            sim_id=sim_with_agents,
            sender="BANK_A",
            receiver="BANK_B",
            amount=100_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

        assert isinstance(tx_id, str)
        assert len(tx_id) > 0

    def test_submit_transaction_tracks_metadata(
        self,
        transaction_service: TransactionService,
        sim_with_agents: str,
    ) -> None:
        """Submitted transactions are tracked with metadata."""
        tx_id = transaction_service.submit_transaction(
            sim_id=sim_with_agents,
            sender="BANK_A",
            receiver="BANK_B",
            amount=100_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

        tx = transaction_service.get_transaction(sim_with_agents, tx_id)

        assert tx is not None
        assert tx["sender"] == "BANK_A"
        assert tx["receiver"] == "BANK_B"
        assert tx["amount"] == 100_000
        assert tx["deadline_tick"] == 50
        assert tx["priority"] == 5
        assert tx["divisible"] is False

    def test_submit_transaction_to_nonexistent_simulation_raises_error(
        self,
        transaction_service: TransactionService,
    ) -> None:
        """Submitting to non-existent simulation raises SimulationNotFoundError."""
        with pytest.raises(SimulationNotFoundError):
            transaction_service.submit_transaction(
                sim_id="nonexistent",
                sender="BANK_A",
                receiver="BANK_B",
                amount=100_000,
                deadline_tick=50,
                priority=5,
                divisible=False,
            )

    def test_submit_transaction_invalid_sender_raises_error(
        self,
        transaction_service: TransactionService,
        sim_with_agents: str,
    ) -> None:
        """Invalid sender raises RuntimeError."""
        with pytest.raises(RuntimeError):
            transaction_service.submit_transaction(
                sim_id=sim_with_agents,
                sender="BANK_X",  # Doesn't exist
                receiver="BANK_B",
                amount=100_000,
                deadline_tick=50,
                priority=5,
                divisible=False,
            )


class TestTransactionQueries:
    """Tests for transaction queries."""

    def test_get_transaction_returns_details(
        self,
        transaction_service: TransactionService,
        sim_with_agents: str,
    ) -> None:
        """Can retrieve transaction details by ID."""
        tx_id = transaction_service.submit_transaction(
            sim_id=sim_with_agents,
            sender="BANK_A",
            receiver="BANK_B",
            amount=100_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

        tx = transaction_service.get_transaction(sim_with_agents, tx_id)

        assert tx is not None
        assert tx["transaction_id"] == tx_id
        assert tx["tx_id"] == tx_id  # Alias
        assert "status" in tx

    def test_get_nonexistent_transaction_raises_error(
        self,
        transaction_service: TransactionService,
        sim_with_agents: str,
    ) -> None:
        """Getting non-existent transaction raises TransactionNotFoundError."""
        with pytest.raises(TransactionNotFoundError):
            transaction_service.get_transaction(sim_with_agents, "nonexistent-tx")

    def test_list_transactions_returns_all(
        self,
        transaction_service: TransactionService,
        sim_with_agents: str,
    ) -> None:
        """list_transactions returns all transactions for simulation."""
        # Submit multiple transactions
        tx_ids = []
        for i in range(3):
            tx_id = transaction_service.submit_transaction(
                sim_id=sim_with_agents,
                sender="BANK_A",
                receiver="BANK_B",
                amount=50_000 + (i * 10_000),
                deadline_tick=50,
                priority=5,
                divisible=False,
            )
            tx_ids.append(tx_id)

        transactions = transaction_service.list_transactions(sim_with_agents)

        assert len(transactions) >= 3
        listed_ids = [tx["tx_id"] for tx in transactions]
        for tx_id in tx_ids:
            assert tx_id in listed_ids

    def test_list_transactions_filter_by_status(
        self,
        transaction_service: TransactionService,
        simulation_service: SimulationService,
        sim_with_agents: str,
    ) -> None:
        """Can filter transactions by status."""
        # Submit a transaction
        transaction_service.submit_transaction(
            sim_id=sim_with_agents,
            sender="BANK_A",
            receiver="BANK_B",
            amount=50_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

        # Advance simulation to settle
        for _ in range(5):
            simulation_service.tick(sim_with_agents)

        # Filter by settled
        settled = transaction_service.list_transactions(
            sim_with_agents, status="settled"
        )

        for tx in settled:
            assert tx["status"] == "settled"

    def test_list_transactions_filter_by_agent(
        self,
        transaction_service: TransactionService,
        sim_with_agents: str,
    ) -> None:
        """Can filter transactions by agent (sender or receiver)."""
        transaction_service.submit_transaction(
            sim_id=sim_with_agents,
            sender="BANK_A",
            receiver="BANK_B",
            amount=50_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

        # Filter by BANK_A
        transactions = transaction_service.list_transactions(
            sim_with_agents, agent="BANK_A"
        )

        for tx in transactions:
            assert tx["sender"] == "BANK_A" or tx["receiver"] == "BANK_A"


class TestTransactionStatus:
    """Tests for transaction status tracking."""

    def test_initial_status_is_pending(
        self,
        transaction_service: TransactionService,
        sim_with_agents: str,
    ) -> None:
        """Newly submitted transactions have 'pending' status."""
        tx_id = transaction_service.submit_transaction(
            sim_id=sim_with_agents,
            sender="BANK_A",
            receiver="BANK_B",
            amount=100_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

        tx = transaction_service.get_transaction(sim_with_agents, tx_id)
        assert tx["status"] == "pending"

    def test_status_updates_after_settlement(
        self,
        transaction_service: TransactionService,
        simulation_service: SimulationService,
        sim_with_agents: str,
    ) -> None:
        """Transaction status updates to 'settled' after settlement."""
        tx_id = transaction_service.submit_transaction(
            sim_id=sim_with_agents,
            sender="BANK_A",
            receiver="BANK_B",
            amount=100_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

        # Advance simulation to settle
        for _ in range(5):
            simulation_service.tick(sim_with_agents)

        tx = transaction_service.get_transaction(sim_with_agents, tx_id)
        assert tx["status"] == "settled"


class TestTransactionServiceCleanup:
    """Tests for cleanup operations."""

    def test_cleanup_removes_simulation_transactions(
        self,
        transaction_service: TransactionService,
        sim_with_agents: str,
    ) -> None:
        """Cleaning up a simulation removes its transactions."""
        tx_id = transaction_service.submit_transaction(
            sim_id=sim_with_agents,
            sender="BANK_A",
            receiver="BANK_B",
            amount=100_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

        transaction_service.cleanup_simulation(sim_with_agents)

        with pytest.raises(TransactionNotFoundError):
            transaction_service.get_transaction(sim_with_agents, tx_id)
