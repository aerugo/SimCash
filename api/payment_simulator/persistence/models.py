"""
Pydantic Models for Persistence Layer

These models are the single source of truth for database schema.
All DDL generation is derived from these models.

Phase 8: Includes collateral management fields and CollateralEventRecord.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ============================================================================
# Enums
# ============================================================================


class TransactionStatus(str, Enum):
    """Transaction status enumeration."""

    PENDING = "pending"
    SETTLED = "settled"
    DROPPED = "dropped"


class SimulationStatus(str, Enum):
    """Simulation run status."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class CollateralActionType(str, Enum):
    """Collateral action types."""

    POST = "post"
    WITHDRAW = "withdraw"
    HOLD = "hold"


class PolicyCreatedBy(str, Enum):
    """Policy snapshot creation source."""

    INIT = "init"  # Initial policy at simulation start
    MANUAL = "manual"  # Manual policy change
    LLM = "llm"  # LLM-managed policy change


# ============================================================================
# Transaction Record
# ============================================================================


class TransactionRecord(BaseModel):
    """Transaction record for persistence.

    This model defines the schema for the transactions table.
    Changes to this model will trigger schema migration warnings.
    """

    model_config = ConfigDict(
        table_name="transactions",
        primary_key=["simulation_id", "tx_id"],
        indexes=[
            ("idx_tx_sim_sender", ["simulation_id", "sender_id"]),
            ("idx_tx_sim_day", ["simulation_id", "arrival_day"]),
            ("idx_tx_status", ["status"]),
        ],
    )

    # Identity
    simulation_id: str = Field(..., description="Foreign key to simulations table")
    tx_id: str = Field(..., description="Unique transaction identifier")

    # Participants
    sender_id: str = Field(..., description="Sender agent ID")
    receiver_id: str = Field(..., description="Receiver agent ID")

    # Transaction details
    amount: int = Field(..., description="Amount in cents", ge=0)
    priority: int = Field(..., description="Priority level", ge=0, le=10)
    is_divisible: bool = Field(..., description="Can be split")

    # Lifecycle timing
    arrival_tick: int = Field(..., description="Tick when arrived")
    arrival_day: int = Field(..., description="Day when arrived")
    deadline_tick: int = Field(..., description="Settlement deadline")
    settlement_tick: Optional[int] = Field(None, description="Tick when settled")
    settlement_day: Optional[int] = Field(None, description="Day when settled")

    # Status
    status: TransactionStatus = Field(..., description="Current status")
    drop_reason: Optional[str] = Field(None, description="Why dropped (if applicable)")

    # Settlement tracking
    amount_settled: int = Field(0, description="Amount settled in cents")

    # Metrics
    queue1_ticks: int = Field(0, description="Time spent in Queue 1")
    queue2_ticks: int = Field(0, description="Time spent in Queue 2")
    total_delay_ticks: int = Field(0, description="Total delay")

    # Costs
    delay_cost: int = Field(0, description="Queue 1 delay cost in cents")

    # Splitting
    parent_tx_id: Optional[str] = Field(None, description="Parent transaction if split")
    split_index: Optional[int] = Field(None, description="Split index (1, 2, ...)")


# ============================================================================
# Simulation Run Record
# ============================================================================


class SimulationRunRecord(BaseModel):
    """Simulation run metadata."""

    model_config = ConfigDict(
        table_name="simulation_runs",
        primary_key=["simulation_id"],
        indexes=[
            ("idx_sim_config_seed", ["config_hash", "rng_seed"]),
            ("idx_sim_started", ["start_time"]),
        ],
    )

    # Core identification
    simulation_id: str = Field(..., description="Unique simulation identifier")
    config_name: str = Field(..., description="Configuration file name")
    config_hash: str = Field(..., description="Configuration content hash")
    description: Optional[str] = Field(None, description="Simulation description")

    # Timing
    start_time: datetime = Field(..., description="When simulation started")
    end_time: Optional[datetime] = Field(None, description="When simulation ended")

    # Configuration
    ticks_per_day: int = Field(..., description="Ticks per simulated day")
    num_days: int = Field(..., description="Number of days to simulate")
    rng_seed: int = Field(..., description="RNG seed for determinism")

    # Results
    status: SimulationStatus = Field(..., description="Simulation status")
    total_transactions: int = Field(0, description="Total transactions processed")


# ============================================================================
# Daily Agent Metrics
# ============================================================================


class DailyAgentMetricsRecord(BaseModel):
    """Daily agent metrics for persistence."""

    model_config = ConfigDict(
        table_name="daily_agent_metrics",
        primary_key=["simulation_id", "agent_id", "day"],
        indexes=[
            ("idx_metrics_sim_day", ["simulation_id", "day"]),
        ],
    )

    simulation_id: str
    agent_id: str
    day: int

    # Balance metrics
    opening_balance: int
    closing_balance: int
    min_balance: int
    max_balance: int

    # Credit usage
    credit_limit: int
    peak_overdraft: int

    # Collateral management (Phase 8)
    opening_posted_collateral: int = 0
    closing_posted_collateral: int = 0
    peak_posted_collateral: int = 0
    collateral_capacity: int = 0  # 10x credit_limit
    num_collateral_posts: int = 0
    num_collateral_withdrawals: int = 0

    # Transaction counts
    num_arrivals: int = 0
    num_sent: int = 0
    num_received: int = 0
    num_settled: int = 0
    num_dropped: int = 0

    # Queue metrics
    queue1_peak_size: int = 0
    queue1_eod_size: int = 0

    # Costs
    liquidity_cost: int = 0
    delay_cost: int = 0
    collateral_cost: int = 0  # Phase 8: Opportunity cost of posted collateral
    split_friction_cost: int = 0
    deadline_penalty_cost: int = 0
    total_cost: int = 0


# ============================================================================
# Collateral Events (Phase 8)
# ============================================================================


class CollateralEventRecord(BaseModel):
    """Collateral management events.

    Tracks when agents post or withdraw collateral during simulation.
    Added in Phase 8 (two-layer collateral management).
    """

    model_config = ConfigDict(
        table_name="collateral_events",
        primary_key=["id"],
        indexes=[
            ("idx_collateral_sim_agent", ["simulation_id", "agent_id"]),
            ("idx_collateral_sim_day", ["simulation_id", "day"]),
            ("idx_collateral_action", ["action"]),
        ],
    )

    id: Optional[int] = None  # Auto-increment
    simulation_id: str
    agent_id: str
    tick: int
    day: int

    action: CollateralActionType
    amount: int  # Amount posted/withdrawn (cents), 0 for hold
    reason: str  # Decision reason from tree policy

    # Layer context
    layer: str  # 'strategic' or 'end_of_tick'

    # Agent state at time of action
    balance_before: int
    posted_collateral_before: int
    posted_collateral_after: int
    available_capacity_after: int


# ============================================================================
# Policy Snapshots (Phase 4)
# ============================================================================


class PolicySnapshotRecord(BaseModel):
    """Policy snapshot tracking for reproducibility.

    Tracks policy changes during simulation lifecycle for:
    - Initial policies at simulation start
    - Manual policy changes
    - LLM-managed policy optimization

    Added in Phase 4 (Policy Snapshot Tracking).
    """

    model_config = ConfigDict(
        table_name="policy_snapshots",
        primary_key=["simulation_id", "agent_id", "snapshot_day", "snapshot_tick"],
        indexes=[
            ("idx_policy_sim_agent", ["simulation_id", "agent_id"]),
            ("idx_policy_hash", ["policy_hash"]),
            ("idx_policy_created_by", ["created_by"]),
        ],
    )

    # Identity
    simulation_id: str = Field(..., description="Foreign key to simulations table")
    agent_id: str = Field(..., description="Agent whose policy changed")
    snapshot_day: int = Field(..., description="Day when policy changed")
    snapshot_tick: int = Field(..., description="Tick when policy changed")

    # Policy content
    policy_hash: str = Field(..., description="SHA256 hash of policy JSON", min_length=64, max_length=64)
    policy_file_path: str = Field(..., description="Path to policy JSON file")
    policy_json: str = Field(..., description="Full policy JSON for quick access")

    # Metadata
    created_by: PolicyCreatedBy = Field(..., description="Who/what created this policy")
