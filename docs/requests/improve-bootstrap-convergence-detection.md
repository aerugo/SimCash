# Feature Request: Improve Bootstrap Mode Convergence Detection

**Date**: 2025-12-20
**Priority**: High
**Affects**: `api/payment_simulator/ai_cash_mgmt/optimization/convergence_detector.py`, `api/payment_simulator/experiments/runner/optimization.py`

## Summary

The current bootstrap mode convergence detection uses a simple relative-change threshold (5%) that triggers too early when costs are still meaningfully decreasing, and fails to detect divergent behavior. This leads to premature convergence declarations and suboptimal final policies.

## Problem Statement

### Current Behavior

The `ConvergenceDetector` class checks if the relative change between consecutive cost measurements is below a threshold:

```python
def _is_stable_change(self, prev: float, current: float) -> bool:
    if prev == 0:
        return abs(current) < self._stability_threshold
    relative_change = abs(current - prev) / abs(prev)
    return relative_change <= self._stability_threshold  # e.g., 0.05 = 5%
```

When 5 consecutive iterations have relative changes ≤5%, convergence is declared.

### Evidence from Exp2 Data

Analysis of `docs/papers/simcash-paper/paper_generator/data/exp2.db` reveals three failure modes:

**Pass 1 (converged at iter 10)**: Costs still dropping ~4-5% per iteration
```
Iter  7 | Total: $418.55 | Δ: -4.5%
Iter  8 | Total: $402.93 | Δ: -3.7%
Iter  9 | Total: $383.36 | Δ: -4.9%  ← Converged here, but still improving!
```

**Pass 2 (hit max iter 25)**: Optimization found minimum at $264, then diverged to $459
```
Iter 13 | Total: $264.10 | Δ: -1.9%  ← Best point
Iter 14 | Total: $371.99 | Δ: +40.9% ← Diverged!
Iter 15 | Total: $451.54 | Δ: +21.4%
...
Iter 24 | Total: $459.32 | Δ: +0.0%  ← Converged at 74% worse than best
```

**Pass 3 (converged at iter 11)**: Similar to Pass 1
```
Iter  9 | Total: $468.12 | Δ: -4.1%
Iter 10 | Total: $448.20 | Δ: -4.3%  ← Converged, but still improving
```

### Why This Is a Problem

1. **Premature convergence**: 4-5% improvement per iteration is meaningful—Pass 1 stopped at $383 when it could have continued improving
2. **No trend detection**: Consecutive 4% drops indicate a consistent downward trend, not stability
3. **No divergence detection**: Pass 2 converged at a point 74% worse than its best, with no warning
4. **Inconsistent final costs**: Pass 1 ended at $383, Pass 2 at $459, Pass 3 at $448—high variance suggests none found true equilibrium

## Proposed Solution

Replace the simple relative-change check with a more robust convergence criterion that:
1. Uses coefficient of variation (CV) over a rolling window
2. Detects and rejects converging during consistent trends
3. Tracks best-so-far and prevents converging at significantly worse points

### Design Goals

1. **Statistical soundness**: Use standard statistical measures for stability
2. **Trend awareness**: Don't converge during consistent improvement
3. **Divergence protection**: Don't converge if current cost >> best observed cost
4. **Backward compatible**: Keep same interface, just smarter internals

### Proposed API / Interface

```python
class BootstrapConvergenceDetector:
    """Improved convergence detection for bootstrap evaluation mode.

    Uses three criteria, ALL must be satisfied:
    1. CV criterion: Coefficient of variation over window < cv_threshold
    2. Trend criterion: No statistically significant trend (Mann-Kendall p > 0.05)
    3. Regret criterion: Current cost within regret_threshold of best observed
    """

    def __init__(
        self,
        cv_threshold: float = 0.03,  # 3% coefficient of variation
        window_size: int = 5,
        regret_threshold: float = 0.10,  # Within 10% of best
        max_iterations: int = 25,
    ) -> None:
        ...

    def record_metric(self, metric: float) -> None:
        """Record a new cost observation."""
        ...

    @property
    def is_converged(self) -> bool:
        """True only if CV, trend, AND regret criteria all satisfied."""
        ...

    @property
    def convergence_diagnostics(self) -> dict:
        """Return detailed diagnostics for debugging/logging."""
        return {
            "cv": self._current_cv,
            "cv_satisfied": self._cv < self._cv_threshold,
            "trend_p_value": self._trend_p_value,
            "trend_satisfied": self._trend_p_value > 0.05,
            "current_cost": self._history[-1],
            "best_cost": self._best_cost,
            "regret": (self._history[-1] - self._best_cost) / self._best_cost,
            "regret_satisfied": self._regret < self._regret_threshold,
        }
```

### Detailed Criteria

**1. Coefficient of Variation (CV)**
```python
def _compute_cv(self) -> float:
    """CV = std_dev / mean over last window_size observations."""
    window = self._history[-self._window_size:]
    mean = sum(window) / len(window)
    variance = sum((x - mean) ** 2 for x in window) / len(window)
    std_dev = variance ** 0.5
    return std_dev / mean if mean > 0 else float('inf')
```

CV < 3% indicates costs are stable (not improving or worsening significantly).

**2. Trend Test (Mann-Kendall)**
```python
def _has_significant_trend(self) -> bool:
    """Return True if there's a statistically significant trend."""
    # Simplified Mann-Kendall: count concordant vs discordant pairs
    window = self._history[-self._window_size:]
    s = 0
    for i in range(len(window) - 1):
        for j in range(i + 1, len(window)):
            s += sign(window[j] - window[i])

    # For small samples, use lookup table or normal approximation
    # Return True if |s| indicates significant trend at p < 0.05
    ...
```

Prevents declaring convergence during consistent downward (improvement) trends.

**3. Regret Bound**
```python
def _within_regret_bound(self) -> bool:
    """True if current cost is within threshold of best observed."""
    if self._best_cost is None or self._best_cost == 0:
        return True
    regret = (self._history[-1] - self._best_cost) / self._best_cost
    return regret <= self._regret_threshold
```

Prevents converging at a point much worse than previously achieved (Pass 2 failure).

### Usage Example

```python
# In optimization.py, replace current detector for bootstrap mode
if evaluation_mode == "bootstrap":
    detector = BootstrapConvergenceDetector(
        cv_threshold=0.03,
        window_size=5,
        regret_threshold=0.10,
        max_iterations=config.convergence.max_iterations,
    )
else:
    # Keep existing detector for deterministic-temporal mode
    detector = ConvergenceDetector(...)
```

## Implementation Notes

### Invariants to Respect

- **INV-1 (Money is i64)**: Convergence operates on integer costs; division for CV/regret is fine for detection logic
- **Determinism**: No randomness in detection; same cost sequence → same convergence decision

### Related Components

| Component | Impact |
|-----------|--------|
| `api/payment_simulator/ai_cash_mgmt/optimization/convergence_detector.py` | Add new `BootstrapConvergenceDetector` class |
| `api/payment_simulator/experiments/runner/optimization.py` | Use new detector in bootstrap mode |
| `api/payment_simulator/experiments/config/experiment_config.py` | Add new config fields for CV/regret thresholds |

### Migration Path

1. Phase 1: Add `BootstrapConvergenceDetector` alongside existing `ConvergenceDetector`
2. Phase 2: Update `optimization.py` to use new detector for `mode: bootstrap`
3. Phase 3: Update experiment configs with new threshold parameters
4. Phase 4: Re-run experiments and validate improved convergence behavior

## Acceptance Criteria

- [ ] `BootstrapConvergenceDetector` class implemented with CV, trend, and regret criteria
- [ ] Pass 1 scenario (4-5% drops) does NOT trigger premature convergence
- [ ] Pass 2 scenario (divergence to 74% worse) does NOT converge at worse point
- [ ] Convergence diagnostics property provides debugging information
- [ ] Existing `ConvergenceDetector` unchanged (backward compatible)
- [ ] Experiment config supports new `cv_threshold` and `regret_threshold` parameters
- [ ] Unit tests cover each criterion independently
- [ ] Integration test with Exp2 data shows improved final costs

## Testing Requirements

1. **Unit tests**:
   - CV computation correctness
   - Trend detection (no trend, upward trend, downward trend)
   - Regret bound enforcement
   - All-criteria-must-pass logic

2. **Integration tests**:
   - Replay Exp2 cost sequences through new detector
   - Verify Pass 1/3 don't converge at iter 10/11
   - Verify Pass 2 would converge near iteration 13 (not 24)

3. **Regression tests**:
   - Deterministic-temporal mode still uses old detector
   - Existing experiment configs still work

## Related Documentation

- `docs/reference/ai_cash_mgmt/optimization.md` - Update convergence detection section
- `docs/reference/experiments/configuration.md` - Document new config parameters

## Related Code

- `api/payment_simulator/ai_cash_mgmt/optimization/convergence_detector.py` - Current implementation
- `api/payment_simulator/experiments/runner/optimization.py` - Uses detector in `_check_convergence()`
- `api/payment_simulator/experiments/runner/policy_stability.py` - Temporal mode (unchanged)

## Notes

The coefficient of variation (CV) is a standard statistical measure for relative variability. A CV of 3% means the standard deviation is 3% of the mean—much more robust than checking individual relative changes.

The Mann-Kendall test is a non-parametric trend test commonly used in time series analysis. For our short windows (5 iterations), a simplified version or lookup table suffices.

The regret bound is borrowed from online learning theory—we should never "settle" at a point significantly worse than what we've already achieved.
