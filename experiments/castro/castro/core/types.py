"""Core type definitions for castro experiments.

This module provides TypedDicts and dataclasses that define the shape of
all data structures used in the experiment framework. Using TypedDicts
ensures type safety at dict boundaries (database, JSON serialization).

All monetary values are in integer cents (i64 equivalent in Python).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TypedDict


# ============================================================================
# Cost Breakdown Types
# ============================================================================


class CostBreakdown(TypedDict):
    """Breakdown of simulation costs by category.

    All values are in integer cents.
    """

    collateral: int
    delay: int
    overdraft: int
    eod_penalty: int


class CostRates(TypedDict, total=False):
    """Cost rate configuration from scenario YAML.

    Uses total=False since some rates may be optional.
    """

    collateral_cost_per_tick_bps: int
    overdraft_cost_per_tick_bps: int
    delay_penalty_per_tick: int
    eod_penalty: int


# ============================================================================
# Simulation Types
# ============================================================================


class RawSimulationOutput(TypedDict, total=False):
    """Raw JSON output from payment-sim run command.

    Uses total=False since fields may vary by simulation config.
    """

    costs: dict[str, int]
    agents: list[dict[str, str | int]]
    metrics: dict[str, int | float]


class SimulationResult(TypedDict, total=False):
    """Result from a single simulation run.

    Returned by run_single_simulation(). Contains both parsed metrics
    and raw output for full reproducibility.

    All cost values are in integer cents.
    """

    seed: int
    total_cost: int
    bank_a_cost: int
    bank_b_cost: int
    settlement_rate: float
    bank_a_balance_end: int
    bank_b_balance_end: int
    cost_breakdown: CostBreakdown
    raw_output: RawSimulationOutput
    verbose_log: str | None
    # For filtered replay support
    db_path: str
    simulation_id: str
    # Error case
    error: str


# ============================================================================
# Database Record Types
# ============================================================================


class ExperimentConfigRecord(TypedDict):
    """Record from experiment_config table.

    Stores full experiment configuration for reproducibility.
    """

    experiment_id: str
    experiment_name: str
    created_at: datetime
    config_yaml: str
    config_hash: str
    cost_rates: str  # JSON string
    agent_configs: str  # JSON string
    model_name: str
    reasoning_effort: str
    num_seeds: int
    max_iterations: int
    convergence_threshold: float
    convergence_window: int
    master_seed: int
    seed_matrix: str  # JSON string
    notes: str | None


class PolicyIterationRecord(TypedDict):
    """Record from policy_iterations table.

    Every policy version is stored for full audit trail.
    """

    iteration_id: str
    experiment_id: str
    iteration_number: int
    agent_id: str
    policy_json: str
    policy_hash: str
    parameters: str  # JSON string
    created_at: datetime
    created_by: str  # 'init', 'llm', 'manual'
    was_accepted: bool
    is_best: bool


class LlmInteractionRecord(TypedDict):
    """Record from llm_interactions table.

    All LLM calls are logged for reproducibility.
    """

    interaction_id: str
    experiment_id: str
    iteration_number: int
    prompt_text: str
    prompt_hash: str
    response_text: str
    response_hash: str
    model_name: str
    reasoning_effort: str
    tokens_used: int
    latency_seconds: float
    created_at: datetime
    error_message: str | None


class SimulationRunRecord(TypedDict):
    """Record from simulation_runs table.

    Per-seed simulation results.
    """

    run_id: str
    experiment_id: str
    iteration_number: int
    seed: int
    total_cost: int
    bank_a_cost: int
    bank_b_cost: int
    settlement_rate: float
    collateral_cost: int | None
    delay_cost: int | None
    overdraft_cost: int | None
    eod_penalty: int | None
    bank_a_final_balance: int | None
    bank_b_final_balance: int | None
    total_arrivals: int | None
    total_settlements: int | None
    raw_output: str  # JSON string
    verbose_log: str | None
    created_at: datetime


class IterationMetricsRecord(TypedDict):
    """Record from iteration_metrics table.

    Aggregated metrics for each iteration.
    """

    metric_id: str
    experiment_id: str
    iteration_number: int
    total_cost_mean: float
    total_cost_std: float
    risk_adjusted_cost: float
    settlement_rate_mean: float
    failure_rate: float
    best_seed: int
    worst_seed: int
    best_seed_cost: int
    worst_seed_cost: int
    converged: bool
    policy_was_accepted: bool
    is_best_iteration: bool
    comparison_to_best: str | None
    created_at: datetime


class ValidationErrorRecord(TypedDict):
    """Record from validation_errors table.

    Tracks policy validation failures for learning.
    """

    error_id: str
    experiment_id: str
    iteration_number: int
    agent_id: str
    attempt_number: int
    policy_json: str
    error_messages: str  # JSON array string
    error_category: str | None
    was_fixed: bool
    fix_attempt_count: int
    created_at: datetime


# ============================================================================
# Metrics Types
# ============================================================================


class AggregatedMetrics(TypedDict):
    """Aggregated metrics from multiple simulation runs.

    Computed by compute_metrics() function.
    """

    total_cost_mean: float
    total_cost_std: float
    risk_adjusted_cost: float
    settlement_rate_mean: float
    failure_rate: float
    best_seed: int
    worst_seed: int
    best_seed_cost: int
    worst_seed_cost: int
    # Per-bank metrics for selfish evaluation
    bank_a_cost_mean: float
    bank_b_cost_mean: float


class ValidationErrorSummary(TypedDict):
    """Summary statistics for validation errors."""

    by_category: dict[str, int]
    total_errors: int
    fixed_count: int
    fix_rate: float
    avg_fix_attempts: float
    by_agent: dict[str, int]


# ============================================================================
# Experiment Configuration Types
# ============================================================================


@dataclass(frozen=True)
class ExperimentDefinition:
    """Definition of an experiment from the registry.

    Immutable configuration for a reproducible experiment.
    """

    name: str
    description: str
    config_path: str
    policy_a_path: str
    policy_b_path: str
    num_seeds: int
    max_iterations: int
    convergence_threshold: float
    convergence_window: int
    castro_mode: bool = False


@dataclass
class ExperimentState:
    """Mutable state during experiment execution.

    Tracks current policies, best policies, and iteration history.
    """

    experiment_id: str
    policy_a: dict[str, object]
    policy_b: dict[str, object]
    best_policy_a: dict[str, object] | None = None
    best_policy_b: dict[str, object] | None = None
    best_cost: float | None = None
    current_iteration: int = 0
    converged: bool = False
    # Iteration history for extended context
    iteration_history: list[object] = field(default_factory=list)


# ============================================================================
# Chart Data Types
# ============================================================================


class CostRibbonData(TypedDict):
    """Data for cost ribbon chart."""

    iterations: list[int]
    mean_costs: list[float]
    best_costs: list[int]
    worst_costs: list[int]


class SettlementRateData(TypedDict):
    """Data for settlement rate chart."""

    iterations: list[int]
    settlement_rates: list[float]
    failure_rates: list[float]


class PerAgentCostData(TypedDict):
    """Data for per-agent cost chart."""

    iterations: list[int]
    bank_a_costs: list[float]
    bank_b_costs: list[float]


class AcceptanceData(TypedDict):
    """Data for iteration acceptance chart."""

    iterations: list[int]
    mean_costs: list[float]
    accepted: list[bool]
    is_best: list[bool]
