"""Database models for AI Cash Management persistence.

Pydantic models defining the schema for game sessions and policy iterations.
These models integrate with the main SimCash database.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class GameStatus(str, Enum):
    """Game session status."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CONVERGED = "converged"


class GameSessionRecord(BaseModel):
    """Game session metadata for persistence.

    This model defines the schema for the game_sessions table.
    Stores metadata about each AI Cash Management game run.
    """

    model_config = ConfigDict(  # type: ignore[typeddict-unknown-key]
        table_name="game_sessions",
        primary_key=["game_id"],
        indexes=[
            ("idx_game_status", ["status"]),
            ("idx_game_started_at", ["started_at"]),
            ("idx_game_mode", ["game_mode"]),
        ],
    )

    # Identity
    game_id: str = Field(..., description="Unique game identifier")

    # Configuration
    scenario_config: str = Field(..., description="Path to scenario configuration")
    master_seed: int = Field(..., description="Master seed for determinism")
    game_mode: str = Field(..., description="Game mode (rl_optimization, campaign_learning)")
    config_json: str = Field(..., description="Full configuration as JSON")

    # Lifecycle
    started_at: datetime = Field(..., description="When game started")
    completed_at: datetime | None = Field(None, description="When game completed")
    status: str = Field(..., description="Current status")

    # Agents
    optimized_agents: list[str] = Field(..., description="List of agent IDs being optimized")

    # Results (populated on completion)
    total_iterations: int = Field(0, description="Total optimization iterations")
    converged: bool = Field(False, description="Whether game reached convergence")
    final_cost: float | None = Field(None, description="Final aggregate cost")


class PolicyIterationRecord(BaseModel):
    """Policy iteration record for tracking optimization history.

    This model defines the schema for the policy_iterations table.
    Stores each policy optimization iteration with metrics and diffs.
    """

    model_config = ConfigDict(  # type: ignore[typeddict-unknown-key]
        table_name="policy_iterations",
        primary_key=["game_id", "agent_id", "iteration_number"],
        indexes=[
            ("idx_iter_game", ["game_id"]),
            ("idx_iter_agent", ["game_id", "agent_id"]),
            ("idx_iter_accepted", ["was_accepted"]),
        ],
    )

    # Identity
    game_id: str = Field(..., description="Foreign key to game_sessions")
    agent_id: str = Field(..., description="Agent being optimized")
    iteration_number: int = Field(..., description="Iteration number (1-indexed)")

    # Trigger context
    trigger_tick: int = Field(..., description="Tick that triggered optimization")

    # Policies
    old_policy_json: str = Field(..., description="Previous policy as JSON")
    new_policy_json: str = Field(..., description="New/proposed policy as JSON")

    # Costs
    old_cost: float = Field(..., description="Cost of old policy")
    new_cost: float = Field(..., description="Cost of new policy")
    cost_improvement: float = Field(..., description="Cost reduction (old - new)")

    # Decision
    was_accepted: bool = Field(..., description="Whether new policy was accepted")
    validation_errors: list[str] = Field(
        default_factory=list,
        description="Validation errors if rejected",
    )

    # LLM metadata
    llm_model: str = Field(..., description="LLM model used (provider/model)")
    llm_latency_seconds: float = Field(..., description="LLM call latency")
    tokens_used: int = Field(..., description="Total tokens used")

    # Timestamp
    created_at: datetime = Field(..., description="When iteration was created")
