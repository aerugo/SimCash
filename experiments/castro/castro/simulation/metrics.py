"""Metrics computation for simulation results.

Computes aggregated metrics from multiple simulation runs including
per-bank metrics for selfish policy evaluation.
"""

from __future__ import annotations

import statistics
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from experiments.castro.castro.core.types import AggregatedMetrics, SimulationResult


def compute_metrics(results: list[SimulationResult]) -> AggregatedMetrics | None:
    """Compute aggregated metrics from simulation results.

    Returns None if all simulations failed, allowing caller to handle gracefully.

    IMPORTANT: Each bank is selfish and only cares about their own costs!
    This function computes per-bank cost metrics for independent policy evaluation.

    Args:
        results: List of simulation results (may contain errors)

    Returns:
        AggregatedMetrics dict or None if all simulations failed
    """
    # Filter out error results
    valid_results = [r for r in results if "error" not in r]

    if not valid_results:
        return None  # Let caller handle this gracefully

    costs = [r["total_cost"] for r in valid_results]
    settlements = [r["settlement_rate"] for r in valid_results]

    # Per-bank costs for selfish evaluation
    bank_a_costs = [r["bank_a_cost"] for r in valid_results]
    bank_b_costs = [r["bank_b_cost"] for r in valid_results]

    mean_cost = statistics.mean(costs)
    std_cost = statistics.stdev(costs) if len(costs) > 1 else 0.0

    # Per-bank cost statistics
    bank_a_mean = statistics.mean(bank_a_costs)
    bank_b_mean = statistics.mean(bank_b_costs)

    best_idx = costs.index(min(costs))
    worst_idx = costs.index(max(costs))

    failures = sum(1 for r in valid_results if r["settlement_rate"] < 1.0)

    return {
        "total_cost_mean": mean_cost,
        "total_cost_std": std_cost,
        "risk_adjusted_cost": mean_cost + std_cost,
        "settlement_rate_mean": statistics.mean(settlements),
        "failure_rate": failures / len(valid_results),
        "best_seed": valid_results[best_idx]["seed"],
        "worst_seed": valid_results[worst_idx]["seed"],
        "best_seed_cost": min(costs),
        "worst_seed_cost": max(costs),
        # Per-bank metrics for selfish policy evaluation
        "bank_a_cost_mean": bank_a_mean,
        "bank_b_cost_mean": bank_b_mean,
    }
