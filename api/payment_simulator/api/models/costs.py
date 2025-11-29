"""Pydantic models for cost and metrics endpoints."""

from pydantic import BaseModel, Field


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
    agents: dict[str, AgentCostBreakdown] = Field(
        ..., description="Per-agent cost breakdowns"
    )
    total_system_cost: int = Field(
        ..., description="Total cost across all agents in cents"
    )


class TickCostDataPoint(BaseModel):
    """Cost data for a single tick."""

    tick: int
    agent_costs: dict[str, int]  # agent_id -> accumulated cost in cents


class CostTimelineResponse(BaseModel):
    """Response model for GET /simulations/{id}/costs/timeline endpoint."""

    simulation_id: str
    agent_ids: list[str]
    tick_costs: list[TickCostDataPoint]
    ticks_per_day: int


class SystemMetrics(BaseModel):
    """System-wide performance metrics."""

    total_arrivals: int = Field(..., description="Total transactions arrived")
    total_settlements: int = Field(..., description="Total transactions settled")
    settlement_rate: float = Field(
        ..., ge=0.0, le=1.0, description="Settlement rate (0.0-1.0)"
    )
    avg_delay_ticks: float = Field(
        ..., description="Average settlement delay in ticks"
    )
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
