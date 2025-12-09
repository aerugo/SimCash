"""Metrics aggregation for simulation results.

This module provides utilities for computing aggregated metrics from
multiple simulation runs. These metrics are used to evaluate policy
performance and guide optimization decisions.

Functions:
    compute_metrics: Compute aggregated metrics from simulation results

Types:
    AggregatedMetrics: TypedDict with all metric fields
"""

from __future__ import annotations

import statistics
from typing import Any, TypedDict


class AggregatedMetrics(TypedDict):
    """Aggregated metrics from multiple simulation runs.

    Attributes:
        total_cost_mean: Mean total cost across all seeds.
        total_cost_std: Standard deviation of total cost.
        risk_adjusted_cost: Mean + std (penalizes high variance).
        settlement_rate_mean: Mean settlement rate (1.0 = all settled).
        failure_rate: Fraction of runs with settlement_rate < 1.0.
        best_seed: Seed number with lowest cost.
        worst_seed: Seed number with highest cost.
        best_seed_cost: Total cost from best seed.
        worst_seed_cost: Total cost from worst seed.
        agent_cost_mean: Mean of agent-specific costs (for selfish evaluation).
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
    agent_cost_mean: float


def compute_metrics(
    results: list[dict[str, Any]],
    agent_id: str,
) -> AggregatedMetrics | None:
    """Compute aggregated metrics from simulation results.

    Returns None if all simulations failed, allowing caller to handle gracefully.

    IMPORTANT: Each agent is selfish and only cares about their own costs!
    This function computes per-agent cost metrics for independent policy evaluation.

    Args:
        results: List of simulation results (may contain errors).
            Each result should have:
            - total_cost: Total cost of the simulation
            - settlement_rate: Fraction of payments settled (0.0-1.0)
            - seed: Random seed used for this run
            - agent_cost: Cost for the specific agent
            OR
            - error: Error message if simulation failed
        agent_id: Agent identifier (used for logging/tracking).

    Returns:
        AggregatedMetrics dict or None if all simulations failed.

    Example:
        >>> results = [
        ...     {"total_cost": 1000, "settlement_rate": 1.0, "seed": 1, "agent_cost": 500},
        ...     {"total_cost": 2000, "settlement_rate": 1.0, "seed": 2, "agent_cost": 1000},
        ... ]
        >>> metrics = compute_metrics(results, agent_id="BANK_A")
        >>> print(f"Mean cost: ${metrics['total_cost_mean']:,.0f}")
        Mean cost: $1,500
    """
    # Filter out error results
    valid_results = [r for r in results if "error" not in r]

    if not valid_results:
        return None  # Let caller handle this gracefully

    costs = [r["total_cost"] for r in valid_results]
    settlements = [r["settlement_rate"] for r in valid_results]
    agent_costs = [r["agent_cost"] for r in valid_results]

    mean_cost = statistics.mean(costs)
    std_cost = statistics.stdev(costs) if len(costs) > 1 else 0.0

    agent_cost_mean = statistics.mean(agent_costs)

    best_idx = costs.index(min(costs))
    worst_idx = costs.index(max(costs))

    failures = sum(1 for r in valid_results if r["settlement_rate"] < 1.0)

    return AggregatedMetrics(
        total_cost_mean=mean_cost,
        total_cost_std=std_cost,
        risk_adjusted_cost=mean_cost + std_cost,
        settlement_rate_mean=statistics.mean(settlements),
        failure_rate=failures / len(valid_results),
        best_seed=valid_results[best_idx]["seed"],
        worst_seed=valid_results[worst_idx]["seed"],
        best_seed_cost=min(costs),
        worst_seed_cost=max(costs),
        agent_cost_mean=agent_cost_mean,
    )
