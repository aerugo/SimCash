"""Pydantic models for diagnostic endpoints."""

from typing import Any

from pydantic import BaseModel, Field

from .costs import AgentCostBreakdown


class SimulationSummary(BaseModel):
    """Summary statistics for a simulation."""

    total_ticks: int
    total_transactions: int
    settlement_rate: float
    total_cost_cents: int
    duration_seconds: float | None = None
    ticks_per_second: float | None = None


class SimulationMetadataResponse(BaseModel):
    """Response model for GET /simulations/{id} diagnostic endpoint."""

    simulation_id: str
    created_at: str
    config: dict[str, Any]
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
    unsecured_cap_cents: int


class AgentListResponse(BaseModel):
    """Response model for GET /simulations/{id}/agents endpoint."""

    agents: list[AgentSummary]


class EventRecord(BaseModel):
    """Single event in the timeline.

    Updated for comprehensive event persistence (Phase 2).
    Per docs/plans/event-timeline-enhancement.md
    """

    event_id: str
    simulation_id: str
    tick: int
    day: int
    event_type: str
    event_timestamp: str
    details: dict[str, Any]
    agent_id: str | None = None
    tx_id: str | None = None
    created_at: str

    # Flattened fields from details for API ergonomics
    # These are populated by event_queries.py for common event types
    sender_id: str | None = None
    receiver_id: str | None = None
    amount: int | None = None
    deadline: int | None = None
    priority: int | None = None


class EventListResponse(BaseModel):
    """Response model for paginated events."""

    events: list[EventRecord]
    total: int
    limit: int
    offset: int
    filters: dict[str, Any | None] | None = None


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
    daily_metrics: list[DailyAgentMetric]
    collateral_events: list[CollateralEvent]


class TransactionEvent(BaseModel):
    """Event in a transaction lifecycle."""

    tick: int
    event_type: str
    details: dict[str, Any]


class RelatedTransaction(BaseModel):
    """Related transaction reference."""

    tx_id: str
    relationship: str
    split_index: int | None = None


class TransactionDetail(BaseModel):
    """Full transaction details."""

    tx_id: str
    sender_id: str
    receiver_id: str
    amount: int
    priority: int
    arrival_tick: int
    deadline_tick: int
    settlement_tick: int | None
    status: str
    delay_cost: int
    amount_settled: int


class TransactionLifecycleResponse(BaseModel):
    """Response model for transaction lifecycle."""

    transaction: TransactionDetail
    events: list[TransactionEvent]
    related_transactions: list[RelatedTransaction]


class QueueTransaction(BaseModel):
    """Transaction in a queue."""

    tx_id: str
    receiver_id: str
    amount: int
    priority: int
    deadline_tick: int


class QueueContents(BaseModel):
    """Contents of a queue."""

    size: int
    transactions: list[QueueTransaction]
    total_value: int


class AgentQueuesResponse(BaseModel):
    """Response model for GET /simulations/{id}/agents/{agentId}/queues."""

    agent_id: str
    simulation_id: str
    tick: int
    day: int
    queue1: QueueContents
    queue2_filtered: QueueContents


class NearDeadlineTransaction(BaseModel):
    """Transaction approaching deadline."""

    tx_id: str
    sender_id: str
    receiver_id: str
    amount: int
    remaining_amount: int
    deadline_tick: int
    ticks_until_deadline: int


class NearDeadlineTransactionsResponse(BaseModel):
    """Response model for GET /simulations/{id}/transactions/near-deadline."""

    simulation_id: str
    current_tick: int
    within_ticks: int
    threshold_tick: int
    transactions: list[NearDeadlineTransaction]
    count: int


class OverdueTransaction(BaseModel):
    """Overdue transaction with cost information."""

    tx_id: str
    sender_id: str
    receiver_id: str
    amount: int
    remaining_amount: int
    deadline_tick: int
    overdue_since_tick: int
    ticks_overdue: int
    estimated_delay_cost: int
    deadline_penalty_cost: int
    total_overdue_cost: int


class OverdueTransactionsResponse(BaseModel):
    """Response model for GET /simulations/{id}/transactions/overdue."""

    simulation_id: str
    current_tick: int
    transactions: list[OverdueTransaction]
    count: int
    total_overdue_cost: int


class AgentStateSnapshot(BaseModel):
    """Agent state at a specific tick."""

    balance: int
    unsecured_cap: int
    liquidity: int
    headroom: int
    queue1_size: int
    queue2_size: int
    costs: AgentCostBreakdown


class SystemStateSnapshot(BaseModel):
    """System-wide state at a specific tick."""

    total_arrivals: int
    total_settlements: int
    settlement_rate: float
    queue1_total_size: int
    queue2_total_size: int
    total_system_cost: int


class TickStateResponse(BaseModel):
    """Response model for GET /simulations/{id}/ticks/{tick}/state."""

    simulation_id: str
    tick: int
    day: int
    agents: dict[str, AgentStateSnapshot]
    system: SystemStateSnapshot
