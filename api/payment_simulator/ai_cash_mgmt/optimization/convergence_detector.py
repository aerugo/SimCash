"""Convergence detection for policy optimization.

Detects when policy optimization has stabilized and further iterations
are unlikely to produce meaningful improvements.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TypedDict


class ConvergenceDetector:
    """Detects convergence in policy optimization.

    Convergence is triggered by either:
    1. Stability: Metric changes stay below threshold for stability_window iterations
    2. Max iterations: Hard cap on total iterations reached

    Example:
        >>> detector = ConvergenceDetector(
        ...     stability_threshold=0.05,
        ...     stability_window=3,
        ...     max_iterations=50,
        ...     improvement_threshold=0.01,
        ... )
        >>> detector.record_metric(100.0)
        >>> detector.record_metric(99.5)
        >>> detector.record_metric(99.2)
        >>> detector.is_converged
        False
        >>> detector.record_metric(99.1)
        >>> detector.is_converged
        True
    """

    def __init__(
        self,
        stability_threshold: float,
        stability_window: int,
        max_iterations: int,
        improvement_threshold: float,
    ) -> None:
        """Initialize convergence detector.

        Args:
            stability_threshold: Maximum relative change to consider stable.
            stability_window: Consecutive stable iterations needed for convergence.
            max_iterations: Hard cap that triggers convergence.
            improvement_threshold: Minimum improvement to accept a new policy.
        """
        self._stability_threshold = stability_threshold
        self._stability_window = stability_window
        self._max_iterations = max_iterations
        self._improvement_threshold = improvement_threshold

        self._history: list[float] = []
        self._consecutive_stable: int = 0
        self._best_metric: float | None = None
        self._converged_by_stability: bool = False
        self._converged_by_max_iter: bool = False

    @property
    def is_converged(self) -> bool:
        """Check if optimization has converged."""
        return self._converged_by_stability or self._converged_by_max_iter

    @property
    def current_iteration(self) -> int:
        """Get current iteration count."""
        return len(self._history)

    @property
    def metric_history(self) -> list[float]:
        """Get history of recorded metrics."""
        return list(self._history)

    @property
    def best_metric(self) -> float | None:
        """Get best (lowest) metric seen."""
        return self._best_metric

    @property
    def convergence_reason(self) -> str:
        """Get reason for convergence."""
        if self._converged_by_stability:
            return f"Stability achieved ({self._stability_window} consecutive stable iterations)"
        elif self._converged_by_max_iter:
            return f"Max iterations reached ({self._max_iterations})"
        else:
            return "Not converged"

    def record_metric(self, metric: float) -> None:
        """Record a new metric value.

        Updates convergence status based on the new metric.

        Args:
            metric: The metric value (lower is better).
        """
        # Update best metric
        if self._best_metric is None or metric < self._best_metric:
            self._best_metric = metric

        # Check stability (relative change from previous)
        if len(self._history) > 0:
            prev = self._history[-1]
            if self._is_stable_change(prev, metric):
                self._consecutive_stable += 1
            else:
                self._consecutive_stable = 0

        # Record history
        self._history.append(metric)

        # Check convergence conditions
        # +1 because we need stability_window stable *changes* (which is window+1 values)
        if self._consecutive_stable >= self._stability_window:
            self._converged_by_stability = True

        if len(self._history) >= self._max_iterations:
            self._converged_by_max_iter = True

    def _is_stable_change(self, prev: float, current: float) -> bool:
        """Check if change from prev to current is stable.

        Args:
            prev: Previous metric value.
            current: Current metric value.

        Returns:
            True if change is within stability threshold.
        """
        if prev == 0:
            # Avoid division by zero; treat zero as stable if current is also small
            return abs(current) < self._stability_threshold
        relative_change = abs(current - prev) / abs(prev)
        return relative_change <= self._stability_threshold

    def should_accept_improvement(self, new_metric: float) -> bool:
        """Check if a new metric represents sufficient improvement.

        Args:
            new_metric: The proposed new metric value.

        Returns:
            True if improvement exceeds threshold.
        """
        if self._best_metric is None:
            return True

        if new_metric >= self._best_metric:
            return False

        # Check if improvement exceeds threshold
        improvement = (self._best_metric - new_metric) / abs(self._best_metric)
        return improvement >= self._improvement_threshold

    def reset(self) -> None:
        """Reset detector state for reuse."""
        self._history = []
        self._consecutive_stable = 0
        self._best_metric = None
        self._converged_by_stability = False
        self._converged_by_max_iter = False


class ConvergenceDiagnostics(TypedDict):
    """Diagnostic information about convergence status."""

    cv: float
    cv_satisfied: bool
    trend_statistic: float
    trend_p_value: float
    trend_satisfied: bool
    current_cost: float
    best_cost: float
    regret: float
    regret_satisfied: bool
    iteration: int
    window_values: list[float]


@dataclass(frozen=True)
class MannKendallResult:
    """Result of Mann-Kendall trend test.

    Attributes:
        s: The Mann-Kendall S statistic (sum of signs of differences).
        var_s: Variance of S, with tie correction.
        z: Standardized test statistic.
        p_value: Two-sided p-value.
        has_trend: True if p_value < significance level indicates trend.
    """

    s: int
    var_s: float
    z: float
    p_value: float
    has_trend: bool


def _sign(x: float) -> int:
    """Return sign of x: -1, 0, or 1."""
    if x > 0:
        return 1
    elif x < 0:
        return -1
    return 0


def _count_ties(values: list[float]) -> list[int]:
    """Count consecutive groups of tied values.

    Args:
        values: List of numeric values.

    Returns:
        List of tie group sizes (groups with size > 1).
    """
    if not values:
        return []

    # Count occurrences of each value
    counts: dict[float, int] = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1

    # Return groups with size > 1 (actual ties)
    return [c for c in counts.values() if c > 1]


def _normal_cdf(z: float) -> float:
    """Compute cumulative distribution function of standard normal.

    Uses error function approximation for accuracy.

    Args:
        z: Z-score.

    Returns:
        P(Z <= z) for standard normal distribution.
    """
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def mann_kendall_test(values: list[float], alpha: float = 0.05) -> MannKendallResult:
    """Perform Mann-Kendall trend test.

    The Mann-Kendall test is a non-parametric test for monotonic trends
    in time series data. It's robust for small samples and doesn't assume
    any particular distribution.

    Args:
        values: Time series values in chronological order.
        alpha: Significance level for trend detection.

    Returns:
        MannKendallResult with test statistics and p-value.

    Example:
        >>> # Downward trend
        >>> result = mann_kendall_test([100, 90, 85, 80, 75])
        >>> result.has_trend
        True
        >>> result.s < 0  # Negative S indicates downward trend
        True

        >>> # No clear trend (oscillating)
        >>> result = mann_kendall_test([100, 102, 99, 101, 100])
        >>> result.has_trend
        False
    """
    n = len(values)

    # Edge case: need at least 2 values
    if n < 2:
        return MannKendallResult(s=0, var_s=0.0, z=0.0, p_value=1.0, has_trend=False)

    # Compute S statistic: sum of sign(x_j - x_i) for all i < j
    s = 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            s += _sign(values[j] - values[i])

    # For n < 4, we can't reliably compute variance; use simple heuristic
    # S = 0 means no trend, |S| = n(n-1)/2 means perfect monotonic
    if n < 4:
        max_s = n * (n - 1) // 2
        # Simple heuristic: if |S| >= 75% of max, consider it a trend
        has_trend = abs(s) >= 0.75 * max_s if max_s > 0 else False
        return MannKendallResult(
            s=s, var_s=0.0, z=0.0, p_value=1.0 if not has_trend else 0.0, has_trend=has_trend
        )

    # Compute variance with tie correction
    # Var(S) = [n(n-1)(2n+5) - sum(t(t-1)(2t+5))] / 18
    # where t is the size of each tie group
    var_s_base = n * (n - 1) * (2 * n + 5)
    tie_groups = _count_ties(values)
    tie_correction = sum(t * (t - 1) * (2 * t + 5) for t in tie_groups)
    var_s = (var_s_base - tie_correction) / 18.0

    # Edge case: all values identical (var_s = 0)
    if var_s <= 0:
        return MannKendallResult(s=s, var_s=0.0, z=0.0, p_value=1.0, has_trend=False)

    # Compute Z statistic with continuity correction
    if s > 0:
        z = (s - 1) / math.sqrt(var_s)
    elif s < 0:
        z = (s + 1) / math.sqrt(var_s)
    else:
        z = 0.0

    # Two-sided p-value from standard normal
    p_value = 2 * (1 - _normal_cdf(abs(z)))

    return MannKendallResult(
        s=s,
        var_s=var_s,
        z=z,
        p_value=p_value,
        has_trend=p_value < alpha,
    )


class BootstrapConvergenceDetector:
    """Improved convergence detection for bootstrap evaluation mode.

    Uses three criteria that ALL must be satisfied for convergence:

    1. **CV Criterion**: Coefficient of variation over window < cv_threshold
       - CV = std_dev / |mean|
       - Indicates costs are stable (not improving or worsening significantly)

    2. **Trend Criterion**: No statistically significant trend (Mann-Kendall p > 0.05)
       - Prevents declaring convergence during consistent downward trends
       - Uses non-parametric test robust for small samples

    3. **Regret Criterion**: Current cost within regret_threshold of best observed
       - Prevents converging at a point much worse than previously achieved
       - Catches divergence scenarios

    Example:
        >>> detector = BootstrapConvergenceDetector(
        ...     cv_threshold=0.03,
        ...     window_size=5,
        ...     regret_threshold=0.10,
        ...     max_iterations=25,
        ... )
        >>> # Consistent 4% drops - should NOT converge (trend detected)
        >>> for cost in [500, 480, 461, 443, 425]:
        ...     detector.record_metric(cost)
        >>> detector.is_converged
        False
        >>> detector.convergence_diagnostics['trend_satisfied']
        False

        >>> # Reset and try stable values
        >>> detector.reset()
        >>> for cost in [100, 101, 99, 100, 101]:
        ...     detector.record_metric(cost)
        >>> detector.is_converged
        True
    """

    def __init__(
        self,
        cv_threshold: float = 0.03,
        window_size: int = 5,
        regret_threshold: float = 0.10,
        max_iterations: int = 25,
        trend_alpha: float = 0.05,
    ) -> None:
        """Initialize bootstrap convergence detector.

        Args:
            cv_threshold: Maximum coefficient of variation for stability.
                Default 0.03 (3%) means std_dev must be < 3% of mean.
            window_size: Number of recent observations to analyze.
            regret_threshold: Maximum allowed regret from best observed.
                Default 0.10 (10%) means current must be within 10% of best.
            max_iterations: Hard cap that triggers convergence.
            trend_alpha: Significance level for Mann-Kendall trend test.
                Default 0.05 means p > 0.05 required (no significant trend).
        """
        self._cv_threshold = cv_threshold
        self._window_size = window_size
        self._regret_threshold = regret_threshold
        self._max_iterations = max_iterations
        self._trend_alpha = trend_alpha

        self._history: list[float] = []
        self._best_metric: float | None = None
        self._converged_by_criteria: bool = False
        self._converged_by_max_iter: bool = False

    @property
    def is_converged(self) -> bool:
        """Check if optimization has converged.

        Returns True only if:
        - All three criteria (CV, trend, regret) are satisfied, OR
        - Max iterations reached
        """
        return self._converged_by_criteria or self._converged_by_max_iter

    @property
    def current_iteration(self) -> int:
        """Get current iteration count."""
        return len(self._history)

    @property
    def metric_history(self) -> list[float]:
        """Get history of recorded metrics."""
        return list(self._history)

    @property
    def best_metric(self) -> float | None:
        """Get best (lowest) metric seen."""
        return self._best_metric

    @property
    def convergence_reason(self) -> str:
        """Get reason for convergence."""
        if self._converged_by_criteria:
            return "All convergence criteria satisfied (CV, trend, regret)"
        elif self._converged_by_max_iter:
            return f"Max iterations reached ({self._max_iterations})"
        else:
            return "Not converged"

    @property
    def convergence_diagnostics(self) -> ConvergenceDiagnostics:
        """Return detailed diagnostics for debugging/logging.

        Returns:
            Dictionary with CV, trend, and regret information.
        """
        window = self._get_window()
        cv = self._compute_cv(window)
        mk_result = mann_kendall_test(window, self._trend_alpha) if len(window) >= 2 else None
        regret = self._compute_regret()

        current = self._history[-1] if self._history else 0.0
        best = self._best_metric if self._best_metric is not None else 0.0

        return ConvergenceDiagnostics(
            cv=cv,
            cv_satisfied=cv < self._cv_threshold,
            trend_statistic=mk_result.s if mk_result else 0,
            trend_p_value=mk_result.p_value if mk_result else 1.0,
            trend_satisfied=not mk_result.has_trend if mk_result else True,
            current_cost=current,
            best_cost=best,
            regret=regret,
            regret_satisfied=regret <= self._regret_threshold,
            iteration=len(self._history),
            window_values=window,
        )

    def record_metric(self, metric: float) -> None:
        """Record a new cost observation.

        Updates convergence status based on all three criteria.

        Args:
            metric: The cost metric value (lower is better).
        """
        # Update best metric
        if self._best_metric is None or metric < self._best_metric:
            self._best_metric = metric

        # Record history
        self._history.append(metric)

        # Check max iterations
        if len(self._history) >= self._max_iterations:
            self._converged_by_max_iter = True
            return

        # Need at least window_size observations to check criteria
        if len(self._history) < self._window_size:
            return

        # Check all three criteria
        if self._check_all_criteria():
            self._converged_by_criteria = True

    def _get_window(self) -> list[float]:
        """Get the current analysis window."""
        return self._history[-self._window_size :] if self._history else []

    def _compute_cv(self, window: list[float]) -> float:
        """Compute coefficient of variation for window.

        CV = std_dev / |mean|

        Args:
            window: List of values to analyze.

        Returns:
            Coefficient of variation, or inf if mean is 0.
        """
        if len(window) < 2:
            return float("inf")

        mean = sum(window) / len(window)
        if mean == 0:
            # If mean is 0, check if all values are 0
            if all(v == 0 for v in window):
                return 0.0  # Perfect stability
            return float("inf")

        variance = sum((x - mean) ** 2 for x in window) / len(window)
        std_dev = math.sqrt(variance)
        return std_dev / abs(mean)

    def _compute_regret(self) -> float:
        """Compute regret: how much worse current is than best.

        Regret = (current - best) / |best|

        Returns:
            Regret ratio, or 0.0 if best is 0 or no history.
        """
        if not self._history or self._best_metric is None:
            return 0.0

        current = self._history[-1]

        if self._best_metric == 0:
            # If best is 0, any positive current is "infinite" regret
            # but 0 current is 0 regret
            return 0.0 if current == 0 else float("inf")

        return (current - self._best_metric) / abs(self._best_metric)

    def _check_all_criteria(self) -> bool:
        """Check if all three convergence criteria are satisfied.

        Returns:
            True if CV, trend, AND regret criteria all pass.
        """
        window = self._get_window()

        # 1. CV criterion
        cv = self._compute_cv(window)
        if cv >= self._cv_threshold:
            return False

        # 2. Trend criterion (Mann-Kendall)
        mk_result = mann_kendall_test(window, self._trend_alpha)
        if mk_result.has_trend:
            return False

        # 3. Regret criterion
        regret = self._compute_regret()
        if regret > self._regret_threshold:
            return False

        return True

    def should_accept_improvement(self, new_metric: float) -> bool:
        """Check if a new metric represents sufficient improvement.

        For bootstrap mode, we're more permissive - any improvement
        is accepted since we rely on convergence criteria for stopping.

        Args:
            new_metric: The proposed new metric value.

        Returns:
            True if metric improves on best seen.
        """
        if self._best_metric is None:
            return True
        return new_metric < self._best_metric

    def reset(self) -> None:
        """Reset detector state for reuse."""
        self._history = []
        self._best_metric = None
        self._converged_by_criteria = False
        self._converged_by_max_iter = False
