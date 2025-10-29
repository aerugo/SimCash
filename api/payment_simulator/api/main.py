"""FastAPI application for Payment Simulator."""
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
import uuid

from payment_simulator._core import Orchestrator
from payment_simulator.config import SimulationConfig, ValidationError


# ============================================================================
# Request/Response Models
# ============================================================================

class TransactionSubmission(BaseModel):
    """Request model for submitting a transaction."""
    sender: str = Field(..., description="Sender agent ID")
    receiver: str = Field(..., description="Receiver agent ID")
    amount: int = Field(..., description="Transaction amount in cents")  # Let FFI validate
    deadline_tick: int = Field(..., description="Deadline tick number", gt=0)
    priority: int = Field(5, description="Priority level (0-10)", ge=0, le=10)
    divisible: bool = Field(False, description="Whether transaction can be split")


class TransactionResponse(BaseModel):
    """Response model for transaction submission."""
    transaction_id: str
    message: str = "Transaction submitted successfully"


class SimulationCreateResponse(BaseModel):
    """Response model for simulation creation."""
    simulation_id: str
    state: Dict[str, Any]
    message: str = "Simulation created successfully"


class TickResponse(BaseModel):
    """Response model for single tick execution."""
    tick: int
    num_arrivals: int
    num_settlements: int
    num_lsm_releases: int
    total_cost: int


class MultiTickResponse(BaseModel):
    """Response model for multiple tick execution."""
    results: List[TickResponse]
    final_tick: int


class SimulationListResponse(BaseModel):
    """Response model for listing simulations."""
    simulations: List[Dict[str, Any]]


class TransactionListResponse(BaseModel):
    """Response model for listing transactions."""
    transactions: List[Dict[str, Any]]


class CheckpointSaveRequest(BaseModel):
    """Request model for saving a checkpoint."""
    checkpoint_type: str = Field(..., description="Type of checkpoint (manual/auto/eod/final)")
    description: Optional[str] = Field(None, description="Human-readable description")


class CheckpointSaveResponse(BaseModel):
    """Response model for checkpoint save."""
    checkpoint_id: str
    simulation_id: str
    checkpoint_tick: int
    checkpoint_day: int
    message: str = "Checkpoint saved successfully"


class CheckpointLoadRequest(BaseModel):
    """Request model for loading from checkpoint."""
    checkpoint_id: str = Field(..., description="Checkpoint ID to restore from")


class CheckpointLoadResponse(BaseModel):
    """Response model for loading from checkpoint."""
    simulation_id: str
    current_tick: int
    current_day: int
    message: str = "Simulation restored from checkpoint"


class CheckpointListResponse(BaseModel):
    """Response model for listing checkpoints."""
    checkpoints: List[Dict[str, Any]]


# ============================================================================
# Simulation Manager (In-Memory State)
# ============================================================================

class SimulationManager:
    """Manages active simulation instances."""

    def __init__(self, db_manager=None):
        self.simulations: Dict[str, Orchestrator] = {}
        self.configs: Dict[str, Dict] = {}  # Store both original and FFI configs: {"original": dict, "ffi": dict}
        self.transactions: Dict[str, Dict[str, Dict[str, Any]]] = {}  # sim_id -> tx_id -> tx_data
        self.db_manager = db_manager  # Optional database manager for checkpoints

    def create_simulation(self, config_dict: dict) -> tuple[str, Orchestrator]:
        """Create new simulation from config."""
        # Validate config
        try:
            config = SimulationConfig.from_dict(config_dict)
        except ValidationError as e:
            raise ValueError(f"Invalid configuration: {e}")

        # Convert to FFI dict
        ffi_dict = config.to_ffi_dict()

        # Create orchestrator
        try:
            orchestrator = Orchestrator.new(ffi_dict)
        except Exception as e:
            raise RuntimeError(f"Failed to create orchestrator: {e}")

        # Generate unique ID
        sim_id = str(uuid.uuid4())

        # Store (keep both original and FFI configs for checkpoint restoration)
        self.simulations[sim_id] = orchestrator
        self.configs[sim_id] = {"original": config_dict, "ffi": ffi_dict}
        self.transactions[sim_id] = {}  # Initialize empty transaction tracking

        return sim_id, orchestrator

    def get_simulation(self, sim_id: str) -> Orchestrator:
        """Get simulation by ID."""
        if sim_id not in self.simulations:
            raise KeyError(f"Simulation not found: {sim_id}")
        return self.simulations[sim_id]

    def delete_simulation(self, sim_id: str):
        """Delete simulation."""
        if sim_id in self.simulations:
            del self.simulations[sim_id]
            del self.configs[sim_id]
            del self.transactions[sim_id]

    def list_simulations(self) -> List[Dict[str, Any]]:
        """List all active simulations."""
        return [
            {
                "simulation_id": sim_id,
                "current_tick": orch.current_tick(),
                "current_day": orch.current_day(),
            }
            for sim_id, orch in self.simulations.items()
        ]

    def get_state(self, sim_id: str) -> Dict[str, Any]:
        """Get full simulation state."""
        orch = self.get_simulation(sim_id)

        # Collect agent states
        agents = {}
        for agent_id in orch.get_agent_ids():
            agents[agent_id] = {
                "balance": orch.get_agent_balance(agent_id),
                "queue1_size": orch.get_queue1_size(agent_id),
                "credit_limit": self.configs[sim_id]["original"]["agents"][
                    next(i for i, a in enumerate(self.configs[sim_id]["original"]["agents"]) if a["id"] == agent_id)
                ]["credit_limit"],
            }

        return {
            "simulation_id": sim_id,
            "current_tick": orch.current_tick(),
            "current_day": orch.current_day(),
            "agents": agents,
            "queue2_size": orch.get_queue2_size(),
        }

    def track_transaction(
        self,
        sim_id: str,
        tx_id: str,
        sender: str,
        receiver: str,
        amount: int,
        deadline_tick: int,
        priority: int,
        divisible: bool,
    ):
        """Track a submitted transaction."""
        if sim_id not in self.transactions:
            self.transactions[sim_id] = {}

        # Capture sender balance at submission time
        orch = self.simulations[sim_id]
        sender_balance_at_submission = orch.get_agent_balance(sender)

        self.transactions[sim_id][tx_id] = {
            "transaction_id": tx_id,
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

    def get_transaction(self, sim_id: str, tx_id: str) -> Optional[Dict[str, Any]]:
        """Get transaction by ID, with status inference."""
        if sim_id not in self.transactions:
            return None

        tx_data = self.transactions[sim_id].get(tx_id)
        if tx_data is None:
            return None

        # Make a copy to avoid modifying stored data
        tx_data = tx_data.copy()

        # Infer status based on balance changes since submission
        # If sender's balance has decreased by at least the transaction amount,
        # assume the transaction has settled
        orch = self.simulations[sim_id]
        current_balance = orch.get_agent_balance(tx_data["sender"])
        balance_at_submission = tx_data.get("sender_balance_at_submission")

        if balance_at_submission is not None:
            balance_decrease = balance_at_submission - current_balance

            # If balance decreased by at least 80% of transaction amount, assume settled
            # (allowing for some costs/fees)
            if balance_decrease >= (tx_data["amount"] * 0.8):
                tx_data["status"] = "settled"

        return tx_data

    def list_transactions(
        self,
        sim_id: str,
        status: Optional[str] = None,
        agent: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List transactions with optional filtering."""
        if sim_id not in self.transactions:
            return []

        transactions = list(self.transactions[sim_id].values())

        # Apply filters
        if status:
            transactions = [tx for tx in transactions if tx["status"] == status]

        if agent:
            transactions = [
                tx for tx in transactions
                if tx["sender"] == agent or tx["receiver"] == agent
            ]

        return transactions


# ============================================================================
# FastAPI Application
# ============================================================================

# Global simulation manager
manager = SimulationManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    # Startup
    yield
    # Shutdown: cleanup simulations
    manager.simulations.clear()
    manager.configs.clear()
    manager.transactions.clear()


app = FastAPI(
    title="Payment Simulator API",
    description="REST API for Payment Simulator - Real-Time Gross Settlement System",
    version="0.1.0",
    lifespan=lifespan,
)


# ============================================================================
# Simulation Endpoints
# ============================================================================

@app.post("/simulations", response_model=SimulationCreateResponse, status_code=200)
def create_simulation(config: dict):
    """
    Create a new simulation from configuration.

    Accepts simulation configuration as JSON and returns a unique simulation ID.
    The simulation starts at tick 0 and can be advanced using the tick endpoint.
    """
    try:
        sim_id, orch = manager.create_simulation(config)
        state = manager.get_state(sim_id)

        return SimulationCreateResponse(
            simulation_id=sim_id,
            state=state,
        )

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


@app.get("/simulations", response_model=SimulationListResponse)
def list_simulations():
    """List all active simulations."""
    simulations = manager.list_simulations()
    return SimulationListResponse(simulations=simulations)


@app.get("/simulations/{sim_id}/state")
def get_simulation_state(sim_id: str):
    """
    Get current simulation state.

    Returns full state including:
    - Current tick and day
    - All agent balances
    - Queue sizes
    """
    try:
        state = manager.get_state(sim_id)
        return state
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Simulation not found: {sim_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


@app.post("/simulations/{sim_id}/tick")
def advance_simulation(sim_id: str, count: int = Query(1, ge=1, le=1000)):
    """
    Advance simulation by one or more ticks.

    Args:
        sim_id: Simulation ID
        count: Number of ticks to advance (default: 1, max: 1000)

    Returns:
        Single tick result if count=1, list of results if count>1
    """
    try:
        orch = manager.get_simulation(sim_id)

        if count == 1:
            # Single tick
            result = orch.tick()
            return TickResponse(**result)
        else:
            # Multiple ticks
            results = []
            for _ in range(count):
                result = orch.tick()
                results.append(TickResponse(**result))

            return MultiTickResponse(
                results=results,
                final_tick=orch.current_tick(),
            )

    except KeyError:
        raise HTTPException(status_code=404, detail=f"Simulation not found: {sim_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tick execution failed: {e}")


@app.delete("/simulations/{sim_id}")
def delete_simulation(sim_id: str):
    """Delete a simulation."""
    try:
        manager.delete_simulation(sim_id)
        return {"message": "Simulation deleted successfully", "simulation_id": sim_id}
    except KeyError:
        # Idempotent - don't error if already deleted
        return {"message": "Simulation not found (may have been already deleted)", "simulation_id": sim_id}


# ============================================================================
# Transaction Endpoints
# ============================================================================

@app.post("/simulations/{sim_id}/transactions", response_model=TransactionResponse)
def submit_transaction(sim_id: str, tx: TransactionSubmission):
    """
    Submit a new transaction to the simulation.

    The transaction will be queued in the sender's internal queue (Queue 1)
    and processed by their policy during subsequent ticks.
    """
    try:
        orch = manager.get_simulation(sim_id)

        # Submit transaction via FFI
        tx_id = orch.submit_transaction(
            sender=tx.sender,
            receiver=tx.receiver,
            amount=tx.amount,
            deadline_tick=tx.deadline_tick,
            priority=tx.priority,
            divisible=tx.divisible,
        )

        # Track transaction metadata
        manager.track_transaction(
            sim_id=sim_id,
            tx_id=tx_id,
            sender=tx.sender,
            receiver=tx.receiver,
            amount=tx.amount,
            deadline_tick=tx.deadline_tick,
            priority=tx.priority,
            divisible=tx.divisible,
        )

        return TransactionResponse(transaction_id=tx_id)

    except KeyError:
        raise HTTPException(status_code=404, detail=f"Simulation not found: {sim_id}")
    except RuntimeError as e:
        # FFI errors (agent not found, invalid amount, etc.)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


@app.get("/simulations/{sim_id}/transactions/{tx_id}")
def get_transaction(sim_id: str, tx_id: str):
    """
    Get transaction details and status.

    Returns the tracked metadata for a transaction, including its current status.
    Note: Status is initially set to "pending" and would need to be updated
    based on settlement events (future enhancement).
    """
    try:
        # Verify simulation exists
        orch = manager.get_simulation(sim_id)

        # Get transaction from tracking
        tx_data = manager.get_transaction(sim_id, tx_id)

        if tx_data is None:
            raise HTTPException(
                status_code=404,
                detail=f"Transaction not found: {tx_id}",
            )

        return tx_data

    except KeyError:
        raise HTTPException(status_code=404, detail=f"Simulation not found: {sim_id}")
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


@app.get("/simulations/{sim_id}/transactions", response_model=TransactionListResponse)
def list_transactions(
    sim_id: str,
    status: Optional[str] = None,
    agent: Optional[str] = None,
):
    """
    List all transactions in a simulation.

    Optional filters:
    - status: Filter by transaction status (pending/settled/dropped)
    - agent: Filter by sender or receiver agent ID

    Returns all tracked transactions with optional filtering.
    """
    try:
        # Verify simulation exists
        orch = manager.get_simulation(sim_id)

        # Get filtered transactions
        transactions = manager.list_transactions(sim_id, status=status, agent=agent)

        return TransactionListResponse(transactions=transactions)

    except KeyError:
        raise HTTPException(status_code=404, detail=f"Simulation not found: {sim_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


# ============================================================================
# Checkpoint Endpoints
# ============================================================================

@app.post("/simulations/{sim_id}/checkpoint", response_model=CheckpointSaveResponse)
def save_checkpoint(sim_id: str, request: CheckpointSaveRequest):
    """
    Save simulation state as checkpoint to database.

    Creates a checkpoint that can be used to restore the simulation later.
    The checkpoint includes complete state (agents, transactions, queues, RNG state).
    """
    try:
        # Verify simulation exists
        orch = manager.get_simulation(sim_id)

        # Verify database manager is available
        if not hasattr(app.state, 'db_manager') or app.state.db_manager is None:
            raise HTTPException(
                status_code=503,
                detail="Checkpoint feature not available (database not configured)"
            )

        # Import CheckpointManager
        from payment_simulator.persistence.checkpoint import CheckpointManager

        # Create checkpoint manager
        checkpoint_mgr = CheckpointManager(app.state.db_manager)

        # Get the FFI config that was used to create this simulation
        config_data = manager.configs[sim_id]
        ffi_dict = config_data["ffi"]

        # Save checkpoint
        checkpoint_id = checkpoint_mgr.save_checkpoint(
            orchestrator=orch,
            simulation_id=sim_id,
            config=ffi_dict,
            checkpoint_type=request.checkpoint_type,
            description=request.description,
            created_by="api_user"  # TODO: Get from auth context
        )

        return CheckpointSaveResponse(
            checkpoint_id=checkpoint_id,
            simulation_id=sim_id,
            checkpoint_tick=orch.current_tick(),
            checkpoint_day=orch.current_day(),
        )

    except KeyError:
        raise HTTPException(status_code=404, detail=f"Simulation not found: {sim_id}")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save checkpoint: {e}")


@app.post("/simulations/from-checkpoint", response_model=CheckpointLoadResponse)
def load_from_checkpoint(request: CheckpointLoadRequest):
    """
    Create new simulation by restoring from checkpoint.

    Loads the simulation state from the specified checkpoint and creates a new
    active simulation instance that can be advanced independently.
    """
    try:
        # Verify database manager is available
        if not hasattr(app.state, 'db_manager') or app.state.db_manager is None:
            raise HTTPException(
                status_code=503,
                detail="Checkpoint feature not available (database not configured)"
            )

        # Import CheckpointManager
        from payment_simulator.persistence.checkpoint import CheckpointManager

        # Create checkpoint manager
        checkpoint_mgr = CheckpointManager(app.state.db_manager)

        # Get checkpoint to extract config
        checkpoint = checkpoint_mgr.get_checkpoint(request.checkpoint_id)
        if checkpoint is None:
            raise HTTPException(
                status_code=404,
                detail=f"Checkpoint not found: {request.checkpoint_id}"
            )

        # Load orchestrator and config from checkpoint
        # The config is stored in the checkpoint database record, so we don't need
        # the original simulation to still be active in memory
        orch, ffi_dict = checkpoint_mgr.load_checkpoint(request.checkpoint_id)

        # Create new simulation ID
        new_sim_id = str(uuid.uuid4())

        # Convert FFI dict back to original config dict for storage
        # This is for API compatibility (list_simulations needs original format)
        from payment_simulator.config import SimulationConfig
        # We need to reconstruct the original dict from the FFI dict
        # For now, we'll just use the ffi_dict as both (they're similar enough)
        # TODO: Store original_config_dict in checkpoint too if needed for perfect reconstruction
        config_dict = ffi_dict  # Simplified: use FFI dict as original

        # Store in manager
        manager.simulations[new_sim_id] = orch
        manager.configs[new_sim_id] = {"original": config_dict, "ffi": ffi_dict}
        manager.transactions[new_sim_id] = {}  # Initialize empty transaction tracking

        return CheckpointLoadResponse(
            simulation_id=new_sim_id,
            current_tick=orch.current_tick(),
            current_day=orch.current_day(),
        )

    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load checkpoint: {e}")


@app.get("/simulations/{sim_id}/checkpoints", response_model=CheckpointListResponse)
def list_checkpoints(sim_id: str):
    """
    List all checkpoints for a simulation.

    Returns checkpoint metadata sorted by tick (chronological order).
    """
    try:
        # Verify simulation exists (or existed)
        # Note: Checkpoints may exist for deleted simulations
        if sim_id not in manager.simulations and sim_id not in manager.configs:
            raise HTTPException(status_code=404, detail=f"Simulation not found: {sim_id}")

        # Verify database manager is available
        if not hasattr(app.state, 'db_manager') or app.state.db_manager is None:
            raise HTTPException(
                status_code=503,
                detail="Checkpoint feature not available (database not configured)"
            )

        # Import CheckpointManager
        from payment_simulator.persistence.checkpoint import CheckpointManager

        # Create checkpoint manager
        checkpoint_mgr = CheckpointManager(app.state.db_manager)

        # List checkpoints
        checkpoints = checkpoint_mgr.list_checkpoints(simulation_id=sim_id)

        return CheckpointListResponse(checkpoints=checkpoints)

    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list checkpoints: {e}")


@app.get("/checkpoints/{checkpoint_id}")
def get_checkpoint_details(checkpoint_id: str):
    """
    Get checkpoint metadata by ID.

    Returns full checkpoint metadata (excluding large state_json field).
    """
    try:
        # Verify database manager is available
        if not hasattr(app.state, 'db_manager') or app.state.db_manager is None:
            raise HTTPException(
                status_code=503,
                detail="Checkpoint feature not available (database not configured)"
            )

        # Import CheckpointManager
        from payment_simulator.persistence.checkpoint import CheckpointManager

        # Create checkpoint manager
        checkpoint_mgr = CheckpointManager(app.state.db_manager)

        # Get checkpoint
        checkpoint = checkpoint_mgr.get_checkpoint(checkpoint_id)

        if checkpoint is None:
            raise HTTPException(
                status_code=404,
                detail=f"Checkpoint not found: {checkpoint_id}"
            )

        # Remove large state_json field from response (use /checkpoints/{id}/state to get it)
        checkpoint_metadata = {k: v for k, v in checkpoint.items() if k != "state_json"}

        return checkpoint_metadata

    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get checkpoint: {e}")


@app.delete("/checkpoints/{checkpoint_id}")
def delete_checkpoint(checkpoint_id: str):
    """
    Delete a checkpoint by ID.

    This operation is idempotent - deleting a non-existent checkpoint succeeds.
    """
    try:
        # Verify database manager is available
        if not hasattr(app.state, 'db_manager') or app.state.db_manager is None:
            raise HTTPException(
                status_code=503,
                detail="Checkpoint feature not available (database not configured)"
            )

        # Import CheckpointManager
        from payment_simulator.persistence.checkpoint import CheckpointManager

        # Create checkpoint manager
        checkpoint_mgr = CheckpointManager(app.state.db_manager)

        # Delete checkpoint (idempotent)
        checkpoint_mgr.delete_checkpoint(checkpoint_id)

        return {"message": "Checkpoint deleted successfully", "checkpoint_id": checkpoint_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete checkpoint: {e}")


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "active_simulations": len(manager.simulations),
    }


# ============================================================================
# Root
# ============================================================================

@app.get("/")
def root():
    """API root with basic info."""
    return {
        "name": "Payment Simulator API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }
