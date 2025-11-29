"""Service layer for transaction management.

This module provides the TransactionService class which encapsulates
all business logic for submitting, tracking, and querying transactions.
"""

from __future__ import annotations

from typing import Any

from payment_simulator.api.services.simulation_service import (
    SimulationNotFoundError,
    SimulationService,
)


class TransactionNotFoundError(Exception):
    """Raised when a transaction cannot be found."""

    def __init__(self, tx_id: str, simulation_id: str | None = None) -> None:
        self.tx_id = tx_id
        self.simulation_id = simulation_id
        msg = f"Transaction not found: {tx_id}"
        if simulation_id:
            msg += f" in simulation {simulation_id}"
        super().__init__(msg)


class TransactionService:
    """Service for managing transactions.

    This service handles:
    - Transaction submission to simulations
    - Transaction metadata tracking
    - Transaction status queries
    - Transaction listing with filtering

    All transaction interactions are encapsulated here,
    providing a clean interface for the API layer.
    """

    def __init__(self, simulation_service: SimulationService) -> None:
        """Initialize the transaction service.

        Args:
            simulation_service: The simulation service for orchestrator access
        """
        self._simulation_service = simulation_service
        # Tracked transactions: sim_id -> tx_id -> tx_metadata
        self._transactions: dict[str, dict[str, dict[str, Any]]] = {}

    def submit_transaction(
        self,
        sim_id: str,
        sender: str,
        receiver: str,
        amount: int,
        deadline_tick: int,
        priority: int,
        divisible: bool,
    ) -> str:
        """Submit a new transaction to a simulation.

        Args:
            sim_id: The simulation ID
            sender: Sender agent ID
            receiver: Receiver agent ID
            amount: Transaction amount in cents
            deadline_tick: Deadline tick number
            priority: Priority level (0-10)
            divisible: Whether transaction can be split

        Returns:
            The transaction ID

        Raises:
            SimulationNotFoundError: If simulation doesn't exist
            RuntimeError: If submission fails (e.g., invalid agent)
        """
        # Get orchestrator (raises SimulationNotFoundError if not found)
        orch = self._simulation_service.get_simulation(sim_id)

        # Submit transaction via FFI
        try:
            tx_id = orch.submit_transaction(
                sender=sender,
                receiver=receiver,
                amount=amount,
                deadline_tick=deadline_tick,
                priority=priority,
                divisible=divisible,
            )
        except Exception as e:
            raise RuntimeError(f"Transaction submission failed: {e}") from e

        # Track transaction metadata
        self._track_transaction(
            sim_id=sim_id,
            tx_id=tx_id,
            sender=sender,
            receiver=receiver,
            amount=amount,
            deadline_tick=deadline_tick,
            priority=priority,
            divisible=divisible,
        )

        return tx_id

    def _track_transaction(
        self,
        sim_id: str,
        tx_id: str,
        sender: str,
        receiver: str,
        amount: int,
        deadline_tick: int,
        priority: int,
        divisible: bool,
    ) -> None:
        """Track submitted transaction metadata.

        Args:
            sim_id: The simulation ID
            tx_id: The transaction ID
            sender: Sender agent ID
            receiver: Receiver agent ID
            amount: Transaction amount in cents
            deadline_tick: Deadline tick number
            priority: Priority level
            divisible: Whether transaction can be split
        """
        if sim_id not in self._transactions:
            self._transactions[sim_id] = {}

        # Capture sender balance at submission time
        orch = self._simulation_service.get_simulation(sim_id)
        sender_balance_at_submission = orch.get_agent_balance(sender)

        self._transactions[sim_id][tx_id] = {
            "transaction_id": tx_id,
            "tx_id": tx_id,  # Alias for compatibility
            "sender": sender,
            "receiver": receiver,
            "amount": amount,
            "deadline_tick": deadline_tick,
            "priority": priority,
            "divisible": divisible,
            "status": "pending",  # Initial status
            "submitted_at_tick": orch.current_tick(),
            "sender_balance_at_submission": sender_balance_at_submission,
        }

    def get_transaction(
        self, sim_id: str, tx_id: str
    ) -> dict[str, Any]:
        """Get transaction details with current status.

        Args:
            sim_id: The simulation ID
            tx_id: The transaction ID

        Returns:
            Transaction dictionary with all metadata and current status

        Raises:
            SimulationNotFoundError: If simulation doesn't exist
            TransactionNotFoundError: If transaction doesn't exist
        """
        # Check simulation exists
        if not self._simulation_service.has_simulation(sim_id):
            raise SimulationNotFoundError(sim_id)

        # Check transaction exists in our tracking
        if sim_id not in self._transactions:
            raise TransactionNotFoundError(tx_id, sim_id)
        if tx_id not in self._transactions[sim_id]:
            raise TransactionNotFoundError(tx_id, sim_id)

        # Get tracked data
        tx_data = self._transactions[sim_id][tx_id].copy()

        # Update status from orchestrator
        self._update_transaction_status(sim_id, tx_data)

        return tx_data

    def _update_transaction_status(
        self, sim_id: str, tx_data: dict[str, Any]
    ) -> None:
        """Update transaction status from orchestrator.

        Args:
            sim_id: The simulation ID
            tx_data: Transaction data dictionary (modified in place)
        """
        orch = self._simulation_service.get_simulation(sim_id)
        tx_id = tx_data["tx_id"]

        orchestrator_tx = orch.get_transaction_details(tx_id)
        if orchestrator_tx is not None:
            # Map orchestrator status strings to API status format
            orch_status = orchestrator_tx.get("status", "Pending")
            status_map = {
                "Pending": "pending",
                "Settled": "settled",
                "Dropped": "dropped",
                "PartiallySettled": "partially_settled",
            }
            tx_data["status"] = status_map.get(orch_status, "pending")

            # Update remaining amount if available
            if "remaining_amount" in orchestrator_tx:
                tx_data["remaining_amount"] = orchestrator_tx["remaining_amount"]

    def list_transactions(
        self,
        sim_id: str,
        status: str | None = None,
        agent: str | None = None,
    ) -> list[dict[str, Any]]:
        """List transactions with optional filtering.

        Args:
            sim_id: The simulation ID
            status: Optional status filter (pending/settled/dropped)
            agent: Optional agent filter (matches sender or receiver)

        Returns:
            List of transaction dictionaries

        Raises:
            SimulationNotFoundError: If simulation doesn't exist
        """
        # Check simulation exists
        if not self._simulation_service.has_simulation(sim_id):
            raise SimulationNotFoundError(sim_id)

        if sim_id not in self._transactions:
            return []

        # Get all transactions with updated statuses
        transactions = []
        for tx_id in self._transactions[sim_id]:
            tx = self.get_transaction(sim_id, tx_id)
            transactions.append(tx)

        # Apply filters
        if status:
            transactions = [tx for tx in transactions if tx["status"] == status]

        if agent:
            transactions = [
                tx
                for tx in transactions
                if tx["sender"] == agent or tx["receiver"] == agent
            ]

        return transactions

    def cleanup_simulation(self, sim_id: str) -> None:
        """Remove all tracked transactions for a simulation.

        Args:
            sim_id: The simulation ID
        """
        if sim_id in self._transactions:
            del self._transactions[sim_id]

    def clear_all(self) -> None:
        """Clear all tracked transactions. Used for testing cleanup."""
        self._transactions.clear()
