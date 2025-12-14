"""Bootstrap support structures for OptimizationLoop integration.

This module provides data structures for integrating the bootstrap evaluation
infrastructure (from ai_cash_mgmt.bootstrap) into the experiment runner.

Key structures:
- SimulationResult: Complete simulation output from _run_simulation() method.
  This is the unified result type for all simulation execution.
- InitialSimulationResult: Captures results from the initial simulation
  used to collect historical data for bootstrap resampling.
- BootstrapLLMContext: LLM context with 3 event streams (initial sim,
  best sample, worst sample) as specified in the feature request.

Reference: docs/requests/implement-real-bootstrap-evaluation.md
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import CostBreakdown

if TYPE_CHECKING:
    from payment_simulator.ai_cash_mgmt.bootstrap.history_collector import (
        AgentTransactionHistory,
    )


@dataclass(frozen=True)
class SimulationResult:
    """Complete simulation output from _run_simulation().

    This is the unified result type for all simulation execution. It captures
    all data that any caller might need, allowing callers to transform or
    filter as required.

    ONE method runs simulations → ONE result type → callers transform as needed.

    All costs are integer cents (INV-1: Money is ALWAYS i64).

    Attributes:
        seed: RNG seed used for this simulation (for reproducibility).
        simulation_id: Unique identifier for replay and debugging.
            Format: {run_id}-sim-{counter:03d}-{purpose}
        total_cost: Sum of all agent costs in integer cents.
        per_agent_costs: Cost per agent in integer cents.
        events: All events from the simulation (immutable tuple).
        cost_breakdown: Breakdown of costs by type (delay, overdraft, etc.).
        settlement_rate: Fraction of transactions settled (0.0 to 1.0).
        avg_delay: Average settlement delay in ticks.

    Example:
        >>> from payment_simulator.experiments.runner.bootstrap_support import (
        ...     SimulationResult,
        ... )
        >>> from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
        ...     CostBreakdown,
        ... )
        >>> result = SimulationResult(
        ...     seed=12345,
        ...     simulation_id="exp1-sim-001-init",
        ...     total_cost=15000,  # $150.00 in cents
        ...     per_agent_costs={"BANK_A": 7500, "BANK_B": 7500},
        ...     events=({"event_type": "Arrival", "tick": 0},),
        ...     cost_breakdown=CostBreakdown(
        ...         delay_cost=5000,
        ...         overdraft_cost=8000,
        ...         deadline_penalty=2000,
        ...         eod_penalty=0,
        ...     ),
        ...     settlement_rate=0.95,
        ...     avg_delay=5.2,
        ... )

    Note:
        This dataclass is frozen (immutable) per project convention.
        Events are stored as a tuple to ensure immutability.
    """

    seed: int
    simulation_id: str
    total_cost: int  # INV-1: Integer cents
    per_agent_costs: dict[str, int]  # INV-1: Integer cents
    events: tuple[dict[str, Any], ...]
    cost_breakdown: CostBreakdown
    settlement_rate: float
    avg_delay: float


@dataclass(frozen=True)
class InitialSimulationResult:
    """Result from the initial simulation used for bootstrap sampling.

    This captures all data needed from the ONE initial simulation that
    provides the historical transaction data for bootstrap resampling.

    The initial simulation:
    1. Runs ONCE at the start of optimization (not every iteration)
    2. Uses stochastic arrivals (the base scenario config)
    3. Collects ALL transactions that occurred
    4. Provides verbose output for LLM context (Stream 1)

    Attributes:
        events: All events from the simulation (for verbose output).
        agent_histories: Transaction history per agent (for bootstrap sampling).
        total_cost: Total cost across all optimized agents (integer cents, INV-1).
        per_agent_costs: Cost per agent (integer cents, INV-1).
        verbose_output: Formatted verbose output string (for LLM Stream 1).
    """

    events: tuple[dict[str, Any], ...]
    agent_histories: dict[str, AgentTransactionHistory]
    total_cost: int  # INV-1: Integer cents
    per_agent_costs: dict[str, int]  # INV-1: Integer cents
    verbose_output: str | None = None


@dataclass
class BootstrapLLMContext:
    """Complete LLM context with 3 event streams for bootstrap evaluation.

    This provides the LLM with rich context from:
    1. Initial simulation (Stream 1) - the full simulation that generated history
    2. Best bootstrap sample (Stream 2) - lowest cost evaluation
    3. Worst bootstrap sample (Stream 3) - highest cost evaluation

    The 3 streams help the LLM understand:
    - What the typical transaction flow looks like (Stream 1)
    - What happens when things go well (Stream 2 - best case)
    - What happens when things go poorly (Stream 3 - worst case)

    All costs are integer cents (INV-1).

    Attributes:
        agent_id: ID of the agent being optimized.

        # Stream 1: Initial simulation
        initial_simulation_output: Verbose output from initial simulation.
        initial_simulation_cost: Total cost from initial simulation.

        # Stream 2: Best bootstrap sample
        best_seed: Seed that produced lowest cost.
        best_seed_cost: Lowest cost achieved.
        best_seed_output: Verbose output from best sample.

        # Stream 3: Worst bootstrap sample
        worst_seed: Seed that produced highest cost.
        worst_seed_cost: Highest cost achieved.
        worst_seed_output: Verbose output from worst sample.

        # Statistics
        mean_cost: Mean cost across all bootstrap samples.
        cost_std: Standard deviation of costs.
        num_samples: Number of bootstrap samples evaluated.
    """

    agent_id: str

    # Stream 1: Initial simulation (full verbose trace)
    initial_simulation_output: str | None
    initial_simulation_cost: int  # INV-1: Integer cents

    # Stream 2: Best bootstrap sample
    best_seed: int
    best_seed_cost: int  # INV-1: Integer cents
    best_seed_output: str | None

    # Stream 3: Worst bootstrap sample
    worst_seed: int
    worst_seed_cost: int  # INV-1: Integer cents
    worst_seed_output: str | None

    # Statistics
    mean_cost: int  # INV-1: Integer cents
    cost_std: int  # INV-1: Integer cents (standard deviation, rounded)
    num_samples: int

    @classmethod
    def from_agent_context_with_initial(
        cls,
        agent_id: str,
        initial_output: str | None,
        initial_cost: int,
        best_seed: int,
        best_seed_cost: int,
        best_seed_output: str | None,
        worst_seed: int,
        worst_seed_cost: int,
        worst_seed_output: str | None,
        mean_cost: int,
        cost_std: int,
        num_samples: int,
    ) -> BootstrapLLMContext:
        """Create context combining initial simulation with bootstrap results.

        This is a convenience constructor that combines:
        - Initial simulation output (captured once at start)
        - Best/worst sample outputs (from current bootstrap evaluation)

        Args:
            agent_id: Agent being optimized.
            initial_output: Verbose output from initial simulation.
            initial_cost: Cost from initial simulation.
            best_seed: Seed that produced lowest cost.
            best_seed_cost: Lowest cost achieved.
            best_seed_output: Verbose output from best sample.
            worst_seed: Seed that produced highest cost.
            worst_seed_cost: Highest cost achieved.
            worst_seed_output: Verbose output from worst sample.
            mean_cost: Mean cost across samples.
            cost_std: Standard deviation of costs.
            num_samples: Number of samples.

        Returns:
            BootstrapLLMContext with all 3 streams populated.
        """
        return cls(
            agent_id=agent_id,
            initial_simulation_output=initial_output,
            initial_simulation_cost=initial_cost,
            best_seed=best_seed,
            best_seed_cost=best_seed_cost,
            best_seed_output=best_seed_output,
            worst_seed=worst_seed,
            worst_seed_cost=worst_seed_cost,
            worst_seed_output=worst_seed_output,
            mean_cost=mean_cost,
            cost_std=cost_std,
            num_samples=num_samples,
        )
