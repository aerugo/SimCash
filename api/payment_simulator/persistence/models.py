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
    OVERDUE = "overdue"  # Phase 5: Transactions past deadline


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


class CheckpointType(str, Enum):
    """Checkpoint creation type."""

    MANUAL = "manual"  # Manual user-triggered checkpoint
    AUTO = "auto"  # Automatic periodic checkpoint
    EOD = "end_of_day"  # End-of-day checkpoint
    FINAL = "final"  # Final checkpoint at simulation end


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
    overdue_since_tick: Optional[int] = Field(
        None, description="Tick when became overdue (Phase 5)"
    )
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
# Simulation Metadata Record (Phase 5: Query Interface)
# ============================================================================


class SimulationRecord(BaseModel):
    """Simulation metadata for query interface.

    This table stores high-level metadata about each simulation run,
    optimized for query and comparison operations in Phase 5.
    """

    model_config = ConfigDict(
        table_name="simulations",
        primary_key=["simulation_id"],
        indexes=[
            ("idx_sim_status", ["status"]),
            ("idx_sim_started_at", ["started_at"]),
        ],
    )

    # Identity
    simulation_id: str = Field(..., description="Unique simulation identifier")
    config_file: str = Field(..., description="Configuration file name")
    config_hash: str = Field(..., description="SHA256 hash of configuration")
    rng_seed: int = Field(..., description="RNG seed for determinism")

    # Configuration
    ticks_per_day: int = Field(..., description="Ticks per day")
    num_days: int = Field(..., description="Number of simulated days")
    num_agents: int = Field(..., description="Number of agents")
    config_json: Optional[str] = Field(
        None, description="Complete configuration as JSON (for diagnostic frontend)"
    )

    # Status
    status: SimulationStatus = Field(..., description="Simulation status")
    started_at: Optional[datetime] = Field(None, description="When simulation started")
    completed_at: Optional[datetime] = Field(
        None, description="When simulation completed"
    )

    # Results (populated at end)
    total_arrivals: Optional[int] = Field(
        None, description="Total transactions arrived"
    )
    total_settlements: Optional[int] = Field(
        None, description="Total transactions settled"
    )
    total_cost_cents: Optional[int] = Field(None, description="Total cost in cents")
    duration_seconds: Optional[float] = Field(None, description="Wall-clock duration")
    ticks_per_second: Optional[float] = Field(None, description="Simulation speed")


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
# Agent Queue Snapshots (Phase 3: Queue Contents Persistence)
# ============================================================================


class AgentQueueSnapshotRecord(BaseModel):
    """Agent queue contents snapshot for perfect state reconstruction.

    Captures the exact contents of each agent's internal queue (Queue 1)
    at end-of-day, preserving queue order via position field.
    Added in Phase 3 (Queue Contents Persistence).
    """

    model_config = ConfigDict(
        table_name="agent_queue_snapshots",
        primary_key=["simulation_id", "agent_id", "day", "queue_type", "position"],
        indexes=[
            ("idx_queue_sim_agent_day", ["simulation_id", "agent_id", "day"]),
            ("idx_queue_sim_day", ["simulation_id", "day"]),
        ],
    )

    simulation_id: str = Field(..., description="Foreign key to simulations table")
    agent_id: str = Field(..., description="Agent identifier")
    day: int = Field(..., description="Day number", ge=0)
    queue_type: str = Field(..., description="Queue type (queue1)")
    position: int = Field(..., description="Position in queue (0-indexed)", ge=0)
    transaction_id: str = Field(..., description="Transaction ID at this position")


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
    policy_hash: str = Field(
        ...,
        description="SHA256 hash of policy JSON for deduplication",
        min_length=64,
        max_length=64,
    )
    policy_json: str = Field(..., description="Full policy JSON document")

    # Metadata
    created_by: PolicyCreatedBy = Field(..., description="Who/what created this policy")


# ============================================================================
# Simulation Checkpoints (Save/Load Feature)
# ============================================================================


class SimulationCheckpointRecord(BaseModel):
    """Simulation checkpoint for save/load functionality.

    Stores complete orchestrator state snapshots to enable:
    - Pausing and resuming simulations
    - Creating restore points during long runs
    - Debugging from specific simulation states
    - Rollback to previous states

    Each checkpoint contains:
    - Full simulation state (JSON snapshot from Rust)
    - Metadata (tick, day, timestamp)
    - Integrity hashes (state + config validation)
    - Human-readable description
    """

    model_config = ConfigDict(
        table_name="simulation_checkpoints",
        primary_key=["checkpoint_id"],
        indexes=[
            ("idx_cp_sim", ["simulation_id"]),
            ("idx_cp_timestamp", ["checkpoint_timestamp"]),
            ("idx_cp_type", ["checkpoint_type"]),
            ("idx_cp_tick", ["simulation_id", "checkpoint_tick"]),
        ],
    )

    # Identity
    checkpoint_id: str = Field(..., description="Unique checkpoint identifier (UUID)")
    simulation_id: str = Field(..., description="Foreign key to simulation_runs table")

    # Checkpoint position
    checkpoint_tick: int = Field(..., description="Tick when checkpoint was created")
    checkpoint_day: int = Field(..., description="Day when checkpoint was created")
    checkpoint_timestamp: datetime = Field(
        ..., description="Real-world timestamp of checkpoint creation"
    )

    # State snapshot
    state_json: str = Field(
        ..., description="Complete orchestrator state (from Rust save_state())"
    )
    state_hash: str = Field(
        ...,
        description="SHA256 hash of state_json for integrity validation",
        min_length=64,
        max_length=64,
    )
    config_json: str = Field(
        ..., description="Complete config used to create simulation (FFI dict as JSON)"
    )
    config_hash: str = Field(
        ...,
        description="SHA256 hash of config (from Rust snapshot)",
        min_length=64,
        max_length=64,
    )

    # Checkpoint metadata
    checkpoint_type: CheckpointType = Field(
        ..., description="Type of checkpoint (manual/auto/eod/final)"
    )
    description: Optional[str] = Field(
        None, description="Human-readable checkpoint description"
    )
    created_by: str = Field(..., description="User or system that created checkpoint")

    # Size tracking
    num_agents: int = Field(..., description="Number of agents in snapshot")
    num_transactions: int = Field(..., description="Number of transactions in snapshot")
    total_size_bytes: int = Field(..., description="Total checkpoint size in bytes")


# ============================================================================
# LSM Cycle Events (Phase 4)
# ============================================================================


class LsmCycleRecord(BaseModel):
    """LSM cycle event for analyzing liquidity-saving mechanisms.

    Tracks every LSM cycle settled (bilateral offsets and multilateral cycles)
    with full details about the cycle pattern and values.

    Added in Phase 4 (LSM Cycle Persistence).
    """

    model_config = ConfigDict(
        table_name="lsm_cycles",
        primary_key=["id"],
        indexes=[
            ("idx_lsm_sim_day", ["simulation_id", "day"]),
            ("idx_lsm_cycle_type", ["cycle_type"]),
        ],
    )

    id: Optional[int] = Field(None, description="Auto-increment primary key")
    simulation_id: str = Field(..., description="Foreign key to simulations table")
    tick: int = Field(..., description="Tick when cycle was settled", ge=0)
    day: int = Field(..., description="Day when cycle was settled", ge=0)

    cycle_type: str = Field(
        ..., description="Type of cycle: 'bilateral' or 'multilateral'"
    )
    cycle_length: int = Field(
        ...,
        description="Number of agents in cycle (2 for bilateral, 3+ for multilateral)",
        ge=2,
    )

    agents: str = Field(..., description="JSON array of agent IDs in cycle")
    transactions: str = Field(..., description="JSON array of transaction IDs in cycle")

    settled_value: int = Field(..., description="Net value settled (cents)")
    total_value: int = Field(..., description="Gross value before netting (cents)")


# ============================================================================
# Full Replay Tables (Per-Tick Data)
# ============================================================================


class PolicyDecisionRecord(BaseModel):
    """Policy decision event for full replay.

    Captures every policy decision (submit/hold/drop/split) made during
    simulation. Enables perfect replay of agent behavior.
    Added for --full-replay mode.
    """

    model_config = ConfigDict(
        table_name="policy_decisions",
        primary_key=["id"],
        indexes=[
            ("idx_policy_sim_tick", ["simulation_id", "tick"]),
            ("idx_policy_sim_agent", ["simulation_id", "agent_id"]),
        ],
    )

    id: Optional[int] = Field(None, description="Auto-increment primary key")
    simulation_id: str = Field(..., description="Foreign key to simulations table")
    agent_id: str = Field(..., description="Agent who made the decision")
    tick: int = Field(..., description="Tick when decision was made", ge=0)
    day: int = Field(..., description="Day when decision was made", ge=0)

    decision_type: str = Field(
        ..., description="Decision type: submit, hold, drop, split"
    )
    tx_id: str = Field(..., description="Transaction ID")
    reason: Optional[str] = Field(None, description="Reason for hold/drop decisions")
    num_splits: Optional[int] = Field(
        None, description="Number of splits (for split decisions)"
    )
    child_tx_ids: Optional[str] = Field(
        None, description="JSON array of child TX IDs (for split decisions)"
    )


class TickAgentStateRecord(BaseModel):
    """Agent state snapshot for a specific tick (full replay).

    Captures agent balance, costs, and collateral after each tick.
    Enables tick-by-tick replay of agent state evolution.
    Added for --full-replay mode.
    """

    model_config = ConfigDict(
        table_name="tick_agent_states",
        primary_key=["simulation_id", "agent_id", "tick"],
        indexes=[
            ("idx_tick_states_sim_tick", ["simulation_id", "tick"]),
        ],
    )

    simulation_id: str = Field(..., description="Foreign key to simulations table")
    agent_id: str = Field(..., description="Agent identifier")
    tick: int = Field(..., description="Tick number", ge=0)
    day: int = Field(..., description="Day number", ge=0)

    # Balance tracking
    balance: int = Field(..., description="Balance at end of tick (cents)")
    balance_change: int = Field(..., description="Change in balance this tick (cents)")
    credit_limit: int = Field(..., description="Agent credit limit (cents)", ge=0)
    posted_collateral: int = Field(
        ..., description="Posted collateral at end of tick (cents)"
    )

    # Cumulative costs (running totals)
    liquidity_cost: int = Field(..., description="Cumulative liquidity cost (cents)")
    delay_cost: int = Field(..., description="Cumulative delay cost (cents)")
    collateral_cost: int = Field(
        ..., description="Cumulative collateral opportunity cost (cents)"
    )
    penalty_cost: int = Field(..., description="Cumulative deadline penalty (cents)")
    split_friction_cost: int = Field(
        ..., description="Cumulative split friction cost (cents)"
    )

    # Per-tick cost deltas (incremental changes)
    liquidity_cost_delta: int = Field(
        ..., description="Liquidity cost accrued this tick (cents)"
    )
    delay_cost_delta: int = Field(
        ..., description="Delay cost accrued this tick (cents)"
    )
    collateral_cost_delta: int = Field(
        ..., description="Collateral cost accrued this tick (cents)"
    )
    penalty_cost_delta: int = Field(
        ..., description="Penalty accrued this tick (cents)"
    )
    split_friction_cost_delta: int = Field(
        ..., description="Split friction accrued this tick (cents)"
    )


class TickQueueSnapshotRecord(BaseModel):
    """Queue contents snapshot for a specific tick (full replay).

    Captures exact queue state (Queue 1 and RTGS) after each tick.
    Preserves queue order via position field.
    Added for --full-replay mode.
    """

    model_config = ConfigDict(
        table_name="tick_queue_snapshots",
        primary_key=["simulation_id", "agent_id", "tick", "queue_type", "position"],
        indexes=[
            ("idx_tick_queue_sim_tick", ["simulation_id", "tick"]),
            ("idx_tick_queue_sim_agent", ["simulation_id", "agent_id", "tick"]),
        ],
    )

    simulation_id: str = Field(..., description="Foreign key to simulations table")
    agent_id: str = Field(..., description="Agent identifier")
    tick: int = Field(..., description="Tick number", ge=0)
    queue_type: str = Field(..., description="Queue type: queue1 or rtgs")
    position: int = Field(..., description="Position in queue (0-indexed)", ge=0)
    tx_id: str = Field(..., description="Transaction ID at this position")


# ============================================================================
# Simulation Event Record (Phase 2: Event Timeline Enhancement)
# ============================================================================


class SimulationEventRecord(BaseModel):
    """Comprehensive event record for simulation timeline.

    This model defines the schema for the simulation_events table.
    Stores all events that occur during simulation execution for complete
    event timeline functionality.

    Per docs/plans/event-timeline-enhancement.md Phase 2:
    - Captures all event types (arrival, policy, settlement, LSM, collateral, etc.)
    - Supports filtering by tick, day, agent_id, tx_id, event_type
    - Event details stored as JSON for flexibility
    """

    model_config = ConfigDict(
        table_name="simulation_events",
        primary_key=["event_id"],
        indexes=[
            ("idx_sim_events_sim_tick", ["simulation_id", "tick"]),
            ("idx_sim_events_sim_agent", ["simulation_id", "agent_id"]),
            ("idx_sim_events_sim_tx", ["simulation_id", "tx_id"]),
            ("idx_sim_events_sim_type", ["simulation_id", "event_type"]),
            ("idx_sim_events_sim_day", ["simulation_id", "day"]),
            ("idx_sim_events_composite", ["simulation_id", "tick", "event_type"]),
        ],
    )

    # Core identifiers
    event_id: str = Field(..., description="Unique event identifier (UUID)")
    simulation_id: str = Field(..., description="Foreign key to simulations table")

    # Temporal information
    tick: int = Field(..., description="Tick when event occurred", ge=0)
    day: int = Field(..., description="Day when event occurred", ge=0)
    event_timestamp: datetime = Field(
        ..., description="Timestamp when event was created"
    )

    # Event classification
    event_type: str = Field(
        ...,
        description="Event type (e.g., Arrival, PolicySubmit, Settlement, etc.)",
    )

    # Event details (JSON)
    details: str = Field(
        ..., description="JSON-encoded event-specific details"
    )

    # Optional filters for efficient querying
    agent_id: Optional[str] = Field(
        None, description="Agent ID if event relates to specific agent"
    )
    tx_id: Optional[str] = Field(
        None, description="Transaction ID if event relates to specific transaction"
    )

    # Metadata
    created_at: datetime = Field(..., description="When record was created")
