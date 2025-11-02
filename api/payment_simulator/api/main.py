"""FastAPI application for Payment Simulator."""

import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from payment_simulator._core import Orchestrator
from payment_simulator.config import SimulationConfig, ValidationError
from pydantic import BaseModel, Field

# ============================================================================
# Request/Response Models
# ============================================================================


class TransactionSubmission(BaseModel):
    """Request model for submitting a transaction."""

    sender: str = Field(..., description="Sender agent ID")
    receiver: str = Field(..., description="Receiver agent ID")
    amount: int = Field(
        ..., description="Transaction amount in cents"
    )  # Let FFI validate
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

    checkpoint_type: str = Field(
        ..., description="Type of checkpoint (manual/auto/eod/final)"
    )
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


class AgentCostBreakdown(BaseModel):
    """Cost breakdown for a single agent."""

    liquidity_cost: int = Field(..., description="Overdraft cost in cents")
    collateral_cost: int = Field(
        ..., description="Collateral opportunity cost in cents"
    )
    delay_cost: int = Field(..., description="Queue 1 delay cost in cents")
    split_friction_cost: int = Field(
        ..., description="Transaction splitting cost in cents"
    )
    deadline_penalty: int = Field(..., description="Deadline miss penalties in cents")
    total_cost: int = Field(..., description="Sum of all costs in cents")


class CostResponse(BaseModel):
    """Response model for GET /simulations/{id}/costs endpoint."""

    simulation_id: str = Field(..., description="Simulation identifier")
    tick: int = Field(..., description="Current tick number")
    day: int = Field(..., description="Current day number")
    agents: Dict[str, AgentCostBreakdown] = Field(
        ..., description="Per-agent cost breakdowns"
    )
    total_system_cost: int = Field(
        ..., description="Total cost across all agents in cents"
    )


class SystemMetrics(BaseModel):
    """System-wide performance metrics."""

    total_arrivals: int = Field(..., description="Total transactions arrived")
    total_settlements: int = Field(..., description="Total transactions settled")
    settlement_rate: float = Field(
        ..., ge=0.0, le=1.0, description="Settlement rate (0.0-1.0)"
    )
    avg_delay_ticks: float = Field(..., description="Average settlement delay in ticks")
    max_delay_ticks: int = Field(..., description="Maximum delay observed in ticks")
    queue1_total_size: int = Field(
        ..., description="Total transactions in agent queues"
    )
    queue2_total_size: int = Field(..., description="Total transactions in RTGS queue")
    peak_overdraft: int = Field(
        ..., description="Largest overdraft across all agents in cents"
    )
    agents_in_overdraft: int = Field(
        ..., description="Number of agents with negative balance"
    )


class MetricsResponse(BaseModel):
    """Response model for GET /simulations/{id}/metrics endpoint."""

    simulation_id: str = Field(..., description="Simulation identifier")
    tick: int = Field(..., description="Current tick number")
    day: int = Field(..., description="Current day number")
    metrics: SystemMetrics = Field(..., description="System-wide metrics")


# ============================================================================
# Diagnostic Endpoints Response Models
# ============================================================================


class SimulationSummary(BaseModel):
    """Summary statistics for a simulation."""

    total_ticks: int
    total_transactions: int
    settlement_rate: float
    total_cost_cents: int
    duration_seconds: Optional[float] = None
    ticks_per_second: Optional[float] = None


class SimulationMetadataResponse(BaseModel):
    """Response model for GET /simulations/{id} diagnostic endpoint."""

    simulation_id: str
    created_at: str
    config: Dict[str, Any]
    summary: SimulationSummary


class AgentSummary(BaseModel):
    """Summary statistics for a single agent."""

    agent_id: str
    total_sent: int
    total_received: int
    total_settled: int
    total_dropped: int
    total_cost_cents: int
    avg_balance_cents: int
    peak_overdraft_cents: int
    credit_limit_cents: int


class AgentListResponse(BaseModel):
    """Response model for GET /simulations/{id}/agents endpoint."""

    agents: List[AgentSummary]


class EventRecord(BaseModel):
    """Single event in the timeline."""

    tick: int
    day: int
    event_type: str
    tx_id: Optional[str] = None
    sender_id: Optional[str] = None
    receiver_id: Optional[str] = None
    agent_id: Optional[str] = None
    amount: Optional[int] = None
    priority: Optional[int] = None
    deadline_tick: Optional[int] = None
    timestamp: Optional[str] = None


class EventListResponse(BaseModel):
    """Response model for paginated events."""

    events: List[EventRecord]
    total: int
    limit: int
    offset: int


class DailyAgentMetric(BaseModel):
    """Daily metrics for an agent."""

    day: int
    opening_balance: int
    closing_balance: int
    min_balance: int
    max_balance: int
    transactions_sent: int
    transactions_received: int
    total_cost_cents: int


class CollateralEvent(BaseModel):
    """Collateral event record."""

    tick: int
    day: int
    action: str
    amount: int
    reason: str
    balance_before: int


class AgentTimelineResponse(BaseModel):
    """Response model for agent timeline."""

    agent_id: str
    daily_metrics: List[DailyAgentMetric]
    collateral_events: List[CollateralEvent]


class TransactionEvent(BaseModel):
    """Event in a transaction lifecycle."""

    tick: int
    event_type: str
    details: Dict[str, Any]


class RelatedTransaction(BaseModel):
    """Related transaction reference."""

    tx_id: str
    relationship: str
    split_index: Optional[int] = None


class TransactionDetail(BaseModel):
    """Full transaction details."""

    tx_id: str
    sender_id: str
    receiver_id: str
    amount: int
    priority: int
    arrival_tick: int
    deadline_tick: int
    settlement_tick: Optional[int]
    status: str
    delay_cost: int
    amount_settled: int


class TransactionLifecycleResponse(BaseModel):
    """Response model for transaction lifecycle."""

    transaction: TransactionDetail
    events: List[TransactionEvent]
    related_transactions: List[RelatedTransaction]


# ============================================================================
# Simulation Manager (In-Memory State)
# ============================================================================


class SimulationManager:
    """Manages active simulation instances."""

    def __init__(self, db_manager=None):
        self.simulations: Dict[str, Orchestrator] = {}
        self.configs: Dict[str, Dict] = (
            {}
        )  # Store both original and FFI configs: {"original": dict, "ffi": dict}
        self.transactions: Dict[str, Dict[str, Dict[str, Any]]] = (
            {}
        )  # sim_id -> tx_id -> tx_data
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

        # Handle both YAML format ("agents") and FFI format ("agent_configs")
        config = self.configs[sim_id]["original"]
        agent_list = config.get("agents") or config.get("agent_configs")

        for agent_id in orch.get_agent_ids():
            # Find agent config
            agent_config = next((a for a in agent_list if a["id"] == agent_id), None)
            credit_limit = agent_config["credit_limit"] if agent_config else 0

            agents[agent_id] = {
                "balance": orch.get_agent_balance(agent_id),
                "queue1_size": orch.get_queue1_size(agent_id),
                "credit_limit": credit_limit,
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

    def get_transaction(self, sim_id: str, tx_id: str) -> Optional[Dict[str, Any]]:
        """Get transaction by ID with status from orchestrator."""
        if sim_id not in self.transactions:
            return None

        tx_data = self.transactions[sim_id].get(tx_id)
        if tx_data is None:
            return None

        # Make a copy to avoid modifying stored data
        tx_data = tx_data.copy()

        # Query the orchestrator for ground truth transaction status
        # This replaces the old balance-based heuristic which was unreliable
        orch = self.simulations[sim_id]
        orchestrator_tx = orch.get_transaction_details(tx_id)

        if orchestrator_tx is not None:
            # Update status from orchestrator's ground truth
            # Map orchestrator status strings to API status format
            orch_status = orchestrator_tx.get("status", "Pending")

            # Convert status to lowercase for API consistency
            status_map = {
                "Pending": "pending",
                "Settled": "settled",
                "Dropped": "dropped",
                "PartiallySettled": "partially_settled",
            }
            tx_data["status"] = status_map.get(orch_status, "pending")

            # Also update amount information from orchestrator if available
            if "remaining_amount" in orchestrator_tx:
                tx_data["remaining_amount"] = orchestrator_tx["remaining_amount"]

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

        # Get all transactions with updated statuses from orchestrator
        transactions = []
        for tx_id in self.transactions[sim_id].keys():
            tx = self.get_transaction(sim_id, tx_id)
            if tx is not None:
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


# ============================================================================
# FastAPI Application
# ============================================================================

# Global simulation manager
manager = SimulationManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    # Startup: Configure database if environment variable is set
    import os

    db_path = os.environ.get("PAYMENT_SIM_DB_PATH")
    if db_path:
        from payment_simulator.persistence.connection import DatabaseManager

        app.state.db_manager = DatabaseManager(db_path)
        app.state.db_manager.setup()
        manager.db_manager = app.state.db_manager

    yield

    # Shutdown: cleanup simulations and close database
    manager.simulations.clear()
    manager.configs.clear()
    manager.transactions.clear()
    if hasattr(app.state, "db_manager") and app.state.db_manager:
        app.state.db_manager.close()


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
    """List all simulations (both active and database-persisted).

    Returns:
        - Active in-memory simulations with current_tick, current_day
        - Database-persisted simulations with config_file, status, timestamps
    """
    try:
        simulations = []

        # Get active in-memory simulations
        active_sims = manager.list_simulations()
        simulations.extend(active_sims)

        # Get database-persisted simulations
        if manager.db_manager:
            conn = manager.db_manager.get_connection()

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

                simulations.append(
                    {
                        "simulation_id": str(row[0]),
                        "config_file": str(row[1]) if row[1] else None,
                        "config_hash": str(row[2]) if row[2] else None,
                        "rng_seed": int(row[3]) if row[3] else None,
                        "ticks_per_day": int(row[4]) if row[4] else None,
                        "num_days": int(row[5]) if row[5] else None,
                        "num_agents": int(row[6]) if row[6] else None,
                        "status": str(row[7]) if row[7] else None,
                        "started_at": row[8].isoformat() if row[8] else None,
                        "completed_at": row[9].isoformat() if row[9] else None,
                    }
                )

        return SimulationListResponse(simulations=simulations)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


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
        return {
            "message": "Simulation not found (may have been already deleted)",
            "simulation_id": sim_id,
        }


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
        if not hasattr(app.state, "db_manager") or app.state.db_manager is None:
            raise HTTPException(
                status_code=503,
                detail="Checkpoint feature not available (database not configured)",
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
            created_by="api_user",  # TODO: Get from auth context
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
        if not hasattr(app.state, "db_manager") or app.state.db_manager is None:
            raise HTTPException(
                status_code=503,
                detail="Checkpoint feature not available (database not configured)",
            )

        # Import CheckpointManager
        from payment_simulator.persistence.checkpoint import CheckpointManager

        # Create checkpoint manager
        checkpoint_mgr = CheckpointManager(app.state.db_manager)

        # Get checkpoint to extract config
        checkpoint = checkpoint_mgr.get_checkpoint(request.checkpoint_id)
        if checkpoint is None:
            raise HTTPException(
                status_code=404, detail=f"Checkpoint not found: {request.checkpoint_id}"
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
            raise HTTPException(
                status_code=404, detail=f"Simulation not found: {sim_id}"
            )

        # Verify database manager is available
        if not hasattr(app.state, "db_manager") or app.state.db_manager is None:
            raise HTTPException(
                status_code=503,
                detail="Checkpoint feature not available (database not configured)",
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
        if not hasattr(app.state, "db_manager") or app.state.db_manager is None:
            raise HTTPException(
                status_code=503,
                detail="Checkpoint feature not available (database not configured)",
            )

        # Import CheckpointManager
        from payment_simulator.persistence.checkpoint import CheckpointManager

        # Create checkpoint manager
        checkpoint_mgr = CheckpointManager(app.state.db_manager)

        # Get checkpoint
        checkpoint = checkpoint_mgr.get_checkpoint(checkpoint_id)

        if checkpoint is None:
            raise HTTPException(
                status_code=404, detail=f"Checkpoint not found: {checkpoint_id}"
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
        if not hasattr(app.state, "db_manager") or app.state.db_manager is None:
            raise HTTPException(
                status_code=503,
                detail="Checkpoint feature not available (database not configured)",
            )

        # Import CheckpointManager
        from payment_simulator.persistence.checkpoint import CheckpointManager

        # Create checkpoint manager
        checkpoint_mgr = CheckpointManager(app.state.db_manager)

        # Delete checkpoint (idempotent)
        checkpoint_mgr.delete_checkpoint(checkpoint_id)

        return {
            "message": "Checkpoint deleted successfully",
            "checkpoint_id": checkpoint_id,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete checkpoint: {e}")


# ============================================================================
# Cost & Metrics Endpoints (Phase 8)
# ============================================================================


@app.get("/simulations/{sim_id}/costs", response_model=CostResponse)
def get_simulation_costs(sim_id: str):
    """
    Get accumulated costs for all agents in a simulation.

    Returns per-agent cost breakdown and total system cost.
    All costs are in cents (i64).

    ## Cost Types

    - **Liquidity Cost**: Overdraft cost (negative balance × overdraft rate)
    - **Collateral Cost**: Opportunity cost of pledged collateral
    - **Delay Cost**: Queue 1 delay cost (transactions waiting × delay rate)
    - **Split Friction Cost**: Cost of splitting divisible transactions
    - **Deadline Penalty**: Penalties for missing transaction deadlines

    ## Example Response

    ```json
    {
      "simulation_id": "sim-001",
      "tick": 150,
      "day": 1,
      "agents": {
        "BANK_A": {
          "liquidity_cost": 1000,
          "collateral_cost": 500,
          "delay_cost": 200,
          "split_friction_cost": 50,
          "deadline_penalty": 0,
          "total_cost": 1750
        }
      },
      "total_system_cost": 5000
    }
    ```
    """
    try:
        # Get simulation
        orchestrator = manager.get_simulation(sim_id)

        # Get costs for all agents
        agent_costs = {}
        total_system_cost = 0

        # Get agent list from config
        config = manager.configs.get(sim_id, {}).get("original", {})
        agent_configs = config.get("agents", [])

        for agent_config in agent_configs:
            agent_id = agent_config["id"]

            # Get costs from FFI
            costs_dict = orchestrator.get_agent_accumulated_costs(agent_id)

            # Convert to Pydantic model
            breakdown = AgentCostBreakdown(**costs_dict)
            agent_costs[agent_id] = breakdown
            total_system_cost += breakdown.total_cost

        # Get current tick and day
        current_tick = orchestrator.current_tick()
        current_day = orchestrator.current_day()

        return CostResponse(
            simulation_id=sim_id,
            tick=current_tick,
            day=current_day,
            agents=agent_costs,
            total_system_cost=total_system_cost,
        )

    except KeyError:
        raise HTTPException(status_code=404, detail=f"Simulation not found: {sim_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


@app.get("/simulations/{sim_id}/metrics", response_model=MetricsResponse)
def get_simulation_metrics(sim_id: str):
    """
    Get comprehensive system-wide metrics for a simulation.

    Returns settlement rates, delays, queue statistics, and liquidity usage.

    ## Metrics

    - **Settlement Rate**: Ratio of settled to arrived transactions (0.0-1.0)
    - **Average Delay**: Mean time from arrival to settlement (ticks)
    - **Queue Sizes**: Transactions waiting in agent queues (Queue 1) and RTGS queue (Queue 2)
    - **Overdraft Usage**: Peak overdraft and number of agents in overdraft

    ## Example Response

    ```json
    {
      "simulation_id": "sim-001",
      "tick": 150,
      "day": 1,
      "metrics": {
        "total_arrivals": 1000,
        "total_settlements": 950,
        "settlement_rate": 0.95,
        "avg_delay_ticks": 2.5,
        "max_delay_ticks": 20,
        "queue1_total_size": 45,
        "queue2_total_size": 5,
        "peak_overdraft": 500000,
        "agents_in_overdraft": 3
      }
    }
    ```
    """
    try:
        # Get simulation
        orchestrator = manager.get_simulation(sim_id)

        # Get metrics from FFI
        metrics_dict = orchestrator.get_system_metrics()

        # Convert to Pydantic model
        metrics = SystemMetrics(**metrics_dict)

        # Get current tick and day
        current_tick = orchestrator.current_tick()
        current_day = orchestrator.current_day()

        return MetricsResponse(
            simulation_id=sim_id, tick=current_tick, day=current_day, metrics=metrics
        )

    except KeyError:
        raise HTTPException(status_code=404, detail=f"Simulation not found: {sim_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


# ============================================================================
# Health Check
# ============================================================================

# ============================================================================
# Diagnostic Endpoints (for Frontend)
# ============================================================================


@app.get("/simulations/{sim_id}", response_model=SimulationMetadataResponse)
def get_simulation_metadata(sim_id: str):
    """
    Get complete simulation metadata including config and summary statistics.

    This endpoint provides all information needed for the diagnostic frontend dashboard.
    """
    try:
        # Check if simulation exists in manager or database
        if sim_id in manager.simulations:
            # Active simulation - get from manager
            config = manager.configs[sim_id]["original"]
            orch = manager.simulations[sim_id]

            # Normalize config structure: extract from nested 'simulation' key if present
            if "simulation" in config:
                normalized_config = {
                    "ticks_per_day": config["simulation"].get("ticks_per_day"),
                    "num_days": config["simulation"].get("num_days"),
                    "rng_seed": config["simulation"].get("rng_seed"),
                    "agents": config.get("agents", []),
                }
                # Include LSM config if present
                if "lsm" in config:
                    normalized_config["lsm_config"] = config["lsm"]
            else:
                # Already flat structure
                normalized_config = config

            # Calculate summary from current state
            transactions = manager.list_transactions(sim_id)
            settled = sum(1 for tx in transactions if tx["status"] == "settled")
            total_tx = len(transactions)
            settlement_rate = settled / total_tx if total_tx > 0 else 0.0

            return SimulationMetadataResponse(
                simulation_id=sim_id,
                created_at=datetime.now().isoformat(),  # Approximate
                config=normalized_config,
                summary=SimulationSummary(
                    total_ticks=orch.current_tick(),
                    total_transactions=total_tx,
                    settlement_rate=settlement_rate,
                    total_cost_cents=0,  # Would need to calculate
                    duration_seconds=None,
                    ticks_per_second=None,
                ),
            )
        else:
            # Check database if available
            if not manager.db_manager:
                raise HTTPException(
                    status_code=404, detail=f"Simulation not found: {sim_id}"
                )

            conn = manager.db_manager.get_connection()

            # Query simulation metadata - use named columns instead of SELECT *
            sim_query = """
                SELECT
                    simulation_id,
                    config_file,
                    config_hash,
                    rng_seed,
                    ticks_per_day,
                    num_days,
                    num_agents,
                    config_json,
                    status,
                    started_at,
                    completed_at,
                    total_arrivals,
                    total_settlements,
                    total_cost_cents,
                    duration_seconds,
                    ticks_per_second
                FROM simulations
                WHERE simulation_id = ?
            """
            sim_result = conn.execute(sim_query, [sim_id]).fetchone()

            if not sim_result:
                raise HTTPException(
                    status_code=404, detail=f"Simulation not found: {sim_id}"
                )

            # Unpack result with named indices (including config_json)
            (
                sim_id_result,
                config_file,
                config_hash,
                rng_seed,
                ticks_per_day,
                num_days,
                num_agents,
                config_json_str,
                status,
                started_at,
                completed_at,
                total_arrivals,
                total_settlements,
                total_cost_cents,
                duration_seconds,
                ticks_per_second,
            ) = sim_result

            # Parse config_json if available
            import json

            if config_json_str:
                config_dict = json.loads(config_json_str)
            else:
                # Fallback: Build minimal config dict from available fields
                config_dict = {
                    "config_file": config_file,
                    "config_hash": config_hash,
                    "rng_seed": rng_seed,
                    "ticks_per_day": ticks_per_day,
                    "num_days": num_days,
                    "num_agents": num_agents,
                    "agents": [],
                }

            # Get transaction summary if total_arrivals not populated
            if total_arrivals is None or total_settlements is None:
                tx_summary_query = """
                    SELECT
                        COUNT(*) as total_transactions,
                        SUM(CASE WHEN status = 'settled' THEN 1 ELSE 0 END) as settled_count,
                        SUM(delay_cost) as total_delay_cost
                    FROM transactions
                    WHERE simulation_id = ?
                """
                tx_summary = conn.execute(tx_summary_query, [sim_id]).fetchone()
                total_arrivals = tx_summary[0] if tx_summary else 0
                total_settlements = tx_summary[1] if tx_summary and tx_summary[1] else 0
                if total_cost_cents is None:
                    total_cost_cents = (
                        tx_summary[2] if tx_summary and tx_summary[2] else 0
                    )

            # CRITICAL FIX: Recalculate settlement rate correctly
            # The pre-calculated values in the simulations table may have been
            # calculated with buggy code that counted split children as arrivals.
            # Instead, calculate from raw transaction data:
            # - Only count original transactions (parent_tx_id IS NULL) as arrivals
            # - Count transaction as settled if:
            #   1. It has no children AND is fully settled, OR
            #   2. It has children AND ALL children are fully settled

            recalc_query = """
                WITH parent_transactions AS (
                    -- Get all original (non-split) transactions
                    SELECT
                        tx_id,
                        status,
                        amount,
                        amount_settled,
                        parent_tx_id
                    FROM transactions
                    WHERE simulation_id = ? AND parent_tx_id IS NULL
                ),
                child_status AS (
                    -- For each parent, check if all children are fully settled
                    SELECT
                        parent_tx_id,
                        COUNT(*) as child_count,
                        SUM(CASE WHEN status = 'settled' AND amount_settled = amount THEN 1 ELSE 0 END) as settled_child_count
                    FROM transactions
                    WHERE simulation_id = ? AND parent_tx_id IS NOT NULL
                    GROUP BY parent_tx_id
                )
                SELECT
                    COUNT(DISTINCT pt.tx_id) as total_arrivals,
                    SUM(CASE
                        -- Transaction with no children: check if settled itself
                        WHEN cs.child_count IS NULL THEN
                            CASE WHEN pt.status = 'settled' AND pt.amount_settled = pt.amount THEN 1 ELSE 0 END
                        -- Transaction with children: check if ALL children settled
                        ELSE
                            CASE WHEN cs.settled_child_count = cs.child_count THEN 1 ELSE 0 END
                    END) as effective_settlements
                FROM parent_transactions pt
                LEFT JOIN child_status cs ON pt.tx_id = cs.parent_tx_id
            """

            recalc_result = conn.execute(recalc_query, [sim_id, sim_id]).fetchone()

            if recalc_result and recalc_result[0] > 0:
                # Use recalculated values
                total_arrivals = recalc_result[0]
                total_settlements = recalc_result[1] if recalc_result[1] else 0

            settlement_rate = (
                total_settlements / total_arrivals
                if total_arrivals and total_arrivals > 0
                else 0.0
            )

            # Calculate total ticks (ticks_per_day * num_days)
            total_ticks = ticks_per_day * num_days if ticks_per_day and num_days else 0

            return SimulationMetadataResponse(
                simulation_id=sim_id_result,
                created_at=(
                    started_at.isoformat() if started_at else datetime.now().isoformat()
                ),
                config=config_dict,
                summary=SimulationSummary(
                    total_ticks=total_ticks,
                    total_transactions=total_arrivals or 0,
                    settlement_rate=settlement_rate,
                    total_cost_cents=total_cost_cents or 0,
                    duration_seconds=duration_seconds,
                    ticks_per_second=ticks_per_second,
                ),
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


@app.get("/simulations/{sim_id}/agents", response_model=AgentListResponse)
def get_agent_list(sim_id: str):
    """
    Get list of all agents with summary statistics.

    For in-memory simulations: returns current state
    For database simulations: aggregates full metrics from daily_agent_metrics
    """
    try:
        # Check if simulation exists in memory
        if sim_id in manager.simulations:
            orch = manager.get_simulation(sim_id)
            config = manager.configs[sim_id]["original"]
            agent_list = config.get("agents") or config.get("agent_configs")

            agents = []
            for agent_id in orch.get_agent_ids():
                agent_config = next(
                    (a for a in agent_list if a["id"] == agent_id), None
                )
                credit_limit = (
                    agent_config.get("credit_limit", 0) if agent_config else 0
                )

                # For in-memory simulations, we can only provide current state
                # Full metrics require database persistence
                agents.append(
                    AgentSummary(
                        agent_id=agent_id,
                        total_sent=0,  # Would need to track this
                        total_received=0,  # Would need to track this
                        total_settled=0,  # Would need to track this
                        total_dropped=0,  # Would need to track this
                        total_cost_cents=0,  # Would need to track this
                        avg_balance_cents=orch.get_agent_balance(agent_id),
                        peak_overdraft_cents=0,  # Would need to track this
                        credit_limit_cents=credit_limit,
                    )
                )

            return AgentListResponse(agents=agents)

        # Not in memory, try database
        if not manager.db_manager:
            raise HTTPException(
                status_code=404, detail=f"Simulation not found: {sim_id}"
            )

        conn = manager.db_manager.get_connection()

        # Query from database
        query = """
            SELECT
                dam.agent_id,
                COALESCE(SUM(dam.num_sent), 0) as total_sent,
                COALESCE(SUM(dam.num_received), 0) as total_received,
                COALESCE(SUM(dam.num_settled), 0) as total_settled,
                COALESCE(SUM(dam.num_dropped), 0) as total_dropped,
                COALESCE(SUM(dam.total_cost), 0) as total_cost_cents,
                COALESCE(AVG(dam.closing_balance), 0) as avg_balance_cents,
                COALESCE(MIN(dam.min_balance), 0) as peak_overdraft_cents,
                0 as credit_limit_cents
            FROM daily_agent_metrics dam
            WHERE dam.simulation_id = ?
            GROUP BY dam.agent_id
            ORDER BY dam.agent_id
        """

        results = conn.execute(query, [sim_id]).fetchall()

        if not results:
            raise HTTPException(
                status_code=404, detail=f"Simulation not found: {sim_id}"
            )

        agents = [
            AgentSummary(
                agent_id=row[0],
                total_sent=int(row[1]),
                total_received=int(row[2]),
                total_settled=int(row[3]),
                total_dropped=int(row[4]),
                total_cost_cents=int(row[5]),
                avg_balance_cents=int(row[6]),
                peak_overdraft_cents=int(row[7]),
                credit_limit_cents=int(row[8]),
            )
            for row in results
        ]

        return AgentListResponse(agents=agents)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


@app.get("/simulations/{sim_id}/events", response_model=EventListResponse)
def get_events(
    sim_id: str,
    tick: Optional[int] = Query(None),
    tick_min: Optional[int] = Query(None),
    tick_max: Optional[int] = Query(None),
    agent_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """
    Get paginated list of events with optional filtering.

    For in-memory simulations: reconstructs events from transaction tracking
    For database simulations: queries full event history
    """
    try:
        # Check if simulation exists in memory
        if sim_id in manager.simulations:
            orch = manager.get_simulation(sim_id)
            txs = manager.transactions.get(sim_id, {})

            # Reconstruct events from tracked transactions
            events = []
            for tx_id, tx_data in txs.items():
                arrival_tick = tx_data.get("submitted_at_tick", 0)

                # Apply filters
                if tick is not None and arrival_tick != tick:
                    continue
                if tick_min is not None and arrival_tick < tick_min:
                    continue
                if tick_max is not None and arrival_tick > tick_max:
                    continue
                if (
                    agent_id
                    and tx_data["sender"] != agent_id
                    and tx_data["receiver"] != agent_id
                ):
                    continue

                events.append(
                    EventRecord(
                        tick=arrival_tick,
                        day=arrival_tick // 100,  # Assume 100 ticks per day
                        event_type="Arrival",
                        tx_id=tx_id,
                        sender_id=tx_data["sender"],
                        receiver_id=tx_data["receiver"],
                        amount=tx_data["amount"],
                        priority=tx_data["priority"],
                        deadline_tick=tx_data["deadline_tick"],
                        timestamp=None,
                    )
                )

            # Sort and paginate
            events.sort(key=lambda e: (e.tick, e.tx_id or ""))
            total = len(events)
            events = events[offset : offset + limit]

            return EventListResponse(
                events=events, total=total, limit=limit, offset=offset
            )

        # Not in memory, try database
        if not manager.db_manager:
            raise HTTPException(
                status_code=404, detail=f"Simulation not found: {sim_id}"
            )

        conn = manager.db_manager.get_connection()

        # Build base query - get events from transactions (arrivals and settlements)
        where_clauses = ["simulation_id = ?"]
        params = [sim_id]

        if tick is not None:
            where_clauses.append("arrival_tick = ?")
            params.append(tick)
        elif tick_min is not None or tick_max is not None:
            if tick_min is not None:
                where_clauses.append("arrival_tick >= ?")
                params.append(tick_min)
            if tick_max is not None:
                where_clauses.append("arrival_tick <= ?")
                params.append(tick_max)

        if agent_id:
            where_clauses.append("(sender_id = ? OR receiver_id = ?)")
            params.extend([agent_id, agent_id])

        where_sql = " AND ".join(where_clauses)

        # Get total count
        count_query = f"SELECT COUNT(*) FROM transactions WHERE {where_sql}"
        total = conn.execute(count_query, params).fetchone()[0]

        if total == 0:
            raise HTTPException(
                status_code=404, detail=f"Simulation not found: {sim_id}"
            )

        # Get paginated events
        events_query = f"""
            SELECT
                arrival_tick as tick,
                arrival_day as day,
                'Arrival' as event_type,
                tx_id,
                sender_id,
                receiver_id,
                amount,
                priority,
                deadline_tick
            FROM transactions
            WHERE {where_sql}
            ORDER BY arrival_tick, tx_id
            LIMIT ? OFFSET ?
        """

        params.extend([limit, offset])
        results = conn.execute(events_query, params).fetchall()

        events = [
            EventRecord(
                tick=int(row[0]),
                day=int(row[1]),
                event_type=str(row[2]),
                tx_id=str(row[3]) if row[3] else None,
                sender_id=str(row[4]) if row[4] else None,
                receiver_id=str(row[5]) if row[5] else None,
                amount=int(row[6]) if row[6] else None,
                priority=int(row[7]) if row[7] else None,
                deadline_tick=int(row[8]) if row[8] else None,
                timestamp=None,
            )
            for row in results
        ]

        return EventListResponse(events=events, total=total, limit=limit, offset=offset)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


@app.get(
    "/simulations/{sim_id}/agents/{agent_id}/timeline",
    response_model=AgentTimelineResponse,
)
def get_agent_timeline(sim_id: str, agent_id: str):
    """
    Get complete timeline for a specific agent including daily metrics and collateral events.

    For in-memory simulations: returns current state as single day metric
    For database simulations: returns full historical timeline
    """
    try:
        # Check if simulation exists in memory
        if sim_id in manager.simulations:
            orch = manager.get_simulation(sim_id)

            # Verify agent exists
            if agent_id not in orch.get_agent_ids():
                raise HTTPException(
                    status_code=404, detail=f"Agent {agent_id} not found"
                )

            # For in-memory simulations, provide current state as single metric
            current_balance = orch.get_agent_balance(agent_id)
            current_day = orch.current_day()

            daily_metrics = [
                DailyAgentMetric(
                    day=current_day,
                    opening_balance=current_balance,  # Approximation
                    closing_balance=current_balance,
                    min_balance=current_balance,  # Would need tracking
                    max_balance=current_balance,  # Would need tracking
                    transactions_sent=0,  # Would need tracking
                    transactions_received=0,  # Would need tracking
                    total_cost_cents=0,  # Would need tracking
                )
            ]

            return AgentTimelineResponse(
                agent_id=agent_id, daily_metrics=daily_metrics, collateral_events=[]
            )

        # Not in memory, try database
        if not manager.db_manager:
            raise HTTPException(
                status_code=404, detail=f"Simulation not found: {sim_id}"
            )

        conn = manager.db_manager.get_connection()

        # Get daily metrics
        metrics_query = """
            SELECT
                day,
                opening_balance,
                closing_balance,
                min_balance,
                max_balance,
                num_sent,
                num_received,
                total_cost
            FROM daily_agent_metrics
            WHERE simulation_id = ? AND agent_id = ?
            ORDER BY day
        """

        metrics_results = conn.execute(metrics_query, [sim_id, agent_id]).fetchall()

        if not metrics_results:
            raise HTTPException(
                status_code=404,
                detail=f"Agent {agent_id} not found in simulation {sim_id}",
            )

        daily_metrics = [
            DailyAgentMetric(
                day=int(row[0]),
                opening_balance=int(row[1]),
                closing_balance=int(row[2]),
                min_balance=int(row[3]),
                max_balance=int(row[4]),
                transactions_sent=int(row[5]),
                transactions_received=int(row[6]),
                total_cost_cents=int(row[7]),
            )
            for row in metrics_results
        ]

        # Get collateral events
        collateral_query = """
            SELECT
                tick,
                day,
                action,
                amount,
                reason,
                balance_before
            FROM collateral_events
            WHERE simulation_id = ? AND agent_id = ?
            ORDER BY tick
        """

        collateral_results = conn.execute(
            collateral_query, [sim_id, agent_id]
        ).fetchall()

        collateral_events = [
            CollateralEvent(
                tick=int(row[0]),
                day=int(row[1]),
                action=str(row[2]),
                amount=int(row[3]),
                reason=str(row[4]),
                balance_before=int(row[5]),
            )
            for row in collateral_results
        ]

        return AgentTimelineResponse(
            agent_id=agent_id,
            daily_metrics=daily_metrics,
            collateral_events=collateral_events,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


@app.get(
    "/simulations/{sim_id}/transactions/{tx_id}/lifecycle",
    response_model=TransactionLifecycleResponse,
)
def get_transaction_lifecycle(sim_id: str, tx_id: str):
    """
    Get complete lifecycle of a transaction including all events and related transactions.
    """
    try:
        if not manager.db_manager:
            # Fall back to manager if no database
            tx = manager.get_transaction(sim_id, tx_id)
            if not tx:
                raise HTTPException(
                    status_code=404, detail=f"Transaction {tx_id} not found"
                )

            # Minimal response from manager
            return TransactionLifecycleResponse(
                transaction=TransactionDetail(
                    tx_id=tx_id,
                    sender_id=tx["sender"],
                    receiver_id=tx["receiver"],
                    amount=tx["amount"],
                    priority=tx["priority"],
                    arrival_tick=tx.get("submitted_at_tick", 0),
                    deadline_tick=tx["deadline_tick"],
                    settlement_tick=None,
                    status=tx["status"],
                    delay_cost=0,
                    amount_settled=0,
                ),
                events=[
                    TransactionEvent(
                        tick=tx.get("submitted_at_tick", 0),
                        event_type="Arrival",
                        details={},
                    )
                ],
                related_transactions=[],
            )

        conn = manager.db_manager.get_connection()

        # Get transaction details
        tx_query = """
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
                COALESCE(amount_settled, amount) as amount_settled
            FROM transactions
            WHERE simulation_id = ? AND tx_id = ?
        """

        tx_result = conn.execute(tx_query, [sim_id, tx_id]).fetchone()

        if not tx_result:
            raise HTTPException(
                status_code=404, detail=f"Transaction {tx_id} not found"
            )

        transaction = TransactionDetail(
            tx_id=str(tx_result[0]),
            sender_id=str(tx_result[1]),
            receiver_id=str(tx_result[2]),
            amount=int(tx_result[3]),
            priority=int(tx_result[4]),
            arrival_tick=int(tx_result[5]),
            deadline_tick=int(tx_result[6]),
            settlement_tick=int(tx_result[7]) if tx_result[7] is not None else None,
            status=str(tx_result[8]),
            delay_cost=int(tx_result[9]) if tx_result[9] else 0,
            amount_settled=int(tx_result[10]) if tx_result[10] else 0,
        )

        # Build events from transaction lifecycle
        events = [
            TransactionEvent(
                tick=transaction.arrival_tick, event_type="Arrival", details={}
            )
        ]

        if transaction.settlement_tick is not None:
            events.append(
                TransactionEvent(
                    tick=transaction.settlement_tick,
                    event_type="Settlement",
                    details={"method": "rtgs"},
                )
            )

        # Get related transactions (splits)
        related_query = """
            SELECT tx_id, parent_tx_id, split_index
            FROM transactions
            WHERE simulation_id = ? AND (parent_tx_id = ? OR tx_id IN (
                SELECT parent_tx_id FROM transactions WHERE simulation_id = ? AND tx_id = ?
            ))
            AND tx_id != ?
        """

        related_results = conn.execute(
            related_query, [sim_id, tx_id, sim_id, tx_id, tx_id]
        ).fetchall()

        related_transactions = [
            RelatedTransaction(
                tx_id=str(row[0]),
                relationship="split_from" if row[1] == tx_id else "split_to",
                split_index=int(row[2]) if row[2] is not None else None,
            )
            for row in related_results
        ]

        return TransactionLifecycleResponse(
            transaction=transaction,
            events=events,
            related_transactions=related_transactions,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


# ============================================================================
# Health & Status
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
