"""Statistical computations for policy evaluation.

Provides functions to compute derived statistics from evaluation samples:
- Standard deviation of costs
- 95% confidence intervals using t-distribution

All monetary values are integer cents (INV-1 compliance).
"""

from __future__ import annotations

import math
import statistics as stats_module
from typing import Any

# t-distribution critical values for 95% CI (two-tailed)
# t_{df, 0.975} for df from 1 to 100, then use normal approx for df > 100
_T_CRITICAL_VALUES = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    15: 2.131,
    20: 2.086,
    25: 2.060,
    30: 2.042,
    40: 2.021,
    50: 2.009,
    60: 2.000,
    80: 1.990,
    100: 1.984,
}


def _get_t_critical(df: int) -> float:
    """Get t-distribution critical value for 95% CI.

    Args:
        df: Degrees of freedom (n - 1)

    Returns:
        t-critical value for two-tailed 95% CI
    """
    if df <= 0:
        return float("inf")

    # Direct lookup
    if df in _T_CRITICAL_VALUES:
        return _T_CRITICAL_VALUES[df]

    # Interpolate or use closest value
    if df > 100:
        return 1.96  # Normal approximation

    # Find closest lower key
    lower_keys = [k for k in _T_CRITICAL_VALUES if k <= df]
    if lower_keys:
        closest = max(lower_keys)
        return _T_CRITICAL_VALUES[closest]

    return 1.96


def compute_cost_statistics(sample_costs: list[int]) -> dict[str, int | None]:
    """Compute standard deviation and 95% CI for sample costs.

    Uses sample standard deviation (N-1 denominator) and t-distribution
    for confidence intervals.

    Args:
        sample_costs: List of costs in integer cents

    Returns:
        Dict with:
        - std_dev: Standard deviation in cents (None if N < 2)
        - ci_95_lower: Lower bound of 95% CI in cents (None if N < 2)
        - ci_95_upper: Upper bound of 95% CI in cents (None if N < 2)

    Example:
        >>> costs = [10000, 12000, 11000, 13000, 9000]
        >>> stats = compute_cost_statistics(costs)
        >>> stats["std_dev"]  # Sample std dev
        1581
        >>> 9000 <= stats["ci_95_lower"] <= stats["ci_95_upper"] <= 13000
        True
    """
    n = len(sample_costs)

    if n < 2:
        return {
            "std_dev": None,
            "ci_95_lower": None,
            "ci_95_upper": None,
        }

    mean = stats_module.mean(sample_costs)
    std = stats_module.stdev(sample_costs)

    # t-distribution critical value for 95% CI
    df = n - 1
    t_crit = _get_t_critical(df)

    # Margin of error
    margin = t_crit * (std / math.sqrt(n))

    return {
        "std_dev": int(std),
        "ci_95_lower": int(mean - margin),
        "ci_95_upper": int(mean + margin),
    }


def compute_per_agent_statistics(
    per_agent_samples: dict[str, list[int]],
) -> dict[str, dict[str, Any]]:
    """Compute statistics for each agent from per-sample costs.

    Args:
        per_agent_samples: Dict mapping agent_id to list of costs across samples

    Returns:
        Dict mapping agent_id to statistics dict with:
        - cost: Mean cost in cents (integer)
        - std_dev: Std dev in cents (None if N < 2)
        - ci_95_lower: Lower CI bound in cents (None if N < 2)
        - ci_95_upper: Upper CI bound in cents (None if N < 2)

    Example:
        >>> samples = {"BANK_A": [5000, 6000, 5500], "BANK_B": [4000, 4500, 3500]}
        >>> stats = compute_per_agent_statistics(samples)
        >>> stats["BANK_A"]["cost"]
        5500
        >>> stats["BANK_A"]["std_dev"] is not None
        True
    """
    result: dict[str, dict[str, Any]] = {}

    for agent_id, costs in per_agent_samples.items():
        if not costs:
            result[agent_id] = {
                "cost": 0,
                "std_dev": None,
                "ci_95_lower": None,
                "ci_95_upper": None,
            }
            continue

        mean = int(stats_module.mean(costs))
        stats = compute_cost_statistics(costs)

        result[agent_id] = {
            "cost": mean,
            "std_dev": stats["std_dev"],
            "ci_95_lower": stats["ci_95_lower"],
            "ci_95_upper": stats["ci_95_upper"],
        }

    return result
