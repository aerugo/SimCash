"""Protocol definitions for castro experiments.

Protocols define the interfaces for key components, enabling:
- Composition over inheritance
- Easy mocking for tests
- Clear API contracts

Usage:
    from castro.core.protocols import Repository

    def run_experiment(repo: Repository, ...) -> None:
        repo.record_policy_iteration(...)
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from experiments.castro.castro.core.types import (
        AggregatedMetrics,
        SimulationResult,
        ValidationErrorSummary,
    )
    from experiments.castro.prompts.context import IterationRecord


# ============================================================================
# Repository Protocol
# ============================================================================


@runtime_checkable
class Repository(Protocol):
    """Protocol for experiment data persistence.

    Implementations:
    - ExperimentRepository (DuckDB implementation)
    - MockRepository (for testing)

    All methods should be idempotent where possible.
    """

    def close(self) -> None:
        """Close database connection."""
        ...

    # ------------------------------------------------------------------
    # Write Operations
    # ------------------------------------------------------------------

    def record_experiment_config(
        self,
        experiment_id: str,
        experiment_name: str,
        config_yaml: str,
        cost_rates: dict[str, int | float],
        agent_configs: list[dict[str, str | int]],
        model_name: str,
        reasoning_effort: str,
        num_seeds: int,
        max_iterations: int,
        convergence_threshold: float,
        convergence_window: int,
        master_seed: int,
        seed_matrix: dict[int, list[int]],
        notes: str | None = None,
    ) -> None:
        """Record experiment configuration."""
        ...

    def record_policy_iteration(
        self,
        experiment_id: str,
        iteration_number: int,
        agent_id: str,
        policy_json: str,
        created_by: str = "init",
        was_accepted: bool = True,
        is_best: bool = False,
    ) -> str:
        """Record a policy iteration. Returns iteration_id."""
        ...

    def record_llm_interaction(
        self,
        experiment_id: str,
        iteration_number: int,
        prompt_text: str,
        response_text: str,
        model_name: str,
        reasoning_effort: str,
        tokens_used: int,
        latency_seconds: float,
        error_message: str | None = None,
    ) -> str:
        """Record an LLM interaction. Returns interaction_id."""
        ...

    def record_simulation_run(
        self,
        experiment_id: str,
        iteration_number: int,
        seed: int,
        result: dict[str, object],
    ) -> str:
        """Record a simulation run. Returns run_id."""
        ...

    def record_iteration_metrics(
        self,
        experiment_id: str,
        iteration_number: int,
        metrics: dict[str, float | int],
        converged: bool = False,
        policy_was_accepted: bool = True,
        is_best_iteration: bool = False,
        comparison_to_best: str | None = None,
    ) -> str:
        """Record aggregated iteration metrics. Returns metric_id."""
        ...

    def record_validation_error(
        self,
        experiment_id: str,
        iteration_number: int,
        agent_id: str,
        attempt_number: int,
        policy: dict[str, object],
        errors: list[str],
        was_fixed: bool,
        fix_attempt_count: int,
    ) -> str:
        """Record a policy validation error. Returns error_id."""
        ...

    # ------------------------------------------------------------------
    # Read Operations
    # ------------------------------------------------------------------

    def get_latest_policies(
        self,
        experiment_id: str,
    ) -> dict[str, dict[str, object]]:
        """Get the latest policy for each agent."""
        ...

    def get_iteration_history(
        self,
        experiment_id: str,
    ) -> list[IterationRecord]:
        """Get complete iteration history with policies and changes."""
        ...

    def get_verbose_output_for_seeds(
        self,
        experiment_id: str,
        iteration_number: int,
        seeds: list[int],
    ) -> dict[int, str]:
        """Get verbose output logs for specific seeds."""
        ...

    def get_validation_error_summary(
        self,
        experiment_id: str | None = None,
    ) -> ValidationErrorSummary:
        """Get summary statistics for validation errors."""
        ...

    def export_summary(self) -> dict[str, object]:
        """Export experiment summary for reproducibility."""
        ...


# ============================================================================
# Simulation Executor Protocol
# ============================================================================


@runtime_checkable
class SimulationExecutor(Protocol):
    """Protocol for simulation execution.

    Implementations:
    - ParallelSimulationExecutor (real subprocess execution)
    - MockSimulationExecutor (for testing)
    """

    def run_simulations(
        self,
        config_path: str | Path,
        seeds: list[int],
        work_dir: str | Path,
    ) -> list[SimulationResult]:
        """Run simulations in parallel for all seeds.

        Args:
            config_path: Path to simulation config YAML
            seeds: List of random seeds to run
            work_dir: Directory for simulation database files

        Returns:
            List of SimulationResult dicts sorted by seed
        """
        ...

    def get_filtered_replay_output(
        self,
        db_path: str | Path,
        simulation_id: str,
        agent_id: str,
    ) -> str:
        """Get filtered verbose output for a specific agent.

        Args:
            db_path: Path to simulation database file
            simulation_id: Simulation ID to replay
            agent_id: Agent ID to filter for (e.g., "BANK_A")

        Returns:
            Filtered verbose output string
        """
        ...


# ============================================================================
# Policy Generator Protocol
# ============================================================================


@runtime_checkable
class PolicyGenerator(Protocol):
    """Protocol for LLM-based policy generation.

    Implementations:
    - RobustPolicyAgent (real LLM calls)
    - MockPolicyGenerator (for testing)
    """

    def generate_policy(
        self,
        instruction: str,
        current_policy: dict[str, object] | None = None,
        current_cost: float | None = None,
        settlement_rate: float | None = None,
        per_bank_costs: dict[str, float] | None = None,
        iteration: int = 0,
        **kwargs: object,
    ) -> dict[str, object]:
        """Generate a constrained policy.

        Args:
            instruction: Natural language optimization instruction
            current_policy: Current policy to improve
            current_cost: Current total cost
            settlement_rate: Current settlement rate
            per_bank_costs: Per-bank cost breakdown
            iteration: Current iteration number
            **kwargs: Additional context (iteration_history, etc.)

        Returns:
            Generated policy as dict
        """
        ...


# ============================================================================
# Metrics Computer Protocol
# ============================================================================


@runtime_checkable
class MetricsComputer(Protocol):
    """Protocol for computing aggregated metrics."""

    def compute_metrics(
        self,
        results: list[SimulationResult],
    ) -> AggregatedMetrics | None:
        """Compute aggregated metrics from simulation results.

        Returns None if all simulations failed.
        """
        ...


# ============================================================================
# Policy Validator Protocol
# ============================================================================


@runtime_checkable
class PolicyValidator(Protocol):
    """Protocol for policy validation."""

    def validate_policy(
        self,
        policy: dict[str, object],
        config_path: str | Path,
    ) -> tuple[bool, list[str]]:
        """Validate a policy against SimCash validator.

        Args:
            policy: Policy dict to validate
            config_path: Path to config for validation context

        Returns:
            Tuple of (is_valid, error_messages)
        """
        ...
