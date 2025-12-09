"""Game configuration models for ai_cash_mgmt.

Defines the complete configuration for an AI cash management game session,
including optimization schedules, Monte Carlo settings, convergence criteria,
and policy constraints.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator

from payment_simulator.ai_cash_mgmt.config.llm_config import (
    AgentOptimizationConfig,
    LLMConfig,
)


class OptimizationScheduleType(str, Enum):
    """When optimization occurs during simulation."""

    EVERY_X_TICKS = "every_x_ticks"
    AFTER_EOD = "after_eod"
    ON_SIMULATION_END = "on_simulation_end"


class SampleMethod(str, Enum):
    """Monte Carlo sampling methods."""

    BOOTSTRAP = "bootstrap"
    PERMUTATION = "permutation"
    STRATIFIED = "stratified"


class OptimizationSchedule(BaseModel):
    """Configuration for when optimization occurs.

    Example:
        >>> # Optimize every 100 ticks
        >>> schedule = OptimizationSchedule(
        ...     type=OptimizationScheduleType.EVERY_X_TICKS,
        ...     interval_ticks=100,
        ... )

        >>> # Optimize after each day
        >>> schedule = OptimizationSchedule(
        ...     type=OptimizationScheduleType.AFTER_EOD,
        ...     min_remaining_days=2,
        ... )
    """

    type: OptimizationScheduleType = Field(
        ...,
        description="Schedule type",
    )
    interval_ticks: int | None = Field(
        default=None,
        ge=1,
        description="Interval for every_x_ticks schedule",
    )
    min_remaining_days: int | None = Field(
        default=None,
        ge=1,
        description="Minimum remaining days for after_eod schedule",
    )
    min_remaining_repetitions: int | None = Field(
        default=None,
        ge=1,
        description="Minimum remaining repetitions for on_simulation_end schedule",
    )

    model_config = {"use_enum_values": True}

    @model_validator(mode="after")
    def validate_schedule_params(self) -> OptimizationSchedule:
        """Validate schedule-specific parameters are provided."""
        if self.type == OptimizationScheduleType.EVERY_X_TICKS:
            if self.interval_ticks is None:
                raise ValueError("interval_ticks required for every_x_ticks schedule")
        elif self.type == OptimizationScheduleType.AFTER_EOD:
            if self.min_remaining_days is None:
                object.__setattr__(self, "min_remaining_days", 1)
        elif self.type == OptimizationScheduleType.ON_SIMULATION_END:
            if self.min_remaining_repetitions is None:
                object.__setattr__(self, "min_remaining_repetitions", 1)
        return self


class MonteCarloConfig(BaseModel):
    """Monte Carlo evaluation configuration.

    Example:
        >>> config = MonteCarloConfig(
        ...     num_samples=30,
        ...     sample_method="bootstrap",
        ...     evaluation_ticks=200,
        ... )

        >>> # Deterministic mode (single evaluation, no sampling)
        >>> config = MonteCarloConfig(deterministic=True)
    """

    deterministic: bool = Field(
        default=False,
        description="Skip Monte Carlo sampling; run single deterministic evaluation",
    )
    num_samples: int = Field(
        default=20,
        ge=1,
        le=1000,
        description="Number of resampled scenarios",
    )
    sample_method: SampleMethod | str = Field(
        default=SampleMethod.BOOTSTRAP,
        description="Sampling method",
    )
    evaluation_ticks: int = Field(
        default=100,
        ge=1,
        description="Ticks to simulate per sample (minimum 10 unless deterministic)",
    )
    parallel_workers: int = Field(
        default=8,
        ge=1,
        le=64,
        description="Parallel simulation workers",
    )

    model_config = {"use_enum_values": True}

    @model_validator(mode="after")
    def validate_deterministic_samples(self) -> MonteCarloConfig:
        """Validate and enforce sample constraints based on deterministic mode."""
        if self.deterministic:
            # Force num_samples to 1 in deterministic mode
            object.__setattr__(self, "num_samples", 1)
            # No minimum evaluation_ticks in deterministic mode
        else:
            if self.num_samples < 5:
                msg = "num_samples must be >= 5 when not in deterministic mode"
                raise ValueError(msg)
            if self.evaluation_ticks < 10:
                msg = "evaluation_ticks must be >= 10 when not in deterministic mode"
                raise ValueError(msg)
        return self


class ConvergenceCriteria(BaseModel):
    """Convergence detection configuration.

    Example:
        >>> config = ConvergenceCriteria(
        ...     metric="total_cost",
        ...     stability_threshold=0.03,
        ...     stability_window=5,
        ...     max_iterations=100,
        ... )
    """

    metric: str = Field(
        default="total_cost",
        description="Metric to track for convergence",
    )
    stability_threshold: float = Field(
        default=0.05,
        ge=0.001,
        le=0.5,
        description="Relative change threshold for stability",
    )
    stability_window: int = Field(
        default=5,
        ge=2,
        le=20,
        description="Consecutive stable iterations required",
    )
    max_iterations: int = Field(
        default=50,
        ge=5,
        le=500,
        description="Hard cap on optimization iterations",
    )
    improvement_threshold: float = Field(
        default=0.01,
        ge=0.0,
        le=0.5,
        description="Minimum relative improvement to accept new policy",
    )


class PolicyConstraints(BaseModel):
    """Policy generation constraints.

    Defines what parameters, fields, and actions are allowed in
    generated policies. If None, derived from scenario config.

    Example:
        >>> constraints = PolicyConstraints(
        ...     allowed_parameters=[
        ...         {"name": "amount_threshold", "type": "int", "min": 0}
        ...     ],
        ...     allowed_fields=["amount", "priority"],
        ...     allowed_actions=["submit", "queue"],
        ... )
    """

    allowed_parameters: list[dict[str, Any]] | None = Field(
        default=None,
        description="Allowed parameters (ParameterSpec dicts)",
    )
    allowed_fields: list[str] | None = Field(
        default=None,
        description="Allowed context fields",
    )
    allowed_actions: list[str] | None = Field(
        default=None,
        description="Allowed payment tree actions",
    )
    allowed_bank_actions: list[str] | None = Field(
        default=None,
        description="Allowed bank tree actions",
    )
    allowed_collateral_actions: list[str] | None = Field(
        default=None,
        description="Allowed collateral tree actions",
    )


class OutputConfig(BaseModel):
    """Output and persistence configuration.

    Example:
        >>> config = OutputConfig(
        ...     database_path="results/my_game.db",
        ...     verbose=True,
        ... )
    """

    database_path: str = Field(
        default="results/game_sessions.db",
        description="Path to database file",
    )
    save_policy_diffs: bool = Field(
        default=True,
        description="Save policy diffs between iterations",
    )
    save_iteration_metrics: bool = Field(
        default=True,
        description="Save detailed iteration metrics",
    )
    verbose: bool = Field(
        default=True,
        description="Enable verbose output",
    )


class GameConfig(BaseModel):
    """Complete game configuration.

    The game config references a scenario config which already contains:
    - Agent definitions (IDs, opening balances, credit limits)
    - Cost rate configurations
    - Arrival configurations
    - Seed policies for all agents

    This avoids redundancy - seed policies are defined in ONE place (scenario config).

    Example:
        >>> config = GameConfig(
        ...     game_id="experiment-001",
        ...     scenario_config="scenarios/3bank.yaml",
        ...     master_seed=42,
        ...     optimized_agents={
        ...         "BANK_A": AgentOptimizationConfig(
        ...             llm_config=LLMConfig(provider="anthropic")
        ...         ),
        ...         "BANK_B": AgentOptimizationConfig(),  # Uses default
        ...     },
        ...     optimization_schedule=OptimizationSchedule(
        ...         type=OptimizationScheduleType.AFTER_EOD,
        ...     ),
        ... )
    """

    # Metadata
    game_id: str = Field(
        ...,
        min_length=1,
        description="Unique game identifier",
    )
    description: str | None = Field(
        default=None,
        description="Human-readable description",
    )

    # Scenario reference (contains agents AND their seed policies)
    scenario_config: str = Field(
        ...,
        description="Path to scenario configuration file (includes seed policies)",
    )

    # Master seed
    master_seed: int = Field(
        ...,
        ge=0,
        description="Master seed for determinism",
    )

    # Per-agent optimization config (only listed agents are optimized)
    optimized_agents: dict[str, AgentOptimizationConfig] = Field(
        ...,
        min_length=1,
        description="Agent ID to optimization config mapping. Only these agents are optimized.",
    )

    # Default LLM config (used when agent doesn't specify llm_config)
    default_llm_config: LLMConfig = Field(
        default_factory=LLMConfig,
        description="Default LLM configuration for agents without explicit config",
    )

    # Components
    optimization_schedule: OptimizationSchedule = Field(
        ...,
        description="When to run optimization",
    )
    monte_carlo: MonteCarloConfig = Field(
        default_factory=MonteCarloConfig,
        description="Monte Carlo evaluation settings",
    )
    convergence: ConvergenceCriteria = Field(
        default_factory=ConvergenceCriteria,
        description="Convergence detection settings",
    )
    policy_constraints: PolicyConstraints | None = Field(
        default=None,
        description="Policy generation constraints (derived from scenario if null)",
    )
    output: OutputConfig = Field(
        default_factory=OutputConfig,
        description="Output configuration",
    )

    def get_llm_config_for_agent(self, agent_id: str) -> LLMConfig:
        """Get the LLM config for a specific agent.

        Returns agent's specific config if defined, otherwise default.

        Args:
            agent_id: The agent ID to get config for.

        Returns:
            LLMConfig for the agent.
        """
        agent_config = self.optimized_agents.get(agent_id)
        if agent_config and agent_config.llm_config:
            return agent_config.llm_config
        return self.default_llm_config

    def get_optimized_agent_ids(self) -> list[str]:
        """Get list of agent IDs that will be optimized.

        Returns:
            List of agent IDs.
        """
        return list(self.optimized_agents.keys())

    @classmethod
    def from_yaml(cls, path: str | Path) -> GameConfig:
        """Load configuration from YAML file.

        Args:
            path: Path to YAML configuration file.

        Returns:
            Parsed GameConfig instance.
        """
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)
