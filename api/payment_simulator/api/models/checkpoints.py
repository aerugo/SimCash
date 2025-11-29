"""Pydantic models for checkpoint endpoints."""

from typing import Any

from pydantic import BaseModel, Field


class CheckpointSaveRequest(BaseModel):
    """Request model for saving a checkpoint."""

    checkpoint_type: str = Field(
        ..., description="Type of checkpoint (manual/auto/eod/final)"
    )
    description: str | None = Field(None, description="Human-readable description")


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

    checkpoints: list[dict[str, Any]]
