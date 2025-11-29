"""Router for transaction endpoints.

Handles transaction submission, queries, and status.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from payment_simulator.api.dependencies import (
    get_db_manager,
    get_simulation_service,
    get_transaction_service,
)
from payment_simulator.api.models import (
    NearDeadlineTransaction,
    NearDeadlineTransactionsResponse,
    OverdueTransaction,
    OverdueTransactionsResponse,
    TransactionListResponse,
    TransactionResponse,
    TransactionSubmission,
)
from payment_simulator.api.services import (
    SimulationNotFoundError,
    SimulationService,
    TransactionNotFoundError,
    TransactionService,
)

router = APIRouter(tags=["transactions"])


@router.post(
    "/simulations/{sim_id}/transactions", response_model=TransactionResponse
)
def submit_transaction(
    sim_id: str,
    tx: TransactionSubmission,
    service: TransactionService = Depends(get_transaction_service),
) -> TransactionResponse:
    """Submit a new transaction to the simulation.

    The transaction will be queued in the sender's internal queue (Queue 1)
    and processed by their policy during subsequent ticks.
    """
    try:
        tx_id = service.submit_transaction(
            sim_id=sim_id,
            sender=tx.sender,
            receiver=tx.receiver,
            amount=tx.amount,
            deadline_tick=tx.deadline_tick,
            priority=tx.priority,
            divisible=tx.divisible,
        )

        return TransactionResponse(transaction_id=tx_id)

    except SimulationNotFoundError:
        raise HTTPException(
            status_code=404, detail=f"Simulation not found: {sim_id}"
        ) from None
    except RuntimeError as e:
        # FFI errors (agent not found, invalid amount, etc.)
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}") from e


@router.get(
    "/simulations/{sim_id}/transactions/near-deadline",
    response_model=NearDeadlineTransactionsResponse,
)
def get_near_deadline_transactions(
    sim_id: str,
    within_ticks: int = Query(2, ge=1, le=100),
    sim_service: SimulationService = Depends(get_simulation_service),
) -> NearDeadlineTransactionsResponse:
    """Get transactions approaching their deadline.

    Returns transactions that are within the specified number of ticks from their
    deadline but not yet overdue. Useful for deadline warning displays.

    Args:
        within_ticks: Number of ticks ahead to check (default: 2, range: 1-100)

    Returns:
        List of transactions with countdown information
    """
    try:
        orch = sim_service.get_simulation(sim_id)
        current_tick = orch.current_tick()
        threshold_tick = current_tick + within_ticks

        # Get near-deadline transactions from orchestrator
        near_deadline_txs = orch.get_transactions_near_deadline(within_ticks)

        # Convert to response format
        transactions = [
            NearDeadlineTransaction(
                tx_id=tx["tx_id"],
                sender_id=tx["sender_id"],
                receiver_id=tx["receiver_id"],
                amount=tx["amount"],
                remaining_amount=tx["remaining_amount"],
                deadline_tick=tx["deadline_tick"],
                ticks_until_deadline=tx["ticks_until_deadline"],
            )
            for tx in near_deadline_txs
        ]

        return NearDeadlineTransactionsResponse(
            simulation_id=sim_id,
            current_tick=current_tick,
            within_ticks=within_ticks,
            threshold_tick=threshold_tick,
            transactions=transactions,
            count=len(transactions),
        )

    except SimulationNotFoundError:
        raise HTTPException(
            status_code=404, detail=f"Simulation not found: {sim_id}"
        ) from None
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}") from e


@router.get(
    "/simulations/{sim_id}/transactions/overdue",
    response_model=OverdueTransactionsResponse,
)
def get_overdue_transactions(
    sim_id: str,
    sim_service: SimulationService = Depends(get_simulation_service),
) -> OverdueTransactionsResponse:
    """Get all currently overdue transactions with cost breakdown.

    Returns transactions that have passed their deadline but are not yet settled.
    Includes cost information for overdue delay penalties.

    This endpoint provides data for overdue transaction warnings and cost analysis.
    """
    try:
        orch = sim_service.get_simulation(sim_id)
        current_tick = orch.current_tick()

        # Get overdue transactions from orchestrator
        overdue_txs = orch.get_overdue_transactions()

        # Convert to response format and calculate totals
        transactions = []
        total_overdue_cost = 0

        for tx in overdue_txs:
            overdue_tx = OverdueTransaction(
                tx_id=tx["tx_id"],
                sender_id=tx["sender_id"],
                receiver_id=tx["receiver_id"],
                amount=tx["amount"],
                remaining_amount=tx["remaining_amount"],
                deadline_tick=tx["deadline_tick"],
                overdue_since_tick=tx["overdue_since_tick"],
                ticks_overdue=tx["ticks_overdue"],
                estimated_delay_cost=tx.get("estimated_delay_cost", 0),
                deadline_penalty_cost=tx.get("deadline_penalty_cost", 0),
                total_overdue_cost=tx.get("total_overdue_cost", 0),
            )
            transactions.append(overdue_tx)
            total_overdue_cost += overdue_tx.total_overdue_cost

        return OverdueTransactionsResponse(
            simulation_id=sim_id,
            current_tick=current_tick,
            transactions=transactions,
            count=len(transactions),
            total_overdue_cost=total_overdue_cost,
        )

    except SimulationNotFoundError:
        raise HTTPException(
            status_code=404, detail=f"Simulation not found: {sim_id}"
        ) from None
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}") from e


@router.get("/simulations/{sim_id}/transactions/{tx_id}")
def get_transaction(
    sim_id: str,
    tx_id: str,
    service: TransactionService = Depends(get_transaction_service),
) -> dict[str, Any]:
    """Get transaction details and status.

    Returns the tracked metadata for a transaction, including its current status.
    """
    try:
        tx_data = service.get_transaction(sim_id, tx_id)
        return tx_data

    except SimulationNotFoundError:
        raise HTTPException(
            status_code=404, detail=f"Simulation not found: {sim_id}"
        ) from None
    except TransactionNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Transaction not found: {tx_id}",
        ) from None
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}") from e


@router.get(
    "/simulations/{sim_id}/transactions", response_model=TransactionListResponse
)
def list_transactions(
    sim_id: str,
    status: str | None = None,
    agent: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    service: TransactionService = Depends(get_transaction_service),
    sim_service: SimulationService = Depends(get_simulation_service),
    db_manager: Any = Depends(get_db_manager),
) -> TransactionListResponse:
    """List all transactions in a simulation.

    For in-memory simulations: returns tracked transactions
    For database simulations: queries transaction history

    Optional filters:
    - status: Filter by transaction status (pending/settled/dropped)
    - agent: Filter by sender or receiver agent ID
    - limit: Maximum number of transactions to return
    - offset: Number of transactions to skip
    """
    try:
        # Check if simulation exists in memory
        if sim_service.has_simulation(sim_id):
            # In-memory simulation - use service
            transactions = service.list_transactions(sim_id, status=status, agent=agent)
            return TransactionListResponse(transactions=transactions)

        # Not in memory, try database
        if not db_manager:
            raise HTTPException(
                status_code=404, detail=f"Simulation not found: {sim_id}"
            )

        conn = db_manager.get_connection()

        # Build query with filters
        where_clauses = ["simulation_id = ?"]
        params: list[Any] = [sim_id]

        if status:
            where_clauses.append("status = ?")
            params.append(status)

        if agent:
            where_clauses.append("(sender_id = ? OR receiver_id = ?)")
            params.extend([agent, agent])

        where_sql = " AND ".join(where_clauses)

        # Get transactions from database
        query = f"""
            SELECT
                tx_id,
                sender_id,
                receiver_id,
                amount,
                priority,
                arrival_tick,
                deadline_tick,
                settlement_tick,
                status,
                delay_cost,
                parent_tx_id,
                split_index
            FROM transactions
            WHERE {where_sql}
            ORDER BY arrival_tick DESC, tx_id
            LIMIT ? OFFSET ?
        """

        params.extend([limit, offset])
        results = conn.execute(query, params).fetchall()

        if not results and offset == 0:
            # No transactions at all - simulation might not exist
            # Verify simulation exists
            sim_check = conn.execute(
                "SELECT COUNT(*) FROM simulations WHERE simulation_id = ?", [sim_id]
            ).fetchone()

            if not sim_check or sim_check[0] == 0:
                raise HTTPException(
                    status_code=404, detail=f"Simulation not found: {sim_id}"
                )

        transactions = []
        for row in results:
            tx_dict = {
                "tx_id": str(row[0]),
                "transaction_id": str(row[0]),  # Alias for compatibility
                "sender": str(row[1]),
                "sender_id": str(row[1]),  # Alias for compatibility
                "receiver": str(row[2]),
                "receiver_id": str(row[2]),  # Alias for compatibility
                "amount": int(row[3]),
                "priority": int(row[4]),
                "arrival_tick": int(row[5]),
                "deadline_tick": int(row[6]),
                "settlement_tick": int(row[7]) if row[7] is not None else None,
                "status": str(row[8]),
                "delay_cost": int(row[9]) if row[9] else 0,
                "parent_tx_id": str(row[10]) if row[10] else None,
                "split_index": int(row[11]) if row[11] is not None else None,
            }
            transactions.append(tx_dict)

        return TransactionListResponse(transactions=transactions)

    except HTTPException:
        raise
    except SimulationNotFoundError:
        raise HTTPException(
            status_code=404, detail=f"Simulation not found: {sim_id}"
        ) from None
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}") from e
