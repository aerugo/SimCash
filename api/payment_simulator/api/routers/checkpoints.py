"""Router for checkpoint endpoints.

Handles checkpoint save, restore, list, and delete operations.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from payment_simulator.api.dependencies import (
    container,
    get_db_manager,
    get_simulation_service,
)
from payment_simulator.api.models import (
    CheckpointListResponse,
    CheckpointLoadRequest,
    CheckpointLoadResponse,
    CheckpointSaveRequest,
    CheckpointSaveResponse,
)
from payment_simulator.api.services import (
    SimulationNotFoundError,
    SimulationService,
)

router = APIRouter(tags=["checkpoints"])


@router.post(
    "/simulations/{sim_id}/checkpoint", response_model=CheckpointSaveResponse
)
def save_checkpoint(
    sim_id: str,
    request: CheckpointSaveRequest,
    service: SimulationService = Depends(get_simulation_service),
    db_manager: Any = Depends(get_db_manager),
) -> CheckpointSaveResponse:
    """Save simulation state as checkpoint to database.

    Creates a checkpoint that can be used to restore the simulation later.
    The checkpoint includes complete state (agents, transactions, queues, RNG state).
    """
    try:
        # Verify simulation exists
        orch = service.get_simulation(sim_id)

        # Verify database manager is available
        if not db_manager:
            raise HTTPException(
                status_code=503,
                detail="Checkpoint feature not available (database not configured)",
            )

        # Import CheckpointManager
        from payment_simulator.persistence.checkpoint import CheckpointManager

        # Create checkpoint manager
        checkpoint_mgr = CheckpointManager(db_manager)

        # Get the FFI config that was used to create this simulation
        config_data = service.get_config(sim_id)
        ffi_dict = config_data["ffi"]

        # Save checkpoint
        checkpoint_id = checkpoint_mgr.save_checkpoint(
            orchestrator=orch,
            simulation_id=sim_id,
            config=ffi_dict,
            checkpoint_type=request.checkpoint_type,
            description=request.description,
            created_by="api_user",  # TODO: Get from auth context
        )

        return CheckpointSaveResponse(
            checkpoint_id=checkpoint_id,
            simulation_id=sim_id,
            checkpoint_tick=orch.current_tick(),
            checkpoint_day=orch.current_day(),
        )

    except SimulationNotFoundError:
        raise HTTPException(
            status_code=404, detail=f"Simulation not found: {sim_id}"
        ) from None
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to save checkpoint: {e}"
        ) from e


@router.post("/simulations/from-checkpoint", response_model=CheckpointLoadResponse)
def load_from_checkpoint(
    request: CheckpointLoadRequest,
    service: SimulationService = Depends(get_simulation_service),
    db_manager: Any = Depends(get_db_manager),
) -> CheckpointLoadResponse:
    """Create new simulation by restoring from checkpoint.

    Loads the simulation state from the specified checkpoint and creates a new
    active simulation instance that can be advanced independently.
    """
    try:
        # Verify database manager is available
        if not db_manager:
            raise HTTPException(
                status_code=503,
                detail="Checkpoint feature not available (database not configured)",
            )

        # Import CheckpointManager
        from payment_simulator.persistence.checkpoint import CheckpointManager

        # Create checkpoint manager
        checkpoint_mgr = CheckpointManager(db_manager)

        # Get checkpoint to extract config
        checkpoint = checkpoint_mgr.get_checkpoint(request.checkpoint_id)
        if checkpoint is None:
            raise HTTPException(
                status_code=404, detail=f"Checkpoint not found: {request.checkpoint_id}"
            )

        # Load orchestrator and config from checkpoint
        orch, ffi_dict = checkpoint_mgr.load_checkpoint(request.checkpoint_id)

        # Create new simulation ID
        new_sim_id = str(uuid.uuid4())

        # Store in service (direct access to internal state for now)
        # TODO: Add a proper method for this
        service._simulations[new_sim_id] = orch
        service._configs[new_sim_id] = {"original": ffi_dict, "ffi": ffi_dict}

        return CheckpointLoadResponse(
            simulation_id=new_sim_id,
            current_tick=orch.current_tick(),
            current_day=orch.current_day(),
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to load checkpoint: {e}"
        ) from e


@router.get(
    "/simulations/{sim_id}/checkpoints", response_model=CheckpointListResponse
)
def list_checkpoints(
    sim_id: str,
    service: SimulationService = Depends(get_simulation_service),
    db_manager: Any = Depends(get_db_manager),
) -> CheckpointListResponse:
    """List all checkpoints for a simulation.

    Returns checkpoint metadata sorted by tick (chronological order).
    """
    try:
        # Verify simulation exists (or existed)
        if not service.has_simulation(sim_id):
            raise HTTPException(
                status_code=404, detail=f"Simulation not found: {sim_id}"
            )

        # Verify database manager is available
        if not db_manager:
            raise HTTPException(
                status_code=503,
                detail="Checkpoint feature not available (database not configured)",
            )

        # Import CheckpointManager
        from payment_simulator.persistence.checkpoint import CheckpointManager

        # Create checkpoint manager
        checkpoint_mgr = CheckpointManager(db_manager)

        # List checkpoints
        checkpoints = checkpoint_mgr.list_checkpoints(simulation_id=sim_id)

        return CheckpointListResponse(checkpoints=checkpoints)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list checkpoints: {e}"
        ) from e


@router.get("/checkpoints/{checkpoint_id}")
def get_checkpoint_details(
    checkpoint_id: str,
    db_manager: Any = Depends(get_db_manager),
) -> dict[str, Any]:
    """Get checkpoint metadata by ID.

    Returns full checkpoint metadata (excluding large state_json field).
    """
    try:
        # Verify database manager is available
        if not db_manager:
            raise HTTPException(
                status_code=503,
                detail="Checkpoint feature not available (database not configured)",
            )

        # Import CheckpointManager
        from payment_simulator.persistence.checkpoint import CheckpointManager

        # Create checkpoint manager
        checkpoint_mgr = CheckpointManager(db_manager)

        # Get checkpoint
        checkpoint = checkpoint_mgr.get_checkpoint(checkpoint_id)

        if checkpoint is None:
            raise HTTPException(
                status_code=404, detail=f"Checkpoint not found: {checkpoint_id}"
            )

        # Remove large state_json field from response
        checkpoint_metadata = {k: v for k, v in checkpoint.items() if k != "state_json"}

        return checkpoint_metadata

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get checkpoint: {e}"
        ) from e


@router.delete("/checkpoints/{checkpoint_id}")
def delete_checkpoint(
    checkpoint_id: str,
    db_manager: Any = Depends(get_db_manager),
) -> dict[str, str]:
    """Delete a checkpoint by ID.

    This operation is idempotent - deleting a non-existent checkpoint succeeds.
    """
    try:
        # Verify database manager is available
        if not db_manager:
            raise HTTPException(
                status_code=503,
                detail="Checkpoint feature not available (database not configured)",
            )

        # Import CheckpointManager
        from payment_simulator.persistence.checkpoint import CheckpointManager

        # Create checkpoint manager
        checkpoint_mgr = CheckpointManager(db_manager)

        # Delete checkpoint (idempotent)
        checkpoint_mgr.delete_checkpoint(checkpoint_id)

        return {
            "message": "Checkpoint deleted successfully",
            "checkpoint_id": checkpoint_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete checkpoint: {e}"
        ) from e
