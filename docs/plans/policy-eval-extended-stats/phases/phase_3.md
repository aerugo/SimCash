# Phase 3: Derived Statistics

**Status**: Pending
**Started**:

---

## Objective

Compute derived statistics (standard deviation and 95% confidence intervals) for bootstrap evaluations, with both total and per-agent granularity.

---

## Invariants Enforced in This Phase

- **INV-1**: Money is ALWAYS i64 - `cost_std_dev` and CI bounds stored as integer cents
- **INV-2**: Determinism is Sacred - Statistical computations produce identical results for same inputs

---

## TDD Steps

### Step 3.1: Write Failing Tests (RED)

Add tests to `api/tests/experiments/runner/test_policy_evaluation_metrics.py`:

**Test Cases**:
1. `test_compute_cost_std_dev_known_values` - Verify std dev calculation
2. `test_compute_confidence_interval_known_values` - Verify CI calculation
3. `test_std_dev_returns_none_for_single_sample` - N=1 edge case
4. `test_per_agent_std_dev_computed` - Per-agent statistics
5. `test_statistics_use_integer_cents` - INV-1 compliance

```python
import statistics

class TestDerivedStatistics:
    """Tests for std dev and confidence interval computation."""

    def test_compute_cost_std_dev_known_values(self) -> None:
        """Standard deviation should be computed correctly for known sample data."""
        from payment_simulator.experiments.runner.statistics import compute_cost_statistics

        # Known sample costs
        sample_costs = [10000, 12000, 11000, 13000, 9000]  # cents

        stats = compute_cost_statistics(sample_costs)

        # Expected std dev: stdev([10000, 12000, 11000, 13000, 9000]) ≈ 1581
        expected_std = int(statistics.stdev(sample_costs))
        assert stats["std_dev"] == expected_std

    def test_compute_confidence_interval_known_values(self) -> None:
        """95% CI should be computed using t-distribution."""
        from payment_simulator.experiments.runner.statistics import compute_cost_statistics

        sample_costs = [10000, 12000, 11000, 13000, 9000]  # cents
        n = len(sample_costs)

        stats = compute_cost_statistics(sample_costs)

        # Mean = 11000, std ≈ 1581
        # For n=5, t_{4, 0.975} ≈ 2.776
        # Margin = 2.776 * (1581 / sqrt(5)) ≈ 1963
        # CI = [11000 - 1963, 11000 + 1963] = [9037, 12963]
        assert stats["ci_95_lower"] is not None
        assert stats["ci_95_upper"] is not None
        assert stats["ci_95_lower"] < 11000 < stats["ci_95_upper"]

    def test_std_dev_returns_none_for_single_sample(self) -> None:
        """Std dev should be None when N=1 (undefined)."""
        from payment_simulator.experiments.runner.statistics import compute_cost_statistics

        sample_costs = [10000]  # Single sample

        stats = compute_cost_statistics(sample_costs)

        assert stats["std_dev"] is None
        assert stats["ci_95_lower"] is None
        assert stats["ci_95_upper"] is None

    def test_std_dev_returns_none_for_empty_samples(self) -> None:
        """Std dev should be None for empty sample list."""
        from payment_simulator.experiments.runner.statistics import compute_cost_statistics

        stats = compute_cost_statistics([])

        assert stats["std_dev"] is None
        assert stats["ci_95_lower"] is None
        assert stats["ci_95_upper"] is None

    def test_per_agent_std_dev_computed(self) -> None:
        """Per-agent std dev should be computed from per-agent sample costs."""
        from payment_simulator.experiments.runner.statistics import (
            compute_per_agent_statistics,
        )

        # Per-agent costs across 5 samples
        per_agent_samples = {
            "BANK_A": [5000, 6000, 5500, 6500, 4500],
            "BANK_B": [5000, 6000, 5500, 6500, 4500],
        }

        agent_stats = compute_per_agent_statistics(per_agent_samples)

        assert "BANK_A" in agent_stats
        assert "std_dev" in agent_stats["BANK_A"]
        assert agent_stats["BANK_A"]["std_dev"] is not None

    def test_statistics_stored_as_integer_cents(self) -> None:
        """All statistical values should be integer cents (INV-1)."""
        from payment_simulator.experiments.runner.statistics import compute_cost_statistics

        sample_costs = [10000, 12000, 11000, 13000, 9000]

        stats = compute_cost_statistics(sample_costs)

        # Verify integer types (INV-1)
        assert isinstance(stats["std_dev"], int)
        assert isinstance(stats["ci_95_lower"], int)
        assert isinstance(stats["ci_95_upper"], int)
```

### Step 3.2: Implement to Pass Tests (GREEN)

**Create** `api/payment_simulator/experiments/runner/statistics.py`:

```python
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
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
    6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
    15: 2.131, 20: 2.086, 25: 2.060, 30: 2.042, 40: 2.021,
    50: 2.009, 60: 2.000, 80: 1.990, 100: 1.984,
}


def _get_t_critical(df: int) -> float:
    """Get t-distribution critical value for 95% CI.

    Args:
        df: Degrees of freedom (n - 1)

    Returns:
        t-critical value for two-tailed 95% CI
    """
    if df <= 0:
        return float('inf')

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

    Args:
        sample_costs: List of costs in integer cents

    Returns:
        Dict with:
        - std_dev: Standard deviation in cents (None if N < 2)
        - ci_95_lower: Lower bound of 95% CI in cents (None if N < 2)
        - ci_95_upper: Upper bound of 95% CI in cents (None if N < 2)
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
    per_agent_samples: dict[str, list[int]]
) -> dict[str, dict[str, Any]]:
    """Compute statistics for each agent from per-sample costs.

    Args:
        per_agent_samples: Dict mapping agent_id to list of costs across samples

    Returns:
        Dict mapping agent_id to statistics dict with:
        - mean: Mean cost in cents
        - std_dev: Std dev in cents (None if N < 2)
        - ci_95_lower: Lower CI bound in cents (None if N < 2)
        - ci_95_upper: Upper CI bound in cents (None if N < 2)
    """
    result = {}

    for agent_id, costs in per_agent_samples.items():
        if not costs:
            result[agent_id] = {
                "mean": 0,
                "std_dev": None,
                "ci_95_lower": None,
                "ci_95_upper": None,
            }
            continue

        mean = int(stats_module.mean(costs))
        stats = compute_cost_statistics(costs)

        result[agent_id] = {
            "mean": mean,
            "std_dev": stats["std_dev"],
            "ci_95_lower": stats["ci_95_lower"],
            "ci_95_upper": stats["ci_95_upper"],
        }

    return result
```

**Update** `api/payment_simulator/experiments/runner/optimization.py`:

In `_evaluate_policy_pair()` bootstrap path, compute statistics:

```python
from payment_simulator.experiments.runner.statistics import (
    compute_cost_statistics,
    compute_per_agent_statistics,
)

# After collecting sample results...
new_costs = [pd.cost_b for pd in paired_deltas]
cost_stats = compute_cost_statistics(new_costs)

cost_std_dev = cost_stats["std_dev"]
confidence_interval_95 = (
    [cost_stats["ci_95_lower"], cost_stats["ci_95_upper"]]
    if cost_stats["ci_95_lower"] is not None
    else None
)

# Per-agent statistics from sample_details
per_agent_samples = {}  # Build from sample results
for sample in evaluation.sample_results:
    for agent_id, cost in sample.per_agent_costs.items():
        if agent_id not in per_agent_samples:
            per_agent_samples[agent_id] = []
        per_agent_samples[agent_id].append(cost)

per_agent_stats = compute_per_agent_statistics(per_agent_samples)
```

### Step 3.3: Refactor

- Ensure consistent handling of empty/small samples
- Add comprehensive docstrings
- Consider using scipy.stats if available for more accurate t-distribution

---

## Implementation Details

### Standard Deviation Formula

Uses Python's `statistics.stdev()` which computes sample standard deviation:

```
s = sqrt( sum((x_i - mean)^2) / (n-1) )
```

### 95% Confidence Interval Formula

```
CI = mean ± t_{n-1, 0.975} * (s / sqrt(n))
```

Where:
- `t_{n-1, 0.975}` is the t-distribution critical value for df = n-1
- `s` is the sample standard deviation
- `n` is the sample size

### t-Distribution Critical Values

Stored as a lookup table for common degrees of freedom. For large df (> 100), use normal approximation (1.96).

### Edge Cases to Handle

- N = 0: Return all None
- N = 1: Return all None (std dev undefined)
- N = 2: Valid but high uncertainty (large CI)
- Negative costs: Mathematically valid, should compute correctly

---

## Files

| File | Action |
|------|--------|
| `api/payment_simulator/experiments/runner/statistics.py` | CREATE |
| `api/payment_simulator/experiments/runner/optimization.py` | MODIFY |
| `api/tests/experiments/runner/test_policy_evaluation_metrics.py` | MODIFY (add tests) |

---

## Verification

```bash
# Run tests
cd /home/user/SimCash/api
.venv/bin/python -m pytest tests/experiments/runner/test_policy_evaluation_metrics.py -v -k "statistics or std_dev or confidence"

# Type check
.venv/bin/python -m mypy payment_simulator/experiments/runner/statistics.py
.venv/bin/python -m mypy payment_simulator/experiments/runner/optimization.py

# Lint
.venv/bin/python -m ruff check payment_simulator/experiments/runner/statistics.py
```

---

## Completion Criteria

- [ ] `compute_cost_statistics()` function implemented
- [ ] `compute_per_agent_statistics()` function implemented
- [ ] Std dev computed correctly for known values
- [ ] 95% CI computed using t-distribution
- [ ] Edge cases (N=0, N=1) return None appropriately
- [ ] All values stored as integer cents (INV-1)
- [ ] Statistics integrated into `_evaluate_policy_pair()` for bootstrap
- [ ] All test cases pass
- [ ] Type check passes
- [ ] Lint passes
