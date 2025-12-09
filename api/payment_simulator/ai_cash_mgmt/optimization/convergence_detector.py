"""Convergence detection for policy optimization.

Detects when policy optimization has stabilized and further iterations
are unlikely to produce meaningful improvements.
"""

from __future__ import annotations


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
