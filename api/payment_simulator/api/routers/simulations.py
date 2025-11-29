"""Router for simulation endpoints.

Handles simulation lifecycle: create, list, get state, tick, delete.
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
    MultiTickResponse,
    SimulationCreateResponse,
    SimulationListResponse,
    TickResponse,
)
from payment_simulator.api.services import (
    SimulationNotFoundError,
    SimulationService,
    TransactionService,
)

router = APIRouter(prefix="/simulations", tags=["simulations"])


@router.post("", response_model=SimulationCreateResponse, status_code=200)
def create_simulation(
    config: dict[str, Any],
    service: SimulationService = Depends(get_simulation_service),
) -> SimulationCreateResponse:
    """Create a new simulation from configuration.

    Accepts simulation configuration as JSON and returns a unique simulation ID.
    The simulation starts at tick 0 and can be advanced using the tick endpoint.
    """
    try:
        sim_id, _ = service.create_simulation(config)
        state = service.get_state(sim_id)

        return SimulationCreateResponse(
            simulation_id=sim_id,
            state=state,
        )

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}") from e


@router.get("", response_model=SimulationListResponse)
def list_simulations(
    service: SimulationService = Depends(get_simulation_service),
    db_manager: Any = Depends(get_db_manager),
) -> SimulationListResponse:
    """List all simulations (both active and database-persisted).

    Returns:
        - Active in-memory simulations with current_tick, current_day
        - Database-persisted simulations with config_file, status, timestamps
    """
    try:
        simulations = []

        # Get active in-memory simulations
        active_sims = service.list_simulations()
        simulations.extend(active_sims)

        # Get database-persisted simulations
        if db_manager:
            conn = db_manager.get_connection()

            query = """
                SELECT
                    simulation_id,
                    config_file,
                    config_hash,
                    rng_seed,
                    ticks_per_day,
                    num_days,
                    num_agents,
                    status,
                    started_at,
                    completed_at
                FROM simulations
                ORDER BY started_at DESC
            """

            results = conn.execute(query).fetchall()

            for row in results:
                # Skip if already in active list
                if any(s["simulation_id"] == row[0] for s in simulations):
                    continue

                # Handle datetime conversion
                started_at = row[8]
                if started_at:
                    if hasattr(started_at, "isoformat"):
                        started_at = started_at.isoformat()
                    else:
                        started_at = str(started_at)

                completed_at = row[9]
                if completed_at:
                    if hasattr(completed_at, "isoformat"):
                        completed_at = completed_at.isoformat()
                    else:
                        completed_at = str(completed_at)

                simulations.append(
                    {
                        "simulation_id": str(row[0]),
                        "config_file": str(row[1]) if row[1] else None,
                        "config_hash": str(row[2]) if row[2] else None,
                        "rng_seed": int(row[3]) if row[3] is not None else None,
                        "ticks_per_day": int(row[4]) if row[4] is not None else None,
                        "num_days": int(row[5]) if row[5] is not None else None,
                        "num_agents": int(row[6]) if row[6] is not None else None,
                        "status": str(row[7]) if row[7] else None,
                        "started_at": started_at,
                        "completed_at": completed_at,
                    }
                )

        return SimulationListResponse(simulations=simulations)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}") from e


@router.get("/{sim_id}/state")
def get_simulation_state(
    sim_id: str,
    service: SimulationService = Depends(get_simulation_service),
) -> dict[str, Any]:
    """Get current simulation state.

    Returns full state including:
    - Current tick and day
    - All agent balances
    - Queue sizes
    """
    try:
        state = service.get_state(sim_id)
        return state
    except SimulationNotFoundError:
        raise HTTPException(
            status_code=404, detail=f"Simulation not found: {sim_id}"
        ) from None
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}") from e


@router.post("/{sim_id}/tick")
def advance_simulation(
    sim_id: str,
    count: int = Query(1, ge=1, le=1000),
    service: SimulationService = Depends(get_simulation_service),
) -> TickResponse | MultiTickResponse:
    """Advance simulation by one or more ticks.

    Args:
        sim_id: Simulation ID
        count: Number of ticks to advance (default: 1, max: 1000)

    Returns:
        Single tick result if count=1, list of results if count>1
    """
    try:
        if count == 1:
            result = service.tick(sim_id)
            return TickResponse(**result)
        else:
            results = service.tick_multiple(sim_id, count)
            orch = service.get_simulation(sim_id)
            return MultiTickResponse(
                results=[TickResponse(**r) for r in results],
                final_tick=orch.current_tick(),
            )

    except SimulationNotFoundError:
        raise HTTPException(
            status_code=404, detail=f"Simulation not found: {sim_id}"
        ) from None
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tick execution failed: {e}") from e


@router.delete("/{sim_id}")
def delete_simulation(
    sim_id: str,
    service: SimulationService = Depends(get_simulation_service),
    tx_service: TransactionService = Depends(get_transaction_service),
) -> dict[str, str]:
    """Delete a simulation."""
    try:
        service.delete_simulation(sim_id)
        tx_service.cleanup_simulation(sim_id)
        return {"message": "Simulation deleted successfully", "simulation_id": sim_id}
    except SimulationNotFoundError:
        # Idempotent - don't error if already deleted
        return {
            "message": "Simulation not found (may have been already deleted)",
            "simulation_id": sim_id,
        }
