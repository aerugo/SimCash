"""Unit tests for ConvergenceDetector - stability and convergence detection.

TDD: These tests are written BEFORE the implementation.
"""

from __future__ import annotations

import math

import pytest

from payment_simulator.ai_cash_mgmt.optimization.convergence_detector import (
    BootstrapConvergenceDetector,
    ConvergenceDetector,
    MannKendallResult,
    mann_kendall_test,
)


class TestConvergenceDetector:
    """Test convergence detection logic."""

    def test_detector_not_converged_initially(self) -> None:
        """Detector should not be converged with no history."""
        from payment_simulator.ai_cash_mgmt.optimization.convergence_detector import (
            ConvergenceDetector,
        )

        detector = ConvergenceDetector(
            stability_threshold=0.05,
            stability_window=3,
            max_iterations=50,
            improvement_threshold=0.01,
        )

        assert not detector.is_converged

    def test_detector_converges_after_stable_window(self) -> None:
        """Detector should converge after stability_window stable iterations."""
        from payment_simulator.ai_cash_mgmt.optimization.convergence_detector import (
            ConvergenceDetector,
        )

        detector = ConvergenceDetector(
            stability_threshold=0.05,
            stability_window=3,
            max_iterations=50,
            improvement_threshold=0.01,
        )

        # Add 3 similar values (within threshold)
        detector.record_metric(100.0)
        assert not detector.is_converged

        detector.record_metric(99.0)  # 1% change
        assert not detector.is_converged

        detector.record_metric(98.5)  # <1% change
        assert not detector.is_converged

        detector.record_metric(98.2)  # <1% change - should converge
        assert detector.is_converged

    def test_detector_resets_on_large_change(self) -> None:
        """Large metric change should reset stability counter."""
        from payment_simulator.ai_cash_mgmt.optimization.convergence_detector import (
            ConvergenceDetector,
        )

        detector = ConvergenceDetector(
            stability_threshold=0.05,
            stability_window=3,
            max_iterations=50,
            improvement_threshold=0.01,
        )

        # Build up some stability
        detector.record_metric(100.0)
        detector.record_metric(99.0)
        detector.record_metric(98.5)

        # Large change resets
        detector.record_metric(80.0)  # 20% drop
        assert not detector.is_converged

        # Need to rebuild stability window
        detector.record_metric(79.5)
        detector.record_metric(79.2)
        detector.record_metric(79.0)
        assert detector.is_converged

    def test_detector_max_iterations_triggers_convergence(self) -> None:
        """Should report converged after max_iterations regardless of stability."""
        from payment_simulator.ai_cash_mgmt.optimization.convergence_detector import (
            ConvergenceDetector,
        )

        detector = ConvergenceDetector(
            stability_threshold=0.01,  # Very strict
            stability_window=3,
            max_iterations=5,  # Low max
            improvement_threshold=0.01,
        )

        # Keep changing significantly
        for i in range(6):
            detector.record_metric(100.0 - i * 10)  # 10% drops

        assert detector.is_converged  # max_iterations reached
        assert detector.current_iteration >= 5

    def test_detector_tracks_best_metric(self) -> None:
        """Detector should track best (lowest) metric seen."""
        from payment_simulator.ai_cash_mgmt.optimization.convergence_detector import (
            ConvergenceDetector,
        )

        detector = ConvergenceDetector(
            stability_threshold=0.05,
            stability_window=3,
            max_iterations=50,
            improvement_threshold=0.01,
        )

        detector.record_metric(100.0)
        assert detector.best_metric == 100.0

        detector.record_metric(80.0)
        assert detector.best_metric == 80.0

        detector.record_metric(90.0)  # Worse
        assert detector.best_metric == 80.0  # Still 80

    def test_detector_improvement_check(self) -> None:
        """should_accept_improvement should use improvement_threshold."""
        from payment_simulator.ai_cash_mgmt.optimization.convergence_detector import (
            ConvergenceDetector,
        )

        detector = ConvergenceDetector(
            stability_threshold=0.05,
            stability_window=3,
            max_iterations=50,
            improvement_threshold=0.05,  # 5% improvement required
        )

        detector.record_metric(100.0)

        # 10% improvement - should accept
        assert detector.should_accept_improvement(90.0)

        # 2% improvement - below threshold
        assert not detector.should_accept_improvement(98.0)

        # No improvement
        assert not detector.should_accept_improvement(105.0)

    def test_detector_get_convergence_reason(self) -> None:
        """Should report why convergence was reached."""
        from payment_simulator.ai_cash_mgmt.optimization.convergence_detector import (
            ConvergenceDetector,
        )

        # Stability convergence
        detector1 = ConvergenceDetector(
            stability_threshold=0.05,
            stability_window=2,
            max_iterations=100,
            improvement_threshold=0.01,
        )
        detector1.record_metric(100.0)
        detector1.record_metric(99.5)
        detector1.record_metric(99.3)

        assert "stability" in detector1.convergence_reason.lower()

        # Max iterations convergence
        detector2 = ConvergenceDetector(
            stability_threshold=0.01,
            stability_window=5,
            max_iterations=3,
            improvement_threshold=0.01,
        )
        for i in range(5):
            detector2.record_metric(100.0 - i * 10)

        assert "max" in detector2.convergence_reason.lower()


class TestConvergenceHistory:
    """Test convergence metric history tracking."""

    def test_history_records_all_metrics(self) -> None:
        """Should keep history of all recorded metrics."""
        from payment_simulator.ai_cash_mgmt.optimization.convergence_detector import (
            ConvergenceDetector,
        )

        detector = ConvergenceDetector(
            stability_threshold=0.05,
            stability_window=3,
            max_iterations=50,
            improvement_threshold=0.01,
        )

        detector.record_metric(100.0)
        detector.record_metric(90.0)
        detector.record_metric(85.0)

        history = detector.metric_history
        assert len(history) == 3
        assert history[0] == 100.0
        assert history[1] == 90.0
        assert history[2] == 85.0

    def test_current_iteration_tracks_count(self) -> None:
        """current_iteration should return count of recorded metrics."""
        from payment_simulator.ai_cash_mgmt.optimization.convergence_detector import (
            ConvergenceDetector,
        )

        detector = ConvergenceDetector(
            stability_threshold=0.05,
            stability_window=3,
            max_iterations=50,
            improvement_threshold=0.01,
        )

        assert detector.current_iteration == 0

        detector.record_metric(100.0)
        assert detector.current_iteration == 1

        detector.record_metric(90.0)
        assert detector.current_iteration == 2


class TestConvergenceEdgeCases:
    """Test edge cases in convergence detection."""

    def test_single_value_not_converged(self) -> None:
        """Single value should not trigger convergence."""
        from payment_simulator.ai_cash_mgmt.optimization.convergence_detector import (
            ConvergenceDetector,
        )

        detector = ConvergenceDetector(
            stability_threshold=0.05,
            stability_window=1,  # Even with window=1
            max_iterations=50,
            improvement_threshold=0.01,
        )

        detector.record_metric(100.0)
        # Need at least 2 values to compare
        assert not detector.is_converged

    def test_zero_metric_handled(self) -> None:
        """Zero metric values should be handled correctly."""
        from payment_simulator.ai_cash_mgmt.optimization.convergence_detector import (
            ConvergenceDetector,
        )

        detector = ConvergenceDetector(
            stability_threshold=0.05,
            stability_window=3,
            max_iterations=50,
            improvement_threshold=0.01,
        )

        detector.record_metric(0.0)
        detector.record_metric(0.0)
        detector.record_metric(0.0)
        detector.record_metric(0.0)

        # Should converge (zero change)
        assert detector.is_converged

    def test_negative_metrics_handled(self) -> None:
        """Negative metric values should work (for metrics where lower is better)."""
        from payment_simulator.ai_cash_mgmt.optimization.convergence_detector import (
            ConvergenceDetector,
        )

        detector = ConvergenceDetector(
            stability_threshold=0.05,
            stability_window=3,
            max_iterations=50,
            improvement_threshold=0.01,
        )

        detector.record_metric(-100.0)
        detector.record_metric(-99.0)
        detector.record_metric(-98.5)
        detector.record_metric(-98.2)

        assert detector.is_converged

    def test_reset_clears_state(self) -> None:
        """reset() should clear all state."""
        from payment_simulator.ai_cash_mgmt.optimization.convergence_detector import (
            ConvergenceDetector,
        )

        detector = ConvergenceDetector(
            stability_threshold=0.05,
            stability_window=2,
            max_iterations=50,
            improvement_threshold=0.01,
        )

        detector.record_metric(100.0)
        detector.record_metric(99.5)
        detector.record_metric(99.3)
        assert detector.is_converged

        detector.reset()

        assert not detector.is_converged
        assert detector.current_iteration == 0
        assert len(detector.metric_history) == 0
        assert detector.best_metric is None


# ============================================================================
# Mann-Kendall Trend Test
# ============================================================================


class TestMannKendallTest:
    """Test Mann-Kendall trend test implementation."""

    def test_empty_list(self) -> None:
        """Empty list should return no trend."""
        result = mann_kendall_test([])
        assert result.s == 0
        assert result.p_value == 1.0
        assert not result.has_trend

    def test_single_value(self) -> None:
        """Single value should return no trend."""
        result = mann_kendall_test([100.0])
        assert result.s == 0
        assert result.p_value == 1.0
        assert not result.has_trend

    def test_two_values_increasing(self) -> None:
        """Two increasing values should detect trend for small samples."""
        result = mann_kendall_test([100.0, 110.0])
        assert result.s == 1
        # For n < 4, uses heuristic: |S| >= 0.75 * max_s
        # max_s = 2*(2-1)/2 = 1, so 1 >= 0.75 means trend
        assert result.has_trend

    def test_two_values_decreasing(self) -> None:
        """Two decreasing values should detect trend for small samples."""
        result = mann_kendall_test([110.0, 100.0])
        assert result.s == -1
        assert result.has_trend

    def test_two_values_equal(self) -> None:
        """Two equal values should show no trend."""
        result = mann_kendall_test([100.0, 100.0])
        assert result.s == 0
        assert not result.has_trend

    def test_perfect_ascending_sequence(self) -> None:
        """Perfect ascending sequence should have significant trend."""
        result = mann_kendall_test([1, 2, 3, 4, 5])
        assert result.s > 0  # Positive S for ascending
        assert result.has_trend  # p < 0.05

    def test_perfect_descending_sequence(self) -> None:
        """Perfect descending sequence should have significant trend."""
        result = mann_kendall_test([5, 4, 3, 2, 1])
        assert result.s < 0  # Negative S for descending
        assert result.has_trend  # p < 0.05

    def test_oscillating_sequence_no_trend(self) -> None:
        """Oscillating sequence should show no trend."""
        result = mann_kendall_test([100, 102, 99, 101, 100])
        assert not result.has_trend  # p > 0.05

    def test_s_statistic_calculation(self) -> None:
        """Verify S statistic calculation for known sequence."""
        # [10, 20, 30]: pairs are (10,20)=+1, (10,30)=+1, (20,30)=+1
        # S = 3
        result = mann_kendall_test([10, 20, 30])
        assert result.s == 3

        # [30, 20, 10]: pairs are (30,20)=-1, (30,10)=-1, (20,10)=-1
        # S = -3
        result = mann_kendall_test([30, 20, 10])
        assert result.s == -3

    def test_ties_handled_correctly(self) -> None:
        """Ties should not contribute to S statistic."""
        # [10, 10, 20]: pairs are (10,10)=0, (10,20)=+1, (10,20)=+1
        # S = 2
        result = mann_kendall_test([10, 10, 20])
        assert result.s == 2

    def test_all_ties_no_trend(self) -> None:
        """All identical values should show no trend."""
        result = mann_kendall_test([100, 100, 100, 100, 100])
        assert result.s == 0
        assert not result.has_trend

    def test_variance_with_ties(self) -> None:
        """Variance should be reduced with ties (tie correction)."""
        # Without ties: n=5, Var(S) = 5*4*15 / 18 = 16.67
        result_no_ties = mann_kendall_test([1, 2, 3, 4, 5])

        # With ties: [1, 1, 2, 3, 4] has tie group of size 2
        # tie_correction = 2*(2-1)*(2*2+5) / 18 = 2*1*9/18 = 1
        # Var(S) = (5*4*15 - 18) / 18 = 15.67
        result_with_ties = mann_kendall_test([1, 1, 2, 3, 4])

        # Variance with ties should be less than without
        assert result_with_ties.var_s < result_no_ties.var_s

    def test_z_continuity_correction(self) -> None:
        """Z statistic should use continuity correction."""
        result = mann_kendall_test([1, 2, 3, 4, 5])
        # S = 10 for n=5, Var(S) = 16.67
        # Z = (10 - 1) / sqrt(16.67) = 9 / 4.08 = 2.20
        assert result.s == 10
        expected_z = (10 - 1) / math.sqrt(result.var_s)
        assert abs(result.z - expected_z) < 0.01

    def test_custom_alpha(self) -> None:
        """Custom alpha level should affect has_trend."""
        values = [100, 98, 99, 97, 96]  # Slight downward trend

        # With strict alpha
        result_strict = mann_kendall_test(values, alpha=0.01)
        # With lenient alpha
        result_lenient = mann_kendall_test(values, alpha=0.10)

        # Same p-value, different threshold
        assert result_strict.p_value == result_lenient.p_value
        # Lenient might detect trend when strict doesn't
        assert result_strict.has_trend == (result_strict.p_value < 0.01)
        assert result_lenient.has_trend == (result_lenient.p_value < 0.10)

    def test_consistent_4_percent_drops(self) -> None:
        """Consistent 4% drops should be detected as trend (Pass 1 scenario)."""
        # From feature request: 418.55 → 402.93 → 383.36
        values = [418.55, 402.93, 383.36]
        result = mann_kendall_test(values)
        assert result.s < 0  # Negative = downward trend
        # For n=3, uses heuristic
        assert result.has_trend

    def test_divergence_then_stability(self) -> None:
        """Divergence followed by stability (Pass 2 scenario)."""
        # Values that diverged then stabilized at worse point
        values = [264.10, 371.99, 451.54, 459.00, 459.32]
        result = mann_kendall_test(values)
        # Strong upward trend (divergence)
        assert result.s > 0
        assert result.has_trend


# ============================================================================
# CV Criterion Tests
# ============================================================================


class TestBootstrapConvergenceCVCriterion:
    """Test coefficient of variation criterion."""

    def test_cv_low_variance_converges(self) -> None:
        """Low CV should allow convergence."""
        detector = BootstrapConvergenceDetector(
            cv_threshold=0.03,  # 3%
            window_size=5,
            regret_threshold=0.10,
            max_iterations=50,
        )

        # Values with ~1% CV (stable)
        for cost in [100, 101, 99, 100, 101]:
            detector.record_metric(cost)

        diag = detector.convergence_diagnostics
        assert diag["cv"] < 0.03
        assert diag["cv_satisfied"]

    def test_cv_high_variance_no_convergence(self) -> None:
        """High CV should prevent convergence."""
        detector = BootstrapConvergenceDetector(
            cv_threshold=0.03,  # 3%
            window_size=5,
            regret_threshold=0.10,
            max_iterations=50,
        )

        # Values with ~10% CV (unstable)
        for cost in [100, 90, 110, 95, 105]:
            detector.record_metric(cost)

        diag = detector.convergence_diagnostics
        assert diag["cv"] > 0.03
        assert not diag["cv_satisfied"]
        assert not detector.is_converged

    def test_cv_zero_mean_all_zeros(self) -> None:
        """Zero mean with all zeros should be perfect stability (CV=0)."""
        detector = BootstrapConvergenceDetector(
            cv_threshold=0.03,
            window_size=5,
            regret_threshold=0.10,
            max_iterations=50,
        )

        for _ in range(5):
            detector.record_metric(0.0)

        diag = detector.convergence_diagnostics
        assert diag["cv"] == 0.0
        assert diag["cv_satisfied"]

    def test_cv_zero_mean_mixed_values(self) -> None:
        """Zero mean with non-zero values should be inf CV."""
        detector = BootstrapConvergenceDetector(
            cv_threshold=0.03,
            window_size=5,
            regret_threshold=0.10,
            max_iterations=50,
        )

        # Mean is 0 but values are not
        for cost in [-100, -50, 0, 50, 100]:
            detector.record_metric(cost)

        diag = detector.convergence_diagnostics
        assert diag["cv"] == float("inf")
        assert not diag["cv_satisfied"]

    def test_cv_single_value_inf(self) -> None:
        """Single value should return inf CV (not enough data)."""
        detector = BootstrapConvergenceDetector(
            cv_threshold=0.03,
            window_size=5,
            regret_threshold=0.10,
            max_iterations=50,
        )

        detector.record_metric(100.0)

        diag = detector.convergence_diagnostics
        assert diag["cv"] == float("inf")


# ============================================================================
# Trend Criterion Tests
# ============================================================================


class TestBootstrapConvergenceTrendCriterion:
    """Test Mann-Kendall trend criterion."""

    def test_consistent_drops_no_convergence(self) -> None:
        """Consistent 4% drops should prevent convergence (Pass 1 scenario)."""
        detector = BootstrapConvergenceDetector(
            cv_threshold=0.10,  # Relaxed to focus on trend
            window_size=5,
            regret_threshold=0.10,
            max_iterations=50,
        )

        # 4% drops each iteration
        cost = 500.0
        for _ in range(5):
            detector.record_metric(cost)
            cost *= 0.96

        diag = detector.convergence_diagnostics
        assert not diag["trend_satisfied"]  # Trend detected
        assert not detector.is_converged

    def test_flat_allows_convergence(self) -> None:
        """Flat/oscillating values should allow convergence."""
        detector = BootstrapConvergenceDetector(
            cv_threshold=0.10,  # Relaxed
            window_size=5,
            regret_threshold=0.10,
            max_iterations=50,
        )

        # Oscillating around 100
        for cost in [100, 102, 99, 101, 100]:
            detector.record_metric(cost)

        diag = detector.convergence_diagnostics
        assert diag["trend_satisfied"]  # No significant trend

    def test_upward_trend_no_convergence(self) -> None:
        """Upward trend (divergence) should prevent convergence."""
        detector = BootstrapConvergenceDetector(
            cv_threshold=0.10,
            window_size=5,
            regret_threshold=1.0,  # Relaxed to focus on trend
            max_iterations=50,
        )

        # Diverging (costs increasing)
        for cost in [100, 120, 140, 160, 180]:
            detector.record_metric(cost)

        diag = detector.convergence_diagnostics
        assert not diag["trend_satisfied"]  # Upward trend detected


# ============================================================================
# Regret Criterion Tests
# ============================================================================


class TestBootstrapConvergenceRegretCriterion:
    """Test regret bound criterion."""

    def test_at_best_zero_regret(self) -> None:
        """When at best, regret should be 0."""
        detector = BootstrapConvergenceDetector(
            cv_threshold=0.10,
            window_size=5,
            regret_threshold=0.10,
            max_iterations=50,
        )

        # Best is last value
        for cost in [150, 140, 130, 120, 100]:
            detector.record_metric(cost)

        diag = detector.convergence_diagnostics
        assert diag["regret"] == 0.0
        assert diag["regret_satisfied"]

    def test_slightly_above_best_ok(self) -> None:
        """Slightly above best (within threshold) should allow convergence."""
        detector = BootstrapConvergenceDetector(
            cv_threshold=0.10,
            window_size=5,
            regret_threshold=0.10,  # 10%
            max_iterations=50,
        )

        # Best is 100, current is 105 (5% regret)
        for cost in [150, 140, 100, 105, 105]:
            detector.record_metric(cost)

        diag = detector.convergence_diagnostics
        assert diag["best_cost"] == 100
        assert diag["current_cost"] == 105
        assert diag["regret"] == pytest.approx(0.05)
        assert diag["regret_satisfied"]

    def test_far_above_best_no_convergence(self) -> None:
        """Far above best (Pass 2 scenario) should prevent convergence."""
        detector = BootstrapConvergenceDetector(
            cv_threshold=0.10,
            window_size=5,
            regret_threshold=0.10,  # 10%
            max_iterations=50,
        )

        # Best was 264, diverged to 459 (74% regret)
        detector.record_metric(264.0)  # Best
        for cost in [371.99, 451.54, 459.00, 459.32]:
            detector.record_metric(cost)

        diag = detector.convergence_diagnostics
        assert diag["best_cost"] == 264.0
        assert diag["regret"] > 0.10
        assert not diag["regret_satisfied"]
        assert not detector.is_converged

    def test_best_zero_current_zero(self) -> None:
        """Best=0, current=0 should have 0 regret."""
        detector = BootstrapConvergenceDetector(
            cv_threshold=0.10,
            window_size=5,
            regret_threshold=0.10,
            max_iterations=50,
        )

        for _ in range(5):
            detector.record_metric(0.0)

        diag = detector.convergence_diagnostics
        assert diag["regret"] == 0.0
        assert diag["regret_satisfied"]

    def test_best_zero_current_positive(self) -> None:
        """Best=0, current>0 should have inf regret."""
        detector = BootstrapConvergenceDetector(
            cv_threshold=0.10,
            window_size=5,
            regret_threshold=0.10,
            max_iterations=50,
        )

        detector.record_metric(0.0)  # Best
        for cost in [10, 10, 10, 10]:
            detector.record_metric(cost)

        diag = detector.convergence_diagnostics
        assert diag["regret"] == float("inf")
        assert not diag["regret_satisfied"]


# ============================================================================
# Combined Criteria Tests
# ============================================================================


class TestBootstrapConvergenceCombinedCriteria:
    """Test that ALL criteria must be satisfied."""

    def test_all_satisfied_converges(self) -> None:
        """Convergence requires CV, trend, AND regret all satisfied."""
        detector = BootstrapConvergenceDetector(
            cv_threshold=0.03,
            window_size=5,
            regret_threshold=0.10,
            max_iterations=50,
        )

        # Stable, no trend, at best
        for cost in [100, 101, 99, 100, 101]:
            detector.record_metric(cost)

        diag = detector.convergence_diagnostics
        assert diag["cv_satisfied"]
        assert diag["trend_satisfied"]
        assert diag["regret_satisfied"]
        assert detector.is_converged

    def test_cv_fails_no_convergence(self) -> None:
        """CV failure alone should prevent convergence."""
        detector = BootstrapConvergenceDetector(
            cv_threshold=0.01,  # Very strict
            window_size=5,
            regret_threshold=0.10,
            max_iterations=50,
        )

        # Higher variance, but no trend and at best
        for cost in [100, 102, 98, 101, 99]:
            detector.record_metric(cost)

        diag = detector.convergence_diagnostics
        assert not diag["cv_satisfied"]  # CV fails
        assert diag["trend_satisfied"]  # Trend passes
        assert diag["regret_satisfied"]  # Regret passes
        assert not detector.is_converged

    def test_trend_fails_no_convergence(self) -> None:
        """Trend failure alone should prevent convergence."""
        detector = BootstrapConvergenceDetector(
            cv_threshold=0.10,  # Relaxed
            window_size=5,
            regret_threshold=0.10,
            max_iterations=50,
        )

        # Consistent drops (low CV but significant trend)
        for cost in [100, 97, 94, 91, 88]:
            detector.record_metric(cost)

        diag = detector.convergence_diagnostics
        # CV might pass (values are close), but trend should fail
        assert not diag["trend_satisfied"]
        assert not detector.is_converged

    def test_regret_fails_no_convergence(self) -> None:
        """Regret failure alone should prevent convergence."""
        detector = BootstrapConvergenceDetector(
            cv_threshold=0.10,
            window_size=5,
            regret_threshold=0.05,  # Strict
            max_iterations=50,
        )

        # Stable but not at best
        detector.record_metric(80.0)  # Best
        for cost in [100, 101, 99, 100]:  # Far from best
            detector.record_metric(cost)

        diag = detector.convergence_diagnostics
        assert diag["regret"] > 0.05
        assert not diag["regret_satisfied"]
        assert not detector.is_converged


# ============================================================================
# BootstrapConvergenceDetector Edge Cases
# ============================================================================


class TestBootstrapConvergenceEdgeCases:
    """Test edge cases in bootstrap convergence detection."""

    def test_not_converged_before_window_size(self) -> None:
        """Should not converge before window_size observations."""
        detector = BootstrapConvergenceDetector(
            cv_threshold=0.10,
            window_size=5,
            regret_threshold=0.10,
            max_iterations=50,
        )

        # Only 4 observations (stable)
        for cost in [100, 100, 100, 100]:
            detector.record_metric(cost)

        assert not detector.is_converged
        assert detector.current_iteration == 4

    def test_max_iterations_forces_convergence(self) -> None:
        """Max iterations should force convergence regardless of criteria."""
        detector = BootstrapConvergenceDetector(
            cv_threshold=0.01,  # Very strict
            window_size=5,
            regret_threshold=0.01,  # Very strict
            max_iterations=5,
        )

        # Criteria not satisfied, but max reached
        for cost in [500, 400, 300, 200, 100]:
            detector.record_metric(cost)

        assert detector.is_converged
        assert "Max iterations" in detector.convergence_reason

    def test_reset_clears_state(self) -> None:
        """Reset should clear all state."""
        detector = BootstrapConvergenceDetector(
            cv_threshold=0.10,
            window_size=5,
            regret_threshold=0.10,
            max_iterations=50,
        )

        for cost in [100, 101, 99, 100, 101]:
            detector.record_metric(cost)

        assert detector.is_converged

        detector.reset()

        assert not detector.is_converged
        assert detector.current_iteration == 0
        assert detector.best_metric is None
        assert len(detector.metric_history) == 0

    def test_tracks_best_metric(self) -> None:
        """Should track best (lowest) metric."""
        detector = BootstrapConvergenceDetector(
            cv_threshold=0.10,
            window_size=5,
            regret_threshold=0.10,
            max_iterations=50,
        )

        detector.record_metric(100)
        assert detector.best_metric == 100

        detector.record_metric(80)
        assert detector.best_metric == 80

        detector.record_metric(90)  # Worse
        assert detector.best_metric == 80

    def test_should_accept_improvement(self) -> None:
        """should_accept_improvement should check if better than best."""
        detector = BootstrapConvergenceDetector(
            cv_threshold=0.10,
            window_size=5,
            regret_threshold=0.10,
            max_iterations=50,
        )

        detector.record_metric(100)

        assert detector.should_accept_improvement(90)  # Better
        assert not detector.should_accept_improvement(100)  # Same
        assert not detector.should_accept_improvement(110)  # Worse

    def test_convergence_diagnostics_structure(self) -> None:
        """Diagnostics should have all required fields."""
        detector = BootstrapConvergenceDetector(
            cv_threshold=0.03,
            window_size=5,
            regret_threshold=0.10,
            max_iterations=50,
        )

        for cost in [100, 101, 99, 100, 101]:
            detector.record_metric(cost)

        diag = detector.convergence_diagnostics

        # Check all required fields exist
        assert "cv" in diag
        assert "cv_satisfied" in diag
        assert "trend_statistic" in diag
        assert "trend_p_value" in diag
        assert "trend_satisfied" in diag
        assert "current_cost" in diag
        assert "best_cost" in diag
        assert "regret" in diag
        assert "regret_satisfied" in diag
        assert "iteration" in diag
        assert "window_values" in diag

    def test_window_values_in_diagnostics(self) -> None:
        """Diagnostics should include the window values."""
        detector = BootstrapConvergenceDetector(
            cv_threshold=0.10,
            window_size=3,
            regret_threshold=0.10,
            max_iterations=50,
        )

        detector.record_metric(100)
        detector.record_metric(200)
        detector.record_metric(150)
        detector.record_metric(175)
        detector.record_metric(160)

        diag = detector.convergence_diagnostics
        # Window should be last 3 values
        assert diag["window_values"] == [150, 175, 160]


# ============================================================================
# Exp2 Scenario Replay Tests
# ============================================================================


class TestExp2ScenarioReplay:
    """Test with actual Exp2 data patterns from feature request."""

    def test_pass1_no_premature_convergence(self) -> None:
        """Pass 1: Should NOT converge at iter 10 with 4-5% drops."""
        detector = BootstrapConvergenceDetector(
            cv_threshold=0.03,
            window_size=5,
            regret_threshold=0.10,
            max_iterations=25,
        )

        # Exp2 Pass 1 costs (approximate from feature request)
        costs = [
            600.0,  # iter 1
            580.0,  # iter 2
            560.0,  # iter 3
            540.0,  # iter 4
            510.0,  # iter 5
            480.0,  # iter 6
            418.55,  # iter 7
            402.93,  # iter 8
            383.36,  # iter 9
            # Old detector would converge here (3 consecutive <5% changes)
        ]

        for cost in costs:
            detector.record_metric(cost)

        # New detector should NOT converge - still dropping
        assert not detector.is_converged
        diag = detector.convergence_diagnostics
        assert not diag["trend_satisfied"]  # Downward trend detected

    def test_pass2_no_convergence_at_diverged_point(self) -> None:
        """Pass 2: Should NOT converge at 459 when best was 264."""
        detector = BootstrapConvergenceDetector(
            cv_threshold=0.03,
            window_size=5,
            regret_threshold=0.10,
            max_iterations=50,
        )

        # Exp2 Pass 2 costs (from feature request)
        costs = [
            500.0,  # iter 1-12 (approximate)
            450.0,
            400.0,
            350.0,
            300.0,
            280.0,
            270.0,
            264.10,  # iter 13 - BEST
            371.99,  # iter 14 - diverged +41%
            451.54,  # iter 15
            455.00,  # iter 16
            458.00,  # iter 17
            459.00,  # iter 18
            459.32,  # iter 19 - old detector might converge here (stable)
        ]

        for cost in costs:
            detector.record_metric(cost)

        # Should NOT converge - regret is way too high
        assert not detector.is_converged
        diag = detector.convergence_diagnostics
        # Regret should be (459.32 - 264.10) / 264.10 ≈ 0.74 (74%)
        assert diag["regret"] > 0.10
        assert not diag["regret_satisfied"]

    def test_actual_convergence_at_equilibrium(self) -> None:
        """Should converge when actually at equilibrium."""
        detector = BootstrapConvergenceDetector(
            cv_threshold=0.03,
            window_size=5,
            regret_threshold=0.10,
            max_iterations=50,
        )

        # Simulate reaching equilibrium
        costs = [
            500.0,
            400.0,
            300.0,
            250.0,
            220.0,
            200.0,  # Approaching equilibrium
            198.0,
            199.0,
            201.0,
            200.0,
            199.5,  # Stable around 200
        ]

        for cost in costs:
            detector.record_metric(cost)

        # Should converge - stable, no trend, near best
        assert detector.is_converged
        diag = detector.convergence_diagnostics
        assert diag["cv_satisfied"]
        assert diag["trend_satisfied"]
        assert diag["regret_satisfied"]
