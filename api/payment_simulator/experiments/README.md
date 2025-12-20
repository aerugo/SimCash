# Experiments Module

This module provides experiment configuration and execution for policy optimization studies.

## Overview

The experiments module supports:
- **Bootstrap evaluation mode**: Statistical comparison using multiple random seeds
- **Deterministic evaluation modes**: Same-seed comparison for debugging and development

## Convergence Detection

The optimization loop uses convergence detection to determine when policy improvement has stabilized. Different evaluation modes use different convergence detectors optimized for their characteristics.

### Bootstrap Mode: `BootstrapConvergenceDetector`

Bootstrap mode uses a statistically robust convergence detector with **three criteria that ALL must be satisfied**:

#### 1. CV Criterion (Coefficient of Variation)

```
CV = std_dev / |mean| over last `window_size` observations
```

**Converges when**: CV < `cv_threshold` (default: 3%)

**Purpose**: Ensures costs are stable (not improving or worsening significantly). A CV of 3% means the standard deviation is 3% of the mean.

**Edge cases**:
- Mean = 0 with all zeros: CV = 0 (perfect stability)
- Mean = 0 with non-zero values: CV = infinity (unstable)
- Fewer than 2 values: CV = infinity

#### 2. Trend Criterion (Mann-Kendall Test)

The [Mann-Kendall test](https://en.wikipedia.org/wiki/Kendall_rank_correlation_coefficient) is a non-parametric test for monotonic trends.

```
S = Σ sign(x_j - x_i) for all pairs i < j
```

**Converges when**: p-value > 0.05 (no significant trend)

**Purpose**: Prevents declaring convergence during consistent improvement. Even if individual changes are small (e.g., 4% drops), a consistent downward trend indicates optimization should continue.

**How it works**:
- Positive S indicates upward trend (costs increasing = divergence)
- Negative S indicates downward trend (costs decreasing = still improving)
- S ≈ 0 indicates no clear trend (stable)
- Uses standard normal approximation with tie correction for variance

**Example**:
```python
# Consistent 4% drops - significant downward trend
[500, 480, 461, 443, 425]  # S = -10, p < 0.05, has_trend = True

# Oscillating around equilibrium - no trend
[100, 102, 99, 101, 100]   # S ≈ 0, p > 0.05, has_trend = False
```

#### 3. Regret Criterion

```
Regret = (current - best) / |best|
```

**Converges when**: Regret ≤ `regret_threshold` (default: 10%)

**Purpose**: Prevents converging at a point significantly worse than previously achieved. Catches divergence scenarios where the optimizer finds a good minimum but then moves away.

**Edge cases**:
- Current = best: Regret = 0
- Best = 0, current = 0: Regret = 0
- Best = 0, current > 0: Regret = infinity

**Example**:
```python
# Pass 2 scenario from Exp2: best was $264, converged at $459
# Regret = (459 - 264) / 264 = 74% > 10% threshold
# → Convergence REJECTED
```

### Configuration

```yaml
convergence:
  max_iterations: 25        # Hard cap on iterations
  stability_window: 5       # Window size for CV and trend analysis
  cv_threshold: 0.03        # 3% coefficient of variation
  regret_threshold: 0.10    # 10% regret from best

  # Legacy parameters (used by deterministic modes)
  stability_threshold: 0.05
  improvement_threshold: 0.01
```

### Deterministic Modes: `ConvergenceDetector`

Deterministic modes (pairwise and temporal) use the original simpler detector:

```
relative_change = |current - prev| / |prev|
```

**Converges when**: `stability_window` consecutive changes are below `stability_threshold`.

This is appropriate for deterministic modes where the same seed produces identical results, making relative changes more meaningful.

### Convergence Diagnostics

The `BootstrapConvergenceDetector` provides detailed diagnostics for debugging:

```python
diag = detector.convergence_diagnostics
# Returns:
{
    "cv": 0.025,                    # Current CV
    "cv_satisfied": True,           # CV < threshold?
    "trend_statistic": -2,          # Mann-Kendall S
    "trend_p_value": 0.42,          # Two-sided p-value
    "trend_satisfied": True,        # p > 0.05?
    "current_cost": 198.5,          # Latest cost
    "best_cost": 195.0,             # Best observed
    "regret": 0.018,                # Current regret
    "regret_satisfied": True,       # Regret < threshold?
    "iteration": 12,                # Current iteration
    "window_values": [199, 198, 201, 200, 198.5]
}
```

### Why Three Criteria?

The original detector with a single relative-change check had several failure modes:

1. **Premature convergence**: 4-5% improvement per iteration was treated as "stable" even though optimization was still making meaningful progress.

2. **No trend awareness**: Consecutive small drops indicate a consistent downward trend, not stability.

3. **No divergence protection**: Could converge at a point 74% worse than the best observed cost.

The three-criteria approach addresses each failure mode:
- **CV** catches high variance (unstable)
- **Trend** catches consistent improvement (still optimizing)
- **Regret** catches divergence (moved away from optimum)

ALL three must pass to ensure convergence only happens when:
- Costs are stable (low CV)
- No consistent trend (not still improving)
- Close to the best seen (not diverged)

### References

- Mann, H. B. (1945). Nonparametric tests against trend. *Econometrica*, 13(3), 245-259.
- Kendall, M. G. (1975). *Rank Correlation Methods*. Griffin.
