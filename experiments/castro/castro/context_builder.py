"""Build per-agent context from Monte Carlo simulation results.

This module provides functionality to:
1. Identify best/worst seeds per agent (based on that agent's costs)
2. Extract filtered verbose output for those seeds
3. Build SingleAgentContext for each agent

Key invariants:
- INV-3: Each agent may have different best/worst seeds
- INV-4: Context structure follows SingleAgentContext format

Example:
    >>> from castro.context_builder import MonteCarloContextBuilder
    >>> builder = MonteCarloContextBuilder(results, seeds)
    >>> context = builder.build_context_for_agent(
    ...     agent_id="BANK_A",
    ...     iteration=3,
    ...     current_policy=policy,
    ...     iteration_history=[],
    ...     cost_rates={},
    ... )
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from payment_simulator.ai_cash_mgmt.prompts.context_types import (
    SingleAgentContext,
    SingleAgentIterationRecord,
)

if TYPE_CHECKING:
    from castro.verbose_capture import VerboseOutput


class SimulationResultProtocol(Protocol):
    """Protocol for simulation result objects.

    Allows the builder to work with both real SimulationResult
    and mock objects for testing.
    """

    @property
    def total_cost(self) -> int:
        """Total cost across all agents."""
        ...

    @property
    def per_agent_costs(self) -> dict[str, int]:
        """Cost per agent ID."""
        ...

    @property
    def settlement_rate(self) -> float:
        """Settlement rate (0.0 to 1.0)."""
        ...

    @property
    def verbose_output(self) -> VerboseOutput | None:
        """Optional verbose output capture."""
        ...


@dataclass
class AgentSimulationContext:
    """Context data for a single agent from Monte Carlo samples.

    Aggregates statistics and verbose output for a specific agent
    across all Monte Carlo samples.

    Attributes:
        agent_id: Agent identifier (e.g., "BANK_A").
        best_seed: Seed that produced lowest cost for this agent.
        best_seed_cost: Cost at best seed.
        best_seed_output: Filtered verbose output from best seed.
        worst_seed: Seed that produced highest cost for this agent.
        worst_seed_cost: Cost at worst seed.
        worst_seed_output: Filtered verbose output from worst seed.
        mean_cost: Mean cost across all samples.
        cost_std: Standard deviation of costs.

    Example:
        >>> context = AgentSimulationContext(
        ...     agent_id="BANK_A",
        ...     best_seed=42,
        ...     best_seed_cost=5000,
        ...     best_seed_output="[Tick 0] ...",
        ...     worst_seed=99,
        ...     worst_seed_cost=15000,
        ...     worst_seed_output="[Tick 0] ...",
        ...     mean_cost=9000.0,
        ...     cost_std=3742.0,
        ... )
    """

    agent_id: str
    best_seed: int
    best_seed_cost: int
    best_seed_output: str | None
    worst_seed: int
    worst_seed_cost: int
    worst_seed_output: str | None
    mean_cost: float
    cost_std: float


class MonteCarloContextBuilder:
    """Builds per-agent context from Monte Carlo samples.

    After running multiple simulations with different seeds,
    this class:
    1. Identifies best/worst seeds per agent (by agent's cost)
    2. Extracts filtered verbose output for those seeds
    3. Computes per-agent metrics (mean, std dev)
    4. Builds SingleAgentContext for LLM prompts

    Key invariant (INV-3): Different agents may have different best/worst seeds.
    This is critical for proper per-agent optimization.

    Example:
        >>> results = [runner.run_simulation(policy, seed) for seed in seeds]
        >>> builder = MonteCarloContextBuilder(results, seeds)
        >>> context = builder.build_context_for_agent(
        ...     agent_id="BANK_A",
        ...     iteration=3,
        ...     current_policy=policy,
        ...     iteration_history=[],
        ...     cost_rates={},
        ... )
    """

    def __init__(
        self,
        results: list[Any],  # list[SimulationResultProtocol]
        seeds: list[int],
    ) -> None:
        """Initialize with Monte Carlo results.

        Args:
            results: List of SimulationResult from each sample.
            seeds: List of seeds used (parallel to results).

        Raises:
            ValueError: If results and seeds have different lengths.
        """
        if len(results) != len(seeds):
            msg = f"Results ({len(results)}) and seeds ({len(seeds)}) must have same length"
            raise ValueError(msg)

        self._results = results
        self._seeds = seeds
        # Build index from seed to result index
        self._seed_to_index: dict[int, int] = {seed: i for i, seed in enumerate(seeds)}

    def get_best_seed_for_agent(self, agent_id: str) -> tuple[int, int]:
        """Get best seed and cost for an agent.

        Best seed is the one with lowest cost for this specific agent.

        Args:
            agent_id: Agent to find best seed for.

        Returns:
            Tuple of (seed, cost) where cost is lowest for this agent.
        """
        costs_with_seeds = self._get_agent_costs_with_seeds(agent_id)
        best_seed, best_cost = min(costs_with_seeds, key=lambda x: x[1])
        return best_seed, best_cost

    def get_worst_seed_for_agent(self, agent_id: str) -> tuple[int, int]:
        """Get worst seed and cost for an agent.

        Worst seed is the one with highest cost for this specific agent.

        Args:
            agent_id: Agent to find worst seed for.

        Returns:
            Tuple of (seed, cost) where cost is highest for this agent.
        """
        costs_with_seeds = self._get_agent_costs_with_seeds(agent_id)
        worst_seed, worst_cost = max(costs_with_seeds, key=lambda x: x[1])
        return worst_seed, worst_cost

    def _get_agent_costs_with_seeds(self, agent_id: str) -> list[tuple[int, int]]:
        """Get list of (seed, cost) tuples for an agent.

        Args:
            agent_id: Agent to get costs for.

        Returns:
            List of (seed, agent_cost) tuples.
        """
        costs_with_seeds: list[tuple[int, int]] = []
        for seed, result in zip(self._seeds, self._results, strict=True):
            agent_cost = result.per_agent_costs.get(agent_id, 0)
            costs_with_seeds.append((seed, agent_cost))
        return costs_with_seeds

    def get_best_seed_verbose_output(self, agent_id: str) -> str | None:
        """Get filtered verbose output from best seed for agent.

        Args:
            agent_id: Agent to get verbose output for.

        Returns:
            Filtered verbose output string, or None if not captured.
        """
        best_seed, _ = self.get_best_seed_for_agent(agent_id)
        return self._get_filtered_output(best_seed, agent_id)

    def get_worst_seed_verbose_output(self, agent_id: str) -> str | None:
        """Get filtered verbose output from worst seed for agent.

        Args:
            agent_id: Agent to get verbose output for.

        Returns:
            Filtered verbose output string, or None if not captured.
        """
        worst_seed, _ = self.get_worst_seed_for_agent(agent_id)
        return self._get_filtered_output(worst_seed, agent_id)

    def _get_filtered_output(self, seed: int, agent_id: str) -> str | None:
        """Get filtered verbose output for a specific seed and agent.

        Args:
            seed: Seed to get output for.
            agent_id: Agent to filter for.

        Returns:
            Filtered verbose output string, or None if not available.
        """
        idx = self._seed_to_index.get(seed)
        if idx is None:
            return None

        result = self._results[idx]
        verbose_output = getattr(result, "verbose_output", None)
        if verbose_output is None:
            return None

        # Use the filter_for_agent method from VerboseOutput
        filtered: str = verbose_output.filter_for_agent(agent_id)
        return filtered

    def get_agent_simulation_context(self, agent_id: str) -> AgentSimulationContext:
        """Get full simulation context for an agent.

        Computes all statistics and retrieves verbose output for
        both best and worst seeds.

        Args:
            agent_id: Agent to build context for.

        Returns:
            AgentSimulationContext with all computed values.
        """
        best_seed, best_cost = self.get_best_seed_for_agent(agent_id)
        worst_seed, worst_cost = self.get_worst_seed_for_agent(agent_id)

        best_output = self.get_best_seed_verbose_output(agent_id)
        worst_output = self.get_worst_seed_verbose_output(agent_id)

        mean_cost, cost_std = self._compute_cost_statistics(agent_id)

        return AgentSimulationContext(
            agent_id=agent_id,
            best_seed=best_seed,
            best_seed_cost=best_cost,
            best_seed_output=best_output,
            worst_seed=worst_seed,
            worst_seed_cost=worst_cost,
            worst_seed_output=worst_output,
            mean_cost=mean_cost,
            cost_std=cost_std,
        )

    def _compute_cost_statistics(self, agent_id: str) -> tuple[float, float]:
        """Compute mean and std dev of costs for an agent.

        Args:
            agent_id: Agent to compute statistics for.

        Returns:
            Tuple of (mean_cost, cost_std).
        """
        costs = [r.per_agent_costs.get(agent_id, 0) for r in self._results]
        n = len(costs)

        if n == 0:
            return 0.0, 0.0

        mean = sum(costs) / n

        if n == 1:
            return mean, 0.0

        # Population standard deviation
        variance = sum((c - mean) ** 2 for c in costs) / n
        std = math.sqrt(variance)

        return mean, std

    def build_context_for_agent(
        self,
        agent_id: str,
        iteration: int,
        current_policy: dict[str, Any],
        iteration_history: list[SingleAgentIterationRecord],
        cost_rates: dict[str, Any],
    ) -> SingleAgentContext:
        """Build complete context for a single agent.

        Creates a SingleAgentContext suitable for use with
        SingleAgentContextBuilder to generate LLM prompts.

        Args:
            agent_id: Agent to build context for.
            iteration: Current iteration number.
            current_policy: Agent's current policy.
            iteration_history: Previous iterations for this agent.
            cost_rates: Cost rate configuration.

        Returns:
            SingleAgentContext ready for SingleAgentContextBuilder.
        """
        sim_context = self.get_agent_simulation_context(agent_id)

        # Compute metrics from the context
        current_metrics: dict[str, Any] = {
            "total_cost_mean": sim_context.mean_cost,
            "total_cost_std": sim_context.cost_std,
            "settlement_rate_mean": self._compute_mean_settlement_rate(),
        }

        return SingleAgentContext(
            agent_id=agent_id,
            current_iteration=iteration,
            current_policy=current_policy,
            current_metrics=current_metrics,
            iteration_history=iteration_history,
            best_seed=sim_context.best_seed,
            best_seed_cost=sim_context.best_seed_cost,
            best_seed_output=sim_context.best_seed_output,
            worst_seed=sim_context.worst_seed,
            worst_seed_cost=sim_context.worst_seed_cost,
            worst_seed_output=sim_context.worst_seed_output,
            cost_rates=cost_rates,
        )

    def _compute_mean_settlement_rate(self) -> float:
        """Compute mean settlement rate across all samples.

        Returns:
            Mean settlement rate.
        """
        if not self._results:
            return 0.0

        rates: list[float] = [float(r.settlement_rate) for r in self._results]
        return sum(rates) / len(rates)

    def get_agent_ids(self) -> list[str]:
        """Get list of all agent IDs from results.

        Returns:
            List of agent ID strings.
        """
        if not self._results:
            return []

        # Get agent IDs from first result's per_agent_costs
        return list(self._results[0].per_agent_costs.keys())
