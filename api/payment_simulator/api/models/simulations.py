"""Pydantic models for simulation endpoints."""

from typing import Any

from pydantic import BaseModel


class TickResponse(BaseModel):
    """Response model for single tick execution."""

    tick: int
    num_arrivals: int
    num_settlements: int
    num_lsm_releases: int
    total_cost: int


class MultiTickResponse(BaseModel):
    """Response model for multiple tick execution."""

    results: list[TickResponse]
    final_tick: int


class SimulationCreateResponse(BaseModel):
    """Response model for simulation creation."""

    simulation_id: str
    state: dict[str, Any]
    message: str = "Simulation created successfully"


class SimulationListResponse(BaseModel):
    """Response model for listing simulations."""

    simulations: list[dict[str, Any]]
